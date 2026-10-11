"""Authoritative kana examples and their compiled, byte-exact C++ representation."""

import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/japanese/kana-basic.json"

# Independently reviewed Hepburn readings of the Japanese examples, not glosses.
EXAMPLES = [
    ("あめ", "ame"), ("いぬ", "inu"), ("うみ", "umi"), ("えき", "eki"),
    ("おと", "oto"), ("かさ", "kasa"), ("き", "ki"), ("くつ", "kutsu"),
    ("け", "ke"), ("こえ", "koe"), ("さかな", "sakana"), ("しお", "shio"),
    ("すし", "sushi"), ("せかい", "sekai"), ("そら", "sora"), ("たこ", "tako"),
    ("ちず", "chizu"), ("つき", "tsuki"), ("て", "te"), ("とり", "tori"),
    ("なつ", "natsu"), ("にく", "niku"), ("ぬの", "nuno"), ("ねこ", "neko"),
    ("のり", "nori"), ("はな", "hana"), ("ひと", "hito"), ("ふね", "fune"),
    ("へや", "heya"), ("ほし", "hoshi"), ("まち", "machi"), ("みみ", "mimi"),
    ("むし", "mushi"), ("め", "me"), ("もり", "mori"), ("やま", "yama"),
    ("ゆき", "yuki"), ("よる", "yoru"), ("らくだ", "rakuda"),
    ("りんご", "ringo"), ("るす", "rusu"), ("れきし", "rekishi"),
    ("ろく", "roku"), ("わに", "wani"), ("みずをのむ", "mizu o nomu"),
    ("ほん", "hon"),
]


class KanaExampleRomajiTests(unittest.TestCase):
    def test_all_46_authored_example_readings(self):
        cards = json.loads(SOURCE.read_text(encoding="utf-8"))["cards"]
        self.assertEqual(len(cards), 46)
        self.assertEqual(len(EXAMPLES), 46)
        for index, (card, expected) in enumerate(zip(cards, EXAMPLES)):
            self.assertEqual(len(card), 7, f"card {index} needs exampleRomaji and soundHint")
            with self.subTest(index=index, example=expected[0]):
                self.assertEqual((card[3], card[5]), expected)
                self.assertRegex(card[5], r"^[a-z]+(?: [a-z]+)*$")
                self.assertLessEqual(len(card[5].encode("utf-8")), 24)
        # Card-name spelling remains 'wo', though を as a particle sounds 'o'.
        self.assertEqual(cards[44][2], "wo")
        self.assertEqual(cards[44][5], "mizu o nomu")

    def test_compiled_cpp_fields_match_json_byte_for_byte(self):
        cards = json.loads(SOURCE.read_text(encoding="utf-8"))["cards"]
        code = r'''
#include <array>
#include <cstring>
#include <iostream>
#include "src/activities/apps/japanese/KanaData.generated.h"
int main() {
    std::cout << kana::cards.size() << '\n';
    for (const auto& c : kana::cards) {
        const std::array<const char*, 7> fields = {
            c.hiragana, c.katakana, c.romaji, c.example, c.meaning, c.exampleRomaji, c.soundHint
        };
        for (const char* field : fields) {
            const auto bytes = std::strlen(field);
            std::cout << bytes << ':';
            std::cout.write(field, bytes);
        }
    }
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "kana.cpp"
            binary = Path(directory) / "kana"
            source.write_text(code, encoding="utf-8")
            compile_result = subprocess.run(
                ["g++", "-std=c++17", "-I", str(ROOT), str(source), "-o", str(binary)],
                capture_output=True, text=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            result = subprocess.run([str(binary)], check=True, capture_output=True).stdout
        count_bytes, separator, payload = result.partition(b"\n")
        self.assertEqual(separator, b"\n")
        self.assertEqual(int(count_bytes), len(cards))
        self.assertEqual(len(cards), 46)
        position = 0
        for index, row in enumerate(cards):
            self.assertEqual(len(row), 7)
            for field_index, expected in enumerate(row):
                prefix = re.match(rb"([0-9]+):", payload[position:])
                self.assertIsNotNone(prefix, (index, field_index))
                byte_count = int(prefix.group(1))
                position += prefix.end()
                actual = payload[position:position + byte_count]
                expected_bytes = expected.encode("utf-8")
                with self.subTest(index=index, field=field_index):
                    self.assertEqual(byte_count, len(expected_bytes))
                    self.assertEqual(actual, expected_bytes)
                position += byte_count
        self.assertEqual(position, len(payload), "extra C++ output or unexpected fields")


if __name__ == "__main__":
    unittest.main()
