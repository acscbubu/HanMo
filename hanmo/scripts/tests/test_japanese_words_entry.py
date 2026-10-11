"""Words is real category5; font/labels are checked against emitted bitmaps."""
from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
J = ROOT / 'src/activities/apps/japanese'
FONT = ROOT / 'lib/EpdFont/builtinFonts'


def ranges(data, symbol):
    block = data.split(f'{symbol}[] = {{', 1)[1].split('};', 1)[0]
    return [(int(a, 16), int(b, 16)) for a, b, _ in
            re.findall(r'\{\s*0x([0-9a-fA-F]+),\s*0x([0-9a-fA-F]+),\s*0x([0-9a-fA-F]+)\s*\}', block)]


class JapaneseWordsEntryTests(unittest.TestCase):
    def test_category_five_opens_the_word_lesson(self):
        source = (J / 'JapaneseLearningActivity.cpp').read_text()
        self.assertIn('#include "JapaneseWordsActivity.h"', source)
        self.assertRegex(source, r'category_\s*<\s*0\s*&&\s*index\s*==\s*5')
        self.assertIn('startActivityForResultWith<JapaneseWordsActivity>', source)
        for earlier in ('KanaGroupsActivity', 'KanaStrokeActivity', 'KanaQuizActivity', 'KanaSimilarActivity'):
            self.assertIn('startActivityForResultWith<' + earlier + '>', source)
        self.assertIn('StrId::STR_JP_SENTENCES, StrId::STR_JP_REVIEW', source)
        self.assertIn('if (category_ >= 0) return', source)

    def test_word_font_covers_all_word_examples_including_voiced_kana(self):
        path = FONT / 'hanmo_words_44.h'
        self.assertTrue(path.is_file(), 'word-card font has not been generated')
        covered = ranges(path.read_text(), 'hanmo_words_44Intervals')
        cards = json.loads((ROOT / 'data/japanese/kana-basic.json').read_text())['cards']
        words = [card for index, card in enumerate(cards) if index != 44]
        self.assertEqual(len(words), 45)
        self.assertEqual(len({card[3] for card in words}), 45)
        for card in words:
            for ch in card[3]:
                self.assertTrue(any(a <= ord(ch) <= b for a, b in covered), (card[3], ch))
        self.assertTrue(all(any(a <= ord(ch) <= b for a, b in covered) for ch in 'ずごだ'))

    def test_new_labels_and_word_meanings_fit_six_cjk_charsets(self):
        common = (FONT / 'notosans_cjk_common_intervals.h').read_text()
        cards = json.loads((ROOT / 'data/japanese/kana-basic.json').read_text())['cards']
        values = [card[4] for index, card in enumerate(cards) if index != 44]
        for locale in ('english', 'chinese', 'chinese-traditional'):
            text = (ROOT / 'lib/I18n/translations' / (locale + '.yaml')).read_text()
            translations = {line.split(': ', 1)[0]: json.loads(line.split(': ', 1)[1]) for line in text.splitlines()
                            if line.startswith(('STR_JP_WORDS_', 'STR_CHANGE_JP_WORDS_'))}
            for key in ('STR_JP_WORDS_PROMPT', 'STR_JP_WORDS_SESSION', 'STR_JP_WORDS_DONE',
                        'STR_CHANGE_JP_WORDS_TITLE', 'STR_CHANGE_JP_WORDS_WHAT', 'STR_CHANGE_JP_WORDS_HOW', 'STR_CHANGE_JP_WORDS_NOTE'):
                self.assertIn(key, translations)
            values.extend(translations.values())
        needed = {ord(ch) for value in values for ch in value if '\u4e00' <= ch <= '\u9fff'}
        for size in (8, 10, 12, 14, 16, 18):
            header = (FONT / f'notosans_cjk_{size}.h').read_text()
            own = f'notosans_cjk_{size}Intervals'
            covered = ranges(header, own) if f'{own}[]' in header else ranges(common, 'notosans_cjk_commonIntervals')
            self.assertEqual([chr(cp) for cp in sorted(needed) if not any(a <= cp <= b for a, b in covered)], [], size)

    def test_shared_basics_are_not_extended_or_replaced(self):
        cards = json.loads((ROOT / 'data/japanese/kana-basic.json').read_text())['cards']
        self.assertEqual(len(cards), 46)
        self.assertEqual(cards[44][3:6], ['みずをのむ', '喝水', 'mizu o nomu'])
        self.assertEqual(cards[45][3:6], ['ほん', '書', 'hon'])


if __name__ == '__main__':
    unittest.main()
