"""Stroke reading reuses the 50-sound card's authored Chinese sound hints."""
from pathlib import Path
import json, re, subprocess, tempfile, unittest

ROOT = Path(__file__).resolve().parents[2]
J = ROOT / 'src/activities/apps/japanese'
FONT = ROOT / 'lib/EpdFont/builtinFonts'
CARDS = json.loads((ROOT / 'data/japanese/kana-basic.json').read_text(encoding='utf-8'))['cards']

class StrokeSoundHintTests(unittest.TestCase):
    def test_reading_uses_existing_seventh_field_for_all_46_cards(self):
        self.assertEqual(len(CARDS), 46)
        self.assertEqual(CARDS[0][2:3] + CARDS[0][6:7], ['a', '阿'])
        self.assertEqual(CARDS[0][4], '雨')  # Example meaning is not the sound hint.
        generated = (J / 'KanaData.generated.h').read_text(encoding='utf-8')
        rows = [json.loads('[' + row + ']') for row in re.findall(r'^  \{(".*")\},$', generated, re.M)[:46]]
        self.assertEqual(rows, CARDS)  # Never patch generated data independently.
        self.assertTrue(all(len(c) == 7 and c[2] and c[6] for c in CARDS))

    def test_card_style_formatting_matches_all_46_and_parenthesized_hints(self):
        cpp = '''#include "KanaSoundReading.h"
#include "KanaData.generated.h"
#include <array>
#include <cassert>
#include <cstring>
int main() {
  const char* expected[] = {''' + ','.join(json.dumps(c[2] + ('' if c[6].startswith('（') else ' ') + c[6], ensure_ascii=False) for c in CARDS) + '''};
  for (int i = 0; i < 46; ++i) {
    std::array<char, 64> out{};
    kana::formatSoundReading(kana::cards[i], out);
    assert(std::strcmp(out.data(), expected[i]) == 0);
  }
  assert(std::strcmp(expected[0], "a 阿") == 0);
  assert(std::strcmp(expected[3], "e（矮）") == 0);
}
'''
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / 'reading.cpp').write_text(cpp, encoding='utf-8')
            subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-I', str(J), str(path / 'reading.cpp'), '-o', str(path / 'reading')], check=True)
            subprocess.run([str(path / 'reading')], check=True)

    def test_large_card_font_covers_all_46_chinese_sound_hints(self):
        text = (FONT / 'hanmo_kana_20.h').read_text(encoding='utf-8')
        block = text.split('hanmo_kana_20Intervals[] = {', 1)[1].split('};', 1)[0]
        intervals = [(int(a, 16), int(b, 16)) for a, b in re.findall(r'\{\s*0x([0-9A-Fa-f]+),\s*0x([0-9A-Fa-f]+),\s*0x[0-9A-Fa-f]+\s*\}', block)]
        for c in CARDS:
            for ch in c[2] + c[6] + ' （）':
                if ch == ' ': continue
                self.assertTrue(any(lo <= ord(ch) <= hi for lo, hi in intervals), (c[2], ch, hex(ord(ch))))

    def test_all_readings_fit_left_column_at_real_card_font_metrics(self):
        cpp = '''#include "KanaSoundReading.h"
#include "KanaStrokeLayout.h"
#include "EpdFont.h"
#include "builtinFonts/hanmo_kana_20.h"
#include <array>
#include <cassert>
int main() {
  EpdFont font(&hanmo_kana_20);
  for (int bodyWidth : {456, 380}) {
    auto layout = kana_ui::StrokeLayout::forBody(12, 86, bodyWidth, 702);
    for (const auto& card : kana::cards) {
      std::array<char, 64> reading{};
      kana::formatSoundReading(card, reading);
      int w = 0, h = 0;
      font.getTextDimensions(reading.data(), &w, &h);
      assert(w > 0 && w <= layout.romaji.w);
      assert(h > 0 && h <= 48);
    }
  }
}
'''
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / 'metrics.cpp').write_text(cpp)
            subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-Wno-missing-field-initializers',
                            '-I', str(J), '-I', str(ROOT / 'lib/EpdFont'),
                            '-I', str(ROOT / 'lib/Utf8'), str(path / 'metrics.cpp'),
                            str(ROOT / 'lib/EpdFont/EpdFont.cpp'), str(ROOT / 'lib/Utf8/Utf8.cpp'),
                            '-o', str(path / 'metrics')], check=True)
            subprocess.run([str(path / 'metrics')], check=True)

    def test_reading_is_centered_but_stays_in_left_column(self):
        cpp = '''#include "KanaStrokeLayout.h"
#include <cassert>
int main() {
  const auto l = kana_ui::StrokeLayout::forBody(12, 86, 456, 702);
  for (int width : {24, 50, 80, 142}) {
    const int x = kana_ui::centerReadingInColumn(l.romaji, 104, width);
    assert(x >= l.romaji.x && x + width <= l.romaji.x + l.romaji.w);
    assert(x + width + 6 <= l.artX);
  }
  assert(kana_ui::centerReadingInColumn(l.romaji, 104, 24) == kana_ui::centerUnderGlyph(l.romaji.x, 104, 24));
}
'''
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / 'bounds.cpp').write_text(cpp)
            subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-I', str(J), str(path / 'bounds.cpp'), '-o', str(path / 'bounds')], check=True)
            subprocess.run([str(path / 'bounds')], check=True)

    def test_activity_draws_shared_sound_reading_at_card_font_size(self):
        source = (J / 'KanaStrokeActivity.cpp').read_text(encoding='utf-8')
        header = (J / 'KanaStrokeActivity.h').read_text(encoding='utf-8')
        self.assertIn('#include "KanaSoundReading.h"', source)
        self.assertIn('kana::formatSoundReading(basicCard, soundReading_)', source)
        self.assertIn('kana::cards[lesson_.cardIndex()]', source)
        self.assertIn('renderer.getTextWidth(kReadingFontId, soundReading_.data())', source)
        self.assertIn('kana_ui::centerReadingInColumn(layout.romaji, glyphWidth, readingWidth)', source)
        self.assertIn('renderer.drawText(kReadingFontId, readingX, layout.romaji.y, soundReading_.data())', source)
        self.assertIn('std::array<char, 64> soundReading_', header)
        self.assertIn('hanmo_kana_20', source)
        self.assertNotIn('basicCard.meaning', source)
        self.assertNotIn('savePractice(', source)

if __name__ == '__main__': unittest.main()
