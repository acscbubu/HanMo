"""Reproducible OFL Noto replacement cuts. Run with fontTools and freetype-py."""
from pathlib import Path
import sys,subprocess,re,json,hashlib,math
import freetype
from fontTools.ttLib import TTFont
R=Path(__file__).resolve().parents[1]
F=R/'lib/EpdFont/builtinFonts/source'
out=R/'src/apps_local/ui/fonts'
# Keep stable renderer IDs; replace glyphs, not the caller's action/layout contracts.
cuts=[
 ('toybox_10','public_noto_sans_7',7,'NotoSans/NotoSans-Regular.ttf','kTileCut'),
 ('toybox_14','public_noto_sans_10',10,'NotoSans/NotoSans-Regular.ttf','kButtonCut'),
 ('toybox_20','public_noto_sans_15',15,'NotoSans/NotoSans-Regular.ttf','kUiCut'),
 ('toybox_30','public_noto_sans_22',22,'NotoSans/NotoSans-Regular.ttf','kDisplayCut'),
 ('toybox_44','public_noto_sans_32',32,'NotoSans/NotoSans-Regular.ttf','kLargeCut'),
 ('toybox_64','public_noto_sans_47',47,'NotoSans/NotoSans-Regular.ttf','kHugeCut'),
 ('instrument_10','public_noto_serif_9',9,'NotoSerif/NotoSerif-Regular.ttf','kSerifSmallCut'),
 ('instrument_13','public_noto_serif_12',12,'NotoSerif/NotoSerif-Regular.ttf','kSerifTileCut'),
 ('instrument_24','public_noto_serif_22',22,'NotoSerif/NotoSerif-Regular.ttf','kSerifTitleCut'),
 ('reading_serif_11','reading_serif_11',11,'NotoSerif/NotoSerif-Regular.ttf','kReadingSmallCut'),
 ('reading_serif_14','reading_serif_14',14,'NotoSerif/NotoSerif-Regular.ttf','kReadingCut'),
 ('reading_serif_bold_12','reading_serif_bold_12',12,'NotoSerif/NotoSerif-Bold.ttf','kReadingBoldSmallCut'),
 ('reading_serif_bold_16','reading_serif_bold_16',16,'NotoSerif/NotoSerif-Bold.ttf','kReadingBoldCut'),
]
tokens=(R/'src/apps_local/ui/ToyboxTokens.h').read_text()
cpp=(R/'src/apps_local/ui/ToyboxFonts.cpp').read_text()
records=[]
for old,name,size,source,metric in cuts:
    path=F/source
    with TTFont(path) as font:
        cmap=font.getBestCmap()
        chars=''.join(chr(c) for c in list(range(32,127))+[0xa0,0xb0,0xd7,0xf7,0x2013,0x2014,0x2018,0x2019,0x201c,0x201d,0x2022,0x2026,0xfffd] if c in cmap)
    dest=out/(name+'.h')
    args=[sys.executable,'lib/EpdFont/scripts/fontconvert.py',name,str(size),str(path.relative_to(R)),'--mono','--characters',chars]
    with dest.open('w') as stream:subprocess.run(args,cwd=R,stdout=stream,check=True)
    face=freetype.Face(str(path));face.set_char_size(size<<6,size<<6,150,150)
    face.load_char('H',freetype.FT_LOAD_RENDER|freetype.FT_LOAD_TARGET_MONO)
    values=[math.ceil(face.size.height/64),math.ceil(face.size.ascender/64),face.glyph.bitmap.rows]
    pattern=r'(constexpr CutMetrics '+metric+r')\{[^}]+\};[^\n]*'
    tokens,n=re.subn(pattern,lambda m:m[1]+'{'+', '.join(map(str,values))+'};  // '+name,tokens)
    assert n==1
    cpp=cpp.replace(old,name)
    if name!=old and (out/(old+'.h')).exists():(out/(old+'.h')).unlink()
    records.append(dict(name=name,size=size,source=str(path.relative_to(R)),sourceSha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        output=str(dest.relative_to(R)),sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),metrics=values,characters=chars))
(R/'src/apps_local/ui/ToyboxTokens.h').write_text(tokens)
# Historic face comments no longer describe the replacements.
cpp=re.sub(r'// Jersey 25.*?(?=EpdFont display30)',
    '// Public-edition Noto cuts; exact source TTF/OFL and generation recipe are retained.\n// Monochrome glyphs preserve the renderer bitmap format.\n',cpp,flags=re.S)
cpp=cpp.replace('Jersey is a display cut with uniform heavy stems','The display face has larger cuts')
(R/'src/apps_local/ui/ToyboxFonts.cpp').write_text(cpp)
(R/'docs/public-fonts-manifest.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
print('Generated',len(records),'Noto cuts; metrics updated from FreeType')
