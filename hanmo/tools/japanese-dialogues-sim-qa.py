"""Real simulator category/dialogue + synthetic SD acceptance, no device IO."""
from pathlib import Path
from datetime import date
from concurrent.futures import ThreadPoolExecutor
import argparse,hashlib,json,os,struct,subprocess,time,zlib,threading,shutil
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'build/japanese-dialogues-sim-qa'
PROGRAM=ROOT/'.pio/build/simulator_x4pro_video/program'
CLOCK=BASE/'clock.so';V1='japanese-review-v1.bin';V2='japanese-sentences-v2.bin'
EPOCH=1791417600
parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['smoke','locales','faults','review']);parser.add_argument('tag');args=parser.parse_args()
OUT=BASE/args.tag;assert not OUT.exists();OUT.mkdir(parents=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def legacy():
 b=bytearray(613);b[:8]=b'JRP1\x01\x2d\x01\x06';struct.pack_into('<II',b,8,5,20734);b[16:18]=bytes([3,5]);b[18:24]=bytes(range(6))
 for i in range(45):struct.pack_into('<BIIHBB',b,24+13*i,i if i<44 else 45,20741 if i==0 else 0,20734 if i==0 else 0,1 if i==0 else 0,7 if i==0 else 0,3 if i==0 else 0)
 struct.pack_into('<I',b,609,zlib.crc32(b[:609]));return bytes(b)
def seed(folder,locale):
 sd=folder/'sd';(sd/'.crosspoint').mkdir(parents=True)
 (sd/'.crosspoint/settings.json').write_text(json.dumps({'language':locale,'onboardingVersion':1,'uiTheme':4,'homeLabel':'HanMo','homeShortcut1':4,'homeShortcut2':9,'homeShortcut3':9,'homeShortcut4':9,'homeShortcut5':9,'homeShortcut6':9,'sleepTimeout':0,'hiddenAppsMask':0,'clockUtcOffsetQ':92,'clockAutoSync':0}))
 (sd/'.crosspoint/state.json').write_text(json.dumps({'showBootScreen':False}))
 (sd/'.crosspoint'/V1).write_bytes(legacy());(sd/'.crosspoint'/(V1+'.bak')).write_bytes(legacy())
 for rel in ['AirNote/do-not-change.txt','AirPhoto/do-not-change.bmp','.crosspoint/kana-practice-v1.bin']:
  p=sd/rel;p.parent.mkdir(exist_ok=True);p.write_bytes(b'SYNTHETIC CANARY '+rel.encode())
 return sd
def canaries(sd):return {str(p.relative_to(sd)):sha(p) for p in sd.rglob('*') if p.is_file() and (V1 in p.name or 'do-not-change' in p.name or p.name=='kana-practice-v1.bin')}
def snapshot(path):
 b=path.read_bytes();assert len(b)==104 and b[:10]==b'JSP2\x02\x09\x06\x36\x07\x01'
 assert struct.unpack_from('<HI',b,10)==(104,0x4A534401)
 assert b[37:46]==bytes(range(9)) and b[46:100]==bytes(range(54));assert zlib.crc32(b[:100])==struct.unpack_from('<I',b,100)[0]
 assert b[36]&0xc0==0 and b[20]<9 and all(x<6 for x in b[21:30])
 reads=[i for i in range(54) if b[30+i//8]&(1<<(i%8))]
 return dict(revision=struct.unpack_from('<I',b,16)[0],lastCategory=b[20],positions=list(b[21:30]),readIds=reads,sha256=sha(path))
def run(folder,sd,events,shots,timed=None,mode='sentences'):
 folder.mkdir(parents=True,exist_ok=True);clock=folder/'epoch.txt';clock.write_text(str(EPOCH))
 allEvents=[(2600,'TAP:240,765'),(5300,'TAP:100,140'),(8500,'TAP:100,'+('530' if mode=='review' else '472'))]+events
 allShots=[(7000,'japanese-entry'),(10200,'opened')]+shots
 end=max(t for t,_ in allEvents+allShots)+2200;allEvents.append((end,'QUIT'))
 env=os.environ.copy();env.update(CROSSPOINT_SIM_SD=str(sd),SDL_AUDIODRIVER='dummy',SDL_RENDER_DRIVER='software',LD_PRELOAD=str(CLOCK),HANMO_QA_EPOCH_FILE=str(clock),CROSSPOINT_SIM_INPUT_SCRIPT=';'.join(f'{t}:{a}' for t,a in allEvents),CROSSPOINT_SIM_SCREENSHOTS=';'.join(f'{t}:{folder}/{n}.bmp' for t,n in allShots))
 def timer():
  if timed:time.sleep(timed[0]);timed[1]()
 thread=threading.Thread(target=timer);thread.start()
 try:
  with (folder/'run.log').open('x') as log:subprocess.run(['xvfb-run','-a',str(PROGRAM)],cwd=folder,env=env,stdout=log,stderr=log,timeout=end/1000+30,check=True)
 finally:thread.join()
 assert ('JapaneseReview' if mode=='review' else 'JapaneseSentences') in (folder/'run.log').read_text()
 frames=[]
 for _,n in allShots:
  im=Image.open(folder/(n+'.bmp'));assert im.size==(480,800);im.save(folder/(n+'.png'));frames.append({'name':n,'path':str(folder/(n+'.png')),'sha256':sha(folder/(n+'.png'))})
 contact=Image.new('RGB',(960,800*((len(frames)+1)//2)),'white')
 for i,f in enumerate(frames):contact.paste(Image.open(f['path']).convert('RGB'),((i%2)*480,(i//2)*800))
 contact.save(folder/'contact.png');r=dict(directory=str(folder),frames=frames,contact=str(folder/'contact.png'),realActivity=True)
 (folder/'result.json').write_text(json.dumps(r,indent=2));return r
def locale_case(locale):
 folder=OUT/locale;sd=seed(folder,locale)
 b=bytearray(legacy());b[16:18]=b'\x00\x00';struct.pack_into('<I',b,609,zlib.crc32(b[:609]))
 for n in [V1,V1+'.bak']:(sd/'.crosspoint'/n).write_bytes(b)
 protected=canaries(sd);events=[];shots=[];at=11500
 for cat in range(9):
  if cat:events.append((at,'TAP:400,754'));at+=1000
  events.append((at,f'TAP:240,{139+(cat%5)*72}'));at+=1000
  shots.append((at,f'cat-{cat}-front-01'));at+=500
  for card in range(6):
   events.append((at,'TAP:350,684'));at+=1000
   if card in (0,5):shots.append((at,f'cat-{cat}-reveal-{card+1:02}'));at+=500
   if card<5:events.append((at,'TAP:350,752'));at+=1000
  events.append((at,'TAP:100,684'));at+=1000
  shots.append((at,f'cat-{cat}-picker'));at+=500
 results=[run(folder/'all54',sd,events,shots)]
 final=snapshot(sd/'.crosspoint'/V2)
 assert final['positions']==[5]*9 and final['readIds']==list(range(54)) and final['lastCategory']==8 and final['revision']==107,final
 assert canaries(sd)==protected
 saved=sha(sd/'.crosspoint'/V2)
 results.append(run(folder/'restart',sd,[(11500,'TAP:240,355')],[(13000,'emergency-06-resumed-hidden')]))
 assert sha(sd/'.crosspoint'/V2)==saved and canaries(sd)==protected
 return dict(locale=locale,results=results,state=final,all54Read=True,legacy45WordBytesUnchanged=True,restartNoWrite=True)
def fault_case(case):
 folder=OUT/case;sd=seed(folder,'ZH_TW');protected=canaries(sd);f=sd/'.crosspoint'/V2
 events=[(11500,'TAP:240,211'),(14500,'TAP:350,684')];shots=[(13000,'daily-front'),(16000,'daily-reveal')];timed=None
 if case in ('corrupt','future','part-only','backup-recovery'):
  b=bytearray(104);b[:10]=b'JSP2\x02\x09\x06\x36\x07\x01';struct.pack_into('<HI',b,10,104,0x4A534401);struct.pack_into('<I',b,16,10);b[37:46]=bytes(range(9));b[46:100]=bytes(range(54));struct.pack_into('<I',b,100,zlib.crc32(b[:100]))
  if case=='corrupt':b[100]^=1
  if case=='future':b[4]=3;struct.pack_into('<I',b,100,zlib.crc32(b[:100]))
  target=f if case in ('corrupt','future') else f.with_name(V2+('.part' if case=='part-only' else '.bak'));target.write_bytes(b);original=bytes(b)
 elif case=='failed-save-retry':
  part=f.with_name(V2+'.part');part.mkdir();(part/'blocker').write_bytes(b'SYNTHETIC BLOCKER')
  events.extend([(18500,'TAP:350,752'),(21500,'TAP:350,684'),(26000,'TAP:100,612')]);shots.extend([(20000,'pending-next'),(23000,'pending-two'),(28000,'retry-saved')])
  timed=(24,lambda:shutil.rmtree(part))
 else:raise AssertionError(case)
 result=run(folder/'flow',sd,events,shots,timed)
 assert canaries(sd)==protected
 if case in ('corrupt','future'):assert f.read_bytes()==original
 else:
  s=snapshot(f);assert 6 in s['readIds'],s
  if case=='failed-save-retry':assert s['readIds']==[0,2,6,7] and s['positions'][1]==1 and s['revision']==1,s
 return dict(case=case,results=[result],legacy45WordBytesUnchanged=True)
def collect(item):
 if isinstance(item,dict):
  if 'frames' in item:return [item]
  return sum((collect(v) for v in item.values()),[])
 if isinstance(item,list):return sum((collect(v) for v in item),[])
 return []
if args.phase=='smoke':
 sd=seed(OUT/'ZH_TW','ZH_TW');before=canaries(sd)
 results=[run(OUT/'ZH_TW/read',sd,[(11500,'TAP:240,283'),(14500,'TAP:350,684'),(17500,'TAP:350,752'),(20500,'TAP:350,684'),(23500,'TAP:350,612'),(26500,'TAP:100,684')],[(13000,'restaurant-front-01'),(16000,'restaurant-reveal-01'),(19000,'restaurant-front-02'),(22000,'restaurant-reveal-02'),(25000,'details'),(28000,'back-picker')])]
 assert canaries(sd)==before
 s=snapshot(sd/'.crosspoint'/V2);assert s['positions'][2]==1 and s['lastCategory']==2 and s['readIds']==[0,2,12,13],s
elif args.phase=='locales':
 with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(locale_case,['ZH_TW','ZH_CN','EN']))
elif args.phase=='review':
 sd=seed(OUT/'ZH_TW','ZH_TW');f=sd/'.crosspoint'/V2
 shutil.copy2(BASE/'locales-second/ZH_TW/sd/.crosspoint'/V2,f);saved=sha(f)
 before=(sd/'.crosspoint'/V1).read_bytes()
 results=[run(OUT/'ZH_TW/review',sd,[(11500,'TAP:350,765'),(14500,'TAP:350,765'),(17500,'TAP:390,702')],[(13000,'review-front'),(16000,'review-reveal'),(19000,'review-rated')],mode='review')]
 after=(sd/'.crosspoint'/V1).read_bytes()
 assert len(after)==613 and zlib.crc32(after[:-4])==struct.unpack_from('<I',after,609)[0]
 assert struct.unpack_from('<I',after,8)[0]==6 and after[16:18]==before[16:18]
 assert after[24:37]==before[24:37] and struct.unpack_from('<BIIHBB',after,37)[3:]==(1,7,3)
 assert sha(f)==saved,'Review must not write v2'
else:
 with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(fault_case,['corrupt','future','part-only','backup-recovery','failed-save-retry']))
flows=collect(results)
summary=dict(phase=args.phase,results=results,flows=len(flows),frameCount=sum(len(r['frames']) for r in flows),realSimulator=True,syntheticSdOnly=True,hardwareValidated=False)
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!='results'},indent=2))
