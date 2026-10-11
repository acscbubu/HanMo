"""Release note contract for integrated web locales and Games shelf."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class WebGamesHistoryTest(unittest.TestCase):
    def test_new_integrated_entry_leads_without_displacing_previous_evidence(self):
        records = json.loads((ROOT / 'docs/custom-change-history-evidence.json').read_text())
        ids = [entry['id'] for entry in records]
        lead = ids.index('WEB_GAMES_LOCALE')
        self.assertEqual(ids[lead:lead + 3], [
            'WEB_GAMES_LOCALE', 'AIRNOTE_ITEM_SELECTION', 'AIRPHOTO_VIEW_TOGGLE'])
        # Later same-day web work may lead, but must not displace this entry.
        self.assertTrue(all(entry['date'] >= '2026-09-26' for entry in records[:lead]))
        entry = records[lead]
        self.assertEqual(entry['date'], '2026-09-26')
        self.assertIn('Traditional Chinese', ' '.join(entry['english']))
        self.assertIn('favorite', ' '.join(entry['english']).lower())
        self.assertIn('not yet been verified on hardware', ' '.join(entry['english']).lower())
        self.assertIn('遊戲', ' '.join(entry['traditional']))
        for path in entry['evidence']:
            self.assertTrue((ROOT / path).is_file(), path)
        self.assertIn('STR_CHANGE_WEB_GAMES_LOCALE_TITLE',
                      (ROOT / 'src/activities/settings/ChangeHistoryData.h').read_text())
        document = (ROOT / 'docs/custom-change-history.md').read_text()
        self.assertTrue(document.startswith(f'Latest: {len(records)} entries'))
        self.assertLess(document.index('## 2026-09-26 — Device web locales and Games'),
                        document.index('## 2026-09-26 — AirNote checklist item selection'))


if __name__ == '__main__':
    unittest.main()
