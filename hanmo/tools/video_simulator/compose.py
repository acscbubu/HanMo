from pathlib import Path
import json,subprocess,sys
from record import ROOT,SCENES
lang=sys.argv[1];out=ROOT/'build/video'/lang;export=ROOT/'build/video/exports';export.mkdir(exist_ok=True)
font='/mnt/c/Windows/Fonts/msjh.ttc';parts=[];chapters=[];offset=0
for n,s in enumerate(SCENES):
 key=s['key'];title=s['zh' if lang=='zh' else 'en'];caption=s['zc' if lang=='zh' else 'ec'];badge='模擬器錄製 · 示範資料' if lang=='zh' else 'SIMULATOR RECORDING / DEMO DATA'
 texts=[('title',title,620,265,40),('caption',caption,620,365,28),('badge',badge,620,785,20),('chapter',f'{n+1:02d} / {len(SCENES):02d}   XTEINK X4 PRO',620,115,22)]
 filters=['pad=1440:900:60:50:color=0xf5f1e9','drawbox=x=52:y=42:w=496:h=816:color=0x272722:t=8','drawbox=x=620:y=215:w=65:h=4:color=0xa95234:t=fill']
 for label,text,x,y,size in texts:
  for line_no,line in enumerate(text.splitlines()):
   f=out/(key+'-'+label+str(line_no)+'.txt');f.write_text(line,encoding='utf-8');filters.append(f"drawtext=fontfile={font}:textfile={f}:x={x}:y={y+line_no*(size+18)}:fontsize={size}:fontcolor=0x292922")
 target=out/(key+'-composed.mp4')
 subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(out/(key+'-raw.mp4')),'-vf',','.join(filters),'-an','-c:v','libx264','-preset','fast','-crf','22','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',str(target)],check=True)
 parts.append("file '"+str(target)+"'");chapters.append(dict(start=offset,end=offset+s['duration'],title=title,caption=caption,key=key));offset+=s['duration']
(out/'concat.txt').write_text('\n'.join(parts),encoding='utf-8')
video=export/f'tour-{lang}.mp4'
subprocess.run(['ffmpeg','-y','-loglevel','error','-f','concat','-safe','0','-i',str(out/'concat.txt'),'-c','copy','-movflags','+faststart',str(video)],check=True)
subprocess.run(['ffmpeg','-y','-loglevel','error','-ss','1','-i',str(video),'-frames:v','1','-update','1',str(export/f'tour-{lang}.jpg')],check=True)
def ts(s):return f'{s//3600:02}:{s//60%60:02}:{s%60:02}.000'
(export/f'tour-{lang}.vtt').write_text('WEBVTT\n\n'+'\n\n'.join(ts(c['start'])+' --> '+ts(c['end'])+'\n'+c['title']+'\n'+c['caption'] for c in chapters)+'\n',encoding='utf-8')
(export/f'tour-{lang}.json').write_text(json.dumps(chapters,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(language=lang,seconds=offset,chapters=len(chapters),bytes=video.stat().st_size)),flush=True)
