"""Render the actual Settings category glyphs and check the rows that carry them."""
import pathlib, re, subprocess, tempfile, unittest
ROOT = pathlib.Path(__file__).resolve().parents[2]


def read(rel):
    return (ROOT / rel).read_text(encoding='utf-8')


class SettingsCategoryIconsTest(unittest.TestCase):
    def mapped_icons(self):
        table = re.search(r'icons = \{(.*?)\};', read('src/components/SettingsCategoryIcons.h'), re.S).group(1)
        return re.findall(r'UIIcon::(\w+)', table)

    def resolved_bitmaps(self):
        """UIIcon -> generated Icon struct, as listIconFor actually resolves it."""
        helpers = read('src/components/UiAppHelpers.h')
        body = helpers[helpers.index('listIconFor'):]
        big, small = body.split('switch (icon)')[1:3]
        pattern = r'case UIIcon::(\w+):\s*return freeink::ui::bitmapFromIcon\((\w+)\);'
        return dict(re.findall(pattern, big)), dict(re.findall(pattern, small))

    def test_actual_category_glyphs_render_ink_at_both_row_sizes(self):
        mapped = self.mapped_icons()
        self.assertEqual(len(mapped), 4, mapped)
        # A shared glyph would stop telling the categories apart in the list.
        self.assertEqual(len(set(mapped)), 4, mapped)
        self.assertNotIn('None', mapped)

        big, small = self.resolved_bitmaps()
        structs = []
        for icon in mapped:
            # A category whose UIIcon has no listIconFor case renders blank.
            self.assertIn(icon, big, icon)
            self.assertIn(icon, small, icon)
            structs.append((small[icon], 24))
            structs.append((big[icon], 32))

        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            code = ['#include "components/icons/listIcons.h"', '#include <cassert>', 'int main() {']
            for struct, px in structs:
                code.append('{ const freeink::Icon& i = ' + struct + ';')
                code.append('  assert(i.w == %d && i.h == %d && i.bits);' % (px, px))
                code.append('  int ink = 0;')
                code.append('  for (int b = 0; b < i.w * i.h / 8; ++b)')
                code.append('    for (int bit = 0; bit < 8; ++bit)')
                code.append('      if (((i.bits[b] >> bit) & 1) == 0) ++ink;')
                # Ink, but not a filled square: a blank or solid raster is a
                # generation failure, not an icon.
                code.append('  assert(ink > 10 && ink < i.w * i.h / 2);')
                code.append('  assert(i.opticalCenterY > 0 && i.opticalCenterY < i.h); }')
            code.append('}')
            (tmp / 'glyphs.cpp').write_text('\n'.join(code))
            subprocess.run(['g++', '-std=c++20', '-I' + str(ROOT / 'src'),
                            '-I' + str(ROOT / 'freeink-sdk/libs/assets/Icons/include'),
                            str(tmp / 'glyphs.cpp'), '-o', str(tmp / 'glyphs')], check=True)
            subprocess.run([str(tmp / 'glyphs')], check=True)

    def test_actual_mapping_is_bounded_and_usable_at_compile_time(self):
        mapped = self.mapped_icons()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            code = ['#include "components/SettingsCategoryIcons.h"',
                    'static_assert(SettingsCategoryIcons::count == 4);']
            for index, icon in enumerate(mapped):
                code.append('static_assert(SettingsCategoryIcons::at(%d) == UIIcon::%s);' % (index, icon))
            # Settings rows and any future row kind must not read past the table.
            code.append('static_assert(SettingsCategoryIcons::at(-1) == UIIcon::None);')
            code.append('static_assert(SettingsCategoryIcons::at(4) == UIIcon::None);')
            code.append('static_assert(SettingsCategoryIcons::at(99) == UIIcon::None);')
            code.append('int main() {}')
            (tmp / 'mapping.cpp').write_text('\n'.join(code))
            subprocess.run(['g++', '-std=c++20', '-fsyntax-only',
                            '-I' + str(ROOT / 'test/inx_navigation/stubs'),
                            '-I' + str(ROOT / 'src'), '-I' + str(ROOT / 'lib/hal'),
                            '-I' + str(ROOT / 'freeink-sdk/libs/ui/FreeInkUI/include'),
                            '-I' + str(ROOT / 'freeink-sdk/libs/assets/Icons/include'),
                            str(tmp / 'mapping.cpp')], check=True)

    def test_accordion_gives_categories_the_icon_and_keeps_settings_nested(self):
        activity = read('src/activities/settings/SettingsActivity.cpp')
        rows = activity[activity.index('void SettingsActivity::rebuildAccordionRows'):]
        rows = rows[:rows.index('\nvoid SettingsActivity::')]
        self.assertIn('listIconFor(SettingsCategoryIcons::at(row.category), CATEGORY_ICON_SIZE)', rows)
        self.assertIn('item.icon = rowIconSpacer();', rows)
        # The settings under a category keep their text indent on top of the
        # reserved icon column, so they still read as nested.
        self.assertIn('std::string("  ")', rows)
        self.assertIn('static_assert(SettingsCategoryIcons::count == categoryCount', rows)
        # The spacer reserves the same column width and draws nothing: Mask1
        # treats a set bit as blank.
        self.assertIn('constexpr int CATEGORY_ICON_SIZE = 24;', activity)
        self.assertRegex(activity, r'for \(uint8_t& byte : spacer\.bits\) byte = 0xFF;')
        self.assertIn('ref.format = fui::BitmapFormat::Mask1;', activity)


if __name__ == '__main__':
    unittest.main()
