import os,subprocess,sys,json
from pathlib import Path
root=Path(__file__).resolve().parents[2];lang=sys.argv[1];out=root/'build/video'/lang
seq=json.loads(sys.argv[2]);env=os.environ.copy();env.update(CROSSPOINT_SIM_SD=str(out/'sd'),XTEINK_VIDEO_LANGUAGE=lang,SDL_AUDIODRIVER='dummy',CROSSPOINT_SIM_INPUT_SCRIPT=';'.join(str(t)+':'+e for t,e in seq)+f';{seq[-1][0]+2500}:QUIT',CROSSPOINT_SIM_SCREENSHOTS=';'.join(f'{t+1600}:{out}/probe-{i}.bmp' for i,(t,e) in enumerate(seq)))
with (out/'probe.log').open('w') as log:subprocess.run(['xvfb-run','-a',str(root/'.pio/build/simulator_x4pro_video/program')],cwd=out,env=env,stdout=log,stderr=log,timeout=120)
for i in range(len(seq)):
 subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(out/f'probe-{i}.bmp'),str(out/f'probe-{i}.png')],check=True)
