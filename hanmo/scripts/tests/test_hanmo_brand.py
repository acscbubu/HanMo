"""Guard the public display identity without changing protocol identifiers."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[2]
class HanMoBrandTest(unittest.TestCase):
    def test_translated_default_and_reset(self):
        values = {'english': ('HanMo', 'An empty name restores HanMo.'), 'chinese': ('翰墨', '名称留空使用翰墨。'), 'chinese-traditional': ('翰墨', '名稱留空使用翰墨。')}
        for locale, (name, instruction) in values.items():
            with self.subTest(locale=locale):
                text = (ROOT / 'lib/I18n/translations' / (locale + '.yaml')).read_text()
                self.assertIn(f'STR_CROSSPOINT: "{name}"', text)
                self.assertIn(instruction, text)
    def test_device_webpage_defaults(self):
        pages = ROOT / 'src/network/html'
        for locale, brand in [('en', 'HanMo'), ('zh-CN', '翰墨')]:
            for name in ('HomePage', 'SettingsPage', 'FilesPage', 'FontsPage'):
                with self.subTest(locale=locale, name=name):
                    text = (pages / locale / (name + '.html')).read_text()
                    self.assertIn(brand, text)
                    self.assertNotIn('CrossMux', text)
                    self.assertNotIn('CrossPoint Reader', text)
    def test_ota_and_board_identity_unchanged(self):
        board = (ROOT / 'src/network/FirmwareBoardTag.cpp').read_text()
        self.assertIn('CROSSPOINT-BOARD-V1:', board)
        endpoint = (ROOT / 'src/network/CrossMuxEndpoints.h').read_text()
        self.assertIn('crossmux.com', endpoint)
if __name__ == '__main__':
    unittest.main()
