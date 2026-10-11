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
  const field = {key:'versionDisplayName', name: locale === 'en' ? 'Version display name' : '版本显示名称', category:'System', type:'string', value:'HanMo', maxBytes:32, description:'Empty uses the original name. <safe>', validationError:'Invalid display name'};
  const context = vm.createContext({TextEncoder, console:{error(){}}, setTimeout(){return 0;}, clearTimeout(){}, location:{hash:''}, history:{replaceState(){}}, window:{addEventListener(){}}, document:{getElementById:el}, __field:field, fetch:async (url, opts) => {
    if (!opts) return {ok:true,json:async()=>[field]};
    requests.push({url,body:JSON.parse(opts.body)});
    return {ok:!failSave,text:async()=> failSave ? 'Could not save settings' : 'Applied 1 setting(s)'};
  }});
  vm.runInContext(script, context, {filename:locale+'/SettingsPage.html'});
  await vm.runInContext('loadSettings()', context);
  assert.match(el('settings-panes').innerHTML,/Empty uses the original name\. &lt;safe&gt;/); checks++;
  for (const [name,accepted] of [['Angus Reader',true],['x'.repeat(32),true],['x'.repeat(33),false],['熱'.repeat(10)+'ab',true],['熱'.repeat(11),false],['   ',false],['bad\nname',false],['a\0b',false],['name;with:"quotes"\\',true],['',true]]) {
    requests=[];failSave=false;
    vm.runInContext('allSettings=[__field];originalValues={versionDisplayName:"HanMo"}',context);
    el('setting-versionDisplayName').value=name;
    await vm.runInContext('saveSettings()', context);
    assert.equal(requests.length,accepted?1:0,locale+':'+JSON.stringify(name));
    if(accepted) {
      assert.equal(requests[0].body.versionDisplayName,name);
      const saved=vm.runInContext('originalValues.versionDisplayName',context);
      assert.equal(saved,name);
      if(!name)assert.equal(el('setting-versionDisplayName').value,'');
    } else assert.equal(el('saveBtn').disabled,false);
    checks++;
  }
  // Submit the name and visibility together and preserve both after failures.
  for (const visible of [true, false]) {
    requests=[];failSave=false;
    vm.runInContext('allSettings=[__field,{key:"showVersionNumber",type:"toggle"}];originalValues={versionDisplayName:"HanMo",showVersionNumber:'+(visible ? 0 : 1)+'}',context);
    el('setting-versionDisplayName').value='Angus 專用版';
    el('setting-showVersionNumber').checked=visible;
    await vm.runInContext('saveSettings()',context);
    assert.equal(requests.length,1);
    assert.equal(requests[0].body.versionDisplayName,'Angus 專用版');
    assert.equal(requests[0].body.showVersionNumber,visible?1:0);checks++;
  }
  vm.runInContext('allSettings=[__field]',context);
  failSave=true;requests=[];
  vm.runInContext('originalValues={versionDisplayName:"HanMo"}',context);
  el('setting-versionDisplayName').value='Retry Reader';
  await vm.runInContext('saveSettings()',context);
  assert.equal(vm.runInContext('originalValues.versionDisplayName',context),'HanMo');
  assert.equal(el('saveBtn').disabled,false);checks++;
}
console.log(JSON.stringify({ok:true,locales:2,checks}));
