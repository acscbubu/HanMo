import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import vm from 'node:vm';

const root = fileURLToPath(new URL('../..', import.meta.url));
const source = readFileSync(`${root}/src/network/html/js/nav.js`, 'utf8');

function page(lang, href, savedLanguage) {
  const values = new Map([['crossmux.nav.pages.v2.' + lang, JSON.stringify(['home', 'files'])]]);
  if (savedLanguage) values.set('hanmo.web-ui', savedLanguage);
  const links = ['/', '/files'].map((path, i) => ({
    dataset: {navKey: ['home', 'files'][i]},
    href: 'http://x4pro.local' + path,
    getAttribute(key) { return key === 'href' ? path : null; },
  }));
  const nav = {
    dataset: {navGroup: 'pages'}, children: [...links],
    addEventListener() {},
    querySelector(selector) { return selector === '.web-language-switch' ? this.children.find(el => el.className === 'web-language-switch') : null; },
    appendChild(child) { this.children = this.children.filter(item => item !== child); this.children.push(child); },
  };
  let assigned, replaced;
  const styles = [];
  function element() {
    return {
      dataset: {},
      textContent: '',
      addEventListener(type, fn) { if (type === 'change') this.change = fn; },
      setAttribute() {},
      appendChild(child) { this.child = child; },
    };
  }
  const document = {
    documentElement: {lang},
    head: {appendChild(style) { styles.push(style.textContent); }},
    querySelector(selector) { return selector === '.shell > .nav-links' ? nav : null; },
    getElementById() { return null; },
    querySelectorAll(selector) {
      if (selector === '[data-nav-group]') return [nav];
      if (selector === '[data-brand]') return [];
      if (selector === '[data-nav-group="pages"] a[href]') return links;
      return [];
    },
    createElement: element,
  };
  const window = {
    location: {
      href,
      assign(url) { assigned = url; },
      replace(url) { replaced = url; },
    },
  };
  const localStorage = {
    getItem: key => values.get(key) || null,
    setItem: (key, value) => values.set(key, value),
  };
  vm.runInNewContext(source, {document, window, localStorage, URL, fetch: async () => ({ok: true, json: async () => ({})})});
  return {nav, links, window, values, styles, get assigned() { return assigned; }, get replaced() { return replaced; }};
}

const english = page('en', 'http://x4pro.local/device#airphoto', null);
assert.equal(english.nav.children.at(-1).className, 'web-language-switch');
assert.equal(english.nav.children.at(-1).child.value, 'en');
assert.equal(english.replaced, undefined);
assert.equal(english.links[0].href, '/?ui=en');
assert.match(english.styles.join(''), /\.web-language-switch select\{[^}]*min-height:44px/);
assert.match(english.styles.join(''), /grid-column:1\/-1/);
assert.match(english.nav.children.at(-1).child.innerHTML, /value="zh-CN">简体中文/);
assert.match(english.nav.children.at(-1).child.innerHTML, /value="zh-Hant">繁體中文/);
english.nav.children.at(-1).child.value = 'zh-CN';
english.nav.children.at(-1).child.change();
assert.equal(english.assigned, '/device?ui=zh-CN#airphoto');
assert.equal(english.values.get('hanmo.web-ui'), 'zh-CN');

const chinese = page('zh-CN', 'http://x4pro.local/device?other=1#airphoto', 'zh-CN');
assert.equal(chinese.replaced, '/device?other=1&ui=zh-CN#airphoto');
chinese.window.crossmuxNav.refresh();
assert.equal(chinese.nav.children.at(-1).className, 'web-language-switch', 'selector remains after sidebar ordering');
assert.equal(chinese.nav.children.at(-1).child.value, 'zh-CN');
assert.equal(chinese.nav.children.at(-1).textContent, '语言');

// An explicit URL choice wins over this browser's saved choice.
const explicit = page('en', 'http://x4pro.local/device?other=1&ui=en#airphoto', 'zh-CN');
assert.equal(explicit.replaced, undefined);
assert.equal(explicit.values.get('hanmo.web-ui'), 'en');

// Traditional bookmarks and saved preferences remain Traditional, not simplified.
const traditional = page('zh-Hant', 'http://x4pro.local/device?ui=zh-Hant#airphoto', 'zh-Hant');
assert.equal(traditional.replaced, undefined);
assert.equal(traditional.values.get('hanmo.web-ui'), 'zh-Hant');
assert.equal(traditional.nav.children.at(-1).child.value, 'zh-Hant');
assert.equal(traditional.nav.children.at(-1).textContent, '語言');
const savedTraditional = page('en', 'http://x4pro.local/device?other=1#airphoto', 'zh-Hant');
assert.equal(savedTraditional.replaced, '/device?other=1&ui=zh-Hant#airphoto');
traditional.nav.children.at(-1).child.value = 'zh-CN';
traditional.nav.children.at(-1).child.change();
assert.equal(traditional.assigned, '/device?ui=zh-CN#airphoto');

// Execute the real initial Settings inline script, not a hand-copied redirect.
for (const lang of ['en', 'zh-CN', 'zh-Hant']) {
  const html = readFileSync(`${root}/src/network/html/${lang}/SettingsPage.html`, 'utf8');
  const inline = html.match(/<script>\s*([\s\S]*?)<\/script>/)[1];
  const initial = inline.slice(0, inline.indexOf('  let settingsReady = false;'));
  let redirect;
  const location = {
    pathname: '/settings', search: '?ui=zh-CN&from=bookmark', hash: '#airphoto',
    replace(url) { redirect = url; },
  };
  vm.runInNewContext(initial, {
    location, document: {
      getElementById: () => ({hidden: false}),
      querySelectorAll: () => [],
    },
  });
  assert.equal(redirect, '/device?ui=zh-CN&from=bookmark#airphoto', `${lang} legacy bookmark`);

  // The late hashchange path must preserve the browser choice as well.
  redirect = undefined;
  const paneSource = inline.slice(inline.indexOf('function showPane(name) {'),
                                  inline.indexOf("window.addEventListener('hashchange'"));
  const ctx = {location, IS_DEVICE_PAGE: false, DEVICE_PANES: ['airnote']};
  ctx.location.search = '?ui=en&from=bookmark';
  vm.runInNewContext(paneSource, ctx);
  ctx.showPane('airnote');
  assert.equal(redirect, '/device?ui=en&from=bookmark#airnote', `${lang} late pane redirect`);

  // Browser selection travels with the settings GET and POST, never a
  // language setting in the JSON body sent to the device.
  const loadSource = inline.slice(inline.indexOf('async function loadSettings() {'),
                                  inline.indexOf('async function saveSettings() {'));
  for (const [query, expected] of [
    ['', '/api/settings'],
    ['?ui=en', '/api/settings?ui=en'],
    ['?ui=zh-CN', '/api/settings?ui=zh-CN'],
    ['?ui=zh-Hant', '/api/settings?ui=zh-Hant'],
    ['?ui=bogus', '/api/settings'],
  ]) {
    let fetched;
    const loadContext = {
      location: {search: query}, URLSearchParams,
      fetch: async url => { fetched = url; throw new Error('stop after URL'); },
      installSettingsPanes() {},
      console: {error() {}},
    };
    vm.runInNewContext(loadSource, loadContext);
    await loadContext.loadSettings();
    assert.equal(fetched, expected, `${lang} ${query} settings GET`);
  }
  const saveSource = inline.slice(inline.indexOf('async function saveSettings() {'),
                                  inline.indexOf('  // --- Wi-Fi Network Management ---'));
  for (const [query, expected] of [
    ['', '/api/settings'],
    ['?ui=en', '/api/settings?ui=en'],
    ['?ui=zh-CN', '/api/settings?ui=zh-CN'],
    ['?ui=zh-Hant', '/api/settings?ui=zh-Hant'],
  ]) {
    let posted;
    const saveContext = {
      location: {search: query}, URLSearchParams, encodeURIComponent, TextEncoder,
      allSettings: [{key:'showHiddenFiles', type:'toggle', value:0}],
      originalValues: {showHiddenFiles:0}, getValue: () => 1,
      document: {getElementById(id) { return id === 'saveBtn' ? {disabled:false, textContent:''} : {checked:true}; }},
      fetch: async (url, opts) => { posted = {url, method:opts.method, body:JSON.parse(opts.body)}; return {ok:true}; },
      showMessage() {}, console: {error() {}},
    };
    vm.runInNewContext(saveSource, saveContext);
    await saveContext.saveSettings();
    assert.equal(posted.url, expected, `${lang} ${query} settings POST`);
    assert.equal(posted.method, 'POST');
    assert.deepEqual(posted.body, {showHiddenFiles:1});
  }
}
console.log(JSON.stringify({ok:true}));
