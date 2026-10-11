from pathlib import Path
import unittest,json,subprocess,tempfile,re
R=Path(__file__).resolve().parents[2]
class KanaStatusTests(unittest.TestCase):
 def test_lesson_facts_and_groups(self):
  d=json.loads((R/'data/japanese/kana-basic.json').read_text());cards=d['cards'];self.assertEqual(len(cards),46)
  self.assertEqual(''.join(c[0] for c in cards),'あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん')
  self.assertEqual([c[2] for c in cards],'a i u e o ka ki ku ke ko sa shi su se so ta chi tsu te to na ni nu ne no ha hi fu he ho ma mi mu me mo ya yu yo ra ri ru re ro wa wo n'.split())
  for a,b,roma,example,meaning,example_romaji,sound_hint in cards:
   self.assertEqual(ord(b)-ord(a),0x60);self.assertIn(a,example);self.assertTrue(meaning)
   self.assertTrue(example_romaji);self.assertTrue(example_romaji.isascii());self.assertTrue(sound_hint)
  self.assertEqual([i for _,first,size in d['groups'] for i in range(first,first+size)],list(range(46)))
 def test_actual_state_and_status_layout(self):
  code=r"""#include <cassert>
#include <set>
#include "src/activities/apps/japanese/KanaCardState.h"
#include "src/WifiStatusLayout.h"
int main(){
 for(int start=0;start<46;++start)for(int count=1;count<=46-start;++count){
  kana::State s(start,count);assert(s.current()==start);s.step(-1);assert(s.current()==start+count-1);s.step(1);assert(s.current()==start);
  s.shuffle();std::set<int> seen;for(int i=0;i<count;++i){seen.insert(s.current());s.step(1);}assert(int(seen.size())==count);
  assert(*seen.begin()==start && *seen.rbegin()==start+count-1);s.shuffle();assert(s.current()==start);
 }
 kana::State bad(-5,0);assert(bad.count==46 && bad.start==0);
 for(int w:{480,800})for(int pos=0;pos<4;++pos)for(int battery:{0,1,2}){
  int l=battery==0?12:battery==1?w/2-32:w-80;
  auto b=WifiStatusLayout::place(12,w-12,5,26,pos,l,l+64);
  if(pos==3){assert(b.width==0);continue;}
  assert(b.width==20&&b.height==18&&b.y>=5&&b.y+b.height<=31);
  assert(b.x>=12&&b.x+b.width<=w-12);
  assert(b.x+b.width+8<=l || b.x>=l+64+8);
 }
}"""
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.cpp').write_text(code);subprocess.run(['g++','-std=c++17','-I',str(R),str(p/'test.cpp'),'-o',str(p/'test')],check=True,capture_output=True);subprocess.run([str(p/'test')],check=True)
 def test_glyph_coverage_and_no_viewport_reservation(self):
  d=json.loads((R/'data/japanese/kana-basic.json').read_text())
  for size,chars in [(12,''.join(g[0] for g in d['groups'])+'« 返回全部 46音0123456789/'),(52,''.join(c[0]+c[1] for c in d['cards'])),(20,''.join(c[3]+c[6] for c in d['cards'])+'abcdefghijklmnopqrstuvwxyz（） ')]:
   t=(R/f'lib/EpdFont/builtinFonts/hanmo_kana_{size}.h').read_text();ranges=[(int(a,16),int(b,16)) for a,b in re.findall(r'\{\s*0x([0-9A-Fa-f]+),\s*0x([0-9A-Fa-f]+),',t)]
   self.assertEqual([c for c in set(chars) if not any(a<=ord(c)<=b for a,b in ranges)],[])
  self.assertIn('&GlobalWifiStatus::draw, 0',(R/'src/activities/ActivityManager.cpp').read_text())
  needed=set(''.join(c[4] for c in d['cards']))
  for line in (R/'lib/I18n/translations/chinese-traditional.yaml').read_text().splitlines():
   if line.startswith('STR_KANA_'):needed.update(json.loads(line.split(': ',1)[1]))
  needed={ord(c) for c in needed if '一'<=c<='鿿'}
  for size in [8,10,12,14,16,18]:
   t=(R/f'lib/EpdFont/builtinFonts/notosans_cjk_{size}.h').read_text()
   if 'notosans_cjk_commonIntervals,' in t:t=(R/'lib/EpdFont/builtinFonts/notosans_cjk_common_intervals.h').read_text()
   ranges=[(int(a,16),int(b,16)) for a,b in re.findall(r'\{\s*0x([0-9A-Fa-f]+),\s*0x([0-9A-Fa-f]+),',t)]
   self.assertEqual([chr(c) for c in needed if not any(a<=c<=b for a,b in ranges)],[],str(size))
if __name__=='__main__':unittest.main()
