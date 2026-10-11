from pathlib import Path
import unittest,re,json,hashlib,subprocess,tempfile
R=Path(__file__).resolve().parents[2]
class PublicScopeTests(unittest.TestCase):
 def test_company_sources_and_endpoints_absent(self):
  self.assertFalse((R/'src/activities/apps/dashboard').exists())
  forbidden=re.compile(r'SkuLookup|SkuPrint|sku_lookup|sku_print|dashboardUrl|goToDashboard|work.?hub',re.I)
  for p in (R/'src').rglob('*'):
   if p.suffix in ['.h','.cpp']:
    self.assertIsNone(forbidden.search(p.read_text()),str(p.relative_to(R)))
 def test_retired_settings_preserve_ids(self):
  code=r'''#include "HomeShortcutPolicy.h"
#include <cassert>
int main(){using namespace HomeShortcutPolicy;
 static_assert(RetiredPrivate==11 && ReadingStats==12 && InfoBoard==17 && Count==18);
 static_assert(SELECTABLE_COUNT==16);
 for(int i=0;i<SELECTABLE_COUNT;i++){auto a=storedAction(i);assert(!isRetired(a));assert(selectionIndex(a)==i);}
 assert(selectionIndex(11)==Hidden && selectionIndex(10)==Hidden);
 assert(storedAction(-1)==Default && storedAction(SELECTABLE_COUNT)==Default);
 auto menu=resolve({11,10,Hidden,Hidden,Hidden,Hidden},true,false);assert(menu.count==1 && menu.items[0]==Settings);
 auto mixed=resolve({11,Files,InfoBoard,12,Hidden,10},true,false);assert(mixed.count==3 && mixed.items[0]==Files && mixed.items[1]==InfoBoard && mixed.items[2]==12);
}'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.cpp').write_text(code)
   subprocess.run(['g++','-std=c++17','-I'+str(R/'src'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
   subprocess.run([str(p/'test')],check=True)
 def test_chess_removed_six_games_kept(self):
  self.assertFalse((R/'src/apps_local/chess').exists())
  shelf=(R/'src/apps_local/Shelf.cpp').read_text()
  self.assertNotIn('"CHESS"',shelf)
  for name in ['MEMORY MATCH','REVERSI','SLIDE PUZZLE','MAHJONG SOLITAIRE','BACKGAMMON','TILE RUMMY']:
   self.assertIn('"'+name+'"',shelf)
  self.assertIn('"CHINESE CHESS"',shelf)
 def test_info_board_three_scenes(self):
  cpp=(R/'src/activities/apps/info-board/InfoBoardActivity.cpp').read_text()
  self.assertNotIn('scene_ == 3',cpp)
  self.assertNotIn('(scene_ + 1) % 4',cpp)
  self.assertIn('(scene_ + 2) % 3',cpp)
  self.assertNotIn('OPDS_STORE',cpp)
  self.assertIn('STR_INFO_PC',cpp);self.assertIn('STR_INFO_WEATHER',cpp)
 def test_replacement_font_lineage(self):
  rows=json.loads((R/'docs/public-fonts-manifest.json').read_text())
  self.assertEqual(len(rows),13)
  for row in rows:
   self.assertEqual(hashlib.sha256((R/row['source']).read_bytes()).hexdigest(),row['sourceSha256'])
   self.assertEqual(hashlib.sha256((R/row['output']).read_bytes()).hexdigest(),row['sha256'])
   self.assertTrue((R/row['source']).with_name('OFL.txt').exists())
  names=[p.name for p in (R/'src/apps_local/ui/fonts').glob('*.h')]
  self.assertFalse(any(n.startswith(('instrument_','toybox_')) for n in names))
 def test_prior_cjk_coverage_is_preserved(self):
  baseline=json.loads((R/'docs/public-cjk-baseline-coverage.json').read_text())
  common=(R/'lib/EpdFont/builtinFonts/notosans_cjk_common_intervals.h').read_text()
  for size,prior in baseline.items():
   font=(R/f'lib/EpdFont/builtinFonts/notosans_cjk_{size}.h').read_text()
   source=common if 'notosans_cjk_commonIntervals,' in font else font
   spans=[(int(a,16),int(b,16)) for a,b in re.findall(r'\{\s*(0x[0-9A-Fa-f]+),\s*(0x[0-9A-Fa-f]+),\s*0x[0-9A-Fa-f]+\s*\}',source)]
   now={c for a,b in spans for c in range(a,b+1)}
   self.assertEqual(set(prior)-now,set(),size)
 def test_translation_new_characters(self):
  needed=set()
  for locale in ['chinese','chinese-traditional']:
   for line in (R/f'lib/I18n/translations/{locale}.yaml').read_text().splitlines():
    if line.startswith(('STR_CHANGE_PUBLIC_SCOPE_','STR_INFO_REFRESH:','STR_INFO_FAILED:')):
     needed.update(ord(c) for c in json.loads(line.split(': ',1)[1]) if '\u3400'<=c<='\u9fff')
  common=(R/'lib/EpdFont/builtinFonts/notosans_cjk_common_intervals.h').read_text()
  for size in [8,10,12,14,16,18]:
   font=(R/f'lib/EpdFont/builtinFonts/notosans_cjk_{size}.h').read_text()
   source=common if 'notosans_cjk_commonIntervals,' in font else font
   intervals=[(int(a,16),int(b,16)) for a,b in re.findall(r'\{\s*(0x[0-9A-Fa-f]+),\s*(0x[0-9A-Fa-f]+),\s*0x[0-9A-Fa-f]+\s*\}',source)]
   self.assertTrue(intervals)
   self.assertEqual([chr(c) for c in needed if not any(a<=c<=b for a,b in intervals)],[],str(size))
if __name__=='__main__':unittest.main()
