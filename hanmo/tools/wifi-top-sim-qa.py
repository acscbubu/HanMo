import os, subprocess, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
lang=sys.argv[1] if len(sys.argv)>1 else 'zh'
mode=sys.argv[2] if len(sys.argv)>2 else 'flow'
out=ROOT/'build/wifi-top-qa'/(lang if mode=='flow' else lang+'-'+mode)
sd=out/'sd';(sd/'.crosspoint').mkdir(parents=True,exist_ok=True)
settings={'language':'ZH_TW' if lang=='zh' else 'EN','onboardingVersion':1,'uiTheme':4,
          'homeLabel':'HanMo','homeShortcut1':17,'homeShortcut2':9,'homeShortcut3':9,'homeShortcut4':9,
          'homeShortcut5':9,'homeShortcut6':9,'sleepTimeout':0,'hiddenAppsMask':0,
          'infoBoardDemo':1,'infoBoardRotate':0,'infoBoardInterval':0,'clockUtcOffsetQ':92,'wifiStatusPosition':0}
if mode.startswith('wifi'):settings['wifiStatusPosition']=int(mode[-1])
if mode=='rotation':settings['infoBoardRotate']=1
(sd/'.crosspoint/settings.json').write_text(json.dumps(settings,ensure_ascii=False))
(sd/'.crosspoint/state.json').write_text(json.dumps({'showBootScreen':False}))
(sd/'.crosspoint/wifi.json').write_text(json.dumps({'lastConnectedSsid':'Simulator WiFi (fake)','credentials':[{'ssid':'Simulator WiFi (fake)','password':'','password_len':0,'password_crc32':0}]}))
events=[(2600,'TAP:240,740'),(5800,'TAP:180,120'),(8500,'TAP:300,120'),(11200,'TAP:420,120'),
        (13800,'TAP:390,743'),(16900,'TAP:390,743'),(19500,'TAP:80,743'),(21800,'QUIT')]
shots=[(1900,'home'),(4700,'clock'),(7400,'weather'),(10100,'pc'),(12700,'work'),(15400,'settings'),(18300,'back'),(21000,'home-again')]
if mode.startswith('wifi'):
 events=[(2600,'TAP:240,740'),(6000,'QUIT')]
 shots=[(1900,'offline'),(5000,'online')]
if mode=='rotation':
 events=[(2600,'TAP:240,740'),(21000,'TAP:300,120'),(40000,'QUIT')]
 shots=[(5000,'clock'),(19500,'rotated-weather'),(23500,'manual-pc'),(38500,'still-pc')]
# Physical taps follow the content down by the reserved top status height.
events=[(t,('TAP:'+a[4:].split(',')[0]+','+str(int(a.split(',')[1])+22)) if a.startswith('TAP:') else a) for t,a in events]
env=os.environ.copy();env.update(CROSSPOINT_SIM_SD=str(sd),SDL_AUDIODRIVER='dummy',SDL_RENDER_DRIVER='software',
 CROSSPOINT_SIM_INPUT_SCRIPT=';'.join(f'{t}:{a}' for t,a in events),
 CROSSPOINT_SIM_SCREENSHOTS=';'.join(f'{t}:{out}/{name}.bmp' for t,name in shots))
with (out/'run.log').open('w') as log:
 subprocess.run(['xvfb-run','-a',str(ROOT/'.pio/build/simulator_x4pro_video/program')],cwd=out,env=env,stdout=log,stderr=log,timeout=55)
for _,name in shots:
 subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(out/f'{name}.bmp'),str(out/f'{name}.png')],check=True)
print(out)
