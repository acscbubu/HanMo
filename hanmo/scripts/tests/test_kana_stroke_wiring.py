"""Route and UI checks for the kana stroke lesson."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
ACT = ROOT / "src/activities/apps/japanese/JapaneseLearningActivity.cpp"
SCREEN = ROOT / "src/activities/apps/japanese/KanaStrokeActivity.cpp"


class KanaStrokeWiringTests(unittest.TestCase):
    def test_stroke_row_opens_real_lesson_and_keeps_other_rows(self):
        text = ACT.read_text(encoding="utf-8")
        self.assertIn('#include "KanaStrokeActivity.h"', text)
        self.assertRegex(text, r"category_\s*<\s*0\s*&&\s*index\s*==\s*2")
        self.assertIn("startActivityForResultWith<KanaStrokeActivity>", text)
        self.assertIn("startActivityForResultWith<KanaGroupsActivity>", text)
        self.assertIn("startActivityForResultWith<KanaQuizActivity>", text)

    def test_lesson_uses_generated_stroke_data_and_does_not_persist_marks(self):
        source = SCREEN.read_text(encoding="utf-8")
        self.assertIn('#include "KanaStroke.h"', source)
        for call in ("lesson_.nextStroke()", "lesson_.previousStroke()", "lesson_.nextCard()", "lesson_.previousCard()", "lesson_.restart()"):
            self.assertIn(call, source)
        self.assertIn("drawLine", source)
        self.assertNotIn("KanaPracticeStore", source)
        self.assertNotIn("savePractice(", source)

    def test_stroke_labels_exist_in_all_locales(self):
        keys = ("STROKE_NUMBER", "STROKE_NEXT", "STROKE_PREV", "STROKE_RESTART", "STROKE_SCRIPT", "STROKE_HINT", "STROKE_SOURCE")
        for locale in ("english", "chinese", "chinese-traditional"):
            source = (ROOT / "lib/I18n/translations" / (locale + ".yaml")).read_text(encoding="utf-8")
            for key in keys:
                self.assertIn("STR_KANA_" + key + ":", source, f"{locale}: missing {key}")


if __name__ == "__main__":
    unittest.main()
