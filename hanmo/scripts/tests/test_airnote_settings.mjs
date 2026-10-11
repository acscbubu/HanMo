// Exercise the AirNote settings-page script against a minimal fake DOM:
// the saved-note list is a drag-and-drop <ul>/<li>, with move up/down buttons
// as the keyboard and touch fallback. Run: node scripts/tests/test_airnote_settings.mjs
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import vm from 'node:vm';
const root = fileURLToPath(new URL('../..', import.meta.url));

class El {
  constructor(tag = 'div') {
    this.tagName = tag.toUpperCase();
    this.children = []; this.options = []; this.dataset = {}; this.style = {}; this.attrs = {};
    this.handlers = {}; this.classes = new Set();
    this.value = ''; this.textContent = ''; this.disabled = false; this.hidden = false;
    this.draggable = false; this.focused = false;
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
  appendChild(child) { this.children.push(child); this.options.push(child); return child; }
  add(child) { return this.appendChild(child); }
  replaceChildren() { this.children = []; this.options = []; }
  focus() { this.focused = true; }
  matches(selector) { return selector.startsWith('.') ? this.classes.has(selector.slice(1)) : this.tagName === selector.toUpperCase(); }
  descendants() { return this.children.flatMap(c => c instanceof El ? [c, ...c.descendants()] : []); }
  querySelector(selector) { return this.descendants().find(c => c.matches(selector)) || null; }
  querySelectorAll(selector) { return this.descendants().filter(c => c.matches(selector)); }
  dispatch(type, event = {}) {
    const base = {preventDefault() {}, stopPropagation() {}, type};
    for (const fn of this.handlers[type] || []) fn.call(this, Object.assign(base, event));
  }
}
const transfer = () => ({data: {}, setData(k, v) { this.data[k] = v; }, effectAllowed: '', dropEffect: ''});

const expect = {
  'zh-CN': {conflict: /筆記已被修改/, storage: /無法讀寫 SD 卡/, ordered: /已保存筆記順序/, first: '1. 會議.txt', dirtyDelete: /未儲存/, newNote: /新增筆記/, uncertain: /未能確認/, zeroDeleted: /刪除 0/, refreshed: /重新整理的清單/,
            itemSelect: /勾選事項以批次刪除/, itemRemoved: /已從草稿移除 2 個勾選事項/, itemRefusal: /至少保留一項/},
  en: {conflict: /The note was changed/, storage: /Cannot read or write the SD card/,
       ordered: /Note order saved/, first: '1. 會議.txt', dirtyDelete: /unsaved/i, newNote: /New note/, uncertain: /uncertain/i, zeroDeleted: /0 deleted/i, refreshed: /refreshed list/i,
       itemSelect: /Select item for bulk delete/, itemRemoved: /Removed 2 selected items/, itemRefusal: /at least one item/i},
};
expect['zh-Hant'] = expect['zh-CN'];
for (const locale of ['en', 'zh-CN', 'zh-Hant']) {
  const html = readFileSync(`${root}/src/network/html/${locale}/SettingsPage.html`, 'utf8');
  const code = html.slice(html.indexOf('// ---- AirNote'), html.indexOf('// ---- Panes'));
  const words = expect[locale];
  const elements = {};
  for (const id of ['title','text','save','new','refresh','load','list','more','mode','list-status','type','todo-help','preview','item-delete','bulk-select-visible','bulk-clear','bulk-status','bulk-target','bulk-order','bulk-dest','bulk-move','bulk-delete']) {
    elements['airnote-' + id] = new El(id === 'list' ? 'ul' : 'div');
  }
  const field = id => elements['airnote-' + id];
  field('type').value = 'text';
  const sent = [], notices = [];
  let moveFailure = null, moveFailureAfterRename = false, inFlight = 0, maxInFlight = 0, fileFailure = 0, deleteFailure = false, listFailure = 0;
  const prompts = [];
  let failure = 0, discard = true, revision = 'r1', order = '00000000000000000000000000000001', notes = ['會議.txt', '<b>test</b>.txt'];
  let openText = '原本內容\n', openType;
  const ctx = vm.createContext({
    document: {getElementById: id => elements[id], createElement: tag => new El(tag)},
    window: {addEventListener() {}, confirm: message => { prompts.push(message); return discard; }},
    TextEncoder, URLSearchParams, URL, confirm: () => discard,
    Option: class { constructor(text, value) { this.textContent = text; this.value = value; } },
    showMessage: (message, error) => notices.push({message, error}),
    fetch: async (url, options = {}) => {
      sent.push({url, options});
      assert.equal(field('save').disabled, true);
      if (failure) return {ok: false, status: failure, text: async () => 'SD card unavailable'};
      if (url.startsWith('/api/files?')) {
        if (fileFailure) return {ok: false, status: fileFailure};
        const path = new URL(url, 'http://device').searchParams.get('path');
        const entries = {
          '/': [{name: 'AirNote', isDirectory: true}, {name: 'Read', isDirectory: true}],
          '/Read': [{name: 'Archive', isDirectory: true}, {name: '會議.txt', isDirectory: false}],
          '/Read/Archive': [],
        };
        return {ok: true, json: async () => entries[path] || []};
      }
      if (url === '/move') {
        const {path, dest} = Object.fromEntries(new URLSearchParams(options.body));
        assert.equal(dest, '/Read/Archive');
        ++inFlight; maxInFlight = Math.max(maxInFlight, inFlight);
        await new Promise(r => setImmediate(r)); await new Promise(r => setImmediate(r));
        --inFlight;
        if (path === moveFailure) {
          if (moveFailureAfterRename) notes = notes.filter(name => '/AirNote/' + name !== path);
          return {ok: false, status: 500};
        }
        notes = notes.filter(name => '/AirNote/' + name !== path);
        return {ok: true, text: async () => 'Moved successfully'};
      }
      if (url.includes('offset=') && listFailure) return {ok: false, status: listFailure};
      if (url === '/delete') {
        const paths = JSON.parse(new URLSearchParams(options.body).get('paths'));
        if (deleteFailure) {
          notes = notes.filter(name => '/AirNote/' + name !== paths[0]);
          return {ok: false, status: 500, text: async () => 'Failed to delete some items'};
        }
        notes = notes.filter(name => !paths.includes('/AirNote/' + name));
        return {ok: true, text: async () => 'All items deleted successfully'};
      }
      if (url.includes('/order')) { order = (BigInt('0x' + order) + 1n).toString(16).padStart(32, '0'); return {ok: true, json: async () => ({})}; }
      const offset = Number(new URL(url, 'http://device').searchParams.get('offset'));
      const data = url.includes('offset=')
        ? {notes: notes.slice(offset, offset + 50), total: notes.length, orderRevision: order, nextOffset: offset + 50 < notes.length ? offset + 50 : null}
        : url.includes('name=') ? {name: '會議.txt', title: '會議', text: openText, type: openType, revision}
        : {name: '會議.txt', revision: revision = 'r2'};
      return {ok: true, json: async () => data};
    }});
  vm.runInContext(code, ctx);

  // ---- bulk checkboxes are separate from the note opened for editing ----
  const pane = html.slice(html.indexOf('id="pane-airnote"'), html.indexOf('id="pane-airphoto"'));
  assert.match(html, /#airnote-container \.airnote-bulk-check \{[^}]*width: 24px;[^}]*height: 24px;/);
  assert.match(html, /#airnote-container #airnote-bulk-target,/);
  assert.match(pane, /id="airnote-bulk-select-visible"/);
  if (locale === 'en') assert.match(pane, /id="airnote-bulk-select-visible"[^>]*>Select loaded \(up to 32\)<\/button>/);
  assert.match(pane, /id="airnote-bulk-clear"/);

  // ---- the editing buttons sit ABOVE the saved-note list ----
  const refreshAt = pane.indexOf('id="airnote-refresh"');
  const selectAt = pane.indexOf('id="airnote-bulk-select-visible"');
  const labelAt = pane.indexOf('id="airnote-list-label"');
  const listAt = pane.indexOf('id="airnote-list"');
  assert.ok(refreshAt > 0 && labelAt > 0 && listAt > 0, locale + ': list and buttons exist');
  assert.ok(refreshAt < labelAt, locale + ': refresh/load/new come before the list');
  assert.ok(selectAt < labelAt, locale + ': the selection buttons come before the list');
  // The destination controls read the checkboxes, so they stay under the rows.
  assert.ok(pane.indexOf('id="airnote-bulk-target"') > listAt, locale + ': bulk destination stays below');
  assert.ok(pane.indexOf('id="airnote-bulk-delete"') > listAt, locale + ': bulk delete stays below');
  await ctx.loadAirnotes();
  assert.equal(field('list').children[0].querySelector('.airnote-bulk-check').type, 'checkbox');
  field('list').children[1].querySelector('.airnote-bulk-check').checked = true;
  field('list').children[1].querySelector('.airnote-bulk-check').dispatch('change');
  assert.equal(field('list').children[0].getAttribute('aria-current'), 'true');
  assert.equal(field('list').children[1].getAttribute('aria-current'), 'false');
  ctx.selectVisibleAirnotes();
  assert.equal(field('list').children.filter(row => row.querySelector('.airnote-bulk-check').checked).length, 2);
  ctx.clearSelectedAirnotes();
  assert.equal(field('list').children.filter(row => row.querySelector('.airnote-bulk-check').checked).length, 0);

  // ---- list renders as draggable rows, no <select>, no destination input ----
  await ctx.loadAirnotes();
  const rows = () => field('list').children;
  assert.equal(rows().length, 2);
  assert.equal(rows()[0].tagName, 'LI');
  assert.equal(rows()[0].draggable, true);
  assert.equal(rows()[0].querySelector('.airnote-pick').textContent, words.first);
  assert.equal(rows()[1].querySelector('.airnote-pick').textContent, '2. <b>test</b>.txt');
  assert.equal(rows()[0].getAttribute('aria-posinset'), '1');
  assert.equal(rows()[0].getAttribute('aria-setsize'), '2');
  // ---- "load more" paging and the total still work ----
  await ctx.loadAirnotes(true);
  assert.equal(rows().length, 2); assert.equal(field('more').hidden, true);
  assert.equal(field('list-status').textContent.length > 0, true);

  // ---- only loaded entries are checkable, with a hard cap of 32 ----
  notes = Array.from({length: 60}, (_, i) => `note-${i}.txt`);
  await ctx.loadAirnotes();
  assert.equal(rows().length, 50);
  ctx.selectVisibleAirnotes();
  assert.equal(rows().filter(row => row.querySelector('.airnote-bulk-check').checked).length, 32);
  const extra = rows()[32].querySelector('.airnote-bulk-check');
  extra.checked = true; extra.dispatch('change');
  assert.equal(extra.checked, false);
  await ctx.loadAirnotes(true);
  assert.equal(rows().length, 60);
  assert.equal(rows().filter(row => row.querySelector('.airnote-bulk-check').checked).length, 32);
  notes = ['會議.txt', '<b>test</b>.txt']; await ctx.loadAirnotes();

  // ---- keyboard/touch fallback: per-row move buttons hit moveAirnote(direction) ----
  assert.equal(rows()[0].querySelector('.airnote-up').disabled, true);   // first row cannot move up
  assert.equal(rows()[1].querySelector('.airnote-down').disabled, true); // last row cannot move down
  assert.equal(rows()[0].querySelector('.airnote-up').getAttribute('aria-label').endsWith('會議.txt'), true);
  let before = sent.length;
  rows()[0].querySelector('.airnote-down').dispatch('click');
  await new Promise(r => setImmediate(r));
  const down = sent[before];
  assert.equal(down.url, '/api/airnote/order');
  assert.deepEqual(JSON.parse(down.options.body), {name: '會議.txt', direction: 1, orderRevision: '00000000000000000000000000000001'});
  assert.match(notices.at(-1).message, words.ordered);
  before = sent.length;
  rows()[1].querySelector('.airnote-up').dispatch('click');
  await new Promise(r => setImmediate(r));
  assert.equal(JSON.parse(sent[before].options.body).direction, -1);

  // ---- dragging a row onto another saves an absolute target on the same endpoint ----
  before = sent.length;
  const dt = transfer();
  rows()[0].dispatch('dragstart', {dataTransfer: dt});
  assert.equal(rows()[0].classList.contains('dragging'), true);
  rows()[1].dispatch('dragover', {dataTransfer: dt});
  assert.equal(rows()[1].classList.contains('dragover'), true);
  rows()[1].dispatch('drop', {dataTransfer: dt});
  await new Promise(r => setImmediate(r));
  const drop = sent[before];
  assert.equal(drop.url, '/api/airnote/order');
  assert.equal(drop.options.method, 'PUT');
  assert.deepEqual(JSON.parse(drop.options.body), {name: '會議.txt', target: 1, orderRevision: JSON.parse(drop.options.body).orderRevision});
  assert.equal(JSON.parse(drop.options.body).target, 1);
  assert.equal(rows()[0].classList.contains('dragging'), false);

  // ---- a stale revision is reported, not silently retried ----
  before = sent.length; failure = 409;
  rows()[0].querySelector('.airnote-down').dispatch('click');
  await new Promise(r => setImmediate(r));
  assert.equal(notices.at(-1).error, true);
  failure = 0;
  before = sent.length;
  rows()[0].querySelector('.airnote-down').dispatch('click');  // revision was cleared -> no request
  await new Promise(r => setImmediate(r));
  assert.equal(sent.length, before);
  await ctx.loadAirnotes();

  // ---- group order uses the new atomic endpoint and a loaded, unselected target ----
  assert.match(pane, /id="airnote-bulk-target"/);
  assert.match(pane, /id="airnote-bulk-order"/);
  ctx.clearSelectedAirnotes();
  const box = rows()[0].querySelector('.airnote-bulk-check');
  box.checked = true; box.dispatch('change');
  assert.deepEqual(field('bulk-target').options.map(option => option.value), ['', '<b>test</b>.txt']);
  field('bulk-target').value = '<b>test</b>.txt';
  before = sent.length;
  await ctx.moveSelectedAirnotesInOrder();
  const bulkOrder = sent[before];
  assert.equal(bulkOrder.url, '/api/airnote/order/bulk');
  assert.equal(bulkOrder.options.method, 'PUT');
  assert.deepEqual(JSON.parse(bulkOrder.options.body), {
    names: ['會議.txt'], before: '<b>test</b>.txt', orderRevision: JSON.parse(bulkOrder.options.body).orderRevision,
  });
  assert.match(JSON.parse(bulkOrder.options.body).orderRevision, /^[a-f0-9]{32}$/);
  assert.equal(rows()[0].querySelector('.airnote-bulk-check').checked, false);
  ctx.selectVisibleAirnotes();
  field('bulk-target').value = '';
  before = sent.length;
  await ctx.moveSelectedAirnotesInOrder();
  assert.equal(JSON.parse(sent[before].options.body).before, null);
  assert.deepEqual(JSON.parse(sent[before].options.body).names, ['會議.txt', '<b>test</b>.txt']);
  ctx.selectVisibleAirnotes(); failure = 409; before = sent.length;
  await ctx.moveSelectedAirnotesInOrder();
  assert.equal(sent.length, before + 1);
  assert.equal(notices.at(-1).error, true);
  failure = 0; before = sent.length;
  await ctx.moveSelectedAirnotesInOrder(); // stale token must never be reused
  assert.equal(sent.length, before);
  await ctx.loadAirnotes();

  // ---- moving files checks real /api/files listings before any sequential /move writes ----
  assert.match(pane, /id="airnote-bulk-dest"/);
  assert.match(pane, /id="airnote-bulk-move"/);
  ctx.selectVisibleAirnotes();
  for (const invalid of ['', '  ', 'Read/Archive', '/AirNote', '/AirNote/Archive', '/XTCache', '/.crosspoint', '/Read/../Archive', '/Read/NoSuchFolder']) {
    field('bulk-dest').value = invalid;
    before = sent.filter(x => x.url === '/move').length;
    await ctx.moveSelectedAirnotesToFolder();
    assert.equal(sent.filter(x => x.url === '/move').length, before, invalid);
    assert.equal(notices.at(-1).error, true);
  }
  field('bulk-dest').value = '/Read'; // The first note collides: no file can be moved.
  before = sent.length;
  await ctx.moveSelectedAirnotesToFolder();
  assert.equal(sent.slice(before).some(x => x.url === '/move'), false);
  assert.ok(sent.slice(before).some(x => x.url === '/api/files?path=%2FRead'));
  field('bulk-dest').value = '/Read/Archive';
  before = sent.length;
  await ctx.moveSelectedAirnotesToFolder();
  const moved = sent.slice(before).filter(x => x.url === '/move');
  assert.equal(moved.length, 2, JSON.stringify({last: notices.at(-1), urls: sent.slice(before).map(x => x.url)}));
  assert.deepEqual(moved.map(x => Object.fromEntries(new URLSearchParams(x.options.body))), [
    {path: '/AirNote/會議.txt', dest: '/Read/Archive'},
    {path: '/AirNote/<b>test</b>.txt', dest: '/Read/Archive'},
  ]);
  assert.equal(maxInFlight, 1);
  assert.equal(rows().length, 0); // Refreshed after the successful moves.
  assert.match(notices.at(-1).message, /2/);
  notes = ['會議.txt', '<b>test</b>.txt']; await ctx.loadAirnotes();
  ctx.selectVisibleAirnotes();
  moveFailure = '/AirNote/<b>test</b>.txt';
  before = sent.length;
  await ctx.moveSelectedAirnotesToFolder();
  assert.equal(sent.slice(before).filter(x => x.url === '/move').length, 2);
  assert.equal(rows().length, 1); // Still reload after a partial failure.
  assert.equal(notices.at(-1).error, true);
  assert.match(notices.at(-1).message, /1/); // One confirmed moved; no claim about the failed request.
  moveFailure = null; notes = ['會議.txt', '<b>test</b>.txt']; await ctx.loadAirnotes();
  ctx.selectVisibleAirnotes(); fileFailure = 503; before = sent.length;
  await ctx.moveSelectedAirnotesToFolder();
  assert.equal(sent.slice(before).some(x => x.url === '/move'), false);
  fileFailure = 0; ctx.clearSelectedAirnotes();

  // ---- selecting a row drives "load for editing" (the old <select> value path) ----
  rows()[0].querySelector('.airnote-pick').dispatch('click');
  assert.equal(rows()[0].getAttribute('aria-current'), 'true');
  assert.equal(rows()[0].querySelector('.airnote-pick').getAttribute('aria-pressed'), 'true');
  assert.equal(rows()[1].getAttribute('aria-current'), 'false');
  await ctx.openAirnote();
  assert.equal(field('text').value, '原本內容\n');

  // ---- saving, conflicts and validation are unchanged ----
  field('text').value = '同長新文\n'; await ctx.uploadAirnote();
  const put = sent.find(x => x.options.method === 'PUT' && x.url === '/api/airnote');
  assert.deepEqual(JSON.parse(put.options.body), {title: '會議', text: '同長新文\n', type: 'text', name: '會議.txt', revision: 'r1'});
  assert.equal(field('text').value, '同長新文\n'); assert.equal(notices.at(-1).error, false);
  failure = 409; field('text').value = '不可以遺失'; await ctx.uploadAirnote();
  assert.equal(field('text').value, '不可以遺失'); assert.equal(notices.at(-1).error, true);
  assert.equal(field('save').disabled, false);
  assert.match(notices.at(-1).message, words.conflict);
  // ---- a confirmed move of the open file keeps its unsaved editor text as a new draft ----
  failure = 0;
  ctx.clearSelectedAirnotes();
  rows()[0].querySelector('.airnote-bulk-check').checked = true;
  rows()[0].querySelector('.airnote-bulk-check').dispatch('change');
  field('bulk-dest').value = '/Read/Archive';
  await ctx.moveSelectedAirnotesToFolder();
  assert.equal(field('text').value, '不可以遺失');
  assert.match(field('mode').textContent, words.newNote);
  notes = ['會議.txt', '<b>test</b>.txt']; await ctx.loadAirnotes();

  // /move may rename the source, then fail while relocating metadata.
  rows()[0].querySelector('.airnote-pick').dispatch('click');
  await ctx.openAirnote();
  field('text').value = '失敗時仍保留的草稿';
  ctx.clearSelectedAirnotes();
  rows()[0].querySelector('.airnote-bulk-check').checked = true;
  rows()[0].querySelector('.airnote-bulk-check').dispatch('change');
  moveFailure = '/AirNote/會議.txt'; moveFailureAfterRename = true;
  await ctx.moveSelectedAirnotesToFolder();
  assert.equal(rows().length, 1);
  assert.match(field('mode').textContent, words.newNote);
  assert.equal(field('text').value, '失敗時仍保留的草稿');
  assert.equal(notices.at(-1).error, true);
  moveFailure = null; moveFailureAfterRename = false;
  notes = ['會議.txt', '<b>test</b>.txt']; await ctx.loadAirnotes();
  field('text').value = '不可以遺失';

  // ---- delete confirms names/count, warns for a dirty opened note, preserves draft ----
  failure = 0;
  assert.match(pane, /id="airnote-bulk-delete"/);
  ctx.selectVisibleAirnotes(); discard = false;
  before = sent.length;
  await ctx.deleteSelectedAirnotes();
  assert.equal(sent.length, before); // Cancel is safe; no delete request.
  assert.match(prompts.at(-1), /2/);
  assert.ok(prompts.at(-1).includes('會議.txt') && prompts.at(-1).includes('<b>test</b>.txt'));
  assert.match(prompts.at(-1), words.dirtyDelete);
  discard = true; before = sent.length;
  await ctx.deleteSelectedAirnotes();
  const deleted = sent.slice(before).find(x => x.url === '/delete');
  assert.equal(deleted.options.method, 'POST');
  assert.deepEqual(JSON.parse(new URLSearchParams(deleted.options.body).get('paths')),
    ['/AirNote/會議.txt', '/AirNote/<b>test</b>.txt']);
  assert.equal(rows().length, 0);
  assert.equal(field('text').value, '不可以遺失');
  assert.match(field('mode').textContent, words.newNote);
  notes = ['會議.txt', '<b>test</b>.txt']; await ctx.loadAirnotes();
  await ctx.openAirnote();
  field('text').value = '局部失敗後保留草稿';
  ctx.selectVisibleAirnotes(); deleteFailure = true; before = sent.length;
  await ctx.deleteSelectedAirnotes();
  assert.equal(sent.slice(before).filter(x => x.url === '/delete').length, 1);
  assert.equal(rows().length, 1); // HTTP 500 can follow a partial deletion: reload list.
  assert.equal(notices.at(-1).error, true);
  assert.match(notices.at(-1).message, words.uncertain);
  assert.doesNotMatch(notices.at(-1).message, words.zeroDeleted);
  assert.equal(field('text').value, '局部失敗後保留草稿');
  assert.match(field('mode').textContent, words.newNote);
  field('text').value = '不可以遺失';
  // A failed list refresh after HTTP 500 cannot be described as a refreshed list.
  notes = ['會議.txt', '<b>test</b>.txt']; await ctx.loadAirnotes();
  ctx.selectVisibleAirnotes(); listFailure = 503;
  await ctx.deleteSelectedAirnotes();
  assert.doesNotMatch(notices.at(-1).message, words.refreshed);
  assert.equal(field('bulk-delete').disabled, true); // No stale retry after an uncertain result.
  listFailure = 0;
  deleteFailure = false; notes = ['會議.txt', '<b>test</b>.txt']; await ctx.loadAirnotes();
  discard = false; const count = sent.length; await ctx.openAirnote(); ctx.newAirnote();
  assert.equal(sent.length, count); assert.equal(field('text').value, '不可以遺失');
  discard = true; failure = 507; await ctx.openAirnote(); assert.equal(field('text').value, '不可以遺失');
  assert.match(notices.at(-1).message, words.storage);
  assert.ok(!notices.at(-1).message.includes('SD card unavailable'));
  failure = 0; ctx.newAirnote(); assert.equal(field('text').value, '');
  field('title').value = '會議'; field('text').value = '新筆記'; await ctx.uploadAirnote();
  assert.ok(sent.some(x => x.options.method === 'POST'));
  const mark = sent.length; field('title').value = '../bad'; await ctx.uploadAirnote();
  assert.equal(sent.length, mark);
  field('title').value = 'title'; field('text').value = 'x'.repeat(16385); await ctx.uploadAirnote();
  assert.equal(sent.length, mark);

  // ---- checklist items inside the open note: multi-select + confirmed bulk delete ----
  assert.ok(/#airnote-preview \.airnote-item-select \{[^}]*width: 24px;[^}]*height: 24px;/.test(html),
    locale + ': no 24px .airnote-item-select rule for the per-item selection checkbox');
  assert.ok(/id="airnote-item-delete"/.test(pane), locale + ': no #airnote-item-delete button in the AirNote pane');
  const previewRows = () => field('preview').children.filter(child => child.tagName === 'DIV');
  const itemSelect = index => previewRows()[index].querySelector('.airnote-item-select');
  const itemDone = index => previewRows()[index].querySelector('.airnote-item-done');
  const pickItem = (index, on = true) => { const box = itemSelect(index); box.checked = on; box.dispatch('change'); };
  const itemsSelected = () => previewRows().filter(row => row.querySelector('.airnote-item-select').checked).length;
  openType = 'todo'; openText = '[ ] one\n[x] two\n[ ] three\n[x] four\n';
  discard = true; failure = 0;
  rows()[0].querySelector('.airnote-pick').dispatch('click');
  await ctx.openAirnote();
  assert.equal(field('type').value, 'todo');
  assert.equal(previewRows().length, 4);
  assert.equal(field('item-delete').hidden, false);
  // (e) The selection box is a second, separately labelled control beside the done box.
  assert.equal(itemSelect(0).type, 'checkbox');
  assert.notEqual(itemSelect(1), itemDone(1));
  assert.match(itemSelect(1).getAttribute('aria-label'), words.itemSelect);
  assert.equal(itemSelect(1).getAttribute('aria-label').endsWith('two'), true);
  // (d) Nothing selected: the button is disabled and still reports the count.
  assert.equal(field('item-delete').disabled, true);
  assert.match(field('item-delete').textContent, /0/);
  // (e) Ticking "select" must not touch '[x] ' / '[ ] ' in the draft.
  let draft = field('text').value;
  pickItem(1);
  assert.equal(field('text').value, draft);
  assert.equal(itemDone(1).checked, true);
  assert.equal(field('item-delete').disabled, false);
  assert.match(field('item-delete').textContent, /1/);
  // ...while ticking "done" still edits the draft and keeps the selection.
  itemDone(0).checked = true; itemDone(0).dispatch('change');
  assert.equal(field('text').value, '[x] one\n[x] two\n[ ] three\n[x] four');
  assert.equal(itemSelect(1).checked, true);
  itemDone(0).checked = false; itemDone(0).dispatch('change');
  assert.equal(field('text').value, '[ ] one\n[x] two\n[ ] three\n[x] four');
  // (b) Cancelling confirm() changes nothing, and nothing is sent to the device.
  pickItem(2);
  draft = field('text').value; discard = false; before = sent.length;
  ctx.deleteSelectedAirnoteItems();
  assert.equal(field('text').value, draft);
  assert.equal(sent.length, before);
  assert.match(prompts.at(-1), /2/);
  assert.ok(prompts.at(-1).includes('two') && prompts.at(-1).includes('three'));
  // (a) Confirming drops exactly the selected items, keeping order and done states.
  discard = true; before = sent.length;
  ctx.deleteSelectedAirnoteItems();
  assert.equal(field('text').value, '[ ] one\n[x] four');
  assert.equal(sent.length, before);
  assert.equal(notices.at(-1).error, false);
  assert.match(notices.at(-1).message, words.itemRemoved);
  assert.equal(previewRows().length, 2);
  assert.equal(itemsSelected(), 0);
  assert.equal(field('item-delete').disabled, true);
  // (c) Emptying the checklist is refused; the device reader rejects an empty list.
  pickItem(0); pickItem(1);
  draft = field('text').value; before = sent.length;
  ctx.deleteSelectedAirnoteItems();
  assert.equal(field('text').value, draft);
  assert.equal(sent.length, before);
  assert.equal(notices.at(-1).error, true);
  assert.match(notices.at(-1).message, words.itemRefusal);
  // Reordering an item keeps the selection on that item, not on its old position.
  pickItem(1, false);
  const destination = previewRows()[0].querySelectorAll('select')[0];
  destination.value = '1'; destination.dispatch('change');
  assert.equal(field('text').value, '[x] four\n[ ] one');
  assert.equal(itemSelect(1).checked, true);
  assert.equal(itemSelect(0).checked, false);
  // Typing in the textarea moves items, so the stored positions must be dropped.
  field('text').value = '[ ] alpha\n[ ] beta'; field('text').dispatch('input');
  assert.equal(itemsSelected(), 0);
  assert.equal(field('item-delete').disabled, true);
  // A busy page cannot delete items.
  pickItem(0); ctx.airnoteLock(true);
  assert.equal(itemSelect(0).disabled, true);
  assert.equal(field('item-delete').disabled, true);
  draft = field('text').value;
  ctx.deleteSelectedAirnoteItems();
  assert.equal(field('text').value, draft);
  ctx.airnoteLock(false);
  // (f) Loading another note clears the selection, even for another to-do note.
  pickItem(0);
  assert.equal(field('item-delete').disabled, false);
  rows()[1].querySelector('.airnote-pick').dispatch('click');
  await ctx.openAirnote();
  assert.equal(field('type').value, 'todo');
  assert.equal(previewRows().length, 4);
  assert.equal(itemsSelected(), 0);
  assert.equal(field('item-delete').disabled, true);
  // A new note, and switching the type away from to-do, clear it too.
  pickItem(0); ctx.newAirnote();
  assert.equal(field('type').value, 'text');
  assert.equal(field('item-delete').disabled, true);
  assert.equal(field('item-delete').hidden, true);
  field('type').value = 'todo'; field('text').value = '[ ] one\n[ ] two'; ctx.airnotePreview();
  pickItem(0);
  assert.equal(field('item-delete').disabled, false);
  field('type').value = 'text'; ctx.airnotePreview();
  field('type').value = 'todo'; ctx.airnotePreview();
  assert.equal(itemsSelected(), 0);
  assert.equal(field('item-delete').disabled, true);
}
console.log(JSON.stringify({ok: true, locales: ['en', 'zh-CN', 'zh-Hant']}));
