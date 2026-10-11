"""480x800 touch QA for the revised kana stroke controls and unchanged similar course."""
from pathlib import Path
import json, os, subprocess, sys
from PIL import Image, ImageChops

root=Path(__file__).resolve().parents[1]
program=root/'.pio/build/simulator_x4pro_video/program'
assert program.is_file(), program
out=root/'build/kana-stroke-layout-qa'
mode=sys.argv[1] if len(sys.argv)>1 else 'stroke'
assert mode in ('stroke','similar')
locale=sys.argv[2] if len(sys.argv)>2 else 'ZH_TW'
assert locale in ('ZH_TW','ZH_CN','EN')
run=out/(mode+'-'+locale)
sd=run/'sd'
(sd/'.crosspoint').mkdir(parents=True,exist_ok=True)
settings={'language':locale,'onboardingVersion':1,'uiTheme':4,'homeLabel':'HanMo',
'homeShortcut1':4,'homeShortcut2':9,'homeShortcut3':9,'homeShortcut4':9,
'homeShortcut5':9,'homeShortcut6':9,'sleepTimeout':0,'hiddenAppsMask':0,
'infoBoardDemo':1,'infoBoardRotate':0,'infoBoardInterval':0,
'clockUtcOffsetQ':92,'wifiStatusPosition':0}
(sd/'.crosspoint/settings.json').write_text(json.dumps(settings,ensure_ascii=False))
(sd/'.crosspoint/state.json').write_text(json.dumps({'showBootScreen':False}))
events=[(2600,'TAP:240,765'),(5300,'TAP:100,140')]
if mode=='stroke':
 events += [(8500,'TAP:100,247'),(12700,'TAP:390,710'),(16300,'TAP:95,125'),
            (19900,'TAP:390,765'),(23500,'TAP:80,765'),(27100,'TAP:390,765'),
            (30700,'TAP:350,125'),(34300,'TAP:390,710'),(37900,'TAP:240,710'),
            (41500,'TAP:95,125'),(45100,'TAP:240,765'),(48700,'QUIT')]
 shots=[(10600,'first-stroke'),(14500,'next-stroke'),(18000,'reselect-hiragana'),
        (21500,'next-card'),(25000,'previous-card'),(28500,'card-again'),
        (32300,'katakana'),(35900,'katakana-next-stroke'),
        (39500,'restart'),(43100,'hiragana'),(46700,'returned')]
else:
 events += [(8500,'TAP:100,358'),(12400,'TAP:350,695'),(16400,'TAP:350,765'),
            (20100,'TAP:100,330'),(23900,'TAP:350,765'),(27700,'TAP:350,330'),
            (31600,'TAP:350,765'),(35100,'TAP:80,765'),(37700,'TAP:80,765'),(42500,'QUIT')]
 shots=[(10600,'compare-shi-tsu'),(14500,'compare-so-n'),(18200,'question-shi'),
        (21900,'answer-shi'),(25700,'question-so'),(29500,'answer-so'),
        (33400,'question-tsu'),(36100,'return-to-compare'),(39900,'returned')]
env=os.environ.copy()
env.update(CROSSPOINT_SIM_SD=str(sd),SDL_AUDIODRIVER='dummy',SDL_RENDER_DRIVER='software',
 CROSSPOINT_SIM_INPUT_SCRIPT=';'.join(f'{t}:{act}' for t,act in events),
 CROSSPOINT_SIM_SCREENSHOTS=';'.join(f'{t}:{run}/{name}.bmp' for t,name in shots))
with (run/'run.log').open('w') as log:
 subprocess.run(['xvfb-run','-a',str(program.resolve())],cwd=run,env=env,stdout=log,stderr=log,timeout=75,check=True)
for _,name in shots:
 pic=Image.open(run/(name+'.bmp')); assert pic.size==(480,800),(name,pic.size)
 pic.save(run/(name+'.png'))
assert not (sd/'.crosspoint/kana-practice-v1.bin').exists(),'course must not persist practice marks'
images=[Image.open(run/(name+'.png')).convert('L') for _,name in shots]
diffs=[ImageChops.difference(a,b).getbbox() is not None for a,b in zip(images,images[1:])]
if mode=='stroke':
 assert diffs == [True, False, True, True, True, True, True, True, True, True], (locale,diffs)
 assert ImageChops.difference(images[1].crop((12,154,468,620)), images[2].crop((12,154,468,620))).getbbox() is None
else:
 assert all(diffs),(mode,locale,diffs)
print(json.dumps({'mode':mode,'locale':locale,'out':str(run),'shots':[name for _,name in shots],
                 'adjacent_changes':diffs,'practice_file_created':False},ensure_ascii=False))
