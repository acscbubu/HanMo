"""Real simulator category/dialogue + synthetic SD acceptance, no device IO."""
from pathlib import Path
from datetime import date
from concurrent.futures import ThreadPoolExecutor
import argparse,hashlib,json,os,struct,subprocess,time,zlib,threading,shutil
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'build/japanese-topics30-sim-qa'
PROGRAM=ROOT/'.pio/build/simulator_x4pro_video/program'
CLOCK=BASE/'clock.so';V1='japanese-review-v1.bin';V2='japanese-sentences-v2.bin';V4='japanese-sentences-v4.bin';COUNTS=[30]*9;FIRST=[30*i for i in range(9)]
EPOCH=1791417600
parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['smoke','locales','faults','review','migrations','themes']);parser.add_argument('tag');parser.add_argument('--completed-course',default='locales-first');args=parser.parse_args()
OUT=BASE/args.tag;assert not OUT.exists();OUT.mkdir(parents=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def legacy():
 b=bytearray(613);b[:8]=b'JRP1\x01\x2d\x01\x06';struct.pack_into('<II',b,8,5,20734);b[16:18]=bytes([3,5]);b[18:24]=bytes(range(6))
 for i in range(45):struct.pack_into('<BIIHBB',b,24+13*i,i if i<44 else 45,20741 if i==0 else 0,20734 if i==0 else 0,1 if i==0 else 0,7 if i==0 else 0,3 if i==0 else 0)
 struct.pack_into('<I',b,609,zlib.crc32(b[:609]));return bytes(b)
def seed(folder,locale,theme=4):
 sd=folder/'sd';(sd/'.crosspoint').mkdir(parents=True)
 (sd/'.crosspoint/settings.json').write_text(json.dumps({'language':locale,'onboardingVersion':1,'uiTheme':theme,'uiTextSize':0,'homeLabel':'HanMo','homeShortcut1':4,'homeShortcut2':9,'homeShortcut3':9,'homeShortcut4':9,'homeShortcut5':9,'homeShortcut6':9,'sleepTimeout':0,'hiddenAppsMask':0,'clockUtcOffsetQ':92,'clockAutoSync':0}))
 (sd/'.crosspoint/state.json').write_text(json.dumps({'showBootScreen':False}))
 (sd/'.crosspoint'/V1).write_bytes(legacy());(sd/'.crosspoint'/(V1+'.bak')).write_bytes(legacy())
 for rel in ['AirNote/do-not-change.txt','AirPhoto/do-not-change.bmp','.crosspoint/kana-practice-v1.bin']:
  p=sd/rel;p.parent.mkdir(exist_ok=True);p.write_bytes(b'SYNTHETIC CANARY '+rel.encode())
 return sd
def canaries(sd):return {str(p.relative_to(sd)):sha(p) for p in sd.rglob('*') if p.is_file() and (V1 in p.name or V2 in p.name or 'do-not-change' in p.name or p.name=='kana-practice-v1.bin')}
def legacy_v2(reads=range(54)):
 b=bytearray(104);b[:10]=b'JSP2\x02\x09\x06\x36\x07\x01';struct.pack_into('<HI',b,10,104,0x4A534401);struct.pack_into('<I',b,16,10)
 b[20]=8;b[21:30]=bytes([5,1,2,3,4,5,0,1,2]);b[37:46]=bytes(range(9));b[46:100]=bytes(range(54))
 for i in reads:b[30+i//8]|=1<<(i%8)
 struct.pack_into('<I',b,100,zlib.crc32(b[:100]));return bytes(b)
def v4_bytes(revision=10):
 b=bytearray(648);b[:8]=b'JSP4\x04\x09\x1e\x00'
 struct.pack_into('<HHHHII',b,8,270,34,3,648,0x4A534403,revision)
 b[68:77]=bytes(range(9));b[77:86]=bytes(COUNTS)
 struct.pack_into('<9H',b,86,*FIRST)
 identities=[c*6+j if j<6 else 54+c*24+j-6 for c in range(9) for j in range(30)]
 struct.pack_into('<270H',b,104,*identities)
 struct.pack_into('<I',b,644,zlib.crc32(b[:644]));return b
def snapshot(path):
 b=path.read_bytes();assert len(b)==648 and b[:8]==b'JSP4\x04\x09\x1e\x00'
 assert struct.unpack_from('<HHHHI',b,8)==(270,34,3,648,0x4A534403)
 assert b[68:77]==bytes(range(9)) and b[77:86]==bytes(COUNTS)
 assert list(struct.unpack_from('<9H',b,86))==FIRST
 expected=[c*6+j if j<6 else 54+c*24+j-6 for c in range(9) for j in range(30)]
 assert list(struct.unpack_from('<270H',b,104))==expected
 assert zlib.crc32(b[:644])==struct.unpack_from('<I',b,644)[0]
 assert b[67]&0xc0==0 and b[24]<9 and all(x<30 for x in b[25:34])
 reads=[i for i in range(270) if b[34+i//8]&(1<<(i%8))]
 return dict(revision=struct.unpack_from('<I',b,20)[0],lastCategory=b[24],positions=list(b[25:34]),readIds=reads,readPerCategory=[sum(c*30<=i<(c+1)*30 for i in reads) for c in range(9)],sha256=sha(path))
def run(folder,sd,events,shots,timed=None,mode='sentences'):
 folder.mkdir(parents=True,exist_ok=True);clock=folder/'epoch.txt';clock.write_text(str(EPOCH))
 mainTabs=json.loads((sd/'.crosspoint/settings.json').read_text()).get('uiTheme')==5
 lessonRow=('488' if mode=='review' else '432') if mainTabs else ('530' if mode=='review' else '472')
 allEvents=[(2600,'TAP:240,'+('33' if mainTabs else '765')),(5300,'TAP:100,140'),(8500,'TAP:100,'+lessonRow)]+events
 allShots=[(7000,'japanese-entry'),(10200,'opened')]+shots
 end=max(t for t,_ in allEvents+allShots)+2200;allEvents.append((end,'QUIT'))
 env=os.environ.copy();env.update(CROSSPOINT_SIM_SD=str(sd),SDL_AUDIODRIVER='dummy',SDL_RENDER_DRIVER='software',LD_PRELOAD=str(CLOCK),HANMO_QA_EPOCH_FILE=str(clock),CROSSPOINT_SIM_INPUT_SCRIPT=';'.join(f'{t}:{a}' for t,a in allEvents),CROSSPOINT_SIM_SCREENSHOTS=';'.join(f'{t}:{folder}/{n}.bmp' for t,n in allShots))
 timerErrors=[]
 def timer():
  try:
   if timed:time.sleep(timed[0]);timed[1]()
  except BaseException as error:timerErrors.append(error)
 thread=threading.Thread(target=timer);thread.start()
 try:
  with (folder/'run.log').open('x') as log:subprocess.run(['xvfb-run','-a',str(PROGRAM)],cwd=folder,env=env,stdout=log,stderr=log,timeout=end/1000+30,check=True)
 finally:thread.join()
 assert not timerErrors,timerErrors
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
  for card in range(COUNTS[cat]):
   events.append((at,'TAP:350,684'));at+=1000
   if cat==0 or card in (0,6,14,29):shots.append((at,f'cat-{cat}-reveal-{card+1:02}'));at+=500
   if card<COUNTS[cat]-1:events.append((at,'TAP:350,752'));at+=1000
  events.append((at,'TAP:100,684'));at+=1000
  shots.append((at,f'cat-{cat}-picker'));at+=500
 results=[run(folder/'all270',sd,events,shots)]
 final=snapshot(sd/'.crosspoint'/V4)
 assert final['positions']==[29]*9 and final['readIds']==list(range(270)) and final['readPerCategory']==[30]*9 and final['lastCategory']==8 and final['revision']==539,final
 assert canaries(sd)==protected
 saved=sha(sd/'.crosspoint'/V4)
 results.append(run(folder/'restart',sd,[(11500,'TAP:240,355')],[(13000,'emergency-30-resumed-hidden')]))
 assert sha(sd/'.crosspoint'/V4)==saved and canaries(sd)==protected
 return dict(locale=locale,results=results,state=final,all270Read=True,legacy45WordBytesUnchanged=True,restartNoWrite=True)
def fault_case(case):
 folder=OUT/case;sd=seed(folder,'ZH_TW');protected=canaries(sd);f=sd/'.crosspoint'/V4
 events=[(11500,'TAP:240,211'),(14500,'TAP:350,684')];shots=[(13000,'daily-front'),(16000,'daily-reveal')];timed=None
 if case in ('corrupt','future','part-only','backup-recovery'):
  b=v4_bytes()
  if case=='corrupt':b[644]^=1
  if case=='future':b[4]=5;struct.pack_into('<I',b,644,zlib.crc32(b[:644]))
  target=f if case in ('corrupt','future') else f.with_name(V4+('.part' if case=='part-only' else '.bak'));target.write_bytes(b);original=bytes(b)
 elif case=='failed-save-retry':
  part=f.with_name(V4+'.part');part.mkdir();(part/'blocker').write_bytes(b'SYNTHETIC BLOCKER')
  events.extend([(18500,'TAP:350,752'),(21500,'TAP:350,684'),(26000,'TAP:100,612')]);shots.extend([(20000,'pending-next'),(23000,'pending-two'),(28000,'retry-saved')])
  def repair_without_autosave():
   shutil.rmtree(part)
   time.sleep(1)
   assert not f.exists(),'Must remain unsaved after repair until explicit Retry'
  timed=(24,repair_without_autosave)
 else:raise AssertionError(case)
 result=run(folder/'flow',sd,events,shots,timed)
 assert canaries(sd)==protected
 if case in ('corrupt','future'):
  assert f.read_bytes()==original
  assert not f.with_name(V4+'.part').exists() and not f.with_name(V4+'.bak').exists()
  state=None
 else:
  state=snapshot(f);assert state['lastCategory']==1,state
  if case=='failed-save-retry':
   assert state['readIds']==[0,2,30,31] and state['positions']==[3,1,0,0,0,0,0,0,0] and state['revision']==1,state
   assert not f.with_name(V4+'.bak').exists()
  elif case=='part-only':
   assert state['revision']==2 and state['readIds']==[0,2,30] and state['positions']==[3,0,0,0,0,0,0,0,0],state
  else:
   assert state['revision']==12 and state['readIds']==[30] and state['positions']==[0]*9,state
  assert not f.with_name(V4+'.bak').exists(),'Successful exact-read commit cleans own backup'
  assert not f.with_name(V4+'.part').exists()
 return dict(case=case,results=[result],state=state,legacy45WordBytesUnchanged=True)
def migration_case(case):
 folder=OUT/case;sd=seed(folder,'ZH_TW');old=sd/'.crosspoint'/V2
 old_reads=list(range(54)) if case in ('all54','backup54') else [0,2,6,18,35,53]
 data=bytearray(legacy_v2(old_reads))
 if case=='corrupt-v2':data[100]^=1
 if case=='future-v2':data[4]=3;struct.pack_into('<I',data,100,zlib.crc32(data[:100]))
 target=old.with_name(V2+'.bak') if case=='backup54' else old
 target.write_bytes(data);protected=canaries(sd)
 if case in ('corrupt-v2','future-v2'):
  events=[(11500,'TAP:240,139'),(14500,'TAP:350,684'),(17500,'TAP:100,612')]
  shots=[(13000,'blocked-front'),(16000,'blocked-pending'),(19000,'still-blocked')]
 else:
  # A valid legacy import resumes picker selection8. Use its actual Prev
  # control8times to reach Basic, rather than tapping Hotel on page2.
  events=[(11500+1000*i,'TAP:240,754') for i in range(8)]
  events.extend([(19500,'TAP:240,139'),(22500,'TAP:350,752'),(25500,'TAP:350,684')])
  shots=[(21000,'legacy-basic06-hidden'),(24000,'new-basic07-hidden'),(26500,'new-basic07-reveal')];at=27500
  for _ in range(23):events.append((at,'TAP:350,752'));at+=1000
  events.append((at,'TAP:350,684'));shots.append((at+1200,'new-basic30-reveal'))
 result=run(folder/'flow',sd,events,shots)
 assert canaries(sd)==protected
 if case in ('corrupt-v2','future-v2'):
  assert not (sd/'.crosspoint'/V4).exists();state=None
 else:
  state=snapshot(sd/'.crosspoint'/V4)
  expected=sorted([i//6*30+i%6 for i in old_reads]+[6,29])
  assert state['readIds']==expected and state['positions']==[29,1,2,3,4,5,0,1,2] and state['lastCategory']==0 and state['revision']==37,state
  saved=sha(sd/'.crosspoint'/V4)
  restart=run(folder/'restart',sd,[(11500,'TAP:240,139')],[(13000,'basic30-resumed-hidden')])
  assert sha(sd/'.crosspoint'/V4)==saved and canaries(sd)==protected
  return dict(case=case,results=[result,restart],state=state,legacyReadOnly=True)
 return dict(case=case,results=[result],state=state,legacyReadOnly=True)
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
 s=snapshot(sd/'.crosspoint'/V4);assert s['positions'][2]==1 and s['lastCategory']==2 and s['readIds']==[0,2,60,61],s
elif args.phase=='locales':
 with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(locale_case,['ZH_TW','ZH_CN','EN']))
elif args.phase=='migrations':
 with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(migration_case,['all54','mixed54','backup54','corrupt-v2','future-v2']))
elif args.phase=='review':
 sd=seed(OUT/'ZH_TW','ZH_TW');f=sd/'.crosspoint'/V4
 shutil.copy2(BASE/args.completed_course/'ZH_TW/sd/.crosspoint'/V4,f);saved=sha(f)
 before=(sd/'.crosspoint'/V1).read_bytes();protected={k:v for k,v in canaries(sd).items() if V1 not in k}
 results=[run(OUT/'ZH_TW/review',sd,[(11500,'TAP:350,765'),(14500,'TAP:350,765'),(17500,'TAP:390,702')],[(13000,'review-front'),(16000,'review-reveal'),(19000,'review-rated')],mode='review')]
 after=(sd/'.crosspoint'/V1).read_bytes()
 assert len(after)==613 and zlib.crc32(after[:-4])==struct.unpack_from('<I',after,609)[0]
 expected=bytearray(before);today=EPOCH//86400
 struct.pack_into('<I',expected,8,6)
 struct.pack_into('<BIIHBB',expected,37,1,today+7,today,1,7,3)
 struct.pack_into('<I',expected,609,zlib.crc32(expected[:609]))
 assert after==expected,'Only word1 Known may change; all44 other words/sentence fields exact'
 current={k:v for k,v in canaries(sd).items() if V1 not in k};assert current==protected
 # Review owns its own transaction paths; real store removes its old backup.
 assert not (sd/'.crosspoint'/(V1+'.bak')).exists() and not (sd/'.crosspoint'/(V1+'.part')).exists()
 assert sha(f)==saved,'Review must not write v4'
elif args.phase=='themes':
 def default_theme(locale):
  folder=OUT/locale;sd=seed(folder,locale,5);before=canaries(sd)
  # Actual INX body starts64px; SMALL_FONT_ID height22 gives60px buttons
  # plus8px gap. Restaurant center234, not Lyra's283 (Shopping in INX).
  flow=run(folder/'inx',sd,[(11500,'TAP:240,234'),(14500,'TAP:350,684'),(17500,'TAP:350,752'),(20500,'TAP:350,684'),(23500,'TAP:350,612'),(26500,'TAP:100,684')],[(13000,'restaurant-front-01'),(16000,'restaurant-reveal-01'),(19000,'restaurant-front-02'),(22000,'restaurant-reveal-02'),(25000,'details'),(28000,'back-picker')])
  state=snapshot(sd/'.crosspoint'/V4)
  assert state['positions'][2]==1 and state['lastCategory']==2 and state['readIds']==[0,2,60,61],state
  assert canaries(sd)==before
  return dict(locale=locale,theme='INX',uiTextSize=0,results=[flow],state=state,canariesUnchanged=True)
 with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(default_theme,['ZH_TW','ZH_CN','EN']))
else:
 with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(fault_case,['corrupt','future','part-only','backup-recovery','failed-save-retry']))
flows=collect(results)
summary=dict(phase=args.phase,results=results,flows=len(flows),frameCount=sum(len(r['frames']) for r in flows),realSimulator=True,syntheticSdOnly=True,hardwareValidated=False)
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!='results'},indent=2))
