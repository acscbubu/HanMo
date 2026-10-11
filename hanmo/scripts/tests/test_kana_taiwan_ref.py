"""Authoritative Taiwanese-reference data and card wiring tests."""

import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/japanese/kana-basic.json"
EXPECTED = [
    ("あ", "阿"), ("い", "衣"), ("う", "鳥"), ("え", "矮"), ("お", "歐"),
    ("か", "卡"), ("き", "起"), ("く", "哭"), ("け", "溪"), ("こ", "掘"),
    ("さ", "撒"), ("し", "西"), ("す", "斯"), ("せ", "洗"), ("そ", "索"),
    ("た", "塔"), ("ち", "七"), ("つ", "刺"), ("て", "替"), ("と", "脫"),
    ("な", "那"), ("に", "尼"), ("ぬ", "奴"), ("ね", "奶"), ("の", "諾"),
    ("は", "哈"), ("ひ", "喜"), ("ふ", "夫"), ("へ", "黑"), ("ほ", "候"),
    ("ま", "媽"), ("み", "米"), ("む", "母"), ("め", "妹"), ("も", "摩"),
    ("や", "鴉"), ("ゆ", "優"), ("よ", "有"),
    ("ら", "拉"), ("り", "里"), ("る", "魯"), ("れ", "咧"), ("ろ", "羅"),
    ("わ", "哇"), ("を", "歐"), ("ん", "嗯"),
]


class KanaTaiwanReferenceTests(unittest.TestCase):
    def test_all_46_cards_have_the_reference_in_the_seventh_field(self):
        cards = json.loads(SOURCE.read_text(encoding="utf-8"))["cards"]
        self.assertEqual(len(cards), 46)
        self.assertEqual(len(EXPECTED), 46)
        for index, (kana, reference) in enumerate(EXPECTED):
            with self.subTest(index=index, kana=kana):
                self.assertEqual(cards[index][0], kana)
                self.assertEqual(len(cards[index]), 7)
                expected = f"（{reference}）" if kana in "えきけせてねひゆ" else reference
                self.assertEqual(cards[index][6], expected)
                self.assertNotIn("(", reference)
                self.assertEqual(cards[index][6].startswith("（"), kana in "えきけせてねひゆ")
                self.assertTrue(reference)

    def test_generated_card_keeps_reference_separate_from_romaji(self):
        code = r"""
#include <array>
#include <cassert>
#include <cstring>
#include "src/activities/apps/japanese/KanaData.generated.h"
int main() {
  assert(kana::cards.size() == 46);
  assert(std::strcmp(kana::cards[6].romaji, "ki") == 0);
  assert(std::strcmp(kana::cards[6].soundHint, "（起）") == 0);
  assert(std::strcmp(kana::cards[44].romaji, "wo") == 0);
  assert(std::strcmp(kana::cards[45].soundHint, "嗯") == 0);
}
"""
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "kana.cpp"
            binary = Path(directory) / "kana"
            source.write_text(code, encoding="utf-8")
            result = subprocess.run(
                ["g++", "-std=c++17", "-I", str(ROOT), str(source), "-o", str(binary)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_card_renders_reference_after_romaji_and_legend_is_wired(self):
        source = (ROOT / "src/activities/apps/japanese/KanaActivity.cpp").read_text()
        self.assertIn("card.soundHint", source)
        self.assertRegex(source, r"STR_KANA_TAIWAN_NOTE")
        self.assertIn("card.romaji", source)
        self.assertIn("card.soundHint", source)


if __name__ == "__main__":
    unittest.main()
