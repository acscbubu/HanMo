"""Host C++ behavior tests for the retained Biscuit Minesweeper rules.

Run in WSL: python3 -m unittest scripts.tests.test_imported_minesweeper -v
The fixture compiles the REAL rules; no firmware globals or fabricated board state.
"""
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/apps_local/imported_minesweeper"

CPP = r'''
#include "imported_minesweeper/ImportedMinesweeperRules.h"
#include <cassert>
#include <initializer_list>
using namespace imported_minesweeper;
struct Candidate { int row = -1, col = -1, mineRow = -1, mineCol = -1, safeRow = -1, safeCol = -1; };
Candidate candidateFor(Board& board) {
    const auto size = board.settings();
    for (int row = 0; row < size.rows; ++row) for (int col = 0; col < size.cols; ++col) {
        if (board.state(row, col) != CellState::Revealed || board.adjacent(row, col) != 1) continue;
        Candidate result; result.row = row; result.col = col;
        int hiddenMines = 0;
        for (int dr = -1; dr <= 1; ++dr) for (int dc = -1; dc <= 1; ++dc) {
            const int nr = row + dr, nc = col + dc;
            if (nr < 0 || nc < 0 || nr >= size.rows || nc >= size.cols ||
                board.state(nr, nc) != CellState::Hidden) continue;
            if (board.isMine(nr, nc)) { result.mineRow = nr; result.mineCol = nc; ++hiddenMines; }
            else { result.safeRow = nr; result.safeCol = nc; }
        }
        if (hiddenMines == 1 && result.safeRow >= 0) return result;
    }
    return {};
}
int main() {
    const auto b0 = profile(Variant::Biscuit, 0);
    const auto b1 = profile(Variant::Biscuit, 1);
    const auto b2 = profile(Variant::Biscuit, 2);
    assert(b0.cols == 8 && b0.rows == 12 && b0.mines == 10);
    assert(b1.cols == 10 && b1.rows == 16 && b1.mines == 25);
    assert(b2.cols == 10 && b2.rows == 16 && b2.mines == 40);
    assert(defaultDifficulty(Variant::Biscuit) == 1);
    Board b;
    b.reset(Variant::Biscuit, 1, 0xB15C017u);
    assert(!b.minesPlaced() && b.flagCount() == 0);
    assert(b.setCursor(0, 0));
    b.move(Direction::Up);
    b.move(Direction::Left);
    assert(b.cursorRow() == 0 && b.cursorCol() == 0);
    const ActionResult first = b.confirm(0);
    assert(first.changed && first.minesPlaced);
    int mineCount = 0;
    for (int row = 0; row < b.settings().rows; ++row) {
        for (int col = 0; col < b.settings().cols; ++col) {
            mineCount += b.isMine(row, col) ? 1 : 0;
            if (row <= 1 && col <= 1) assert(!b.isMine(row, col));
        }
    }
    assert(mineCount == b.settings().mines);
    for (Variant variant : {Variant::Biscuit}) {
        Board board;
        board.reset(variant, defaultDifficulty(variant), 42);
        const int r = board.cursorRow();
        const int c = board.cursorCol();
        assert(board.confirm(500).changed);
        assert(board.isFlagged(r, c));
        assert(board.flagCount() == 1 && !board.minesPlaced());
        assert(board.confirm(500).changed);
        assert(board.flagCount() == 0 && !board.isFlagged(r, c));
        assert(board.confirm(0).changed && board.minesPlaced());
        assert(board.adjacent(r, c) == 0);
    }
    // Upstream Biscuit can place a mine on a pre-flagged cell. This port
    // deliberately avoids that bug without weakening first-reveal 3x3 safety.
    for (Variant variant : {Variant::Biscuit}) {
        for (uint32_t seed = 1; seed < 32; ++seed) {
            Board board;
            board.reset(variant, defaultDifficulty(variant), seed);
            board.setCursor(0, 0);
            assert(board.confirm(500).changed);
            board.setCursor(board.settings().rows / 2, board.settings().cols / 2);
            assert(board.confirm(0).changed);
            assert(!board.isMine(0, 0));
            assert(board.isFlagged(0, 0));
        }
    }
    const BoardGeometry geometry = fitBoard(Rect{12, 64, 456, 600}, 16, 10);
    assert(geometry.pitch >= 12 && geometry.cell == geometry.pitch - 6);
    assert(geometry.x >= 12 && geometry.y >= 64);
    assert(geometry.x + geometry.width() <= 468);
    assert(geometry.y + geometry.height() <= 664);
    int hitRow = -1, hitCol = -1;
    assert(geometry.cellAt(geometry.x, geometry.y, hitRow, hitCol));
    assert(hitRow == 0 && hitCol == 0);
    assert(!geometry.cellAt(geometry.x + geometry.cell, geometry.y, hitRow, hitCol));
    assert(!geometry.cellAt(geometry.x - 1, geometry.y, hitRow, hitCol));
    assert(geometry.cellAt(geometry.x + geometry.width() - 7,
                           geometry.y + geometry.height() - 7, hitRow, hitCol));
    assert(hitRow == 15 && hitCol == 9);
    assert(!geometry.cellAt(geometry.x + geometry.width(), geometry.y, hitRow, hitCol));
    assert(fitBoard(Rect{0, 0, 15, 15}, 16, 10).pitch == 0);
    for (Variant variant : {Variant::Biscuit}) {
        Board board;
        board.reset(variant, defaultDifficulty(variant), 1);
        board.confirm(0);
        Candidate candidate = candidateFor(board);
        assert(candidate.row >= 0);
        board.setCursor(candidate.mineRow, candidate.mineCol);
        assert(board.confirm(500).changed && board.flagCount() == 1);
        board.setCursor(candidate.row, candidate.col);
        const bool chordChanged = board.confirm(0).changed;
        assert(chordChanged == (variant != Variant::Biscuit));
        assert(board.state(candidate.safeRow, candidate.safeCol) ==
               (variant == Variant::Biscuit ? CellState::Hidden : CellState::Revealed));
        board.setCursor(candidate.mineRow, candidate.mineCol);
        const bool unflaggedByTap = board.confirm(0).changed;
        assert(unflaggedByTap == (variant != Variant::Biscuit));
        assert(board.flagCount() == (variant == Variant::Biscuit ? 1 : 0));
    }
}
'''


class ImportedMinesweeperTest(unittest.TestCase):
    def test_activity_factory_contract_and_input_paths(self):
        header = (SOURCE / "ImportedMinesweeperActivity.h").read_text()
        source = (SOURCE / "ImportedMinesweeperActivity.cpp").read_text()
        self.assertIn("#include \"ImportedMinesweeperRules.h\"", header)
        rules = (SOURCE / "ImportedMinesweeperRules.h").read_text()
        for variant in ("Biscuit",):
            self.assertIn(variant, rules)
        self.assertIn("ImportedMinesweeperActivity(GfxRenderer& renderer, MappedInputManager& mappedInput,", header)
        self.assertIn("imported_minesweeper::Variant variant", header)
        self.assertIn("Activity(imported_minesweeper::variantActivityName(variant)", header)
        self.assertIn("MappedInputManager::Button::Confirm", source)
        self.assertIn("MappedInputManager::Button::Back", source)
        self.assertIn("routeTouch(mappedInput, true)", source)
        self.assertIn("InputTouch | fui::InputLongPress", source)
        self.assertIn("UITheme::getInstance()", source)
        self.assertNotIn("MinesweeperStore", source)

    def test_profiles_match_pinned_sources(self):
        with tempfile.TemporaryDirectory(prefix="imported_minesweeper_") as directory:
            cpp = pathlib.Path(directory) / "check.cpp"
            binary = pathlib.Path(directory) / ("check.exe" if os.name == "nt" else "check")
            cpp.write_text(CPP)
            command = [os.environ.get("CXX", "g++"), "-std=c++17", "-Wall", "-Wextra", "-Werror", "-pedantic",
                 "-I", str(ROOT / "src"), "-I", str(ROOT / "src/apps_local"), str(cpp),
                 str(SOURCE / "ImportedMinesweeperRules.cpp"), "-o", str(binary)]
            if pathlib.Path(command[0]).name.lower() in ("cl", "cl.exe"):
                command = [command[0], "/nologo", "/EHsc", "/std:c++17", "/W4", "/WX", "/wd4456",
                           "/I" + str(ROOT / "src/apps_local"), str(cpp),
                           str(SOURCE / "ImportedMinesweeperRules.cpp"), "/Fe" + str(binary)]
            build = subprocess.run(command, cwd=directory, capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            test = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(test.returncode, 0, test.stdout + test.stderr)


if __name__ == "__main__":
    unittest.main()
