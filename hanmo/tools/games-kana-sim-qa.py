"""Run the merged binary through actual Home -> Games -> one of six boards."""
from pathlib import Path
import hashlib, json, os, re, shutil, subprocess, sys
from PIL import Image, ImageChops

ROOT=Path(__file__).resolve().parents[1]
PROGRAM=ROOT/'.pio/build/simulator_x4pro_video/program'
CASES=json.loads((ROOT/'tools/games-kana-simulator-cases.json').read_text(encoding='utf-8'))
GAME=sys.argv[1] if len(sys.argv)>1 else 'reversi'
LOCALE=sys.argv[2] if len(sys.argv)>2 else 'ZH_TW'
assert GAME in CASES and LOCALE in ('ZH_TW','ZH_CN','EN')
assert PROGRAM.is_file(),PROGRAM
run=ROOT/'build/games-kana-integration/simulator'/GAME/LOCALE
if run.exists():
    assert (ROOT/'build/games-kana-integration/simulator') in run.parents
    shutil.rmtree(run)
sd=run/'sd';crosspoint=sd/'.crosspoint';crosspoint.mkdir(parents=True)
settings={'language':LOCALE,'onboardingVersion':1,'uiTheme':4,
          'homeLabel':'HanMo','homeShortcut1':15,'homeShortcut2':4,
          'homeShortcut3':9,'homeShortcut4':9,'homeShortcut5':9,'homeShortcut6':9,
          'sleepTimeout':0,'hiddenAppsMask':0,'infoBoardDemo':1,'infoBoardRotate':0,
          'infoBoardInterval':0,'clockUtcOffsetQ':92,'wifiStatusPosition':0}
(crosspoint/'settings.json').write_text(json.dumps(settings,ensure_ascii=False))
(crosspoint/'state.json').write_text(json.dumps({'showBootScreen':False}))
# A favorite moves only this requested title to the top of the real shelf.
# This is a synthetic simulator SD; no user's SD or persisted game state is read.
shelf=(ROOT/'src/apps_local/Shelf.cpp').read_text()
registry=shelf.split('constexpr shelf::Item kGames[] = {',1)[1].split('\n};',1)[0]
titles=re.findall(r'\{"([A-Z0-9& !]+)",\s*&',registry)
assert len(titles)==30 and len(set(titles))==30,(len(titles),titles)
title=CASES[GAME]['title'];assert titles.count(title)==1
body=b'SGP1\n'+b''.join((b'F\t' if row==title else b'N\t')+row.encode('ascii')+b'\n' for row in titles)
checksum=2166136261
for byte in body:checksum=((checksum^byte)*16777619)&0xffffffff
(crosspoint/'shelf-game-prefs.cfg').write_bytes(body+f'END\t{checksum:08X}\n'.encode())
legacy=(crosspoint/'shelf.cfg')
assert not legacy.exists()
events=CASES[GAME]['events']+[[21000,'QUIT']]
shots=[[2000,'home'],[6500,'shelf'],[10500,'menu'],[12700,'board'],[15700,'action'],[18500,'after']]
env=os.environ.copy()
env.update(CROSSPOINT_SIM_SD=str(sd),SDL_AUDIODRIVER='dummy',SDL_RENDER_DRIVER='software',
           CROSSPOINT_SIM_INPUT_SCRIPT=';'.join(f'{at}:{action}' for at,action in events),
           CROSSPOINT_SIM_SCREENSHOTS=';'.join(f'{at}:{run}/{name}.bmp' for at,name in shots))
with (run/'run.log').open('w') as log:
    subprocess.run(['xvfb-run','-a',str(PROGRAM.resolve())],cwd=run,env=env,stdout=log,stderr=log,timeout=42,check=True)
images=[]
for _,name in shots:
    bmp=run/(name+'.bmp')
    pic=Image.open(bmp)
    assert pic.size==(480,800),(GAME,LOCALE,name,pic.size)
    pic.save(run/(name+'.png'))
    images.append(pic.convert('L'))
assert ImageChops.difference(images[1],images[2]).getbbox(),(GAME,LOCALE,'shelf to game navigation did not change')
assert ImageChops.difference(images[1],images[-1]).getbbox(),(GAME,LOCALE,'game vanished by last frame')
assert not (crosspoint/'kana-practice-v1.bin').exists()
result={'game':GAME,'title':title,'locale':LOCALE,'events':events,'shots':[name for _,name in shots],
        'programSha256':hashlib.sha256(PROGRAM.read_bytes()).hexdigest(),
        'exit':0,'syntheticSdOnly':True,'practiceFileCreated':False}
(run/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'game':GAME,'locale':LOCALE,'run':str(run),'frames':len(images),'programSha256':result['programSha256']}))
