"""Host behavior tests for the stand-alone Kana Similar lesson."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
INCLUDE = ROOT / "src/activities/apps/japanese"


class KanaSimilarStateTests(unittest.TestCase):
    def compile_and_run(self, source):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            cpp = directory / "test.cpp"
            exe = directory / "similar-test"
            cpp.write_text('#include "KanaSimilar.h"\n' + source, encoding="utf-8")
            subprocess.run(
                ["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", str(INCLUDE), str(cpp), "-o", str(exe)],
                check=True,
            )
            subprocess.run([str(exe)], check=True)

    def test_compare_screen_starts_and_enters_four_question_test(self):
        self.compile_and_run(r"""
#include <cassert>
int main() {
    kana::Similar lesson;
    assert(lesson.screen() == kana::Similar::Screen::Compare);
    assert(lesson.comparePair() == 0);
    assert(lesson.compareLeftCardId() == 11);
    assert(lesson.compareRightCardId() == 17);
    assert(lesson.startTest());
    assert(lesson.screen() == kana::Similar::Screen::Test);
    assert(lesson.questionCount() == 4);
    assert(lesson.questionIndex() == 0);
    assert(lesson.targetCardId() == 11);
    assert(lesson.leftChoiceCardId() == 11);
    assert(lesson.rightChoiceCardId() == 17);
    assert(!lesson.answered());
}
""")

    def test_questions_train_each_target_and_alternate_choice_order(self):
        self.compile_and_run(r"""
#include <array>
#include <cassert>
int main() {
    kana::Similar lesson;
    assert(lesson.startTest());
    const std::array<int, 4> targets{11, 14, 17, 45};
    const std::array<int, 4> left{11, 45, 11, 45};
    const std::array<int, 4> right{17, 14, 17, 14};
    for (int i = 0; i < 4; ++i) {
        assert(lesson.questionIndex() == i);
        assert(lesson.targetCardId() == targets[i]);
        assert(lesson.leftChoiceCardId() == left[i]);
        assert(lesson.rightChoiceCardId() == right[i]);
        assert(lesson.questionPair() == i % 2);
        assert(lesson.hintPair() == i % 2);
        assert(!lesson.answered());
        assert(lesson.choose(targets[i]));
        assert(lesson.answered());
        assert(lesson.next());
    }
    assert(lesson.screen() == kana::Similar::Screen::Done);
}
""")

    def test_each_pair_trains_left_and_right_correct_positions(self):
        self.compile_and_run(r"""
#include <array>
#include <cassert>
int main() {
    kana::Similar lesson;
    assert(lesson.startTest());
    std::array<std::array<bool, 2>, 2> seen{};
    for (int i = 0; i < lesson.questionCount(); ++i) {
        const int pair = lesson.questionPair();
        const int side = lesson.targetCardId() == lesson.leftChoiceCardId() ? 0 : 1;
        assert(pair == 0 || pair == 1);
        assert(side == 0 || side == 1);
        seen[pair][side] = true;
        assert(lesson.choose(lesson.targetCardId()));
        assert(lesson.next());
    }
    assert(seen[0][0] && seen[0][1]);
    assert(seen[1][0] && seen[1][1]);
}
""")

    def test_answer_feedback_score_and_invalid_transitions(self):
        self.compile_and_run(r"""
#include <cassert>
int main() {
    kana::Similar lesson;
    assert(!lesson.choose(11) && !lesson.next());
    assert(lesson.startTest());
    assert(!lesson.startTest());
    assert(!lesson.next());
    assert(lesson.selectedCardId() == -1 && !lesson.correct());
    assert(!lesson.choose(45));
    assert(lesson.choose(11));
    assert(lesson.correct() && lesson.score() == 1);
    assert(lesson.selectedCardId() == 11);
    assert(!lesson.choose(17));
    assert(lesson.next());
    assert(!lesson.answered() && lesson.selectedCardId() == -1);
    assert(lesson.choose(45));
    assert(!lesson.correct() && lesson.score() == 1);
    assert(lesson.selectedCardId() == 45);
    assert(!lesson.choose(14));
    assert(lesson.next());
    assert(lesson.choose(11) && !lesson.correct());
    assert(lesson.next());
    assert(lesson.choose(45) && lesson.correct());
    assert(lesson.next());
    assert(lesson.screen() == kana::Similar::Screen::Done);
    assert(lesson.questionIndex() == lesson.questionCount());
    assert(lesson.score() == 2);
    assert(lesson.targetCardId() == -1 && lesson.leftChoiceCardId() == -1);
    assert(lesson.rightChoiceCardId() == -1 && lesson.hintPair() == -1);
    assert(!lesson.next() && !lesson.choose(11));
}
""")

    def test_compare_navigation_and_restart_discard_session_score(self):
        self.compile_and_run(r"""
#include <cassert>
int main() {
    kana::Similar lesson;
    assert(lesson.stepCompare(-1));
    assert(lesson.comparePair() == 1);
    assert(lesson.compareLeftCardId() == 14 && lesson.compareRightCardId() == 45);
    assert(lesson.hintPair() == 1);
    assert(lesson.stepCompare(1));
    assert(lesson.comparePair() == 0 && lesson.hintPair() == 0);
    assert(lesson.startTest());
    assert(!lesson.stepCompare(1) && !lesson.restart());
    for (int i = 0; i < lesson.questionCount(); ++i) {
        assert(lesson.choose(lesson.targetCardId()));
        assert(lesson.next());
    }
    assert(lesson.score() == 4 && lesson.screen() == kana::Similar::Screen::Done);
    assert(!lesson.stepCompare(-1));
    assert(lesson.restart());
    assert(lesson.screen() == kana::Similar::Screen::Test);
    assert(lesson.questionIndex() == 0 && lesson.score() == 0);
    assert(!lesson.answered() && lesson.selectedCardId() == -1);
    assert(!lesson.restart());
}
""")

    def test_back_returns_to_compare_before_leaving_lesson(self):
        self.compile_and_run(r"""
#include <cassert>
int main() {
    kana::Similar lesson;
    assert(!lesson.back());
    assert(lesson.startTest());
    assert(lesson.back());
    assert(lesson.screen() == kana::Similar::Screen::Compare);
    assert(lesson.comparePair() == 0);
    assert(!lesson.back());
    assert(lesson.startTest());
    for (int i = 0; i < lesson.questionCount(); ++i) {
        assert(lesson.choose(lesson.targetCardId()));
        assert(lesson.next());
    }
    assert(lesson.screen() == kana::Similar::Screen::Done);
    assert(lesson.back());
    assert(lesson.screen() == kana::Similar::Screen::Compare);
    assert(!lesson.back());
}
""")

    def test_activity_is_standalone_and_uses_safe_touch_geometry(self):
        header = ROOT / "src/activities/apps/japanese/KanaSimilarActivity.h"
        source_path = ROOT / "src/activities/apps/japanese/KanaSimilarActivity.cpp"
        self.assertTrue(header.exists())
        self.assertTrue(source_path.exists())
        source = source_path.read_text(encoding="utf-8")
        self.assertIn('#include "KanaSimilar.h"', header.read_text(encoding="utf-8"))
        self.assertIn('#include "KanaSimilarActivity.h"', source)
        for key in (
            "COMPARE", "TEST", "CHOOSE", "CORRECT", "TRY_AGAIN", "NEXT", "RESTART",
            "SHI_HINT", "TSU_HINT", "SO_HINT", "N_HINT",
        ):
            self.assertIn("STR_KANA_SIMILAR_" + key, source)
        self.assertIn("STR_BACK", source)
        self.assertIn("STR_KANA_PREV", source)
        self.assertIn("STR_KANA_NEXT", source)
        self.assertIn("hanmo_kana_52", source)
        self.assertRegex(source, r"kGap\s*=\s*8")
        self.assertIn("p.minTouchSize = 44", source)
        self.assertNotIn("KanaPractice", source)
        self.assertNotIn("Storage", source)
        self.assertNotIn("kStarOn", source)
        self.assertNotIn("savePractice", source)
        self.assertNotIn("JapaneseLearningActivity", source)

    def test_prompt_hides_glyphs_until_feedback_and_hints_are_pair_specific(self):
        source = (ROOT / "src/activities/apps/japanese/KanaSimilarActivity.cpp").read_text(encoding="utf-8")
        prompt = source.split("void KanaSimilarActivity::drawTestPrompt(", 1)[1].split(
            "void KanaSimilarActivity::drawTestAnswer(", 1
        )[0]
        answer = source.split("void KanaSimilarActivity::drawTestAnswer(", 1)[1]
        compare = source.split("void KanaSimilarActivity::drawCompare(", 1)[1].split(
            "void KanaSimilarActivity::drawTestPrompt(", 1
        )[0]
        self.assertIn("hintLine(0)", compare)
        self.assertIn("hintLine(1)", compare)
        self.assertIn("card.romaji", prompt)
        self.assertNotIn("card.katakana", prompt)
        self.assertNotIn("card.hiragana", prompt)
        self.assertIn("STR_KANA_SIMILAR_CORRECT", answer)
        self.assertIn("STR_KANA_SIMILAR_TRY_AGAIN", answer)
        self.assertIn("lesson_.targetCardId()", source)
        self.assertIn("fui::StateFocused", source)
        self.assertIn("hintLine(0)", answer)
        self.assertIn("hintLine(1)", answer)
        self.assertIn("drawTestAnswer(s, a)", source)
        self.assertIn("if (lesson_.answered()) drawTestAnswer(s, a)", source)
        self.assertIn("focusedChoice_", source)
        self.assertIn("action(4 + focusedChoice_)", source)
        self.assertIn("const char* KanaSimilarActivity::hintLine(int line)", source)
        self.assertIn("STR_KANA_SIMILAR_SHI_HINT", source)
        self.assertIn("STR_KANA_SIMILAR_TSU_HINT", source)
        self.assertIn("STR_KANA_SIMILAR_SO_HINT", source)
        self.assertIn("STR_KANA_SIMILAR_N_HINT", source)

    def test_answer_hint_stays_above_bottom_buttons_on_480x800(self):
        source = (ROOT / "src/activities/apps/japanese/KanaSimilarActivity.cpp").read_text(encoding="utf-8")
        rows = [(int(y), int(h)) for y, h in re.findall(
            r"Rect\{a\.x, int16_t\(a\.y \+ (\d+)\), a\.width, (\d+)\}, hintLine\([01]\)", source
        )]
        self.assertEqual(len(rows), 2)
        body_y = 5 + 45 + 8
        body_bottom = 800 - 12
        button_top = body_bottom - 52
        hint_bottom = body_y + rows[-1][0] + rows[-1][1]
        self.assertLessEqual(hint_bottom + 6, button_top)


if __name__ == "__main__":
    unittest.main()
