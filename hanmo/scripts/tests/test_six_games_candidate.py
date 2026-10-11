"""Private six-game source identity/history gates, independent of hardware."""
import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


class SixGamesCandidateTest(unittest.TestCase):
    def test_candidate_has_distinct_hardware_version(self):
        ini = (ROOT / 'platformio.ini').read_text()
        block = ini.split('[env:x4pro_custom]', 1)[1].split('\n[', 1)[0]
        self.assertIn('${crosspoint.version}-hanmo-japanese-lessons-20261008', block)
        self.assertNotIn('-hanmo-kana-sound-20261006', block)
        raw = (ROOT / 'platformio.ini').read_bytes()
        self.assertNotIn(b'\n', raw.replace(b'\r\n', b''))

    def test_history_is_newest_unique_and_honest(self):
        records = json.loads((ROOT / 'docs/custom-change-history-evidence.json').read_text())
        self.assertEqual([r['id'] for r in records[:3]], ['JP_SENTENCES', 'JP_WORDS', 'SIX_GAMES'])
        self.assertEqual(records[2]['date'], '2026-10-07')
        self.assertEqual(len(records), 63)
        self.assertEqual(len({row['id'] for row in records}), 63)
        note = records[2]
        self.assertIn('not saved', note['english'][2])
        self.assertIn('Hardware testing remains outstanding', note['english'][3])
        for ref in note['evidence']:
            self.assertTrue((ROOT / ref).is_file(), ref)
        header = (ROOT / 'src/activities/settings/ChangeHistoryData.h').read_text()
        for suffix in ('TITLE', 'WHAT', 'HOW', 'NOTE'):
            self.assertEqual(header.count(f'StrId::STR_CHANGE_SIX_GAMES_{suffix}'), 1)
        self.assertIn('63 entries', (ROOT / 'docs/custom-change-history.md').read_text().splitlines()[0])


if __name__ == '__main__':
    unittest.main()
