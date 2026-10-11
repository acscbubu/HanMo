"""Verify new kana strings against the six actual CJK bitmap interval tables."""
from pathlib import Path
import json,re,unittest
ROOT=Path(__file__).resolve().parents[2]
FONT=ROOT/'lib/EpdFont/builtinFonts'
I18N=ROOT/'lib/I18n/translations'
INTERVAL_RE=re.compile(r'\{\s*0x([0-9A-Fa-f]+),\s*0x([0-9A-Fa-f]+),\s*0x([0-9A-Fa-f]+)\s*\}')

def intervals(text,symbol):
 block=text.split(f'{symbol}[] = {{',1)[1].split('};',1)[0]
 return [(int(a,16),int(b,16)) for a,b,_ in INTERVAL_RE.findall(block)]

class KanaFontCoverage(unittest.TestCase):
 def test_new_labels_are_covered_in_each_of_six_cjk_sizes(self):
  common=(FONT/'notosans_cjk_common_intervals.h').read_text()
  for size in (8,10,12,14,16,18):
   header=(FONT/f'notosans_cjk_{size}.h').read_text()
   symbol=(f'notosans_cjk_{size}Intervals' if f'notosans_cjk_{size}Intervals[]' in header else 'notosans_cjk_commonIntervals')
   ranges=intervals(header if symbol.startswith(f'notosans_cjk_{size}') else common,symbol)
   self.assertGreater(len(ranges),100,(size,len(ranges)))
   for locale in ('english','chinese','chinese-traditional'):
    for line in (I18N/f'{locale}.yaml').read_text(encoding='utf-8').splitlines():
     if not (line.startswith('STR_KANA_STROKE_') or line.startswith('STR_KANA_SIMILAR_') or line.startswith('STR_JP_STROKE:') or line.startswith('STR_JP_SIMILAR:')):continue
     key,value=line.split(': ',1)
     for ch in json.loads(value):
      cp=ord(ch)
      if cp<128 or 0x3040<=cp<=0x30ff:continue
      self.assertTrue(any(a<=cp<=b for a,b in ranges),(locale,size,key,ch,hex(cp)))
 def test_large_kana_font_covers_basic_syllabary(self):
  t=(FONT/'hanmo_kana_52.h').read_text()
  ranges=intervals(t,'hanmo_kana_52Intervals')
  cards=json.loads((ROOT/'data/japanese/kana-basic.json').read_text(encoding='utf-8'))['cards']
  for card in cards:
   for ch in card[:2]:
    self.assertTrue(any(a<=ord(ch)<=b for a,b in ranges),(ch,hex(ord(ch))))
if __name__=='__main__':unittest.main()
