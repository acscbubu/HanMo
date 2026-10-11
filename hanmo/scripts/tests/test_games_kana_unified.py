"""A single X4 Pro candidate must route to both six games and latest kana."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
J = ROOT / 'src/activities/apps/japanese'
SHELF = ROOT / 'src/apps_local/Shelf.cpp'
VERSION = '${crosspoint.version}-hanmo-japanese-lessons-20261008'


class GamesKanaUnifiedTests(unittest.TestCase):
    def test_x4pro_custom_uses_a_new_single_candidate_version(self):
        ini = (ROOT / 'platformio.ini').read_text()
        custom = ini.split('[env:x4pro_custom]', 1)[1].split('\n[', 1)[0]
        self.assertIn(f'-DCROSSPOINT_VERSION=\\\"{VERSION}\\\"', custom)
        self.assertNotIn('hanmo-six-games-20261007', custom)
        self.assertNotIn('hanmo-kana-stroke-sound-hint-20261007', custom)

    def test_games_and_real_japanese_lessons_are_routed_in_one_source(self):
        shelf = SHELF.read_text()
        for title, factory in (
            ('MEMORY MATCH', 'MemoryActivity'), ('REVERSI', 'ReversiActivity'),
            ('SLIDE PUZZLE', 'SlidePuzzleActivity'), ('MAHJONG SOLITAIRE', 'MahjongActivity'),
            ('BACKGAMMON', 'BackgammonActivity'), ('TILE RUMMY', 'TileRummyActivity'),
        ):
            self.assertRegex(shelf, rf'\{{"{title}",\s*&icon_[a-z]+_32,\s*&{factory}::create\}}')
        self.assertNotIn('"MURDLE"', shelf)
        self.assertNotIn('"TRIVIA"', shelf)
        menu = (J / 'JapaneseLearningActivity.cpp').read_text()
        for lesson in ('KanaGroupsActivity', 'KanaStrokeActivity', 'KanaQuizActivity', 'KanaSimilarActivity'):
            self.assertIn(f'startActivityForResultWith<{lesson}>', menu)
        stroke = (J / 'KanaStrokeActivity.cpp').read_text()
        self.assertIn('kana::formatSoundReading(basicCard, soundReading_)', stroke)
        self.assertIn('centerReadingInColumn', stroke)
        self.assertIn('selectScript(lesson_', stroke)
        self.assertNotIn('KanaPracticeStore', stroke)
        self.assertTrue((J / 'KanaStroke.generated.h').is_file())
        self.assertTrue((J / 'KanaSoundReading.h').is_file())

    def test_46_card_sound_hint_parity_not_example_meaning(self):
        import json
        cards = json.loads((ROOT / 'data/japanese/kana-basic.json').read_text(encoding='utf-8'))['cards']
        self.assertEqual(len(cards), 46)
        self.assertEqual((cards[0][2], cards[0][4], cards[0][6]), ('a', '雨', '阿'))
        self.assertTrue(all(len(card) == 7 and card[6] for card in cards))
        source = (J / 'KanaSoundReading.h').read_text()
        self.assertIn('card.soundHint', source)
        self.assertIn('card.romaji', source)
        self.assertNotIn('card.meaning', source)


if __name__ == '__main__':
    unittest.main()
