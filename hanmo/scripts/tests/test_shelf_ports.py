"""Shelf retains Biscuit and removes CrossPet, not retired Minesweeper variants."""

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


class IsolatedReleaseShelfTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shelf = (ROOT / "src/apps_local/Shelf.cpp").read_text()
        match = re.search(r"constexpr shelf::Item kGames\[\] = \{(.*?)\n\};", cls.shelf, re.S)
        assert match is not None
        cls.rows = match.group(1)

    def test_biscuit_remains_without_pet_or_retired_minesweeper(self):
        self.assertEqual(0, self.rows.count('"MINESWEEPER"'))
        for label in ('"MINESWEEPER CROSSPET"', '"MINESWEEPER CROSSTHINK"'):
            with self.subTest(label=label):
                self.assertNotIn(label, self.rows)
        self.assertEqual(1, self.rows.count('"MINESWEEPER BISCUIT"'))
        self.assertIn('&makeBiscuitMinesweeper', self.rows)
        self.assertNotIn('CrossPetCompanionActivity.h', self.shelf)
        self.assertEqual(0, self.rows.count('"CROSSPET PET"'))
        self.assertNotIn('&make<CrossPetCompanionActivity>', self.rows)
        for factory in ('makeCrossPetMinesweeper', 'makeCrossThinkMinesweeper'):
            with self.subTest(factory=factory):
                self.assertNotIn(factory, self.shelf)
        self.assertFalse((ROOT / 'src/apps_local/crosspet_companion/CrossPetCore.h').exists())
        self.assertFalse((ROOT / 'src/apps_local/crosspet_companion/CrossPetPersistence.cpp').exists())
        self.assertTrue((ROOT / 'src/apps_local/imported_minesweeper/ImportedMinesweeperActivity.cpp').exists())
        self.assertTrue((ROOT / 'src/apps_local/imported_minesweeper/ImportedMinesweeperRules.cpp').exists())

    def test_original_game_order_remains_stable(self):
        old_titles = [
            '"CHESS"', '"BATTLESHIP"', '"CONNECTIONS"', '"SOLITAIRE"',
            '"D&DIAGRAMS"', '"INSIDER"', '"JAIPUR"', '"SEA SALT"',
            '"CHECKERS"', '"CONNECT FOUR"', '"YAHTZEE"', '"KNUCKLEBONES"',
            '"PICROSS"', '"TOY BATTLE"', '"FOREHEAD"', '"WAVELENGTH"', '"GO"',
            '"SUDOKU"', '"GOMOKU"', '"SOKOBAN"',
            '"CHINESE CHESS"', '"2048"', '"PIXEL SWITCH"',
            '"MINESWEEPER BISCUIT"', '"CROSSPET PET"',
        ]
        positions = [self.rows.index(title) for title in old_titles if title in self.rows]
        self.assertEqual(positions, sorted(positions))

    def test_old_game_and_retired_games_unchanged(self):
        self.assertNotIn("&make<MinesweeperMenuActivity>", self.rows)
        self.assertNotIn('"MURDLE"', self.rows)
        self.assertNotIn('"TRIVIA"', self.rows)
        old_store = (ROOT / "src/activities/apps/minesweeper/MinesweeperStore.cpp").read_text()
        self.assertIn("minesweeper", old_store.lower())

    def test_shelf_titles_fit_wake_and_hidden_file(self):
        state = (ROOT / "src/apps_local/ShelfState.h").read_text()
        match = re.search(r"MAX_ITEM_TITLE\s*=\s*(\d+)", state)
        assert match is not None
        limit = int(match.group(1))
        titles = re.findall(r'\{"([^"\n]+)",\s*&', self.rows)
        self.assertEqual(len(titles), len(set(titles)))
        self.assertTrue(all(len(title) <= limit for title in titles))


if __name__ == "__main__":
    unittest.main()
