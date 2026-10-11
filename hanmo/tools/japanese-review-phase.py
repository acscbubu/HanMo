from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse, hashlib, json, os, subprocess, sys, time, unittest
ROOT=Path(__file__).resolve().parents[1]
E=Path('/mnt/c/Users/angus/OneDrive/文件/ChatGPT/XTEINK UI/migration/japanese-review-20261008')
parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['host','i18n','simulator','hardware']);parser.add_argument('tag');parser.add_argument('--package',action='store_true');args=parser.parse_args()
name=f'{args.mode}-{args.tag}'
assert not (E/(name+'.json')).exists(),'Never overwrite evidence'
start=time.monotonic();result={'startedAt':datetime.now(ZoneInfo('Australia/Sydney')).isoformat(),'root':str(ROOT),'mode':args.mode}
os.chdir(ROOT)
if args.mode=='host':
 sys.path.insert(0,str(ROOT));names=['test_japanese_review_core','test_japanese_review_store','test_japanese_review_ui','test_japanese_sentences_core','test_japanese_sentences_ui','test_japanese_sentence_progress','test_japanese_review_entry']
 if args.package:names.append('test_japanese_review_package')
 suite=unittest.defaultTestLoader.loadTestsFromNames(['scripts.tests.'+n for n in names])
 with (E/(name+'.log')).open('x') as log:
  r=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
 result.update(modules=names,testsRun=r.testsRun,failures=len(r.failures),errors=len(r.errors),skipped=len(r.skipped),success=r.wasSuccessful(),legacySuitesRun=False)
 code=0 if r.wasSuccessful() and not r.skipped else 1
else:
 if args.mode=='i18n':cmd=['python3','scripts/gen_i18n.py','--strip-unused']
 else:cmd=['/root/.platformio/penv/bin/pio','run','-e','simulator_x4pro_video' if args.mode=='simulator' else 'x4pro_custom']
 with (E/(name+'.log')).open('x') as log:
  p=subprocess.run(cmd,stdout=log,stderr=log)
 result.update(command=cmd,returncode=p.returncode,success=p.returncode==0);code=p.returncode
 if args.mode in ('simulator','hardware') and code==0:
  binary=ROOT/('.pio/build/simulator_x4pro_video/program' if args.mode=='simulator' else '.pio/build/x4pro_custom/firmware.bin')
  result.update(binary=str(binary),bytes=binary.stat().st_size,sha256=hashlib.sha256(binary.read_bytes()).hexdigest())
result['seconds']=round(time.monotonic()-start,3)
(E/(name+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
text=(E/(name+'.log')).read_text(errors='replace')
print('\n'.join(text.splitlines()[-14:]),flush=True)
print(json.dumps(result,ensure_ascii=False),flush=True)
raise SystemExit(code)
