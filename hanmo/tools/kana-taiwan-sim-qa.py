"""Touch-QA Japanese cards on a 480x800 isolated simulator SD (not physical hardware)."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import zlib

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--program', type=Path, default=ROOT/'.pio/build/simulator_x4pro_video/program')
parser.add_argument('--name', default='candidate')
args = parser.parse_args()
out = ROOT/'build/kana-taiwan-qa'/args.name
sd = out/'sd'
(sd/'.crosspoint').mkdir(parents=True, exist_ok=True)
settings = {'language':'ZH_TW', 'onboardingVersion':1, 'uiTheme':4, 'homeLabel':'HanMo',
            'homeShortcut1':4, 'homeShortcut2':9, 'homeShortcut3':9, 'homeShortcut4':9,
            'homeShortcut5':9, 'homeShortcut6':9, 'sleepTimeout':0, 'hiddenAppsMask':0,
            'infoBoardDemo':1, 'infoBoardRotate':0, 'infoBoardInterval':0,
            'clockUtcOffsetQ':92, 'wifiStatusPosition':0}
(sd/'.crosspoint/settings.json').write_text(json.dumps(settings,ensure_ascii=False))
(sd/'.crosspoint/state.json').write_text(json.dumps({'showBootScreen':False}))
(sd/'.crosspoint/wifi.json').write_text(json.dumps({'lastConnectedSsid':'Simulator WiFi (fake)',
 'credentials':[{'ssid':'Simulator WiFi (fake)', 'password':'','password_len':0,'password_crc32':0}]}))
events = [(2600,'TAP:240,765'), (5300,'TAP:100,140'), (8000,'TAP:100,190'),
          (10800,'TAP:120,390'), (14800,'TAP:390,765'), (19500,'TAP:110,122'),
          (23000,'TAP:120,122'), (26500,'QUIT')]
shots = [(13000,'ka-card'), (17000,'ki-card'), (21000,'ki-hidden'),
         (25000,'ki-visible')]
env = os.environ.copy()
env.update(CROSSPOINT_SIM_SD=str(sd), SDL_AUDIODRIVER='dummy', SDL_RENDER_DRIVER='software',
           CROSSPOINT_SIM_INPUT_SCRIPT=';'.join(f'{t}:{action}' for t,action in events),
           CROSSPOINT_SIM_SCREENSHOTS=';'.join(f'{t}:{out}/{name}.bmp' for t,name in shots))
with (out/'run.log').open('w') as log:
    subprocess.run(['xvfb-run','-a',str(args.program.resolve())],cwd=out,env=env,
                   stdout=log,stderr=log,timeout=45,check=True)
for _,name in shots:
    subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(out/f'{name}.bmp'),
                    str(out/f'{name}.png')],check=True)
print(json.dumps({'out': str(out), 'screenshots':[name for _,name in shots]}))
