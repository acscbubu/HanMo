"""Render the actual canonical app masks with a minimal host renderer."""
import pathlib, re, subprocess, tempfile, unittest
ROOT = pathlib.Path(__file__).resolve().parents[2]
class AppIconsTest(unittest.TestCase):
    def test_every_visible_app_has_ink_in_both_selection_states(self):
        header = (ROOT/'src/components/icons/inx_apps.h').read_text()
        app = (ROOT/'src/activities/apps/AppsMenuActivity.cpp').read_text()
        icons = sorted(set(re.findall(r'UIIcon::(\w+)', app)))
        all_icons = sorted(set(re.findall(r'UIIcon::(\w+)', header)) | set(icons))
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            (tmp/'components/themes').mkdir(parents=True)
            (tmp/'components/themes/BaseTheme.h').write_text('#pragma once\nenum class UIIcon {'+','.join(all_icons)+'};\n')
            (tmp/'Icon.h').write_text('#pragma once\n#include <cstdint>\nnamespace freeink {struct Icon {int w,h,advance; const uint8_t* bits;};}\n')
            (tmp/'GfxRenderer.h').write_text('#pragma once\nstruct GfxRenderer {mutable int ink=0; void fillRect(int,int,int,int,bool) const {++ink;}};\n')
            code = '#include "components/icons/inx_apps.h"\n#include <cassert>\nint main(){GfxRenderer r;\n'
            for icon in icons:
                code += ('assert(InxAppIcons::get(UIIcon::'+icon+')); r.ink=0; '
                         'InxAppIcons::draw(r,UIIcon::'+icon+',0,0,1,false); assert(r.ink>10); int n'+icon+'=r.ink; r.ink=0; '
                         'InxAppIcons::draw(r,UIIcon::'+icon+',0,0,2,true); assert(r.ink==n'+icon+');\n')
            code += '}\n'
            (tmp/'test.cpp').write_text(code)
            subprocess.run(['g++','-std=c++20','-DENABLE_CHINESE_VERSION=1','-I'+str(tmp),'-I'+str(ROOT/'src'),str(tmp/'test.cpp'),'-o',str(tmp/'test')],check=True)
            subprocess.run([str(tmp/'test')],check=True)
if __name__=='__main__':unittest.main()
