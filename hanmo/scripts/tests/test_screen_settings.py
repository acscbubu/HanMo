import pathlib
import subprocess
import tempfile
import unittest
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
class ScreenSettingsTest(unittest.TestCase):
    def test_routing_paths_and_bmp_bounds(self):
        source = r"""
#include "src/ScreenSettingsPolicy.h"
#include <cassert>
#include <string>
#include <ArduinoJson.h>
using namespace ScreenSettingsPolicy;
int main() {
  for (int shutdown=0; shutdown<ShutdownCount; ++shutdown) {
    assert(usesSleepScreen(true,shutdown));
    assert(usesSleepScreen(false,shutdown)==(shutdown==FollowSleep));
    for (bool keep : {false,true}) for(bool timeout : {false,true}) {
      assert(quickResume(true,shutdown,keep,timeout)==(keep||timeout));
      assert(quickResume(false,shutdown,keep,timeout)==(shutdown==FollowSleep&&keep));
    }
  }
  char path[PATH_BYTES]="/old.bmp";
  for(const char* invalid : {"relative.bmp","/a/../b.bmp","/a/./b.bmp","/a//b.bmp","/a\\b.bmp","/abc.png","/bad\n.bmp"}) {
    assert(!assignPath(path,invalid)); assert(std::string(path)=="/old.bmp");
  }
  assert(!assignPath(path,nullptr));
  assert(assignPath(path,"/圖片/開機.BMP"));
  JsonDocument settings; settings["bootScreenImage"]=path;
  std::string serialized; serializeJson(settings,serialized);
  JsonDocument restored; assert(!deserializeJson(restored,serialized));
  char restoredPath[PATH_BYTES]="";
  assert(assignPath(restoredPath,restored["bootScreenImage"]|""));
  assert(std::string(path)==restoredPath);
  const auto longest = std::string("/")+std::string(250,'x')+".bmp";
  assert(assignPath(path,longest.c_str()));
  assert(!assignPath(path,("/"+longest).c_str()));
  assert(assignPath(path,"")); assert(!path[0]);
  assert(bitmapFits(62,60,800,48062));
  assert(!bitmapFits(62,60,800,48061));
  assert(!bitmapFits(12,60,800,48062));
  assert(!bitmapFits(62,0,800,48062));
  assert(!bitmapFits(62,8193,800,100000000));
  assert(!bitmapFits(62,60,3073,100000000));
  assert(!bitmapFits(UINT64_MAX,60,800,100000000));
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            cpp=pathlib.Path(tmp)/'test.cpp';exe=pathlib.Path(tmp)/'test'
            cpp.write_text(source)
            subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
                '-I'+str(ROOT),'-I'+str(ROOT/'.pio/libdeps/x4pro_custom/ArduinoJson/src'),str(cpp),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)

    def test_new_ui_glyph_coverage(self):
        texts=[]
        for locale in ['chinese','chinese-traditional']:
            texts += [s for s in (ROOT/f'lib/I18n/translations/{locale}.yaml').read_text().splitlines()
                      if s.startswith('STR_SCREEN_') or s.startswith('STR_CHANGE_SCREENS_')]
        needed={ord(c) for text in texts for c in text if '一'<=c<='鿿'}
        common=(ROOT/'lib/EpdFont/builtinFonts/notosans_cjk_common_intervals.h').read_text()
        for size in [8,10,12,14,16,18]:
            font=(ROOT/f'lib/EpdFont/builtinFonts/notosans_cjk_{size}.h').read_text()
            text=common if 'notosans_cjk_commonIntervals,' in font else font
            ranges=[(int(a,16),int(b,16)) for a,b in re.findall(r'\{\s*(0x[0-9A-Fa-f]+),\s*(0x[0-9A-Fa-f]+),\s*0x[0-9A-Fa-f]+\s*\}',text)]
            self.assertTrue(ranges)
            self.assertEqual([chr(c) for c in needed if not any(a<=c<=b for a,b in ranges)],[],f'{size}pt')

if __name__=='__main__':unittest.main()
