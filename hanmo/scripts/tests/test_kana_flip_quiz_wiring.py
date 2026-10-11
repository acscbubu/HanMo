"""Route the existing Flip Quiz row to a real activity, not a placeholder."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
ACT = ROOT / "src/activities/apps/japanese/JapaneseLearningActivity.cpp"


class QuizEntryTests(unittest.TestCase):
    def test_flip_quiz_row_opens_quiz_without_replacing_kana_cards(self):
        text = ACT.read_text(encoding="utf-8")
        self.assertIn('#include "KanaQuizActivity.h"', text)
        self.assertRegex(text, r"category_\s*<\s*0\s*&&\s*index\s*==\s*3")
        self.assertIn('startActivityForResultWith<KanaQuizActivity>', text)
        self.assertIn('startActivityForResultWith<KanaGroupsActivity>', text)
        self.assertIn('if (category_ >= 0) return;', text)


    def test_front_keeps_every_answer_field_hidden_until_reveal(self):
        screen = (ROOT / "src/activities/apps/japanese/KanaQuizActivity.cpp").read_text(encoding="utf-8")
        front = screen.split("void KanaQuizActivity::drawPrompt(", 1)[1].split("void KanaQuizActivity::drawAnswer(", 1)[0]
        answer = screen.split("void KanaQuizActivity::drawAnswer(", 1)[1]
        for secret in ("romaji", "soundHint", "example", "meaning"):
            self.assertNotIn('card.' + secret, front, secret)
            self.assertIn('card.' + secret, answer, secret)
        for transition in ("quiz_.reveal()", "quiz_.mark(true)", "quiz_.mark(false)"):
            self.assertIn(transition, screen)
        self.assertNotIn("savePractice(", screen)
        self.assertNotIn("KanaPracticeStore", screen)

    def test_quiz_labels_exist_in_all_three_locales(self):
        keys = ("REVEAL", "KNOWN", "AGAIN", "DONE", "RESTART", "FIRST", "REVIEW", "PROMPT", "SESSION")
        for locale in ("english", "chinese", "chinese-traditional"):
            with self.subTest(locale=locale):
                source = (ROOT / "lib/I18n/translations" / (locale + ".yaml")).read_text(encoding="utf-8")
                for key in keys:
                    self.assertTrue("STR_KANA_QUIZ_" + key + ":" in source, f"{locale}: missing {key}")


if __name__ == "__main__":
    unittest.main()
