#!/usr/bin/env python3
"""Rebuild shared UI font headers from the delivered, licensed TTF stack."""
from pathlib import Path
import hashlib,json,re,subprocess,sys
from fontTools.ttLib import TTFont
from gen_i18n import parse_yaml_file
R=Path(__file__).resolve().parents[1]
F=R/'lib/EpdFont/builtinFonts';S=F/'source'
def coverage(path):
 s=path.read_text()
 if 'notosans_cjk_commonIntervals,' in s:s=(F/'notosans_cjk_common_intervals.h').read_text()
 spans=re.findall(r'\{\s*(0x[0-9a-fA-F]+),\s*(0x[0-9a-fA-F]+),\s*0x[0-9a-fA-F]+\s*\}',s)
 return {cp for a,b in spans for cp in range(int(a,16),int(b,16)+1)}
required=set(range(32,127))|set(range(0x3041,0x3097))|set(range(0x30a1,0x30fb))|{0xfffd}
for name in ['notosans_cjk_8','notosans_cjk_10','notosans_cjk_12','notosans_8_regular','ubuntu_10_medium','ubuntu_12_medium']:
 required|=coverage(F/(name+'.h'))
translations=set()
for f in (R/'lib/I18n/translations').glob('*.yaml'):
 for key,value in parse_yaml_file(str(f)).items():
  if key.startswith('STR_') and isinstance(value,str):translations|={ord(c) for c in value if ord(c)>=32}
required|=translations
required={cp for cp in required if cp>=32}
stack=[S/p for p in ['HanMoKana/MarukoGothicCJKjp-Bold.ttf','HanMoKana/MarukoGothicCJKjp-Medium.ttf','NotoSans/NotoSans-Regular.ttf','NotoSansHebrew/NotoSansHebrew-UIMedium.ttf','NotoSansArabic/NotoSansArabic-UIMedium.ttf','Ubuntu/Ubuntu-Vietnamese-Medium.ttf']]
maps=[set(TTFont(p).getBestCmap()) for p in stack];missing=required-set.union(*maps)
assert not missing, [hex(cp) for cp in sorted(missing)]
chars=''.join(chr(cp) for cp in sorted(required))
charset=R/'docs/ui-font-characters.txt'
charset.write_text(chars,encoding='utf-8')
sources=[{'path':p.relative_to(R).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in stack]
result={'sourceFonts':sources,'glyphsPerSize':len(required),'uiTranslationCodepoints':len(translations),'translationFallback':[hex(cp) for cp in sorted(translations-maps[0])],'missing':[],'sizes':[],'format':'uncompressed 1-bit native FreeType monochrome; no device TTF parsing'}
for size in [8,10,12]:
 name=f'hanmo_ui_maruko_{size}';out=F/(name+'.h')
 cmd=[sys.executable,'lib/EpdFont/scripts/fontconvert.py',name,str(size),*[p.relative_to(R).as_posix() for p in stack],'--mono','--characters-file',charset.relative_to(R).as_posix()]
 with out.open('w') as f:subprocess.run(cmd,cwd=R,stdout=f,check=True)
 assert required<=coverage(out)
 result['sizes'].append({'size':size,'path':out.relative_to(R).as_posix(),'sha256':hashlib.sha256(out.read_bytes()).hexdigest()})
(R/'docs/ui-font-build.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False))
