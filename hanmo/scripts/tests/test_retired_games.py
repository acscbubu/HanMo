"""Retired games must be fully absent from the HanMo X4 Pro firmware tree.

MURDLE and TRIVIA used to be retired in place: the sources stayed in
``src/apps_local/`` and three ``build_src_filter`` blocks excluded them. Keeping a
dormant copy is what let the shelf, the settings catalogue, the icon table and
three translation files drift apart, so the user asked for complete removal. The
sources, their build exclusions, their icons and the leftover Trivia preference
must all be gone.

MINESWEEPER is different: it is retired from the Games shelf only and its activity
is still compiled, so nothing here may exclude it from a build.
"""

import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
REMOVED_GAMES = ("murdle", "trivia")
TRANSLATIONS = ("english", "chinese", "chinese-traditional")


class RetiredGamesTest(unittest.TestCase):
    def test_shelf_excludes_retired_murdle_trivia_and_minesweeper(self):
        shelf = (ROOT / "src/apps_local/Shelf.cpp").read_text()
        game_rows = re.search(r"constexpr shelf::Item kGames\[\] = \{(.*?)\n\};", shelf, re.S)
        assert game_rows is not None
        self.assertNotIn('"MURDLE"', game_rows.group(1))
        self.assertNotIn('"TRIVIA"', game_rows.group(1))
        self.assertNotIn('"MINESWEEPER"', game_rows.group(1))
        self.assertNotIn("murdle/MurdleActivity.h", shelf)
        self.assertNotIn("trivia/TriviaActivity.h", shelf)

    def test_removed_game_sources_are_deleted(self):
        for game in REMOVED_GAMES:
            with self.subTest(game=game):
                self.assertFalse(
                    (ROOT / "src/apps_local" / game).exists(),
                    f"src/apps_local/{game}/ must be deleted, not merely excluded",
                )

    def test_no_stale_build_exclusions_remain(self):
        ini = (ROOT / "platformio.ini").read_text()
        for game in REMOVED_GAMES:
            with self.subTest(game=game):
                self.assertNotIn(f"apps_local/{game}/", ini)
        # Minesweeper still ships; it must never gain a build exclusion here.
        self.assertNotIn("-<activities/apps/minesweeper/>", ini)
        # Removing two lines must not drop the inherited filter each env relies on.
        for profile, inherited in (
            ("env:x4pro_custom", "${base.build_src_filter}"),
            ("env:simulator_x4pro_video", "${env:simulator.build_src_filter}"),
        ):
            with self.subTest(profile=profile):
                section = ini.split(f"[{profile}]")[1].split("\n[")[0]
                self.assertIn("build_src_filter =", section)
                self.assertIn(inherited, section.partition("build_src_filter =")[2])
        # The simulator keeps its own unrelated exclusions.
        simulator = ini.split("[env:simulator]")[1].split("\n[")[0]
        self.assertIn("-<network/OtaUpdater.cpp>", simulator)

    def test_legacy_trivia_preference_is_gone(self):
        for rel in ("src/CrossPointSettings.h", "src/SettingsList.h"):
            with self.subTest(path=rel):
                self.assertNotIn("triviaShowUsCentric", (ROOT / rel).read_text())
        for locale in TRANSLATIONS:
            with self.subTest(locale=locale):
                catalog = ROOT / f"lib/I18n/translations/{locale}.yaml"
                self.assertNotIn("STR_TRIVIA_US_CENTRIC", catalog.read_text(encoding="utf-8"))
        # The generated blob must be regenerated, not left holding a dead key.
        keys = (ROOT / "lib/I18n/I18nKeys.h").read_text(encoding="utf-8")
        self.assertNotIn("STR_TRIVIA_US_CENTRIC", keys)

    def test_removed_game_icons_are_gone(self):
        icons = (ROOT / "src/apps_local/ui/ToyboxIcons.h").read_text()
        for game in REMOVED_GAMES:
            with self.subTest(game=game):
                self.assertNotIn(f"icon_{game}", icons)
        # Surviving games must keep theirs.
        self.assertIn("icon_sudoku", icons)


if __name__ == "__main__":
    unittest.main()
