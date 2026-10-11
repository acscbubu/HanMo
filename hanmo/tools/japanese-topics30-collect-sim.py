"""Collect only completed real simulator runs; no guessed success/counts."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,hashlib,json,shutil
R=Path(__file__).resolve().parents[1]
BASE=R/'build/japanese-topics30-sim-qa'
E=Path('/mnt/c/Users/angus/OneDrive/文件/ChatGPT/XTEINK UI/migration/japanese-topics30-20261009')
p=argparse.ArgumentParser()
for phase in ('smoke','locales','faults','review','migrations','themes'):p.add_argument('--'+phase,default=phase+'-first')
a=p.parse_args()
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def flows(item):
    if isinstance(item,dict):
        if 'frames' in item:return [item]
        return [r for v in item.values() for r in flows(v)]
    if isinstance(item,list):return [r for v in item for r in flows(v)]
    return []
assert not (E/'simulator-final.json').exists()
assert not (E/'simulator').exists()
phases={}; records=[]; locales=[]
for phase in ('smoke','locales','faults','review','migrations','themes'):
    tag=getattr(a,phase);path=BASE/tag/'summary.json';data=json.loads(path.read_text())
    assert data['phase']==phase and data['realSimulator'] and data['syntheticSdOnly'] and not data['hardwareValidated']
    rows=flows(data['results']);assert rows and len(rows)==data['flows']
    assert sum(len(r['frames']) for r in rows)==data['frameCount']
    phases[phase]=dict(tag=tag,flows=data['flows'],frames=data['frameCount'],summarySha256=sha(path))
    records.extend(rows)
    if phase=='locales':locales=data['results']
assert len(records)==24 and len({r['directory'] for r in records})==24
assert [r['locale'] for r in locales]==['ZH_TW','ZH_CN','EN']
for row in locales:
    assert row['all270Read'] and row['legacy45WordBytesUnchanged'] and row['restartNoWrite']
    assert row['state']['readIds']==list(range(270)) and row['state']['positions']==[29]*9 and row['state']['readPerCategory']==[30]*9
allframes=[f for r in records for f in r['frames']]
assert len(allframes)>161 and len(allframes)==len({f['path'] for f in allframes})
for f in allframes:assert sha(Path(f['path']))==f['sha256']
(E/'simulator').mkdir()
for record in phases.values():shutil.copytree(BASE/record['tag'],E/'simulator'/record['tag'])
for f in allframes:assert sha(E/'simulator'/Path(f['path']).relative_to(BASE))==f['sha256']
result=dict(verifiedAt=datetime.now(ZoneInfo('Australia/Sydney')).isoformat(),newTopics30Flows=len(records),frameCount=len(allframes),phases=phases,locales=[r['locale'] for r in locales],completeLocales=locales,records=records,realSimulator=True,syntheticSdOnly=True,hardwareValidated=False,hardwareFlashed=False,published=False,legacySuitesRun=False,simulatorReadyAlwaysTrue=True)
with (E/'simulator-final.json').open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('completeLocales','records')},indent=2),flush=True)
