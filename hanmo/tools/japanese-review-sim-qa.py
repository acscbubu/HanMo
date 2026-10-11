"""Real simulator + real Review/Sentence + real synthetic SD only."""
from pathlib import Path
from datetime import datetime,timezone,date
from concurrent.futures import ThreadPoolExecutor
import argparse,hashlib,json,os,struct,subprocess,time,zlib,threading,shutil
from PIL import Image,ImageChops
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'build/japanese-review-sim-qa'
PROGRAM=ROOT/'.pio/build/simulator_x4pro_video/program'
CLOCK=BASE/'clock.so'
P='japanese-review-v1.bin'
DAY=(date(2026,10,8)-date(1970,1,1)).days
EPOCH=int(datetime(2026,10,8,tzinfo=timezone.utc).timestamp())
parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['smoke','locales','faults']);parser.add_argument('tag');parser.add_argument('--locale-tag',default='locales-second');args=parser.parse_args()
OUT=BASE/args.tag;assert not OUT.exists();OUT.mkdir(parents=True)

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def snapshot(path):
 b=path.read_bytes();assert len(b)==613 and b[:8]==b'JRP1\x01\x2d\x01\x06'
 assert zlib.crc32(b[:-4])==struct.unpack('<I',b[-4:])[0]
 rev,day=struct.unpack_from('<II',b,8);pos,mask=b[16:18]
 words=[]
 for i in range(45):
  ident,due,last,count,interval,rating=struct.unpack_from('<BIIHBB',b,24+13*i)
  assert ident==(i if i<44 else 45)
  words.append(dict(id=ident,due=due,last=last,reviews=count,interval=interval,rating=rating))
 return dict(revision=rev,latestDay=day,sentencePosition=pos,sentenceReadMask=mask,words=words,sha256=sha(path))
def seed(folder,locale):
 sd=folder/'sd';(sd/'.crosspoint').mkdir(parents=True)
 settings={'language':locale,'onboardingVersion':1,'uiTheme':4,'homeLabel':'HanMo','homeShortcut1':4,'homeShortcut2':9,'homeShortcut3':9,'homeShortcut4':9,'homeShortcut5':9,'homeShortcut6':9,'sleepTimeout':0,'hiddenAppsMask':0,'clockUtcOffsetQ':92,'clockAutoSync':0}
 (sd/'.crosspoint/settings.json').write_text(json.dumps(settings,ensure_ascii=False))
 (sd/'.crosspoint/state.json').write_text(json.dumps({'showBootScreen':False}))
 # Canary files are synthetic, never from the user's device.
 for r,data in [('.crosspoint/kana-practice-v1.bin',b'KEEP-SYNTHETIC-KANA'),('AirNote/do-not-change.txt',b'KEEP-SYNTHETIC-NOTE'),('AirPhoto/do-not-change.bmp',b'KEEP-SYNTHETIC-PHOTO')]:
  q=sd/r;q.parent.mkdir(exist_ok=True);q.write_bytes(data)
 return sd

def run(folder,sd,mode,events,shots,epoch=EPOCH,timed=None):
 folder.mkdir(parents=True,exist_ok=True)
 clock=folder/'epoch.txt';clock.write_text(str(epoch))
 allEvents=[(2600,'TAP:240,765'),(5300,'TAP:100,140'),(8500,'TAP:100,'+('530' if mode=='review' else '472'))]+events
 allShots=[(7000,'categories'),(10200,'opened')]+shots
 end=max([t for t,_ in allEvents+allShots])+2200;allEvents.append((end,'QUIT'))
 env=os.environ.copy();env.update(CROSSPOINT_SIM_SD=str(sd),SDL_AUDIODRIVER='dummy',SDL_RENDER_DRIVER='software',LD_PRELOAD=str(CLOCK),HANMO_QA_EPOCH_FILE=str(clock),CROSSPOINT_SIM_INPUT_SCRIPT=';'.join(f'{t}:{a}' for t,a in allEvents),CROSSPOINT_SIM_SCREENSHOTS=';'.join(f'{t}:{folder}/{n}.bmp' for t,n in allShots))
 def timer():
  if timed:
   time.sleep(timed[0]);timed[1](clock)
 thread=threading.Thread(target=timer);thread.start()
 with (folder/'run.log').open('x') as log:subprocess.run(['xvfb-run','-a',str(PROGRAM)],cwd=folder,env=env,stdout=log,stderr=log,timeout=end/1000+30,check=True)
 thread.join()
 activity='JapaneseReview' if mode=='review' else 'JapaneseSentences'
 assert activity in (folder/'run.log').read_text(),activity
 frames=[]
 for _,name in allShots:
  im=Image.open(folder/(name+'.bmp'));assert im.size==(480,800);im.save(folder/(name+'.png'))
  frames.append(dict(name=name,path=str(folder/(name+'.png')),sha256=sha(folder/(name+'.png'))))
 contact=Image.new('RGB',(960,800*((len(frames)+1)//2)),'white')
 for i,r in enumerate(frames):contact.paste(Image.open(r['path']).convert('RGB'),((i%2)*480,(i//2)*800))
 contact.save(folder/'contact.png')
 record=dict(mode=mode,directory=str(folder),frames=frames,contact=str(folder/'contact.png'),actualActivity=True)
 (folder/'result.json').write_text(json.dumps(record,indent=2));return record

def locale_case(locale,full=False):
 folder=OUT/locale;sd=seed(folder,locale);file=sd/'.crosspoint'/P
 canaries={str(p.relative_to(sd)):sha(p) for p in sd.rglob('*') if p.is_file() and 'do-not-change' in p.name or p.is_file() and p.name=='kana-practice-v1.bin'}
 events=[(11500,'TAP:350,765'),(14500,'TAP:350,765'),(17500,'TAP:85,702'),(20500,'TAP:350,765'),(23500,'TAP:240,702'),(26500,'TAP:350,765'),(29500,'TAP:390,702')]
 shots=[(13000,'front-01'),(16000,'reveal-01'),(19000,'front-02'),(31000,'rated-three')]
 if full:
  at=32000
  for i in range(42):events.extend([(at,'TAP:350,765'),(at+1100,'TAP:390,702')]);at+=2300
  shots.append((at+300,'complete'))
 results=[run(folder/'review-save',sd,'review',events,shots)]
 state=snapshot(file);expected=45 if full else 3
 assert state['revision']==expected and sum(w['reviews'] for w in state['words'])==expected,state
 assert [w['interval'] for w in state['words'][:3]]==[1,3,7]
 for r in canaries:assert sha(sd/r)==canaries[r]
 saved=sha(file)
 results.append(run(folder/'review-restart',sd,'review',[(11500,'TAP:350,765')],[(13300,'resumed')]))
 assert sha(file)==saved,'Opening/resuming must not write or rescore'
 if not full:
  def body(q):return Image.open(q).convert('L').crop((0,170,480,560)).tobytes()
  assert body(folder/'review-save/front-01.png')!=body(folder/'review-restart/resumed.png')
 results.append(run(folder/'sentence-save',sd,'sentences',[(11500,'TAP:350,684'),(14500,'TAP:350,752'),(17500,'TAP:350,684')],[(13000,'reveal-01'),(16000,'front-02'),(19000,'reveal-02')]))
 sentence=snapshot(file);assert sentence['sentencePosition']==1 and sentence['sentenceReadMask']==3
 assert sentence['words']==state['words'] and sentence['latestDay']==state['latestDay']
 saved=sha(file)
 results.append(run(folder/'sentence-restart',sd,'sentences',[],[(12000,'resumed-hidden')]))
 assert sha(file)==saved,'Sentence restart must not write'
 assert Image.open(folder/'sentence-save/front-02.png').crop((0,100,480,440)).tobytes()==Image.open(folder/'sentence-restart/resumed-hidden.png').crop((0,100,480,440)).tobytes()
 if full:
  shutil.copy2(file,folder/'same-day-committed.bin')
  results.append(run(folder/'review-next-day',sd,'review',[(11500,'TAP:350,765'),(14500,'TAP:350,765'),(17500,'TAP:390,702')],[(13000,'due-first'),(16000,'due-reveal'),(19000,'done')],epoch=EPOCH+86400))
  tomorrow=snapshot(file);assert tomorrow['revision']==sentence['revision']+1
  assert tomorrow['words'][0]['reviews']==2 and tomorrow['words'][0]['interval']==3
  assert tomorrow['words'][1:]==sentence['words'][1:] and tomorrow['sentenceReadMask']==3
 for r in canaries:assert sha(sd/r)==canaries[r]
 return dict(locale=locale,results=results,afterReview=state,afterSentence=sentence,full45=full,canariesUnchanged=True)

def fault_case(case,source):
 folder=OUT/case;sd=seed(folder,'ZH_TW');f=sd/'.crosspoint'/P;shutil.copy2(source,f);before=f.read_bytes();ep=EPOCH;timed=None
 events=[(11500,'TAP:350,765')];shots=[(13500,'after-start')]
 if case=='backwards':ep=EPOCH-86400
 elif case=='unset':ep=0
 elif case=='corrupt':f.write_bytes(before[:-1]+bytes([before[-1]^1]));before=f.read_bytes()
 elif case=='future-format':f.write_bytes(before[:4]+b'\x02'+before[5:]);before=f.read_bytes()
 elif case=='part-not-committed':(f.parent/(P+'.part')).write_bytes(before)
 elif case=='recover-backup':f.rename(f.parent/(P+'.bak'))
 elif case=='write-fail-retry':
  # Advance to next day to have one real eligible due word in the full45 fixture.
  ep=EPOCH+86400;part=f.parent/(P+'.part');part.mkdir();(part/'blocker').write_bytes(b'SYNTHETIC BLOCKER')
  events.extend([(14500,'TAP:350,765'),(17500,'TAP:390,702'),(23000,'TAP:350,765')]);shots.extend([(19000,'save-failed'),(24800,'retry-saved')])
  timed=(21,lambda clock:shutil.rmtree(part))
 elif case=='mid-session-date':
  ep=EPOCH+86400;events.extend([(14500,'TAP:350,765'),(20000,'TAP:390,702')]);shots.extend([(16000,'revealed'),(21800,'date-blocked')]);timed=(18,lambda clock:clock.write_text(str(EPOCH+2*86400)))
 else:raise AssertionError(case)
 r=run(folder/'flow',sd,'review',events,shots,epoch=ep,timed=timed)
 if case=='write-fail-retry':
  s=snapshot(f);old=snapshot(source);assert s['revision']==old['revision']+1 and s['words'][0]['reviews']==2
 else:assert f.read_bytes()==before,case
 return dict(case=case,result=r,protectedCommittedBytes=True)

if args.phase=='smoke':
 folder=OUT/'ZH_TW';sd=seed(folder,'ZH_TW')
 results=[run(folder/'flow',sd,'review',[(11500,'TAP:350,765'),(14500,'TAP:350,765'),(17500,'TAP:390,702')],[(13000,'front'),(16000,'reveal'),(19300,'saved')])]
 assert snapshot(sd/'.crosspoint'/P)['revision']==1
elif args.phase=='locales':
 with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(lambda l:locale_case(l,l=='ZH_TW'),['ZH_TW','ZH_CN','EN']))
else:
 # Current locale SD contains tomorrow; use retained same-day committed bytes.
 source=BASE/args.locale_tag/'ZH_TW/same-day-committed.bin';assert source.is_file()
 with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(lambda c:fault_case(c,source),['backwards','unset','corrupt','future-format','part-not-committed','recover-backup','write-fail-retry','mid-session-date']))
def collect(item):
 if isinstance(item,dict):
  if 'frames' in item:return len(item['frames'])
  return sum(collect(v) for v in item.values())
 if isinstance(item,list):return sum(map(collect,item))
 return 0
summary=dict(phase=args.phase,results=results,frameCount=collect(results),hardwareValidated=False,realSimulator=True,syntheticSdOnly=True)
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(phase=args.phase,frameCount=summary['frameCount'],directory=str(OUT))),flush=True)
