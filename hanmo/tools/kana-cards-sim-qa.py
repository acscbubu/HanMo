import os, subprocess, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
lang=sys.argv[1] if len(sys.argv)>1 else 'zh'
mode=sys.argv[2] if len(sys.argv)>2 else 'flow'
out=ROOT/'build/kana-cards-qa'/(lang if mode=='flow' else lang+'-'+mode)
sd=out/'sd';(sd/'.crosspoint').mkdir(parents=True,exist_ok=True)
settings={'language':'ZH_TW' if lang=='zh' else 'EN','onboardingVersion':1,'uiTheme':4,
          'homeLabel':'HanMo','homeShortcut1':4,'homeShortcut2':9,'homeShortcut3':9,'homeShortcut4':9,
          'homeShortcut5':9,'homeShortcut6':9,'sleepTimeout':0,'hiddenAppsMask':0,
          'infoBoardDemo':1,'infoBoardRotate':0,'infoBoardInterval':0,'clockUtcOffsetQ':92,'wifiStatusPosition':0}
if len(sys.argv)>3:settings['uiTheme']=int(sys.argv[3])
if mode.startswith('wifi'):settings['wifiStatusPosition']=int(mode[-1])
if mode=='rotation':settings['infoBoardRotate']=1
(sd/'.crosspoint/settings.json').write_text(json.dumps(settings,ensure_ascii=False))
(sd/'.crosspoint/state.json').write_text(json.dumps({'showBootScreen':False}))
(sd/'.crosspoint/wifi.json').write_text(json.dumps({'lastConnectedSsid':'Simulator WiFi (fake)','credentials':[{'ssid':'Simulator WiFi (fake)','password':'','password_len':0,'password_crc32':0}]}))
events=[(2600,'TAP:240,765'),(5300,'TAP:100,140'),(8000,'TAP:120,192'),(10800,'TAP:130,192'),(14000,'TAP:380,766'),(17000,'TAP:240,766'),(20000,'TAP:240,766'),(23000,'TAP:120,122'),(26000,'TAP:350,122'),(29000,'TAP:350,122'),(32000,'TAP:80,766'),(35000,'TAP:130,388'),(38000,'TAP:240,766'),(41000,'TAP:80,766'),(44000,'TAP:120,134'),(48000,'QUIT')]
shots=[(7000,'japanese-folder'),(9800,'groups'),(13200,'first-card'),(16000,'second-card'),(19000,'first-again'),(22000,'last-card'),(25000,'hidden-roman'),(28000,'shuffle'),(31000,'ordered'),(34000,'back-groups'),(37000,'ka-group'),(40000,'ko-group'),(46500,'back-japanese')]
env=os.environ.copy();env.update(CROSSPOINT_SIM_SD=str(sd),SDL_AUDIODRIVER='dummy',SDL_RENDER_DRIVER='software',
 CROSSPOINT_SIM_INPUT_SCRIPT=';'.join(f'{t}:{a}' for t,a in events),
 CROSSPOINT_SIM_SCREENSHOTS=';'.join(f'{t}:{out}/{name}.bmp' for t,name in shots))
with (out/'run.log').open('w') as log:
 subprocess.run(['xvfb-run','-a',str(ROOT/'.pio/build/simulator_x4pro_video/program')],cwd=out,env=env,stdout=log,stderr=log,timeout=55)
for _,name in shots:
 subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(out/f'{name}.bmp'),str(out/f'{name}.png')],check=True)
print(out)
