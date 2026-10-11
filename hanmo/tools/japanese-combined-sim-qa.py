import os, subprocess, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
lang=sys.argv[1] if len(sys.argv)>1 else 'zh'
mode=sys.argv[2] if len(sys.argv)>2 else 'flow'
out=ROOT/'build/japanese-combined-qa'/(lang if mode=='flow' else lang+'-'+mode)
sd=out/'sd';(sd/'.crosspoint').mkdir(parents=True,exist_ok=True)
settings={'language':'ZH_TW' if lang=='zh' else 'EN','onboardingVersion':1,'uiTheme':4,
          'homeLabel':'HanMo','homeShortcut1':4,'homeShortcut2':9,'homeShortcut3':9,'homeShortcut4':9,
          'homeShortcut5':9,'homeShortcut6':9,'sleepTimeout':0,'hiddenAppsMask':0,
          'infoBoardDemo':1,'infoBoardRotate':0,'infoBoardInterval':0,'clockUtcOffsetQ':92,'wifiStatusPosition':0}
if mode.startswith('wifi'):settings['wifiStatusPosition']=int(mode[-1])
if mode=='rotation':settings['infoBoardRotate']=1
(sd/'.crosspoint/settings.json').write_text(json.dumps(settings,ensure_ascii=False))
(sd/'.crosspoint/state.json').write_text(json.dumps({'showBootScreen':False}))
(sd/'.crosspoint/wifi.json').write_text(json.dumps({'lastConnectedSsid':'Simulator WiFi (fake)','credentials':[{'ssid':'Simulator WiFi (fake)','password':'','password_len':0,'password_crc32':0}]}))
events=[(2600,"TAP:240,740"),(5700,"TAP:100,140")]
shots=[(4500,"apps"),(7600,"categories")]
for i in range(7):
 at=8500+i*4000
 events.extend([(at,f"TAP:200,{192+i*56}"),(at+2400,"TAP:120,140")])
 shots.append((at+1400,f"category-{i+1}"))
events.extend([(36900,"TAP:120,140"),(41000,"QUIT")])
shots.extend([(36200,"categories-return"),(39500,"apps-return")])
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
