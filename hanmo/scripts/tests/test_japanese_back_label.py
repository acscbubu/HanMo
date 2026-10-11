"""The Japanese screens' back row must read as one line.

On the device the back row showed

    « 返回
    應用

because the target sat in the list item's `subtitle`, which the list always
draws on its own line -- so the break happened after 返回 no matter how much
room was left. The row must instead carry a single composed label
(「« 返回應用」, 「« 返回日文學習」) and no subtitle, and with no subtitle left on
that screen the list must stop reserving a second line per row.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'src/activities/apps/japanese/JapaneseLearningActivity.cpp'
HEADER = ROOT / 'src/activities/apps/japanese/JapaneseLearningActivity.h'


class JapaneseBackLabelTests(unittest.TestCase):
    def setUp(self):
        self.source = SOURCE.read_text(encoding='utf-8')
        self.header = HEADER.read_text(encoding='utf-8')

    def test_back_row_label_is_composed_into_one_string(self):
        """Both parts go into one buffer, so the row renders on a single line."""
        self.assertRegex(
            self.source,
            r'snprintf\(\s*backLabel_\.data\(\),\s*backLabel_\.size\(\),\s*"%s%s"',
            'the back label must be composed with snprintf into backLabel_')
        self.assertIn('StrId::STR_BACK', self.source)
        self.assertIn('rows_[0].label = backLabel_.data()', self.source)

    def test_the_target_is_no_longer_a_subtitle(self):
        """A subtitle is drawn on its own line, which is exactly the bug."""
        self.assertNotRegex(
            self.source, r'rows_\[0\]\.subtitle\s*=\s*jpText',
            'the back target must not be a subtitle any more')
        self.assertIn('rows_[0].subtitle = nullptr', self.source)

    def test_both_destinations_still_reach_the_label(self):
        """Top level returns to Apps, a category returns to Japanese Learning."""
        self.assertIn('StrId::STR_APPS_TITLE', self.source)
        self.assertIn('StrId::STR_JP_LEARNING', self.source)
        chooser = re.search(r'category_\s*<\s*0\s*\?\s*StrId::STR_APPS_TITLE\s*:\s*StrId::STR_JP_LEARNING',
                            self.source)
        self.assertIsNotNone(chooser, 'the destination choice must survive the rewrite')

    def test_rows_no_longer_reserve_a_subtitle_line(self):
        """No row on this screen has a subtitle once the label is composed."""
        self.assertEqual(self.source.count('.subtitle = jpText'), 0)
        self.assertRegex(self.source, r'syncListViewport\(screen,\s*props,\s*false\)',
                         'with no subtitles the list must not reserve a second line')

    def test_label_buffer_is_owned_by_the_activity(self):
        """`label` is a const char*, so the composed text needs stable storage."""
        self.assertRegex(self.header, r'std::array<char,\s*\d+>\s*backLabel_',
                         'backLabel_ must be a member buffer, not a local')
        size = int(re.search(r'std::array<char,\s*(\d+)>\s*backLabel_', self.header).group(1))
        # "« 返回" is 9 bytes and the longest target 日文學習 is 12, plus the NUL.
        self.assertGreaterEqual(size, 22, 'buffer must hold the arrow, 返回 and the longest target')

    def test_no_literal_newline_is_used_to_lay_the_row_out(self):
        self.assertNotIn('返回\\n', self.source)


if __name__ == '__main__':
    unittest.main()
