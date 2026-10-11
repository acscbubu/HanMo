"""Practice star, check and five circle icons must be legible on monochrome E Ink."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
HEADER = ROOT / 'src/activities/apps/japanese/KanaPracticeIcons.h'


class KanaMarkerIconTests(unittest.TestCase):
    def test_six_bitmaps_are_bounded_and_distinct(self):
        text = HEADER.read_text()
        masks = {}
        for name in ('StarOff', 'StarOn', 'CheckOff', 'CheckOn', 'CircleOff', 'CircleOn'):
            match = re.search(r'k' + name + r'\[\] = \{([^}]+)\}', text)
            self.assertIsNotNone(match, name)
            data = bytes(int(v, 16) for v in re.findall(r'0x[0-9A-Fa-f]{2}', match[1]))
            self.assertEqual(len(data), 72, name)  # 24x24 BW1, three bytes per row
            pixels = [[not bool(data[y * 3 + x // 8] & (0x80 >> (x % 8)))
                       for x in range(24)] for y in range(24)]
            self.assertTrue(any(pixels[12]), name)
            self.assertFalse(pixels[0][0], name)
            masks[name] = pixels
        for shape in ('Star', 'Check', 'Circle'):
            self.assertNotEqual(masks[shape + 'Off'], masks[shape + 'On'])
            self.assertGreater(sum(map(sum, masks[shape + 'On'])),
                               sum(map(sum, masks[shape + 'Off'])))
        self.assertTrue(masks['CircleOn'][12][12])
        self.assertFalse(masks['CircleOff'][12][12])
        self.assertTrue(masks['StarOn'][12][12])
        self.assertFalse(masks['StarOff'][12][12])


if __name__ == '__main__':
    unittest.main()
