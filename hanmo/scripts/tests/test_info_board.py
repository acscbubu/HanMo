from pathlib import Path
import subprocess, tempfile, unittest, re, json
ROOT=Path(__file__).resolve().parents[2]
class InfoBoardTests(unittest.TestCase):
 def test_policy_parser_and_worker(self):
  with tempfile.TemporaryDirectory() as d:
   exe=Path(d)/'board'
   cmd=['g++','-std=c++17','-Isrc','-I.pio/libdeps/x4pro_custom/ArduinoJson/src','-I.pio/libdeps/simulator/simulator/src','-Ilib/Serialization','-Ilib/Logging','scripts/tests/info_board_cases.cpp','-o',str(exe)]
   subprocess.run(cmd,cwd=ROOT,check=True,capture_output=True)
   subprocess.run([str(exe)],check=True)
 def test_i18n_offsets_above_32k_and_fallback(self):
  code=r"""#include <cassert>
#include <cstring>
#include "I18n.h"
#include "I18nStrings.h"
int main(){
 auto& i=I18n::getInstance();
 assert(!strcmp(i.get(StrId::STR_INFO_BOARD),"Info board"));
 assert(!strcmp(i.get(StrId::STR_INFO_TEMPERATURE),"Temperature"));
 i.setLanguage(Language::ZH_TW);
 assert(!strcmp(i.get(StrId::STR_INFO_BOARD),"資訊看板"));
 assert(!strcmp(i.get(StrId::STR_INFO_TEMPERATURE),"溫度"));
 // Visit every entry in every generated language, including deduplicated
 // fallback pointers and entries beyond the old 15-bit boundary.
 for(int lang=0;lang<int(Language::_COUNT);lang++){
  i.setLanguage(Language(lang));
  for(int id=0;id<int(StrId::_COUNT);id++)assert(strlen(i.get(StrId(id)))<8192);
 }
 assert(!strcmp(i.get(StrId(65535)),"???"));
}"""
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'main.cpp').write_text(code)
   subprocess.run(['g++','-std=c++17','-DENABLE_CHINESE_VERSION','-Ilib/I18n',str(p/'main.cpp'),'lib/I18n/I18n.cpp','lib/I18n/I18nStrings.cpp','-o',str(p/'i18n')],cwd=ROOT,check=True,capture_output=True)
   subprocess.run([str(p/'i18n')],check=True)
 def test_generated_fonts_cover_info_board_labels(self):
  needed=set()
  for locale in ['chinese','chinese-traditional']:
   for line in (ROOT/f'lib/I18n/translations/{locale}.yaml').read_text().splitlines():
    if line.startswith(('STR_INFO_','STR_WIFI_STATUS')):
     needed.update(ord(c) for c in json.loads(line.split(': ',1)[1]) if '一' <= c <= '鿿')
  common=(ROOT/'lib/EpdFont/builtinFonts/notosans_cjk_common_intervals.h').read_text()
  for size in [8,10,12,14,16,18]:
   font=(ROOT/f'lib/EpdFont/builtinFonts/notosans_cjk_{size}.h').read_text()
   intervals=common if 'notosans_cjk_commonIntervals,' in font else font
   ranges=[(int(a,16),int(b,16)) for a,b in re.findall(r'\{\s*(0x[0-9A-Fa-f]+),\s*(0x[0-9A-Fa-f]+),\s*0x[0-9A-Fa-f]+\s*\}',intervals)]
   self.assertTrue(ranges)
   self.assertEqual([chr(c) for c in needed if not any(a<=c<=b for a,b in ranges)],[],f'{size}pt')
if __name__=='__main__':unittest.main()
