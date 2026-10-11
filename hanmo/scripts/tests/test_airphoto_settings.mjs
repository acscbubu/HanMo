// Exercise the AirPhoto settings-page script against a minimal fake DOM plus a
// fake upload socket: a picked photo is decoded, fitted, dithered, encoded as a
// device 2bpp BMP and pushed as three sequential uploads. The encoder is also
// checked byte by byte against lib/GfxRenderer/Bitmap.cpp's reader.
// Run: node scripts/tests/test_airphoto_settings.mjs
import assert from 'node:assert/strict';
import {mkdirSync, readFileSync, writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import vm from 'node:vm';
const root = fileURLToPath(new URL('../..', import.meta.url));
const samples = join(process.env.TMPDIR || process.env.TEMP || tmpdir(), 'airphoto-samples');
mkdirSync(samples, {recursive: true});

// Every drawImage the page asks for, newest last.
const drawCalls = [];
class El {
  constructor(tag = 'div') {
    this.tagName = tag.toUpperCase();
    this.children = []; this.dataset = {}; this.style = {}; this.attrs = {};
    this.handlers = {}; this.classes = new Set();
    this.value = ''; this.textContent = ''; this.disabled = false; this.hidden = false;
    this.width = 0; this.height = 0; this.files = [];
    const classes = this.classes;
    this.classList = {add: c => classes.add(c), remove: c => classes.delete(c), contains: c => classes.has(c)};
  }
  get className() { return [...this.classes].join(' '); }
  set className(value) { this.classes = new Set(String(value).split(' ').filter(Boolean));
    const classes = this.classes;
    this.classList = {add: c => classes.add(c), remove: c => classes.delete(c), contains: c => classes.has(c)}; }
  setAttribute(name, value) { this.attrs[name] = String(value); }
  getAttribute(name) { return name in this.attrs ? this.attrs[name] : null; }
  addEventListener(type, fn) { (this.handlers[type] ||= []).push(fn); }
  appendChild(child) { this.children.push(child); return child; }
  insertBefore(child, before) {
    const at = this.children.indexOf(before);
    if (at < 0) this.children.push(child); else this.children.splice(at, 0, child);
    return child;
  }
  replaceChildren() { this.children = []; }
  matches(selector) { return this.classes.has(selector.replace('.', '')); }
  // The rows nest (row > fields > name/note/bar), so look the whole way down.
  find(cls) {
    if (this.classes.has(cls)) return this;
    for (const child of this.children) { const hit = child.find(cls); if (hit) return hit; }
    return null;
  }
  // Canvas stand-in: a deterministic diagonal gradient, so the dithering and
  // the packing have real varying data to chew on.
  getContext() {
    const canvas = this;
    return {
      fillStyle: '', fillRect() {},
      // Record what was asked for: a crop rectangle that never reaches the
      // canvas would otherwise look exactly like a working crop.
      drawImage(source, ...rest) { canvas.drew = rest; drawCalls.push(rest); },
      createImageData(width, height) { return {data: new Uint8ClampedArray(width * height * 4), width, height}; },
      putImageData(image) { canvas.painted = image; },
      getImageData(x, y, width, height) {
        const data = new Uint8ClampedArray(width * height * 4);
        for (let row = 0; row < height; row++) {
          for (let col = 0; col < width; col++) {
            const value = ((row * 7 + col * 11) % 256);
            const at = (row * width + col) * 4;
            data[at] = value; data[at + 1] = value; data[at + 2] = value; data[at + 3] = 255;
          }
        }
        assert.equal(width, canvas.width); assert.equal(height, canvas.height);
        return {data, width, height};
      }
    };
  }
}

// --- fake File/Blob: only what the page code touches (size + slice/arrayBuffer)
class FakeBlob {
  constructor(parts = [], options = {}) {
    let total = 0;
    const chunks = parts.map(part => {
      const bytes = typeof part === 'string' ? Buffer.from(part) : Buffer.from(part.buffer || part, part.byteOffset || 0, part.length);
      total += bytes.length; return bytes;
    });
    this.bytes = Buffer.concat(chunks, total);
    this.size = this.bytes.length;
    this.type = options.type || '';
  }
  slice(start, end) { const cut = this.bytes.subarray(start, end); return {arrayBuffer: async () => cut.buffer.slice(cut.byteOffset, cut.byteOffset + cut.length)}; }
}
const fakeFile = (name, bytes) => Object.assign(new FakeBlob([bytes]), {name});

// --- fake upload socket speaking the device's START/READY/DONE protocol
const wsLog = [];
let wsAnswer = () => null;   // returns an 'ERROR:...' string to refuse a START
class FakeWebSocket {
  constructor(url) {
    this.url = url; this.readyState = 0; this.bufferedAmount = 0; this.sent = [];
    this.received = Buffer.alloc(0); this.declared = 0; this.record = {url, frames: [], closed: false};
    wsLog.push(this.record);
    setTimeout(() => { this.readyState = 1; if (this.onopen) this.onopen({}); }, 0);
  }
  send(payload) {
    if (typeof payload === 'string') {
      this.record.start = payload;
      this.record.frames.push('START');
      const parts = payload.split(':');
      this.declared = Number(parts[2]);
      const refusal = wsAnswer(payload);
      setTimeout(() => this.deliver(refusal || (this.declared === 0 ? 'DONE' : 'READY')), 0);
      return;
    }
    this.record.frames.push(payload.byteLength);
    this.received = Buffer.concat([this.received, Buffer.from(payload)]);
    if (this.received.length >= this.declared) {
      this.record.body = this.received;
      setTimeout(() => this.deliver('DONE'), 0);
    }
  }
  deliver(message) { if (this.readyState === 1 && this.onmessage) this.onmessage({data: message}); }
  close() { if (this.readyState === 3) return; this.readyState = 3; this.record.closed = true; if (this.onclose) this.onclose({}); }
}

// --- byte readers, so the assertions never lean on the code under test
const u16 = (b, at) => b[at] | (b[at + 1] << 8);
const u32 = (b, at) => (b[at] | (b[at + 1] << 8) | (b[at + 2] << 16)) + b[at + 3] * 16777216;
const i32 = (b, at) => { const raw = u32(b, at); return raw >= 2147483648 ? raw - 4294967296 : raw; };
const strideOf = width => Math.floor((width * 2 + 31) / 32) * 4;
const readLevel = (body, stride, offBits, x, y) => (body[offBits + y * stride + (x >> 2)] >> (6 - ((x & 3) * 2))) & 0x03;

let checks = 0;
// Assert the file really is the device's 2bpp BMP, then hand back the levels.
function assertDeviceBmp(bytes, width, height, label) {
  const bmp = Uint8Array.from(bytes);
  const stride = strideOf(width);
  const offBits = 14 + 40 + 16;
  assert.equal(bmp[0], 0x42, label + ': B');                       // 'BM' magic
  assert.equal(bmp[1], 0x4d, label + ': M');
  assert.equal(u32(bmp, 2), bmp.length, label + ': bfSize');
  assert.equal(u16(bmp, 6), 0, label + ': bfReserved1 must stay 0 (overlay marker)');
  assert.equal(u16(bmp, 8), 0, label + ': bfReserved2 must stay 0 (overlay version)');
  assert.equal(u32(bmp, 10), offBits, label + ': bfOffBits');
  assert.equal(u32(bmp, 14), 40, label + ': biSize');
  assert.equal(i32(bmp, 18), width, label + ': biWidth');
  assert.equal(i32(bmp, 22), -height, label + ': biHeight must be negative (top-down)');
  assert.ok(i32(bmp, 22) < 0, label + ': biHeight sign');
  assert.equal(u16(bmp, 26), 1, label + ': biPlanes');
  assert.equal(u16(bmp, 28), 2, label + ': biBitCount');
  assert.equal(u32(bmp, 30), 0, label + ': biCompression BI_RGB');
  assert.equal(u32(bmp, 34), stride * height, label + ': biSizeImage');
  assert.equal(u32(bmp, 46), 4, label + ': biClrUsed');
  for (let i = 0; i < 4; i++) {                                    // B,G,R,reserved
    assert.deepEqual([bmp[54 + i * 4], bmp[55 + i * 4], bmp[56 + i * 4], bmp[57 + i * 4]],
      [i * 85, i * 85, i * 85, 0], label + ': palette entry ' + i);
  }
  assert.equal(bmp.length, offBits + stride * height, label + ': file length = headers + stride * height');
  assert.ok(width <= 2048 && height <= 3072, label + ': within the parser limits');
  const used = Math.ceil(width * 2 / 8);
  for (let y = 0; y < height; y++) {
    for (let pad = used; pad < stride; pad++) {
      assert.equal(bmp[offBits + y * stride + pad], 0, label + ': row ' + y + ' pad byte ' + pad + ' must be padding');
    }
  }
  checks += 18;
  const levels = new Uint8Array(width * height);
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) levels[y * width + x] = readLevel(bmp, stride, offBits, x, y);
  return levels;
}

// An independent Floyd-Steinberg, so a weight or a direction change is caught.
function referenceDither(gray, width, height) {
  const out = new Uint8Array(width * height);
  const error = [];
  for (let y = 0; y < height + 1; y++) error.push(new Float64Array(width + 2));
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const wanted = gray[y * width + x] + error[y][x + 1];
      const clamped = Math.max(0, Math.min(255, wanted));
      const level = Math.round(clamped / 85);
      out[y * width + x] = level;
      const spill = clamped - level * 85;
      error[y][x + 2] += spill * 7 / 16;
      error[y + 1][x] += spill * 3 / 16;
      error[y + 1][x + 1] += spill * 5 / 16;
      error[y + 1][x + 2] += spill * 1 / 16;
    }
  }
  return out;
}

const SIMPLIFIED = '请选张统浏览转换传备开档显点阵图缩经无败检网连线试过断记忆处个电脑绘与装启单误扩阶层纸纳两种设储';
const CJK = /[\u2E80-\u2FFF\u3040-\u9FFF\uF900-\uFAFF\uFE30-\uFE4F\uFF00-\uFFEF]/;
const wordsOf = region => JSON.parse(/const airphotoWords = (\{[\s\S]*?\});/.exec(region)[1]);
const visibleText = markup => markup.replace(/<[^>]*>/g, ' ');
const expect = {
  'zh-CN': {lang: 'zh-Hant', send: '傳送到 X4 Pro', label: '照片', cjk: true},
  'zh-Hant': {lang: 'zh-Hant', send: '傳送到 X4 Pro', label: '照片', cjk: true},
  en: {lang: 'en', send: 'Send to X4 Pro', label: 'Photos', cjk: false},
};

const written = [];
let galleryFiles = [];        // what /api/files answers for /AirPhoto
let downloads = {};           // path -> thumbnail bytes served by /download
const LOCALES = ['en', 'zh-CN', 'zh-Hant'];
for (const locale of LOCALES) {
  const html = readFileSync(`${root}/src/network/html/${locale}/SettingsPage.html`, 'utf8');
  const words = expect[locale];

  // ---- the pane exists, in every locale, wired the same way as its siblings ----
  assert.ok(html.includes('<a href="#airphoto" id="navpane-airphoto" data-nav-key="airphoto">AirPhoto</a>'),
    locale + ': nav entry');
  assert.ok(/const DEVICE_PANES = \[[^\]]*'airphoto'[^\]]*\];/.test(html), locale + ': airphoto is a device pane');
  assert.ok(html.includes("if (wanted === 'airphoto' && !airphotoReady) initAirphoto();"), locale + ': showPane hook');
  const paneAt = html.indexOf('<div class="pane" id="pane-airphoto"');
  assert.ok(paneAt > 0, locale + ': pane markup');
  const pane = html.slice(paneAt, html.indexOf('</div>\r\n  </div>', paneAt));
  assert.ok(pane.includes('lang="' + words.lang + '"'), locale + ': pane lang');
  assert.ok(pane.includes('id="airphoto-container"') && pane.includes('class="card"'), locale + ': card markup');
  assert.ok(pane.includes('accept="image/jpeg,image/png,image/bmp"') && pane.includes('multiple'),
    locale + ': picker offers only formats the device supports');
  assert.ok(pane.includes('2048') && pane.includes('3072'), locale + ': device JPEG/PNG decoder dimension limit disclosed');
  const warning = locale === 'en'
    ? ['JPEG/PNG originals', 'wider than 2048', 'taller than 3072', 'wallpaper', 'SD card', 'preview cache']
    : ['JPEG／PNG 原始照片', '寬度超過 2048', '高度超過 3072', '待機封面', 'SD 卡', '預覽快取'];
  for (const phrase of warning) assert.ok(pane.includes(phrase), locale + ': missing decoder warning ' + phrase);
  assert.ok(pane.includes('onchange="airphotoPicked()"') && pane.includes('onclick="sendAirphotos()"'), locale + ': handlers');
  assert.ok(html.includes('.airphoto-row {') && html.includes('#airphoto-container button {'), locale + ': pane CSS');
  // ---- what is already on the device, with a picture per photo ----
  assert.ok(pane.includes('id="airphoto-gallery"'), locale + ': gallery container');
  assert.ok(pane.includes('onclick="loadAirphotoGallery()"'), locale + ': gallery refresh button');
  assert.ok(pane.includes('id="airphoto-gallery-status"'), locale + ': gallery status line');
  assert.ok(html.includes('.airphoto-tile {'), locale + ': gallery CSS');
  checks += 13;

  // ---- every visible string is in this locale's language ----
  const code = html.slice(html.indexOf('// ---- AirPhoto'), html.indexOf('// ---- AirNote'));
  assert.ok(code.length > 2000, locale + ': AirPhoto script block found');
  const table = wordsOf(code);
  const text = visibleText(pane);
  for (const [key, value] of Object.entries(table)) {
    assert.ok(value.length > 0, locale + ': word ' + key + ' is not empty');
    assert.equal(CJK.test(value), words.cjk, locale + ': word ' + key + ' language');
  }
  assert.equal(CJK.test(text), words.cjk, locale + ': visible pane text language');
  assert.ok(text.includes(words.send) && text.includes(words.label), locale + ': localized labels');
  if (words.cjk) {
    for (const bad of SIMPLIFIED) {
      assert.ok(!pane.includes(bad) && !code.includes(bad), locale + ': simplified character ' + bad + ' must not appear');
    }
    assert.ok(/[\u4e00-\u9fff]/.test(table.failed), locale + ': error messages are translated');
  } else {
    assert.ok(!/[\u4e00-\u9fff]/.test(pane) && !/[\u4e00-\u9fff]/.test(code), locale + ': no Chinese left in the English file');
  }
  assert.deepEqual(Object.keys(table).sort(), Object.keys(wordsOf(
    readFileSync(`${root}/src/network/html/en/SettingsPage.html`, 'utf8')
      .slice(0, undefined).match(/const airphotoWords = \{[\s\S]*?\};/)[0])).sort(),
    locale + ': every locale carries the same keys');
  checks += 4 + Object.keys(table).length * 2;

  // ---- run the block ----
  const ids = ['file', 'send', 'clear', 'status', 'list', 'gallery', 'gallery-refresh', 'gallery-status',
               'crop', 'dither', 'brightness', 'contrast', 'brightness-value', 'contrast-value'];
  const tags = {file: 'input', crop: 'select', dither: 'select', brightness: 'input', contrast: 'input'};
  const elements = {};
  for (const id of ids) elements['airphoto-' + id] = new El(tags[id] || 'div');
  // The page defaults live in the HTML, which this fake DOM does not parse.
  elements['airphoto-crop'].value = 'cover';
  elements['airphoto-dither'].value = 'floyd';
  elements['airphoto-brightness'].value = '100';
  elements['airphoto-contrast'].value = '100';
  const stored = new Map();
  const storage = {getItem: key => (stored.has(key) ? stored.get(key) : null),
                   setItem: (key, value) => { stored.set(key, String(value)); },
                   removeItem: key => { stored.delete(key); }};
  const field = id => elements['airphoto-' + id];
  const notices = [], posted = [];
  wsLog.length = 0;
  wsAnswer = () => null;
  const ctx = vm.createContext({
    document: {getElementById: id => elements[id], createElement: tag => new El(tag)},
    window: {location: {hostname: '192.168.4.1'}, addEventListener() {}},
    WebSocket: FakeWebSocket, Blob: FakeBlob, URLSearchParams, TextEncoder, console, localStorage: storage,
    setTimeout, clearTimeout, URL: {createObjectURL: () => 'blob:x', revokeObjectURL() {}},
    createImageBitmap: async file => ({width: file.pixels[0], height: file.pixels[1], close() {}}),
    showMessage: (message, error) => notices.push({message, error}),
    fetch: async (url, options = {}) => {
      const body = options.body ? Object.fromEntries(options.body) : {};
      posted.push({url, method: options.method, body});
      if (String(url).startsWith('/api/files')) {
        return {ok: true, status: 200, json: async () => galleryFiles};
      }
      if (String(url).startsWith('/download')) {
        const path = decodeURIComponent(String(url).split('path=')[1].split('&')[0] || '');
        const bytes = downloads[path];
        if (!bytes) return {ok: false, status: 404, arrayBuffer: async () => new ArrayBuffer(0)};
        return {ok: true, status: 200,
                arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.length)};
      }
      return {ok: true, status: 200, text: async () => 'ok'};
    }});
  vm.runInContext(code, ctx);

  // ---- aspect-ratio fitting: landscape, portrait, square, tiny, and the thumb box ----
  // The vm has its own Object.prototype, so sizes are compared as plain pairs.
  const fitOf = (w, h, bw, bh) => { const f = ctx.airphotoFit(w, h, bw, bh); return [f.width, f.height]; };
  assert.deepEqual(fitOf(4000, 3000, 480, 800), [480, 360]);   // landscape
  assert.deepEqual(fitOf(3000, 4000, 480, 800), [480, 640]);   // portrait
  assert.deepEqual(fitOf(1000, 1000, 480, 800), [480, 480]);   // square
  assert.deepEqual(fitOf(60, 40, 480, 800), [60, 40]);         // tiny: no upscale
  assert.deepEqual(fitOf(1, 1, 480, 800), [1, 1]);
  assert.deepEqual(fitOf(4000, 3000, 120, 160), [120, 90]);    // thumbnail box
  assert.deepEqual(fitOf(3000, 4000, 120, 160), [120, 160]);
  assert.deepEqual(fitOf(1600, 900, 480, 800), [480, 270]);    // 16:9
  assert.deepEqual(fitOf(900, 1600, 120, 160), [90, 160]);
  for (const [w, h] of [[4000, 3000], [3000, 4000], [1000, 1000], [1600, 900], [37, 5000]]) {
    const [fitWidth, fitHeight] = fitOf(w, h, 480, 800);
    const fit = {width: fitWidth, height: fitHeight};
    assert.ok(fit.width <= 480 && fit.height <= 800, 'fit stays inside the panel');
    assert.ok(fit.width <= w && fit.height <= h, 'fit never upscales');
    assert.ok(Math.abs((fit.width / fit.height) - (w / h)) < 0.02, 'fit keeps the aspect ratio');
  }
  assert.throws(() => ctx.airphotoFit(0, 10, 480, 800));
  checks += 10 + 15;

  // ---- cropping: the photo fills the box exactly, centred, upscaling if need be ----
  const coverOf = (w, h, bw, bh) => { const c = ctx.airphotoCover(w, h, bw, bh);
    return [c.width, c.height, c.sx, c.sy, c.sWidth, c.sHeight]; };
  assert.deepEqual(coverOf(4000, 3000, 480, 800), [480, 800, 1100, 0, 1800, 3000]);  // landscape
  assert.deepEqual(coverOf(3000, 4000, 480, 800), [480, 800, 300, 0, 2400, 4000]);   // portrait
  assert.deepEqual(coverOf(1000, 1000, 480, 800), [480, 800, 200, 0, 600, 1000]);    // square
  assert.deepEqual(coverOf(500, 2000, 480, 800), [480, 800, 0, 583, 500, 833]);      // very tall
  assert.deepEqual(coverOf(60, 40, 480, 800), [480, 800, 18, 0, 24, 40]);            // tiny: fills anyway
  assert.deepEqual(coverOf(480, 800, 480, 800), [480, 800, 0, 0, 480, 800]);         // already the panel
  assert.deepEqual(coverOf(4000, 3000, 120, 160), [120, 160, 875, 0, 2250, 3000]);   // thumb box
  assert.deepEqual(coverOf(4000, 3000, 800, 480), [800, 480, 0, 300, 4000, 2400]);   // turned panel
  assert.throws(() => ctx.airphotoCover(0, 10, 480, 800));
  for (const [w, h] of [[4000, 3000], [3000, 4000], [1000, 1000], [37, 5000], [60, 40]]) {
    const crop = ctx.airphotoCover(w, h, 480, 800);
    assert.equal(crop.width, 480); assert.equal(crop.height, 800);
    assert.ok(crop.sx >= 0 && crop.sy >= 0 && crop.sx + crop.sWidth <= w && crop.sy + crop.sHeight <= h,
              'the crop stays inside the photo');
    assert.ok(Math.abs((crop.sWidth / crop.sHeight) - 0.6) < 0.02, 'the crop has the panel shape');
  }
  // Both modes are reachable, and "fit" is still the old letterbox.
  const geometry = (w, h, mode) => { const g = ctx.airphotoGeometry(w, h, {width: 480, height: 800}, mode);
    return [g.width, g.height]; };
  assert.deepEqual(geometry(4000, 3000, 'cover'), [480, 800]);
  assert.deepEqual(geometry(4000, 3000, 'fit'), [480, 360]);
  assert.deepEqual(geometry(60, 40, 'fit'), [60, 40]);
  checks += 9 + 20 + 3;

  // ---- brightness and contrast: identity at the defaults, clamped at the ends ----
  const tone = (values, b, c) => Array.from(ctx.airphotoTone(new Uint8Array(values), b, c));
  assert.deepEqual(tone([0, 64, 128, 192, 255], 100, 100), [0, 64, 128, 192, 255]);
  assert.deepEqual(tone([0, 128, 255], 100, 0), [128, 128, 128]);
  assert.deepEqual(tone([128], 200, 100), [255]);
  assert.deepEqual(tone([128], 0, 100), [0]);
  assert.deepEqual(tone([0, 255], 100, 200), [0, 255]);
  assert.deepEqual(tone([100, 160], 100, 200), [72, 192]);
  checks += 6;

  // ---- no dither: nearest of the four panel levels, no error diffusion ----
  assert.deepEqual(Array.from(ctx.airphotoQuantise(new Uint8Array([0, 42, 43, 127, 128, 212, 213, 255]), 8, 1)),
                   [0, 0, 1, 1, 2, 2, 3, 3]);
  const levelRamp = new Uint8Array(64).map((_, i) => i * 4);
  assert.deepEqual(Array.from(ctx.airphotoQuantise(levelRamp, 8, 8)).filter(v => v > 3).length, 0);
  checks += 2;

  // ---- luminance uses the device's own weights ----
  const probe = new Uint8Array([255, 0, 0, 255, 0, 255, 0, 255, 0, 0, 255, 255, 255, 255, 255, 255]);
  assert.deepEqual(Array.from(ctx.airphotoLuminance(probe, 4)),
    [(77 * 255) >> 8, (150 * 255) >> 8, (29 * 255) >> 8, 255]);
  assert.deepEqual(Array.from(ctx.airphotoLuminance(probe, 4)), [76, 149, 28, 255]);
  checks += 2;

  // ---- Floyd-Steinberg, not thresholding ----
  const flat = new Uint8Array(24 * 8).fill(128);
  const dithered = ctx.airphotoDither(flat, 24, 8);
  assert.deepEqual(Array.from(dithered), Array.from(referenceDither(flat, 24, 8)), 'FS matches the reference');
  assert.ok(new Set(dithered).size > 1, 'flat mid-gray must diffuse, not threshold');
  const ramp = new Uint8Array(32 * 6);
  for (let i = 0; i < ramp.length; i++) ramp[i] = (i * 251) % 256;
  assert.deepEqual(Array.from(ctx.airphotoDither(ramp, 32, 6)), Array.from(referenceDither(ramp, 32, 6)));
  assert.deepEqual(Array.from(ctx.airphotoDither(new Uint8Array(9).fill(255), 3, 3)), [3, 3, 3, 3, 3, 3, 3, 3, 3]);
  assert.deepEqual(Array.from(ctx.airphotoDither(new Uint8Array(9).fill(0), 3, 3)), [0, 0, 0, 0, 0, 0, 0, 0, 0]);
  checks += 5;

  // ---- encodeDeviceBmp: widths that are not multiples of 16 so padding matters ----
  for (const width of [1, 3, 5, 17, 33, 479]) {
    for (const height of [1, 2, 7]) {
      const levels = new Uint8Array(width * height);
      for (let i = 0; i < levels.length; i++) levels[i] = (i * 3 + 1) & 3;
      const bmp = ctx.encodeDeviceBmp(levels, width, height);
      assert.equal(ctx.airphotoRowBytes(width), strideOf(width), 'stride formula for width ' + width);
      const back = assertDeviceBmp(bmp, width, height, `${locale} ${width}x${height}`);
      assert.deepEqual(Array.from(back), Array.from(levels),
        `${width}x${height}: levels survive the MSB-first 2bpp packing`);
      checks += 2;
      if (locale === 'en' && height === 7) {
        const file = join(samples, `airphoto_${width}x${height}_levels.bmp`);
        writeFileSync(file, Buffer.from(bmp)); written.push(file);
      }
    }
  }
  assert.equal(ctx.airphotoRowBytes(1), 4);
  assert.equal(ctx.airphotoRowBytes(3), 4);
  assert.equal(ctx.airphotoRowBytes(5), 4);
  assert.equal(ctx.airphotoRowBytes(16), 4);
  assert.equal(ctx.airphotoRowBytes(17), 8);
  assert.equal(ctx.airphotoRowBytes(33), 12);
  assert.equal(ctx.airphotoRowBytes(479), 120);
  assert.equal(ctx.airphotoRowBytes(480), 120);
  checks += 8;

  // ---- the RGBA entry point dithers on the way in ----
  const shades = new Uint8Array(5 * 3 * 4);
  for (let i = 0; i < 15; i++) { const v = i * 17; shades[i * 4] = v; shades[i * 4 + 1] = v; shades[i * 4 + 2] = v; shades[i * 4 + 3] = 255; }
  const fromRgba = ctx.encodeDeviceBmp({data: shades, width: 5, height: 3}, 5, 3);
  const fromLevels = ctx.encodeDeviceBmp(ctx.airphotoDither(ctx.airphotoLuminance(shades, 15), 5, 3), 5, 3);
  assert.deepEqual(Array.from(Uint8Array.from(fromRgba)), Array.from(Uint8Array.from(fromLevels)), 'ImageData in == levels in');
  assertDeviceBmp(fromRgba, 5, 3, locale + ' rgba 5x3');
  assert.throws(() => ctx.encodeDeviceBmp(new Uint8Array(4), 0, 4));
  assert.throws(() => ctx.encodeDeviceBmp(new Uint8Array(4), 2049, 4));
  assert.throws(() => ctx.encodeDeviceBmp(new Uint8Array(2), 4, 4));
  checks += 4;

  // ---- names stay legal for FAT and for the ':' separated START frame ----
  assert.equal(ctx.airphotoSafeName('a:b/c\\d*e?f"g<h>i|j.jpg'), 'a_b_c_d_e_f_g_h_i_j.jpg');
  assert.equal(ctx.airphotoSafeName('  .hidden.png  '), 'hidden.png');
  assert.equal(ctx.airphotoSafeName(''), 'photo');
  assert.equal(ctx.airphotoSafeName('x'.repeat(75) + '.jpeg'), 'x'.repeat(59) + '.jpeg',
    'truncating a long name must preserve the JPEG extension');
  assert.equal(ctx.airphotoSafeName('界'.repeat(30) + '.png'), '界'.repeat(20) + '.png',
    'truncation respects UTF-8 byte length and never splits a Unicode character');
  assert.equal(ctx.airphotoSafeName('caf' + 'e\u0301.jpg'), 'caf\u00e9.jpg', 'NFC-normalized original');
  assert.equal(ctx.airphotoOriginalName('pretty photo.JPEG'), 'pretty photo.JPEG', 'original keeps its extension and spelling');
  assert.equal(ctx.airphotoOriginalName('backup.bmp'), 'backup.bmp', 'BMP originals are supported');
  assert.equal(ctx.airphotoOriginalName('raw.PNG'), 'raw.PNG', 'case-insensitive PNG extension');
  assert.throws(() => ctx.airphotoOriginalName('invalid.gif'));
  checks += 10;

  // ---- the pane lifecycle: pick, then four sequential uploads per photo ----
  await ctx.initAirphoto();   // the pane also lists what is already on the device
  assert.equal(field('status').textContent, table.help);
  assert.equal(field('send').disabled, true, 'nothing picked yet');
  const photo = fakeFile('Holiday:Trip.jpg', Buffer.alloc(9000, 7));
  photo.pixels = [4000, 3000];
  field('file').files = [photo];
  ctx.airphotoPicked();
  assert.equal(field('list').children.length, 1);
  assert.equal(field('list').children[0].find('airphoto-name').textContent, 'Holiday:Trip.jpg');
  assert.equal(field('list').children[0].find('airphoto-note').textContent, table.waiting);
  assert.equal(field('status').textContent, table.picked.replace('%d', '1'));
  assert.equal(field('send').disabled, false);
  await ctx.sendAirphotos();
  const mkdirs = posted.filter(p => p.url === '/mkdir');
  assert.deepEqual(mkdirs.map(p => p.url), ['/mkdir', '/mkdir', '/mkdir'], 'the three directories are asked for');
  assert.deepEqual(mkdirs.map(p => p.body.path + '/' + p.body.name),
    ['//AirPhoto', '/AirPhoto/.view', '/AirPhoto/.thumb']);
  assert.equal(wsLog.length, 4, 'landscape photo uploads original, portrait view, landscape view, thumbnail');
  assert.deepEqual(wsLog.map(s => s.url), Array(4).fill('ws://192.168.4.1:81/'), 'port 81');
  // Cropped, so every photo lands on the device at exactly the panel's size:
  // this is the whole point of the change (uploads used to vary with the
  // source photo's shape).
  assert.equal(wsLog[0].start, `START:Holiday_Trip.jpg:9000:/AirPhoto`);
  assert.equal(wsLog[1].start, `START:Holiday_Trip.jpg.bmp:${14 + 40 + 16 + strideOf(480) * 800}:/AirPhoto/.view`);
  assert.equal(wsLog[2].start, `START:Holiday_Trip.jpg.land.bmp:${14 + 40 + 16 + strideOf(800) * 480}:/AirPhoto/.view`);
  assert.equal(wsLog[3].start, `START:Holiday_Trip.jpg.bmp:${14 + 40 + 16 + strideOf(120) * 160}:/AirPhoto/.thumb`);
  assert.ok(wsLog.every(s => s.closed), 'every socket is closed again');
  assert.ok(wsLog[0].frames.filter(f => f !== 'START').every(f => f <= 4096), 'chunked, 4 KiB at a time');
  assert.equal(wsLog[0].body.length, 9000);
  // The bytes that actually went down the wire are the device format.
  const viewLevels = assertDeviceBmp(wsLog[1].body, 480, 800, locale + ' uploaded view');
  assertDeviceBmp(wsLog[2].body, 800, 480, locale + ' uploaded landscape view');
  assertDeviceBmp(wsLog[3].body, 120, 160, locale + ' uploaded thumb');
  assert.ok(new Set(viewLevels).size > 1, 'the display bitmap is not one flat level');
  assert.equal(field('list').children[0].find('airphoto-note').textContent, table.done);
  assert.equal(field('list').children[0].classList.contains('done'), true);
  assert.equal(field('list').children[0].find('airphoto-bar').children[0].style.width, '100%');
  assert.equal(notices.at(-1).error, false);
  assert.equal(notices.at(-1).message, 'AirPhoto: ' + table.summary.replace('%d', '1').replace('%f', '0'));
  assert.equal(field('send').disabled, false, 'unlocked again');
  checks += 20;
  if (locale === 'en') {
    for (const [name, body, w, h] of [['view_480x800', wsLog[1].body, 480, 800], ['land_800x480', wsLog[2].body, 800, 480], ['thumb_120x160', wsLog[3].body, 120, 160]]) {
      const file = join(samples, `airphoto_${name}_dithered.bmp`);
      writeFileSync(file, Buffer.from(body)); written.push(file);
      assertDeviceBmp(readFileSync(file), w, h, 'sample ' + name);
    }
  }

  // ---- the controls reach the output: same photo, four different bitmaps ----
  const sourceImage = {width: 4000, height: 3000};
  const panel = {width: 480, height: 800};
  const bitmapFor = settings => {
    const geometry = ctx.airphotoGeometry(sourceImage.width, sourceImage.height, panel, settings.crop);
    return {geometry: geometry,
            bytes: ctx.encodeDeviceBmp(ctx.airphotoRender(sourceImage, geometry),
                                       geometry.width, geometry.height, settings)};
  };
  const base = {crop: 'cover', dither: 'floyd', brightness: 100, contrast: 100};
  const cropped = bitmapFor(base);
  const letterboxed = bitmapFor({...base, crop: 'fit'});
  const noDither = bitmapFor({...base, dither: 'none'});
  const brighter = bitmapFor({...base, brightness: 140, contrast: 120});
  assert.deepEqual([cropped.geometry.width, cropped.geometry.height], [480, 800], 'crop fills the panel');
  assert.deepEqual([letterboxed.geometry.width, letterboxed.geometry.height], [480, 360], 'fit letterboxes');
  // The crop rectangle has to actually reach the canvas, not just be computed.
  assert.deepEqual(drawCalls.at(-1), [1100, 0, 1800, 3000, 0, 0, 480, 800],
                   'the centred crop rectangle is what gets drawn');
  assert.notDeepEqual(Array.from(noDither.bytes), Array.from(cropped.bytes), 'no dither changes the pixels');
  assert.notDeepEqual(Array.from(brighter.bytes), Array.from(cropped.bytes), 'brightness/contrast change the pixels');
  assert.equal(noDither.bytes.length, cropped.bytes.length, 'same geometry, same file size');
  if (locale === 'en') {
    for (const [name, made] of [['cover_floyd', cropped], ['fit_floyd', letterboxed],
                                ['cover_nodither', noDither], ['cover_b140_c120', brighter]]) {
      const file = join(samples, `airphoto_option_${name}.bmp`);
      writeFileSync(file, Buffer.from(made.bytes)); written.push(file);
      assertDeviceBmp(readFileSync(file), made.geometry.width, made.geometry.height, 'option sample ' + name);
    }
  }
  checks += 7;

  // ---- the choices are remembered, and the sliders show their own numbers ----
  field('crop').value = 'fit';
  field('dither').value = 'none';
  field('brightness').value = '140';
  field('contrast').value = '120';
  const saved = ctx.airphotoOptionChanged();
  assert.deepEqual({...saved}, {crop: 'fit', dither: 'none', brightness: 140, contrast: 120});
  assert.equal(field('brightness-value').textContent, '140');
  assert.equal(field('contrast-value').textContent, '120');
  assert.deepEqual(JSON.parse(stored.get('airphoto.options.v1')),
                   {crop: 'fit', dither: 'none', brightness: 140, contrast: 120});
  field('crop').value = 'cover';
  field('dither').value = 'floyd';
  field('brightness').value = '100';
  field('contrast').value = '100';
  const restored = ctx.airphotoRestoreOptions();
  assert.deepEqual({...restored}, {crop: 'fit', dither: 'none', brightness: 140, contrast: 120},
                   'a reload comes back to the saved choices');
  assert.equal(field('brightness').value, '140');
  // Back to the defaults for the rest of the run.
  stored.clear();
  field('crop').value = 'cover';
  field('dither').value = 'floyd';
  field('brightness').value = '100';
  field('contrast').value = '100';
  assert.deepEqual({...ctx.airphotoOptions()}, {crop: 'cover', dither: 'floyd', brightness: 100, contrast: 100});
  checks += 7;

  // ---- two photos go one at a time, never in parallel ----
  wsLog.length = 0; posted.length = 0;
  const first = fakeFile('one.png', Buffer.alloc(100, 1)); first.pixels = [200, 100];
  const second = fakeFile('two.png', Buffer.alloc(100, 2)); second.pixels = [100, 200];
  field('file').files = [first, second];
  ctx.airphotoPicked();
  assert.equal(field('list').children.length, 2);
  await ctx.sendAirphotos();
  assert.equal(wsLog.length, 8, 'four per photo, covering manual rotation even on portrait sources');
  assert.deepEqual(wsLog.map(s => s.start.split(':')[3]),
    ['/AirPhoto', '/AirPhoto/.view', '/AirPhoto/.view', '/AirPhoto/.thumb', '/AirPhoto', '/AirPhoto/.view', '/AirPhoto/.view', '/AirPhoto/.thumb']);
  assert.deepEqual(wsLog.map(s => s.start.split(':')[1]),
    ['one.png', 'one.png.bmp', 'one.png.land.bmp', 'one.png.bmp', 'two.png', 'two.png.bmp', 'two.png.land.bmp', 'two.png.bmp']);
  // 200x100 and 100x200 are smaller than the panel, and cropping to fill DOES
  // upscale them: a uniform size on the device is the point of the mode, and
  // only the derived preview grows -- the original file is uploaded untouched.
  assertDeviceBmp(wsLog[1].body, 480, 800, 'one.png view fills the panel');
  assertDeviceBmp(wsLog[2].body, 800, 480, 'one.png landscape view fills the turned panel');
  assertDeviceBmp(wsLog[5].body, 480, 800, 'two.png view fills the panel');
  assertDeviceBmp(wsLog[6].body, 800, 480, 'two.png landscape view fills the turned panel');
  assertDeviceBmp(wsLog[3].body, 120, 160, 'one.png thumb');
  assertDeviceBmp(wsLog[7].body, 120, 160, 'two.png thumb');
  assert.equal(wsLog[0].body.length, 100, 'the original photo is sent as-is');
  checks += 4;

  // ---- equal stems with different source formats must not share any cache ----
  wsLog.length = 0; posted.length = 0;
  const sameStemJpeg = fakeFile('A.jpg', Buffer.alloc(100, 3)); sameStemJpeg.pixels = [40, 30];
  const sameStemPng = fakeFile('A.png', Buffer.alloc(100, 4)); sameStemPng.pixels = [40, 30];
  field('file').files = [sameStemJpeg, sameStemPng];
  ctx.airphotoPicked();
  await ctx.sendAirphotos();
  assert.deepEqual(wsLog.map(s => s.start.split(':')[1]),
    ['A.jpg', 'A.jpg.bmp', 'A.jpg.land.bmp', 'A.jpg.bmp',
     'A.png', 'A.png.bmp', 'A.png.land.bmp', 'A.png.bmp']);
  checks++;
  field('file').files = [first, second];
  ctx.airphotoPicked();

  // ---- preflight rejects normalized FAT-name collisions before any upload ----
  wsLog.length = 0; posted.length = 0;
  const punctuated = fakeFile('A:B.jpg', Buffer.alloc(10, 1)); punctuated.pixels = [12, 8];
  const sanitized = fakeFile('A_B.jpg', Buffer.alloc(10, 2)); sanitized.pixels = [12, 8];
  field('file').files = [punctuated, sanitized, first];
  ctx.airphotoPicked();
  await ctx.sendAirphotos();
  assert.equal(wsLog.length, 0, 'collision aborts the entire batch before original/cache uploads');
  assert.equal(posted.length, 0, 'collision is found before requesting directories');
  assert.equal(field('list').children.length, 3);
  assert.ok(field('list').children.every(row => row.classList.contains('failed')));
  assert.ok(field('list').children[0].find('airphoto-note').textContent.includes(table.collision));
  assert.equal(notices.at(-1).error, true);
  assert.ok(notices.at(-1).message.includes(table.collision));
  assert.equal(field('send').disabled, false, 'failed selection remains changeable');
  const uppercase = fakeFile('a_b.JPG', Buffer.alloc(10, 3)); uppercase.pixels = [12, 8];
  field('file').files = [sanitized, uppercase];
  ctx.airphotoPicked();
  await ctx.sendAirphotos();
  assert.equal(wsLog.length, 0, 'FAT case-folded duplicates are rejected');
  const truncated1 = fakeFile('x'.repeat(75) + '.png', Buffer.alloc(10, 4)); truncated1.pixels = [12, 8];
  const truncated2 = fakeFile('x'.repeat(60) + 'different.png', Buffer.alloc(10, 5)); truncated2.pixels = [12, 8];
  field('file').files = [truncated1, truncated2];
  ctx.airphotoPicked();
  await ctx.sendAirphotos();
  assert.equal(wsLog.length, 0, 'duplicates created by truncation are rejected');
  const nfc = fakeFile('caf\u00e9.jpg', Buffer.alloc(10, 6)); nfc.pixels = [12, 8];
  const nfd = fakeFile('cafe\u0301.jpg', Buffer.alloc(10, 7)); nfd.pixels = [12, 8];
  field('file').files = [nfc, nfd];
  ctx.airphotoPicked();
  await ctx.sendAirphotos();
  assert.equal(wsLog.length, 0, 'Unicode normalization duplicates are rejected');
  // The selector's format filter is advisory; a mixed batch must not upload
  // its valid member before discovering an unsupported original.
  const invalidMixed = fakeFile('preview.webp', Buffer.alloc(10)); invalidMixed.pixels = [12, 8];
  field('file').files = [first, invalidMixed];
  ctx.airphotoPicked();
  await ctx.sendAirphotos();
  assert.equal(wsLog.length, 0, 'an unsupported filename aborts a mixed batch');
  for (const badName of ['image.webp', 'animated.gif', 'picture.heic', 'noextension', '.jpg']) {
    const bad = fakeFile(badName, Buffer.alloc(10)); bad.pixels = [12, 8];
    field('file').files = [bad];
    ctx.airphotoPicked();
    await ctx.sendAirphotos();
    assert.equal(wsLog.length, 0, badName + ' must not be uploaded');
    assert.equal(posted.length, 0, badName + ' must not create directories');
    assert.ok(notices.at(-1).message.includes(table.unsupported), badName + ' error is localized');
  }
  field('file').files = [first, second];
  ctx.airphotoPicked();
  checks += 9;

  // ---- a device refusal is reported per photo, in this locale, and does not stop the run ----
  wsLog.length = 0;
  wsAnswer = start => start.includes('two.png') ? 'ERROR:Failed to create file' : null;
  await ctx.sendAirphotos();
  assert.equal(field('list').children[0].find('airphoto-note').textContent, table.done);
  assert.equal(field('list').children[1].find('airphoto-note').textContent, table.failedWith + table.storage);
  assert.equal(field('list').children[1].classList.contains('failed'), true);
  assert.equal(notices.at(-1).error, true);
  assert.equal(notices.at(-1).message, 'AirPhoto: ' + table.summary.replace('%d', '1').replace('%f', '1'));
  assert.ok(!notices.at(-1).message.includes('Failed to create file'), 'the firmware string never reaches the user');
  // A name already on the card is left alone instead of being rewritten.
  wsLog.length = 0;
  wsAnswer = () => 'ERROR:File already exists: one.png';
  await ctx.sendAirphotos();
  assert.equal(field('list').children[0].find('airphoto-note').textContent, table.exists);
  assert.equal(field('list').children[0].classList.contains('done'), true);
  // An existing original may be a different photo with the same filename.
  // Do not upload NEW previews beside somebody else's original.
  wsLog.length = 0;
  wsAnswer = start => start.startsWith('START:one.png:') ? 'ERROR:File already exists: one.png' : null;
  await ctx.sendAirphotos();
  assert.deepEqual(wsLog.filter(s => s.start?.includes('one.png')).map(s => s.start.split(':')[3]),
    ['/AirPhoto'], 'existing original must not be paired with previews from another upload');
  assert.equal(field('list').children[0].find('airphoto-note').textContent, table.exists);
  // A stale bitmap with this name may depict an OLD image; it cannot be
  // declared a successful upload for the newly written original.
  wsLog.length = 0;
  wsAnswer = start => start.includes('one.png.bmp:') ? 'ERROR:File already exists: one.png.bmp' : null;
  await ctx.sendAirphotos();
  assert.equal(field('list').children[0].classList.contains('failed'), true);
  assert.ok(field('list').children[0].find('airphoto-note').textContent.includes(table.cacheExists));
  assert.equal(wsLog.filter(s => s.start?.includes('one.png')).length, 2,
    'do not go on to landscape/thumbnail when the portrait cache conflicts');
  wsAnswer = () => null;
  // Nothing picked is a message, not a silent no-op.
  ctx.clearAirphotos();
  assert.equal(field('list').children.length, 0);
  assert.equal(field('status').textContent, table.help);
  wsLog.length = 0;
  await ctx.sendAirphotos();
  assert.equal(wsLog.length, 0);
  assert.equal(notices.at(-1).message, 'AirPhoto: ' + table.nothing);
  assert.equal(notices.at(-1).error, true);
  checks += 12;

  // ---- the gallery shows every photo already on the device ----
  // A 4x3 thumbnail with all four panel levels, written by the page's own encoder.
  const thumbBytes = ctx.encodeDeviceBmp(new Uint8Array([0, 1, 2, 3, 3, 2, 1, 0, 0, 3, 1, 2]), 4, 3);
  galleryFiles = [
    {name: 'one.png', size: 1234, isDirectory: false},
    {name: 'notes.txt', size: 10, isDirectory: false},
    {name: '.thumb', size: 0, isDirectory: true},
    {name: 'two.jpg', size: 2048, isDirectory: false},
  ];
  downloads = {'/AirPhoto/.thumb/one.png.bmp': thumbBytes};   // two.jpg has no thumbnail yet
  posted.length = 0;
  await ctx.loadAirphotoGallery();
  assert.equal(posted[0].url.split('&')[0], '/api/files?path=%2FAirPhoto', locale + ': lists the photo folder');
  const tiles = field('gallery').children;
  assert.equal(tiles.length, 2, locale + ': only images are listed, and never the cache folder');
  assert.ok(tiles[0].find('airphoto-tile-name').textContent.includes('one.png'), locale + ': tile is named');
  const painted = tiles[0].find('airphoto-tile-image');
  assert.equal(painted.width, 4, locale + ': canvas takes the thumbnail width');
  assert.equal(painted.height, 3, locale + ': canvas takes the thumbnail height');
  assert.ok(painted.painted, locale + ': the thumbnail is decoded and painted');
  assert.deepEqual(Array.from(painted.painted.data.slice(0, 4)), [0, 0, 0, 255],
    locale + ': level 0 paints black');
  assert.deepEqual(Array.from(painted.painted.data.slice(4, 8)), [85, 85, 85, 255],
    locale + ': level 1 paints the next gray');
  assert.equal(tiles[1].find('airphoto-tile-image'), null, locale + ': a missing thumbnail paints nothing');
  assert.ok(tiles[1].find('airphoto-tile-note').textContent.length > 0, locale + ': and says so');
  assert.ok(field('gallery-status').textContent.includes('2'), locale + ': the count is reported');
  // An unreachable device is reported instead of leaving stale tiles behind.
  galleryFiles = [];
  await ctx.loadAirphotoGallery();
  assert.equal(field('gallery').children.length, 0, locale + ': an empty folder clears the tiles');
  checks += 13;
}

// The other side of the fence parses these with the real C++ reader.
console.log(JSON.stringify({ok: true, locales: LOCALES.length, checks, samples: written}, null, 1));
