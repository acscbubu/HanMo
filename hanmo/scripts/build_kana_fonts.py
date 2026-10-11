from pathlib import Path
import json,subprocess,sys
r=Path(__file__).resolve().parents[1];d=json.loads((r/'data/japanese/kana-basic.json').read_text())
font=r/'lib/EpdFont/builtinFonts/source/HanMoKana/MarukoGothicCJKjp-Medium.ttf'
for size,characters in [(12,''.join(g[0] for g in d['groups'])+'« 返回全部 46音0123456789/'),(52,''.join(c[0]+c[1] for c in d['cards'])),(20,''.join(c[3]+c[6] for c in d['cards'])+'abcdefghijklmnopqrstuvwxyz（） ')]:
 name=f'hanmo_kana_{size}';out=r/f'lib/EpdFont/builtinFonts/{name}.h';tmp=out.with_suffix('.tmp')
 with tmp.open('w') as stream:
  subprocess.run([sys.executable,str(r/'lib/EpdFont/scripts/fontconvert.py'),name,str(size),str(font),'--mono','--characters',characters+' �'],check=True,stdout=stream)
 tmp.replace(out)
