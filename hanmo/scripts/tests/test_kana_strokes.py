"""TDD checks for traced kana stroke data and the stroke lesson state."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
JAPANESE = ROOT / "src/activities/apps/japanese"


class KanaStrokeTests(unittest.TestCase):
    def compile_and_run(self, source):
        with tempfile.TemporaryDirectory() as directory:
            cpp = Path(directory) / "test.cpp"
            exe = Path(directory) / "stroke-test"
            cpp.write_text('#include "KanaStroke.h"\n' + source, encoding="utf-8")
            subprocess.run(
                ["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", str(JAPANESE), str(cpp), "-o", str(exe)],
                check=True,
            )
            subprocess.run([str(exe)], check=True)

    def test_generated_data_covers_all_cards_and_has_ordered_points(self):
        self.compile_and_run(
            """
#include <cassert>
#include <initializer_list>
int main() {
    assert(kana::kStrokeCardCount == 46);
    for (int i = 0; i < kana::kStrokeCardCount; ++i) {
        const auto& card = kana::strokeCards[i];
        assert(card.hiragana.strokeCount > 0);
        assert(card.katakana.strokeCount > 0);
        for (const auto* glyph : {&card.hiragana, &card.katakana}) {
            for (int s = 0; s < glyph->strokeCount; ++s) {
                assert(glyph->strokes[s].partCount > 0);
                for (int part = 0; part < glyph->strokes[s].partCount; ++part) {
                    const auto& segment = glyph->strokes[s].parts[part];
                    assert(segment.pointCount >= 2);
                    for (int p = 0; p < segment.pointCount; ++p) {
                        assert(segment.points[p].x >= 0 && segment.points[p].x <= 1024);
                        assert(segment.points[p].y >= 0 && segment.points[p].y <= 1024);
                    }
                }
            }
        }
    }
}
"""
        )

    def test_lesson_steps_each_glyph_and_resets_on_navigation(self):
        self.compile_and_run(
            """
#include <cassert>
int main() {
    kana::StrokeLesson lesson;
    assert(lesson.cardIndex() == 0);
    assert(lesson.script() == kana::Script::Hiragana);
    assert(lesson.visibleStrokes() == 1);
    const int count = lesson.strokeCount();
    assert(count >= 1);
    for (int i = 1; i < count; ++i) assert(lesson.nextStroke());
    assert(lesson.visibleStrokes() == count);
    assert(!lesson.nextStroke());
    assert(lesson.previousStroke());
    assert(lesson.visibleStrokes() == count - 1);
    lesson.restart();
    assert(lesson.visibleStrokes() == 1);
    assert(lesson.toggleScript());
    assert(lesson.script() == kana::Script::Katakana);
    assert(lesson.visibleStrokes() == 1);
    assert(lesson.nextCard());
    assert(lesson.cardIndex() == 1 && lesson.visibleStrokes() == 1);
    assert(lesson.previousCard());
    assert(lesson.cardIndex() == 0);
}
"""
        )

    def test_kanjivg_rejects_out_of_bounds_points_instead_of_clipping(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("kana_stroke_generator", ROOT / "scripts/generate_kana_strokes.py")
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)
        with tempfile.TemporaryDirectory() as directory:
            svg = Path(directory) / "invalid.svg"
            svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 109 109">'
                           '<path id="kvg:00000-s1" d="M2,2L200,50"/></svg>')
            with self.assertRaises(ValueError):
                generator.kanjivg_paths(svg)

    def test_kanjivg_rejects_unexpected_viewbox(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("kana_stroke_generator", ROOT / "scripts/generate_kana_strokes.py")
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)
        with tempfile.TemporaryDirectory() as directory:
            svg = Path(directory) / "invalid.svg"
            svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">'
                           '<path id="kvg:00000-s1" d="M2,2L100,100"/></svg>')
            with self.assertRaises(ValueError):
                generator.kanjivg_paths(svg)

    def test_generated_data_exactly_matches_92_source_svgs(self):
        with tempfile.TemporaryDirectory() as directory:
            result = Path(directory) / "KanaStroke.generated.h"
            subprocess.run(["python3", str(ROOT / "scripts/generate_kana_strokes.py"), "-o", str(result)], check=True)
            for name in ("KanaStroke.generated.h", "KanaStrokeTypes.generated.h", "KanaStrokeData.generated.h"):
                self.assertEqual((result.parent/name).read_bytes(), (JAPANESE/name).read_bytes())

    def test_provenance_and_assets_are_kept_with_the_generator(self):
        notice = ROOT / "third_party/kanjivg/LICENSE"
        generator = ROOT / "scripts/generate_kana_strokes.py"
        self.assertTrue(notice.is_file())
        notice_text = notice.read_text(encoding="utf-8")
        self.assertIn("Attribution, ShareAlike", notice_text)
        self.assertTrue(generator.is_file())
        for script in ("hiragana", "katakana"):
            files = list((ROOT / "third_party/kanjivg" / script).glob("*.svg"))
            self.assertEqual(len(files), 46, script)


if __name__ == "__main__":
    unittest.main()
