import datetime
import json
import pathlib
import re
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]

class CustomChangeHistoryTest(unittest.TestCase):
    def test_notes_match_translations_and_evidence(self):
        records = json.loads((ROOT / 'docs/custom-change-history-evidence.json').read_text())
        dates = [datetime.date.fromisoformat(r['date']) for r in records]
        self.assertEqual(dates, sorted(dates, reverse=True))
        self.assertEqual(len({r['id'] for r in records}), len(records))
        header = (ROOT / 'src/activities/settings/ChangeHistoryData.h').read_text()
        self.assertEqual(header.count('_TITLE'), len(records))
        for locale, field in [('english', 'english'), ('chinese', 'simplified'),
                              ('chinese-traditional', 'traditional')]:
            translations = {}
            for line in (ROOT / f'lib/I18n/translations/{locale}.yaml').read_text().splitlines():
                if line.startswith('STR_CHANGE_'):
                    key, value = line.split(': ', 1)
                    translations[key] = json.loads(value)
            for entry in records:
                for suffix, text in zip(['TITLE', 'WHAT', 'HOW', 'NOTE'], entry[field]):
                    key = f'STR_CHANGE_{entry["id"]}_{suffix}'
                    self.assertEqual(translations[key], text)
                    self.assertIn('StrId::' + key, header)

    @unittest.skipUnless((ROOT / '.git').exists(), 'Portable source has no Git object database')
    def test_historical_commit_objects(self):
        records = json.loads((ROOT / 'docs/custom-change-history-evidence.json').read_text())
        for entry in records:
            for ref in entry['evidence']:
                if re.fullmatch(r'[0-9a-f]{7}', ref):
                    subprocess.run(['git', 'cat-file', '-e', ref + '^{commit}'], cwd=ROOT, check=True)

    def test_new_20260926_entries_are_newest_and_truthful(self):
        records = json.loads((ROOT / 'docs/custom-change-history-evidence.json').read_text())
        ids = [entry['id'] for entry in records]
        self.assertIn('AIRPHOTO_FILENAME_LIST', ids)
        photo_index = ids.index('AIRPHOTO_FILENAME_LIST')
        self.assertEqual([(entry['id'], entry['date']) for entry in records[photo_index:photo_index + 2]], [
            ('AIRPHOTO_FILENAME_LIST', '2026-09-26'),
            ('AIRNOTE_BULK_SELECTION', '2026-09-26'),
        ])
        self.assertLess(photo_index + 1, ids.index('AIRPHOTO_GALLERY'))
        # Later same-day entries may sit above these two; nothing older may.
        self.assertTrue(all(entry['date'] >= '2026-09-26' for entry in records[:photo_index]))
        photo, notes = records[photo_index:photo_index + 2]
        self.assertIn('filename list by default', photo['english'][1])
        self.assertIn('grid remains optional', photo['english'][1])
        self.assertIn('does not open or decode photos or build thumbnails', photo['english'][2])
        self.assertIn('speed has not been measured on hardware', photo['english'][3])
        self.assertIn('on the device or its web page', notes['english'][1])
        self.assertIn('as a group in their existing order', notes['english'][2])
        self.assertIn('existing SD folder', notes['english'][2])
        self.assertIn('deletion asks for confirmation', notes['english'][3])
        self.assertIn('No on-device hardware verification', notes['english'][3])
        self.assertIn('檔名清單', photo['traditional'][0])
        self.assertIn('文件名列表', photo['simplified'][0])
        self.assertIn('多選筆記', notes['traditional'][0])
        self.assertIn('多选笔记', notes['simplified'][0])
        for entry in (photo, notes):
            for ref in entry['evidence']:
                self.assertTrue((ROOT / ref).is_file(), ref)
        header = (ROOT / 'src/activities/settings/ChangeHistoryData.h').read_text()
        titles = re.findall(r'StrId::STR_CHANGE_([A-Z_]+)_TITLE', header)
        self.assertEqual(titles.index('AIRNOTE_BULK_SELECTION'), titles.index('AIRPHOTO_FILENAME_LIST') + 1)
        self.assertLess(titles.index('AIRNOTE_BULK_SELECTION'), titles.index('AIRPHOTO_GALLERY'))
        doc = (ROOT / 'docs/custom-change-history.md').read_text()
        self.assertTrue(doc.startswith(f'Latest: {len(records)} entries'))
        self.assertLess(doc.index('## 2026-09-26 — AirPhoto default filename list'),
                        doc.index('## 2026-09-26 — AirNote bulk note selection'))
        self.assertLess(doc.index('## 2026-09-26 — AirNote bulk note selection'),
                        doc.index('## 2026-09-25 — AirPhoto photo gallery'))

    def test_item_selection_and_view_toggle_entries_lead_the_history(self):
        records = json.loads((ROOT / 'docs/custom-change-history-evidence.json').read_text())
        ids = [entry['id'] for entry in records]
        at = ids.index('AIRNOTE_ITEM_SELECTION')
        self.assertEqual([(entry['id'], entry['date']) for entry in records[at:at + 2]], [
            ('AIRNOTE_ITEM_SELECTION', '2026-09-26'),
            ('AIRPHOTO_VIEW_TOGGLE', '2026-09-26'),
        ])
        # Only later same-day work may sit above them.
        self.assertTrue(all(entry['date'] >= '2026-09-26' for entry in records[:at]))
        items, toggle = records[at:at + 2]
        self.assertIn('Select several checklist items inside one note', items['english'][1])
        self.assertIn('Delete selected', items['english'][2])
        self.assertIn('device web page', items['english'][2])
        self.assertIn('keeps at least one item', items['english'][3])
        self.assertIn('No on-device hardware verification', items['english'][3])
        self.assertIn('事項多選刪除', items['traditional'][0])
        self.assertIn('事项多选删除', items['simplified'][0])
        self.assertIn('icon with its label and no box', toggle['english'][1])
        self.assertIn('filename list and the thumbnail grid', toggle['english'][2])
        self.assertIn('Not verified on hardware yet', toggle['english'][3])
        self.assertIn('改成圖示加文字', toggle['traditional'][1])
        self.assertIn('改成图标加文字', toggle['simplified'][1])
        self.assertIn('smaller', toggle['english'][1])
        self.assertIn('字小一點', toggle['traditional'][1])
        self.assertIn('字小一点', toggle['simplified'][1])
        self.assertIn('row under the items', items['english'][2])
        self.assertIn('事項下方', items['traditional'][2])
        self.assertIn('事项下方', items['simplified'][2])
        for entry in (items, toggle):
            self.assertTrue(entry['evidence'])
            for ref in entry['evidence']:
                self.assertTrue((ROOT / ref).is_file(), ref)
        header = (ROOT / 'src/activities/settings/ChangeHistoryData.h').read_text()
        titles = re.findall(r'StrId::STR_CHANGE_([A-Z_]+)_TITLE', header)
        row = titles.index('AIRNOTE_ITEM_SELECTION')
        self.assertEqual(titles[row:row + 2], ['AIRNOTE_ITEM_SELECTION', 'AIRPHOTO_VIEW_TOGGLE'])
        web = titles.index('AIRPHOTO_WEB_GALLERY')
        self.assertEqual(titles[web:web + 2], ['AIRPHOTO_WEB_GALLERY', 'AIRNOTE_WEB_ACTIONS_TOP'])
        self.assertLess(web, row)
        doc = (ROOT / 'docs/custom-change-history.md').read_text()
        self.assertTrue(doc.startswith(f'Latest: {len(records)} entries'))
        self.assertLess(doc.index('## 2026-09-26 — AirNote checklist item selection'),
                        doc.index('## 2026-09-26 — AirPhoto view toggle'))
        self.assertLess(doc.index('## 2026-09-26 — AirPhoto view toggle'),
                        doc.index('## 2026-09-26 — AirPhoto default filename list'))

    def test_actual_cjk_fonts_cover_every_history_character(self):
        records = json.loads((ROOT / 'docs/custom-change-history-evidence.json').read_text())
        needed = {ord(c) for entry in records for locale in ['traditional', 'simplified']
                  for text in entry[locale] for c in text if '一' <= c <= '鿿'}
        # Use emitted Unicode intervals, not the input charset: the source font
        # can silently omit requested glyphs that it does not provide.
        common = (ROOT / 'lib/EpdFont/builtinFonts/notosans_cjk_common_intervals.h').read_text()
        for size in [8, 10, 12, 14, 16, 18]:
            font = (ROOT / f'lib/EpdFont/builtinFonts/notosans_cjk_{size}.h').read_text()
            intervals = common if 'notosans_cjk_commonIntervals,' in font else font
            ranges = [(int(a, 16), int(b, 16)) for a, b in
                      re.findall(r'\{\s*(0x[0-9A-Fa-f]+),\s*(0x[0-9A-Fa-f]+),\s*0x[0-9A-Fa-f]+\s*\}', intervals)]
            self.assertTrue(ranges)
            missing = sorted(c for c in needed if not any(a <= c <= b for a, b in ranges))
            self.assertEqual(missing, [], f'{size}pt missing: '+''.join(map(chr, missing)))

if __name__ == '__main__':
    unittest.main()
