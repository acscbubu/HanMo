"""Six-game identities and real monochrome icon assets, independent of HAL."""
import pathlib
import re
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
GAMES = (
    ("memory", "MEMORY MATCH", "MemoryActivity"),
    ("reversi", "REVERSI", "ReversiActivity"),
    ("slidepuzzle", "SLIDE PUZZLE", "SlidePuzzleActivity"),
    ("mahjong", "MAHJONG SOLITAIRE", "MahjongActivity"),
    ("backgammon", "BACKGAMMON", "BackgammonActivity"),
    ("tilerummy", "TILE RUMMY", "TileRummyActivity"),
)
OLD_TITLES = [
    "CHESS", "BATTLESHIP", "CONNECTIONS", "SOLITAIRE", "D&DIAGRAMS",
    "INSIDER", "JAIPUR", "SEA SALT", "CHECKERS", "CONNECT FOUR", "YAHTZEE",
    "KNUCKLEBONES", "PICROSS", "TOY BATTLE", "FOREHEAD", "WAVELENGTH", "GO",
    "SUDOKU", "GOMOKU", "SOKOBAN", "CHINESE CHESS", "2048", "PIXEL SWITCH",
    "MINESWEEPER BISCUIT", "MEMORY MATCH",
]


def registry():
    text = (ROOT / "src/apps_local/Shelf.cpp").read_text()
    match = re.search(r"constexpr shelf::Item kGames\[\] = \{(.*?)\n\};", text, re.S)
    if not match:
        raise AssertionError("actual Games registry not found")
    rows = re.findall(r'(\{"([^"\n]+)",\s*(&[^,]+),\s*(&[^}]+)\})', match.group(1))
    return text, rows


class SixGamesShelfTest(unittest.TestCase):
    def test_original_persisted_identities_keep_their_order(self):
        _, rows = registry()
        new_titles = {title for _, title, _ in GAMES[1:]}
        self.assertEqual([title for _, title, _, _ in rows if title not in new_titles], OLD_TITLES)
        self.assertFalse({"MURDLE", "TRIVIA"} & {title for _, title, _, _ in rows})
        prefs = (ROOT / "src/apps_local/ShelfGamePrefs.h").read_text()
        capacity = int(re.search(r"kMaxGames\s*=\s*(\d+)", prefs).group(1))
        self.assertLessEqual(len(rows), capacity)
        raw = (ROOT / "src/apps_local/Shelf.cpp").read_bytes()
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""), "Shelf CRLF must remain intact")

    def test_each_requested_game_has_exactly_one_wired_row(self):
        text, rows = registry()
        for name, title, activity in GAMES:
            with self.subTest(game=name):
                actual = [(icon, factory) for _, found, icon, factory in rows if found == title]
                self.assertEqual(actual, [(f"&icon_{name}_32", f"&{activity}::create")])
                self.assertEqual(text.count(f'#include "{name}/{activity}.h"'), 1)

    def test_each_icon_has_bounded_distinct_ink_at_both_sizes(self):
        text = (ROOT / "src/apps_local/ui/ToyboxIcons.h").read_text()
        if '#include "SixGameIcons.h"' in text:
            text += (ROOT / "src/apps_local/ui/SixGameIcons.h").read_text()
        for size in (24, 32):
            seen = set()
            for name, _, _ in GAMES:
                with self.subTest(game=name, size=size):
                    match = re.search(rf"static const uint8_t icon_{name}_{size}_bits\[\]\s*=\s*\{{(.*?)\}};", text, re.S)
                    self.assertIsNotNone(match, f"missing {name} {size}px bitmap")
                    tokens = [s.strip() for s in match.group(1).split(",") if s.strip()]
                    self.assertTrue(all(re.fullmatch(r"0x[0-9A-Fa-f]{2}", s) for s in tokens))
                    data = bytes(int(s, 16) for s in tokens)
                    stride = (size + 7) // 8
                    self.assertEqual(len(data), size * stride)
                    ink = [(x, y) for y in range(size) for x in range(size)
                           if not (data[y * stride + x // 8] & (0x80 >> (x % 8)))]
                    self.assertTrue(ink, "blank icon")
                    self.assertTrue(all(0 < x < size - 1 and 0 < y < size - 1 for x, y in ink))
                    definition = re.search(rf"static const freeink::Icon icon_{name}_{size}\s*=\s*\{{\s*{size},\s*{size},\s*(\d+),\s*icon_{name}_{size}_bits\s*\}};", text)
                    self.assertIsNotNone(definition)
                    self.assertLessEqual(abs(int(definition.group(1)) - sum(y for _, y in ink) / len(ink)), 1)
                    self.assertNotIn(data, seen, "new game cannot borrow another game's identity mark")
                    seen.add(data)

    def test_real_icon_header_compiles_into_usable_assets(self):
        cases = "\n".join(
            f"static_assert(sizeof(icon_{name}_{size}_bits) == {size} * {(size + 7) // 8}, \"packed mask\");"
            for name, _, _ in GAMES for size in (24, 32)
        )
        checks = "\n".join(
            f"assert(icon_{name}_{size}.bits == icon_{name}_{size}_bits);"
            for name, _, _ in GAMES for size in (24, 32)
        )
        source = '#include "ToyboxIcons.h"\n#include <cassert>\n' + cases + '\nint main(){\n' + checks + '\n}\n'
        with tempfile.TemporaryDirectory(prefix="six-games-icons-") as directory:
            source_path = pathlib.Path(directory) / "icons.cpp"
            source_path.write_text(source)
            binary = pathlib.Path(directory) / "icons"
            result = subprocess.run([
                "g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                "-I", str(ROOT / "freeink-sdk/libs/assets/Icons/include"),
                "-I", str(ROOT / "src/apps_local/ui"), str(source_path), "-o", str(binary),
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
