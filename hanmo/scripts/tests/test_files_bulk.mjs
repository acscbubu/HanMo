// Exercise the File Manager bulk-selection section against a minimal fake DOM:
// ticking rows reveals an action bar whose Delete sends ONE /delete request with a
// JSON `paths` array, whose Move walks /move one file at a time, and whose Download
// pulls each file from /download sequentially into a single in-browser JSZip.
// Run: node scripts/tests/test_files_bulk.mjs
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import vm from 'node:vm';
const root = fileURLToPath(new URL('../..', import.meta.url));

class El {
  constructor(tag = 'div') {
    this.tagName = tag.toUpperCase();
    this.children = []; this.dataset = {}; this.style = {}; this.attrs = {};
    this.handlers = {}; this.classes = new Set();
    this.value = ''; this.textContent = ''; this.disabled = false; this.hidden = false;
    this.checked = false; this.parentNode = null; this.clicks = 0;
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
  appendChild(child) { this.children.push(child); child.parentNode = this; return child; }
  remove() { this.removed = true; }
  click() { this.clicks++; }
  matches(selector) { return this.classes.has(selector.replace('.', '')); }
}

// --- fakes for the browser bits the zip path touches -------------------------
class FakeBlob {
  constructor(parts = [], options = {}) { this.parts = parts; this.type = options.type || ''; this.size = 1; }
}
class FakeFormData {
  constructor() { this.data = {}; }
  append(key, value) { this.data[key] = value; }
  get(key) { return key in this.data ? this.data[key] : null; }
}

const expect = {
  'zh-CN': {
    // Traditional form that must be there : simplified-only form that must not.
    pairs: [['選','选'],['個','个'],['項','项'],['請','请'],['確','确'],['刪','删'],['無','无'],
            ['復','复'],['資','资'],['將','将'],['嗎','吗'],['敗','败'],['網','网'],['錯','错'],
            ['誤','误'],['輸','输'],['擇','择'],['標','标'],['夾','夹'],['讀','读'],['檔','档'],
            ['過','过'],['載','载'],['點','点'],['壓','压'],['縮','缩'],['沒','没'],['為','为'],
            ['瀏','浏'],['覽','览'],['會','会'],['盡','尽'],['記','记'],['憶','忆'],['體','体'],
            ['繼','继'],['續','续'],['約','约']],
  },
  en: {pairs: []},
};

// markup that must exist in both locales
const markup = [
  'id="bulkActionBar"', 'id="bulkSelectedCount"', 'id="bulkProgress"',
  'id="bulkDeleteBtn"', 'id="bulkMoveBtn"', 'id="bulkDownloadBtn"', 'id="bulkClearBtn"',
  'onclick="bulkDeleteSelected()"', 'onclick="openBulkMoveModal()"', 'onclick="bulkDownloadSelected()"',
  'id="selectAllCheckbox"', 'onchange="toggleSelectAllVisible(this)"',
  'class="select-item"', 'data-size=', 'onchange="updateBulkBar()"',
  'id="bulkMoveConfirmBtn"', 'onclick="confirmBulkMove()"', 'id="moveConfirmBtn"',
];
// pre-existing behaviour that must survive untouched
const untouched = [
  "fetch('/delete'", "xhr.open('POST', '/move', true)", 'function openMoveModal(name, path)',
  'function confirmMove()', 'function toggleSelectAll(master)', 'function getSelectedItems()',
  '/download?path=${encodeURIComponent(filePath)}',
];

let checks = 0;
for (const locale of ['en', 'zh-CN']) {
  const path = `${root}/src/network/html/${locale}/FilesPage.html`;
  const html = readFileSync(path, 'utf8');
  assert.equal(html.includes('\r'), false, `${locale}/FilesPage.html must stay LF-only`);
  for (const needle of markup) assert.ok(html.includes(needle), `${locale}: missing ${needle}`);
  for (const needle of untouched) assert.ok(html.includes(needle), `${locale}: regressed ${needle}`);
  checks += markup.length + untouched.length + 1;

  const start = html.indexOf('// ---- Bulk selection ----');
  const stop = html.indexOf('// ---- End bulk selection ----');
  assert.ok(start > 0 && stop > start, `${locale}: bulk section markers missing`);
  // normalizePath is the page's own helper; the bulk move reuses it verbatim.
  const norm = html.slice(html.indexOf('  function normalizePath(path) {'), html.indexOf('  function getParentPath('));
  assert.ok(norm.includes('normalized.startsWith'), `${locale}: could not lift normalizePath`);
  const code = norm + '\n' + html.slice(start, stop);
  checks += 2;

  // ---- fake DOM ------------------------------------------------------------
  const elements = {};
  for (const id of ['bulkActionBar', 'bulkSelectedCount', 'bulkProgress', 'selectAllCheckbox',
                    'moveItemName', 'moveItemPath', 'moveDestPath', 'moveModal',
                    'moveConfirmBtn', 'bulkMoveConfirmBtn']) elements[id] = new El('div');
  elements.bulkActionBar.hidden = true;
  const body = new El('body');
  let rows = [];
  const row = (spec) => {
    const tr = new El('tr');
    const td = new El('td');
    const cb = new El('input');
    cb.className = 'select-item';
    cb.dataset = {path: encodeURIComponent(spec.path), name: spec.name,
                  type: spec.isFolder ? 'folder' : 'file', size: String(spec.size || 0)};
    cb.checked = !!spec.checked;
    tr.appendChild(td); td.appendChild(cb);
    if (spec.filteredOut) tr.style.display = 'none';   // an active search hid this row
    rows.push(cb);
    return cb;
  };

  const fetched = [];
  let inFlight = 0, maxInFlight = 0, failMovePath = null, failDownloadPath = null, deleteOk = true;
  let partialDelete = false, rejectDelete = false;
  const notices = [], saves = [], objectUrls = [], confirms = [], alerts = [], deleteEvents = [];
  let confirmAnswer = true, reloads = 0;
  const zips = [];
  class FakeJSZip {
    constructor() { this.entries = []; zips.push(this); }
    file(name, data) { this.entries.push({name, data}); }
    async generateAsync(options) { this.options = options; return new FakeBlob([], {type: 'application/zip'}); }
  }

  const ctx = vm.createContext({
    console, setTimeout, setImmediate, TextEncoder, JSON, Math, Number, String, Array, Object, isFinite,
    encodeURIComponent, decodeURIComponent, Promise,
    JSZip: FakeJSZip, FormData: FakeFormData, Blob: FakeBlob,
    currentPath: '/Books',
    URL: {createObjectURL: (blob) => { const u = 'blob:zip-' + objectUrls.length; objectUrls.push({u, blob}); return u; },
          revokeObjectURL: (u) => { objectUrls.revoked = (objectUrls.revoked || 0) + 1; }},
    window: {location: {reload: () => { reloads++; deleteEvents.push('reload'); }}},
    confirm: (message) => { confirms.push(message); return confirmAnswer; },
    alert: (message) => { alerts.push(message); deleteEvents.push('alert'); },
    showNotification: (message, type) => { notices.push({message, type}); },
    formatFileSize: (bytes) => (bytes / 1048576).toFixed(1) + ' MB',
    document: {
      body,
      getElementById: (id) => elements[id] || null,
      createElement: (tag) => { const el = new El(tag); if (tag === 'a') saves.push(el); return el; },
      querySelectorAll: (selector) => {
        assert.equal(selector, '.select-item');
        return rows.slice();
      },
    },
    fetch: async (url, options = {}) => {
      inFlight++; maxInFlight = Math.max(maxInFlight, inFlight);
      fetched.push({url, options, body: options.body});
      // Yield twice: a Promise.all batch would pile up here and push maxInFlight past 1.
      await new Promise(r => setImmediate(r));
      await new Promise(r => setImmediate(r));
      inFlight--;
      if (url === '/delete') {
        if (rejectDelete) throw new Error('connection dropped');
        if (partialDelete) {
          // The device processes the array in order: a.epub is gone, but the
          // nonempty folder rejects the batch with 500 and only failed names.
          return {ok: false, status: 500,
                  text: async () => 'Failed to delete some items: /Books/sub (folder not empty); '};
        }
        return deleteOk ? {ok: true, status: 200, text: async () => 'ok'}
                        : {ok: false, status: 423, text: async () => 'protected'};
      }
      if (url === '/move') {
        const src = options.body.get('path');
        if (src === failMovePath) return {ok: false, status: 409, text: async () => 'Folder not empty'};
        return {ok: true, status: 200, text: async () => 'ok'};
      }
      if (url.startsWith('/download?path=')) {
        const wanted = decodeURIComponent(url.slice('/download?path='.length));
        if (wanted === failDownloadPath) return {ok: false, status: 404, text: async () => 'missing'};
        return {ok: true, status: 200, arrayBuffer: async () => new Uint8Array([1, 2, 3]).buffer};
      }
      throw new Error('unexpected fetch ' + url);
    },
  });
  vm.runInContext(code, ctx);

  // ---- new strings are in the right language, per locale ---------------------
  const strings = ctx.bulkStrings();
  const blob = Object.values(strings).join('\u0001') + '\u0001' + html.slice(html.indexOf('id="bulkActionBar"'), html.indexOf('id="bulkProgress"'));
  if (locale === 'en') {
    assert.equal(/[\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uff00-\uffef]/.test(blob), false,
                 'en: new strings must not contain CJK');
    checks += 1;
  } else {
    for (const [trad, simp] of expect[locale].pairs) {
      assert.ok(blob.includes(trad), `zh-CN: expected traditional ${trad}`);
      assert.equal(blob.includes(simp), false, `zh-CN: simplified ${simp} leaked into a new string`);
      checks += 2;
    }
  }

  // ---- select-all only touches rows the active filter still lists ------------
  rows = [];
  row({path: '/Books/a.epub', name: 'a.epub', size: 100});
  row({path: '/Books/sub/b.txt', name: 'b.txt', size: 200});
  const hiddenRow = row({path: '/Books/hidden.txt', name: 'hidden.txt', size: 300, filteredOut: true});
  assert.equal(ctx.toggleSelectAllVisible({checked: true}), true);
  assert.equal(hiddenRow.checked, false, 'select-all must skip filtered-out rows');
  assert.equal(ctx.collectSelectedPaths().length, 2);
  assert.equal(elements.bulkActionBar.hidden, false);
  assert.equal(elements.bulkActionBar.classList.contains('visible'), true);
  assert.equal(elements.bulkSelectedCount.textContent, strings.selectedCount.replace('{n}', '2'));
  ctx.bulkSelectNone();
  assert.equal(elements.bulkActionBar.hidden, true, 'action bar hides with nothing selected');
  assert.equal(ctx.updateBulkBar(), 0);
  checks += 7;

  // ---- bulk delete: exactly ONE /delete carrying a JSON paths array ----------
  rows = [];
  row({path: '/Books/a.epub', name: 'a.epub', size: 100, checked: true});
  row({path: '/Books/sub', name: 'sub', isFolder: true, checked: true});
  row({path: '/Books/c.txt', name: 'c.txt', size: 50, checked: true});
  row({path: '/Books/skip.txt', name: 'skip.txt', size: 10});
  fetched.length = 0; confirms.length = 0; reloads = 0;
  const deleted = await ctx.bulkDeleteSelected();
  const deleteCalls = fetched.filter(f => f.url === '/delete');
  assert.equal(deleteCalls.length, 1, 'bulk delete must be a single request, not a loop');
  assert.equal(fetched.length, 1);
  assert.equal(deleteCalls[0].options.method, 'POST');
  const sentPaths = JSON.parse(new URLSearchParams(deleteCalls[0].body).get('paths'));
  assert.ok(Array.isArray(sentPaths), 'paths must be a JSON array');
  assert.deepEqual(sentPaths, ['/Books/a.epub', '/Books/sub', '/Books/c.txt']);
  assert.equal(deleted.deleted, 3);
  assert.equal(confirms.length, 1, 'bulk delete must confirm first');
  assert.ok(confirms[0].includes('3'), 'the confirm must state how many items');
  assert.equal(confirms[0], strings.confirmDelete.replace('{n}', '3'));
  assert.equal(reloads, 1);
  checks += 10;

  // cancelling the confirm sends nothing
  fetched.length = 0; confirmAnswer = false;
  assert.equal(await ctx.bulkDeleteSelected(), null);
  assert.equal(fetched.length, 0, 'a declined confirm must not delete');
  confirmAnswer = true;
  // A rejected batch has no reliable count either. Its detail is preserved.
  deleteOk = false; fetched.length = 0; alerts.length = 0; reloads = 0;
  const refused = await ctx.bulkDeleteSelected();
  assert.equal(refused.deleted, null);
  assert.equal(notices.at(-1).type, 'error');
  assert.ok(notices.at(-1).message.includes('protected'));
  assert.ok(alerts[0].includes(strings.deleteUnknown));
  assert.equal(reloads, 1);
  deleteOk = true;
  checks += 7;

  // A 500 can mean earlier paths WERE deleted. Never claim zero; warn the
  // user before refreshing so the transient notification isn't lost on reload.
  partialDelete = true; fetched.length = 0; alerts.length = 0; deleteEvents.length = 0; reloads = 0;
  const partialDeleteResult = await ctx.bulkDeleteSelected();
  assert.equal(fetched.filter(f => f.url === '/delete').length, 1);
  assert.equal(partialDeleteResult.deleted, null, 'the 500 response has no success count');
  assert.equal(alerts.length, 1, 'user must see the warning before page reload');
  assert.ok(alerts[0].includes(strings.deleteUnknown), 'explain that some items may have been deleted');
  assert.ok(alerts[0].includes('/Books/sub'), 'retain the device failure detail');
  assert.equal(reloads, 1, 'refresh the listing after a partial failure');
  assert.deepEqual(deleteEvents, ['alert', 'reload'], 'disclose uncertainty before reloading');
  partialDelete = false;
  checks += 7;

  // A connection drop may occur after the server deletes items too.
  rejectDelete = true; fetched.length = 0; alerts.length = 0; reloads = 0;
  const dropped = await ctx.bulkDeleteSelected();
  assert.equal(dropped.deleted, null);
  assert.equal(reloads, 1);
  assert.ok(alerts[0].includes(strings.deleteUnknown));
  assert.ok(alerts[0].includes(strings.networkError));
  rejectDelete = false;
  checks += 4;

  // ---- bulk move: one /move per file, in order, failures reported ------------
  rows = [];
  row({path: '/Books/a.epub', name: 'a.epub', size: 100, checked: true});
  row({path: '/Books/b.txt', name: 'b.txt', size: 200, checked: true});
  row({path: '/Books/c.txt', name: 'c.txt', size: 300, checked: true});
  fetched.length = 0; maxInFlight = 0; failMovePath = '/Books/b.txt'; reloads = 0;
  const moved = await ctx.bulkMoveSelected('/Archive/');
  const moveCalls = fetched.filter(f => f.url === '/move');
  assert.equal(moveCalls.length, 3, 'one /move request per selected file');
  assert.equal(maxInFlight, 1, '/move requests must be sequential');
  assert.deepEqual(moveCalls.map(c => c.options.body.get('path')),
                   ['/Books/a.epub', '/Books/b.txt', '/Books/c.txt'], 'move order must follow the list');
  assert.deepEqual([...new Set(moveCalls.map(c => c.options.body.get('dest')))], ['/Archive'],
                   'every move uses the normalized destination directory');
  assert.equal(moveCalls[0].options.method, 'POST');
  // the mid-list failure did not abort the tail
  assert.equal(moved.moved, 2);
  assert.equal(moved.failed.length, 1);
  assert.equal(moved.failed[0].name, 'b.txt');
  assert.ok(moved.summary.includes('b.txt'), 'the failure must be named in the summary');
  assert.equal(moved.summary, strings.moveDone.replace('{ok}', '2').replace('{bad}', '1')
               + ' ' + strings.moveFailedList.replace('{names}', 'b.txt'));
  assert.equal(elements.bulkProgress.textContent, moved.summary);
  failMovePath = null;
  // an empty destination never reaches the wire
  fetched.length = 0;
  assert.equal(await ctx.bulkMoveSelected('   '), null);
  assert.equal(fetched.length, 0);
  checks += 13;

  // the bulk move reuses the single-file move modal's destination picker
  let pickerLoads = 0;
  ctx.loadMoveFolderOptions = () => { pickerLoads++; };
  ctx.closeMoveModal = () => { elements.moveModal.classList.remove('open'); };
  assert.equal(ctx.openBulkMoveModal(), true);
  assert.equal(pickerLoads, 1, 'bulk move must reuse loadMoveFolderOptions()');
  assert.equal(elements.moveModal.classList.contains('open'), true);
  assert.equal(elements.moveDestPath.value, '/Books');
  assert.equal(elements.bulkMoveConfirmBtn.style.display, '');
  assert.equal(elements.moveConfirmBtn.style.display, 'none');
  elements.moveDestPath.value = '/Archive';
  fetched.length = 0;
  const viaModal = await ctx.confirmBulkMove();
  assert.equal(viaModal.dest, '/Archive');
  assert.equal(fetched.filter(f => f.url === '/move').length, 3);
  assert.equal(elements.moveConfirmBtn.style.display, '', 'single-file move button is restored');
  checks += 9;

  // ---- bulk download: sequential fetches, one zip, one save ------------------
  rows = [];
  row({path: '/Books/a.epub', name: 'a.epub', size: 1000, checked: true});
  row({path: '/Books/sub', name: 'sub', isFolder: true, checked: true});
  row({path: '/Books/sub/b.txt', name: 'b.txt', size: 2000, checked: true});
  row({path: '/Books/nope.txt', name: 'nope.txt', size: 10});
  fetched.length = 0; maxInFlight = 0; zips.length = 0; saves.length = 0;
  objectUrls.length = 0; confirms.length = 0; notices.length = 0;
  const zipped = await ctx.bulkDownloadSelected();
  const gets = fetched.filter(f => f.url.startsWith('/download?path='));
  assert.equal(gets.length, 2, 'only the selected files are fetched, once each');
  assert.equal(maxInFlight, 1, 'download fetches must be sequential');
  assert.deepEqual(gets.map(g => decodeURIComponent(g.url.slice('/download?path='.length))),
                   ['/Books/a.epub', '/Books/sub/b.txt']);
  assert.equal(new Set(gets.map(g => g.url)).size, gets.length, 'no file fetched twice');
  assert.equal(fetched.filter(f => f.url.includes('nope.txt')).length, 0, 'unselected files are left alone');
  // structure preserved relative to the directory on screen
  assert.equal(zips.length, 1, 'exactly one JSZip');
  assert.deepEqual(zips[0].entries.map(e => e.name), ['a.epub', 'sub/b.txt']);
  assert.deepEqual([...zipped.added], ['a.epub', 'sub/b.txt']);
  // the directory is skipped, with a message that says so
  assert.deepEqual([...zipped.skipped], ['sub']);
  assert.equal(confirms.length, 0, 'a small selection must not warn');
  assert.ok(notices.some(n => n.message.includes(strings.zipDone.replace('{n}', '2'))));
  // exactly one save
  assert.equal(objectUrls.length, 1, 'exactly one object URL');
  assert.equal(saves.length, 1);
  assert.equal(saves[0].clicks, 1, 'exactly one download click');
  assert.equal(saves[0].download, 'Books.zip');
  assert.equal(saves[0].href, objectUrls[0].u);
  checks += 15;

  // a failed file is reported but does not sink the zip
  failDownloadPath = '/Books/sub/b.txt';
  fetched.length = 0; zips.length = 0; saves.length = 0; objectUrls.length = 0;
  const partial = await ctx.bulkDownloadSelected();
  assert.deepEqual([...partial.added], ['a.epub']);
  assert.deepEqual([...partial.failed], ['b.txt']);
  assert.equal(saves.length, 1);
  failDownloadPath = null;
  checks += 3;

  // a selection of only directories never fetches
  rows = [];
  row({path: '/Books/sub', name: 'sub', isFolder: true, checked: true});
  fetched.length = 0;
  assert.equal(await ctx.bulkDownloadSelected(), null);
  assert.equal(fetched.length, 0, 'directories alone means nothing to download');
  assert.equal(notices.at(-1).message, strings.zipNoFiles);
  checks += 3;

  // ---- the oversize warning fires above ~24 MB and not below -----------------
  const limit = ctx.bulkZipWarnBytes();
  assert.equal(limit, 24 * 1024 * 1024);
  const under = [{path: '/Books/x', name: 'x', isFolder: false, size: limit}];
  const over = [{path: '/Books/x', name: 'x', isFolder: false, size: limit + 1}];
  assert.equal(ctx.bulkNeedsSizeWarning(under), false, 'exactly at the limit must not warn');
  assert.equal(ctx.bulkNeedsSizeWarning(over), true);
  assert.equal(ctx.bulkNeedsSizeWarning([{isFolder: true, size: limit * 4}]), false, 'folders carry no bytes');
  checks += 4;

  // ... and the warning really gates the zip
  rows = [];
  row({path: '/Books/big.epub', name: 'big.epub', size: 20 * 1024 * 1024, checked: true});
  row({path: '/Books/big2.epub', name: 'big2.epub', size: 20 * 1024 * 1024, checked: true});
  fetched.length = 0; confirms.length = 0; confirmAnswer = false;
  assert.equal(await ctx.bulkDownloadSelected(), null, 'declining the size warning cancels');
  assert.equal(confirms.length, 1);
  assert.equal(confirms[0], strings.zipTooBig.replace('{size}', '40.0 MB'));
  assert.equal(fetched.length, 0, 'nothing is fetched after cancelling');
  confirmAnswer = true;
  fetched.length = 0; confirms.length = 0; saves.length = 0;
  await ctx.bulkDownloadSelected();
  assert.equal(confirms.length, 1);
  assert.equal(fetched.length, 2, 'accepting the warning proceeds');
  // small selection: no warning at all
  rows = [];
  row({path: '/Books/small.txt', name: 'small.txt', size: 1024, checked: true});
  fetched.length = 0; confirms.length = 0;
  await ctx.bulkDownloadSelected();
  assert.equal(confirms.length, 0, 'a 1 KB selection must not warn');
  checks += 8;

  // ---- zip entry naming is structure preserving, root included ---------------
  assert.equal(ctx.bulkZipEntryName('/Books/sub/b.txt', '/Books'), 'sub/b.txt');
  assert.equal(ctx.bulkZipEntryName('/Books/a.epub', '/Books/'), 'a.epub');
  assert.equal(ctx.bulkZipEntryName('/a.epub', '/'), 'a.epub');
  assert.equal(ctx.bulkZipEntryName('/deep/x/y.txt', '/'), 'deep/x/y.txt');
  checks += 4;
}
console.log(JSON.stringify({ok: true, locales: 2, checks}));
