"""Every pull-down slot the shortcut page can edit must also be persisted.

Settings are written by walking getBaseSettingsList(): toJson() emits one JSON
key per registered entry and fromJson() reads exactly those back. The shortcut
page shows PANEL_SLOT_COUNT (12) rows, so if registration stops at SLOT_COUNT
(6) the optional slots 7-12 can be chosen, take effect immediately, and are then
silently dropped at save time -- the device comes back with them Disabled.

This compiles the REAL registration block from SettingsList.h against a
recording stub for SettingInfo, so it checks what actually gets registered
rather than how the loop is written.
"""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def registration_block(source: str) -> str:
    """The for-loop that registers the quickPanel settings, braces balanced."""
    anchor = source.index('static constexpr const char* keys[] = {"quickPanel1"')
    start = source.rindex('for (int i = 0;', 0, anchor)
    depth, i = 0, source.index('{', start)
    end = i + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


class QuickPanelPersistenceTest(unittest.TestCase):
    def setUp(self):
        self.settings_list = (ROOT / 'src/SettingsList.h').read_text(encoding='utf-8')
        self.block = registration_block(self.settings_list)

    def test_every_editable_slot_is_registered_for_persistence(self):
        settings = (ROOT / 'src/CrossPointSettings.h').read_text(encoding='utf-8')
        fields = '\n'.join(re.findall(r'  uint8_t (?:cornerTap\w+|quickPanel\d+) = [^;]+;', settings))
        enum = re.search(r'  enum CORNER_TAP_ACTION \{.*?\n  \};', settings, re.S).group()
        bindings = (ROOT / 'src/ShortcutBindings.h').read_text(encoding='utf-8')
        bindings = bindings.split('namespace ShortcutBindings', 1)[1]
        ids = sorted(set(re.findall(r'StrId::(STR_\w+)', bindings + self.block)))

        program = '''#include "src/ScreenShortcutPolicy.h"
#include <cassert>
#include <cstring>
#include <functional>
#include <string>
#include <vector>

struct CrossPointSettings {
ENUM
FIELDS
};
static CrossPointSettings SETTINGS;
enum class StrId { IDS };
namespace ShortcutBindings BINDINGS

// Records what the production block registers.
struct SettingInfo {
  StrId nameId{};
  uint8_t CrossPointSettings::* valuePtr = nullptr;
  const char* key = nullptr;
  static SettingInfo Enum(StrId name, uint8_t CrossPointSettings::* field,
                          std::vector<StrId>, const char* key, StrId) {
    return SettingInfo{name, field, key};
  }
};

int main() {
  std::vector<SettingInfo> v;
BLOCK

  // One registered entry per slot the shortcut page is able to edit.
  assert(v.size() == (size_t)ScreenShortcutPolicy::PANEL_SLOT_COUNT);

  for (int i = 0; i < ScreenShortcutPolicy::PANEL_SLOT_COUNT; ++i) {
    const std::string expected = "quickPanel" + std::to_string(i + 1);
    assert(v[i].key != nullptr);
    assert(expected == v[i].key);
    // The entry must point at the same field the panel dispatches through,
    // otherwise a save would write someone else's value.
    assert(v[i].valuePtr == ShortcutBindings::panel[i]);
    assert(v[i].nameId == ShortcutBindings::panelLabels[i]);
  }
  return 0;
}
'''.replace('FIELDS', fields).replace('ENUM', enum).replace('IDS', ','.join(ids)) \
   .replace('BINDINGS', bindings).replace('BLOCK', self.block)

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / 'quickpanel.cpp'
            src.write_text(program, encoding='utf-8')
            binary = Path(tmp) / 'quickpanel'
            compile_result = subprocess.run(
                ['g++', '-std=c++17', '-I', str(ROOT), '-o', str(binary), str(src)],
                capture_output=True, text=True)
            self.assertEqual(compile_result.returncode, 0,
                             f'compile failed:\n{compile_result.stderr[-3000:]}')
            run = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0,
                             'registered settings do not cover every editable slot:\n'
                             f'{run.stderr[-2000:]}')

    def test_reserve_matches_the_number_registered(self):
        """A short reserve() silently reallocates; keep it honest about the count."""
        reserve = re.search(r'v\.reserve\(v\.size\(\) \+ ScreenShortcutPolicy::(\w+)', self.settings_list)
        self.assertIsNotNone(reserve, 'the reserve() before shortcut registration vanished')
        self.assertEqual(reserve.group(1), 'PANEL_SLOT_COUNT')

    def test_keys_table_covers_every_slot(self):
        keys = re.findall(r'"(quickPanel\d+)"', self.block)
        self.assertEqual(keys, [f'quickPanel{i}' for i in range(1, 13)])

    def test_optional_slots_default_to_disabled(self):
        """Upgrade safety: an existing settings.json has no key for 7-12.

        fromJson falls back to the struct-initializer default for a missing key,
        so these must default to Disabled -- 0 would be Night, and every
        upgrading device would suddenly grow six extra night-mode tiles.
        """
        settings = (ROOT / 'src/CrossPointSettings.h').read_text(encoding='utf-8')
        for slot in range(7, 13):
            match = re.search(rf'uint8_t quickPanel{slot} = ([^;]+);', settings)
            self.assertIsNotNone(match, f'quickPanel{slot} is missing')
            self.assertEqual(match.group(1).strip(), 'ScreenShortcutPolicy::Disabled',
                             f'quickPanel{slot} must default to Disabled')


if __name__ == '__main__':
    unittest.main()
