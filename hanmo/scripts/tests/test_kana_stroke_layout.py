"""The stroke lesson's actual control geometry on an X4 Pro portrait screen."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
J = ROOT / 'src/activities/apps/japanese'


class StrokeLayoutTest(unittest.TestCase):
    def test_script_chooser_and_reordered_navigation_have_disjoint_touch_regions(self):
        cpp = '''#include "KanaStrokeLayout.h"
#include <cassert>
using namespace kana_ui;
static void beside(Box a, Box b) {
  assert(a.x + a.w + 6 <= b.x);
  assert(a.y == b.y && a.h == b.h);
  assert(a.h >= 48 && b.h >= 48);
}
int main() {
  const auto l = StrokeLayout::forBody(12, 86, 456, 702);
  beside(l.hiragana, l.katakana);
  beside(l.previousStroke, l.restart);
  beside(l.restart, l.nextStroke);
  beside(l.previousCard, l.back);
  beside(l.back, l.nextCard);
  assert(l.hiragana.y == 86 && l.katakana.y == 86);
  assert(l.previousStroke.y + l.previousStroke.h + 6 <= l.previousCard.y);
  assert(l.nextCard.y + l.nextCard.h <= 788);
  assert(l.previousCard.x == 12 && l.nextCard.x + l.nextCard.w <= 468);
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'layout.cpp'
            executable = Path(directory) / 'layout'
            source.write_text(cpp)
            subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-I', str(J), str(source), '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True)


    def test_direct_script_selection_keeps_progress_when_reselecting(self):
        cpp = '''#include "KanaStroke.h"
#include "KanaStrokeLayout.h"
#include <cassert>
int main() {
  kana::StrokeLesson lesson;
  assert(lesson.nextStroke());
  assert(lesson.visibleStrokes() == 2);
  assert(!kana_ui::selectScript(lesson, kana::Script::Hiragana));
  assert(lesson.visibleStrokes() == 2);
  assert(kana_ui::selectScript(lesson, kana::Script::Katakana));
  assert(lesson.script() == kana::Script::Katakana);
  assert(lesson.visibleStrokes() == 1);
  assert(!kana_ui::selectScript(lesson, kana::Script::Katakana));
  assert(kana_ui::selectScript(lesson, kana::Script::Hiragana));
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'selection.cpp'
            executable = Path(directory) / 'selection'
            source.write_text(cpp)
            subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-I', str(J), str(source), '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True)


    def test_activity_wires_direct_scripts_and_back_between_cards(self):
        source = (J / 'KanaStrokeActivity.cpp').read_text(encoding='utf-8')
        for value, script, rect, label in (
            (6, 'Hiragana', 'hiragana', 'STR_KANA_HIRA'),
            (7, 'Katakana', 'katakana', 'STR_KANA_KATA'),
        ):
            self.assertIn(f'kana_ui::selectScript(lesson_, kana::Script::{script})', source)
            self.assertIn(f'button(text(StrId::{label}), {value}, layout.{rect}', source)
        self.assertIn('button(text(StrId::STR_BACK), 0, layout.back', source)
        self.assertIn('button(text(StrId::STR_KANA_PREV), 4, layout.previousCard', source)
        self.assertIn('button(text(StrId::STR_KANA_NEXT), 5, layout.nextCard', source)
        self.assertIn('button(text(StrId::STR_KANA_STROKE_PREV), 1, layout.previousStroke', source)
        self.assertIn('button(text(StrId::STR_KANA_STROKE_RESTART), 3, layout.restart', source)
        self.assertIn('button(text(StrId::STR_KANA_STROKE_NEXT), 2, layout.nextStroke', source)
        self.assertIn('p.state = selected ? fui::StateSelected : fui::StateNormal', source)
        self.assertNotIn('STR_KANA_STROKE_SCRIPT', source)


    def test_romaji_sits_below_glyph_left_of_the_strokes_and_matches_all_cards(self):
        cpp = '''#include "KanaStrokeLayout.h"
#include "KanaData.generated.h"
#include <cassert>
#include <cstring>
int main() {
  const auto l = kana_ui::StrokeLayout::forBody(12, 86, 456, 702);
  assert(l.romaji.y >= l.glyphY + 90);
  assert(l.romaji.x >= 12 && l.romaji.x + l.romaji.w + 6 <= l.artX);
  assert(l.romaji.y + l.romaji.h < l.artY + l.artSide);
  // One center line for the Japanese glyph and its wider 12pt Latin reading.
  assert(kana_ui::centerUnderGlyph(24, 104, 28) == 62);
  assert(kana_ui::centerUnderGlyph(24, 104, 60) == 46);
  for (int i = 0; i < kana::kStrokeCardCount; ++i) {
    assert(std::strcmp(kana::cards[i].hiragana, kana::strokeCards[i].hiragana.glyph) == 0);
    assert(std::strcmp(kana::cards[i].katakana, kana::strokeCards[i].katakana.glyph) == 0);
    assert(std::strlen(kana::cards[i].romaji) > 0);
  }
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'romaji.cpp'
            executable = Path(directory) / 'romaji'
            source.write_text(cpp)
            subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-I', str(J), str(source), '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True)
        activity = (J / 'KanaStrokeActivity.cpp').read_text(encoding='utf-8')
        self.assertIn('#include "KanaData.generated.h"', activity)
        self.assertIn('renderer.getTextWidth(kBigFontId, glyph.glyph)', activity)
        self.assertIn('renderer.getTextWidth(kReadingFontId, soundReading_.data())', activity)
        self.assertIn('kana_ui::centerReadingInColumn(layout.romaji, glyphWidth, readingWidth)', activity)
        self.assertIn('renderer.drawText(kReadingFontId, readingX, layout.romaji.y, soundReading_.data())', activity)
        self.assertIn('kana::cards[lesson_.cardIndex()]', activity)


    def test_freed_vertical_space_enlarges_stroke_art_and_readable_hint(self):
        cpp = '''#include "KanaStrokeLayout.h"
#include <cassert>
int main() {
  const auto l = kana_ui::StrokeLayout::forBody(12, 86, 456, 702);
  assert(l.artSide >= 280);
  assert(l.artX >= l.romaji.x + l.romaji.w + 6);
  assert(l.artX + l.artSide <= 468);
  assert(l.artY + l.artSide + 24 <= l.progress.y);
  const auto narrow = kana_ui::StrokeLayout::forBody(12, 86, 380, 702);
  assert(narrow.artX >= narrow.romaji.x + narrow.romaji.w + 6);
  assert(narrow.artX + narrow.artSide <= 392);
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'art.cpp'
            executable = Path(directory) / 'art'
            source.write_text(cpp)
            subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-I', str(J), str(source), '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True)
        activity = (J / 'KanaStrokeActivity.cpp').read_text(encoding='utf-8')
        self.assertIn('label(text(StrId::STR_KANA_STROKE_HINT), layout.hint.y, layout.hint.h);', activity)

    def test_two_explanation_blocks_stack_directly_above_stroke_buttons(self):
        cpp = '''#include "KanaStrokeLayout.h"
#include <cassert>
int main() {
  const auto l = kana_ui::StrokeLayout::forBody(12, 86, 456, 702);
  assert(l.progress.y >= l.artY + l.artSide + 24);
  assert(l.progress.y + l.progress.h + 4 <= l.hint.y);
  assert(l.hint.y + l.hint.h + 6 <= l.source.y);
  assert(l.source.y + l.source.h + 6 <= l.previousStroke.y);
  assert(l.previousStroke.y - (l.source.y + l.source.h) <= 16);
  assert(l.progress.x == l.hint.x && l.hint.x == l.source.x);
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'explainer.cpp'
            executable = Path(directory) / 'explainer'
            source.write_text(cpp)
            subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-I', str(J), str(source), '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True)
        activity = (J / 'KanaStrokeActivity.cpp').read_text(encoding='utf-8')
        self.assertIn('label(position_.data(), layout.progress.y, layout.progress.h)', activity)
        self.assertIn('label(text(StrId::STR_KANA_STROKE_HINT), layout.hint.y, layout.hint.h', activity)

    def test_source_caption_is_compact_above_controls_with_full_credit(self):
        cpp = '''#include "KanaStrokeLayout.h"
#include <cassert>
int main() {
  const auto l = kana_ui::StrokeLayout::forBody(12, 86, 456, 702);
  assert(l.source.y >= l.artY + l.artSide + 105);
  assert(l.source.h <= 24);
  assert(l.source.y + l.source.h + 6 <= l.previousStroke.y);
  assert(l.previousStroke.y - (l.source.y + l.source.h) <= 16);
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'caption.cpp'
            executable = Path(directory) / 'caption'
            source.write_text(cpp)
            subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-I', str(J), str(source), '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True)
        activity = (J / 'KanaStrokeActivity.cpp').read_text(encoding='utf-8')
        self.assertIn('sourceStyle.maxLines = 1;', activity)
        self.assertIn('layout.source.x', activity)
        self.assertNotIn('bottom - 122', activity)
        for locale in ('english', 'chinese', 'chinese-traditional'):
            text = (ROOT / 'lib/I18n/translations' / f'{locale}.yaml').read_text(encoding='utf-8')
            line = next(x for x in text.splitlines() if x.startswith('STR_KANA_STROKE_SOURCE:'))
            import json
            label = json.loads(line.split(': ', 1)[1])
            self.assertLessEqual(len(label), 52, locale)
            for credit in ('KanjiVG', 'Ulrich Apel', 'CC BY-SA 3.0'):
                self.assertIn(credit, label, locale)


if __name__ == '__main__':
    unittest.main()
