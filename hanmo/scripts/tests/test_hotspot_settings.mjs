import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

let checks = 0;
for (const locale of ['en', 'zh-CN']) {
  const html = fs.readFileSync(new URL(`../../src/network/html/${locale}/SettingsPage.html`, import.meta.url), 'utf8');
  let script = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)].map(m => m[1]).join('\n');
  script = script.replace(/\(async \(\) => \{\s*await loadSettings\(\);[\s\S]*?\}\)\(\);/, '');
  const elements = new Map();
  const el = id => {
    if (!elements.has(id)) elements.set(id, {value: '', innerHTML: '', textContent: '', disabled: false, children: [], style: {}, classList: {toggle(){},add(){},remove(){}}});
    return elements.get(id);
  };
  let requests = [];
  let failSave = false;
  const field = {key:'hotspotName', name: locale === 'en' ? 'Hotspot name' : '热点名称', category:'System', type:'string', value:'XTEINK-X4-PRO', maxBytes:32, defaultValue:'XTEINK-X4-PRO', description:'Restart hotspot after saving. <safe>', validationError:'Invalid hotspot name'};
  const context = vm.createContext({TextEncoder, console:{error(){}}, setTimeout(){return 0;}, clearTimeout(){}, location:{hash:''}, history:{replaceState(){}}, window:{addEventListener(){}}, document:{getElementById:el}, __field:field, fetch:async (url, opts) => {
    if (!opts) return {ok:true,json:async()=>[field]};
    requests.push({url,body:JSON.parse(opts.body)});
    return {ok:!failSave,text:async()=> failSave ? 'Could not save settings' : 'Applied 1 setting(s)'};
  }});
  vm.runInContext(script, context, {filename:locale+'/SettingsPage.html'});
  await vm.runInContext('loadSettings()', context);
  assert.match(el('settings-panes').innerHTML,/Restart hotspot after saving\. &lt;safe&gt;/); checks++;
  for (const [name,accepted] of [['Angus Reader',true],['x'.repeat(32),true],['x'.repeat(33),false],['熱'.repeat(10)+'ab',true],['熱'.repeat(11),false],['   ',false],['bad\nname',false],['a\0b',false],['name;with:"quotes"\\',true],['',true]]) {
    requests=[];failSave=false;
    vm.runInContext('allSettings=[__field];originalValues={hotspotName:"XTEINK-X4-PRO"}',context);
    el('setting-hotspotName').value=name;
    await vm.runInContext('saveSettings()', context);
    assert.equal(requests.length,accepted?1:0,locale+':'+JSON.stringify(name));
    if(accepted) {
      assert.equal(requests[0].body.hotspotName,name);
      const saved=vm.runInContext('originalValues.hotspotName',context);
      assert.equal(saved,name||'XTEINK-X4-PRO');
      if(!name)assert.equal(el('setting-hotspotName').value,'XTEINK-X4-PRO');
    } else assert.equal(el('saveBtn').disabled,false);
    checks++;
  }
  failSave=true;requests=[];
  vm.runInContext('originalValues={hotspotName:"XTEINK-X4-PRO"}',context);
  el('setting-hotspotName').value='Retry Reader';
  await vm.runInContext('saveSettings()',context);
  assert.equal(vm.runInContext('originalValues.hotspotName',context),'XTEINK-X4-PRO');
  assert.equal(el('saveBtn').disabled,false);checks++;
}
console.log(JSON.stringify({ok:true,locales:2,checks}));
