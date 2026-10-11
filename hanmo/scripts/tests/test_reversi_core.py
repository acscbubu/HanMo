"""Compile the actual Reversi rules with host g++ and play real positions through them.

Freestanding core, same shape as connectfour/ConnectFourCore.h: no renderer, no
Activity, no storage, so the rules can be driven directly from a host harness.
"""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
GAME_DIR = ROOT / "src/apps_local/reversi"

HARNESS = r'''
#include "ReversiCore.h"

#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>

using namespace reversi;

// Lay out a board from eight strings, row 0 first: '.' empty, 'O' light, 'X' dark.
// Reading a position as text is the only way these tests stay auditable; a
// sequence of cell assignments hides which shape is being tested.
static void layout(Game& game, const char* rows[kSize], uint8_t turn) {
  for (int row = 0; row < kSize; ++row) {
    assert(std::strlen(rows[row]) == static_cast<size_t>(kSize));
    for (int column = 0; column < kSize; ++column) {
      const char glyph = rows[row][column];
      game.cell[column][row] = glyph == 'O' ? kLight : glyph == 'X' ? kDark : kEmpty;
    }
  }
  game.lastColumn = kNoCell;
  game.lastRow = kNoCell;
  game.turn = turn;
  game.outcome = Outcome::Running;
}

int main(int argc, char** argv) {
  assert(argc == 2);
  const std::string scenario = argv[1];

  if (scenario == "opening") {
    Game game;
    start(game);
    // The standard Othello opening: the four central cells, light on one
    // diagonal and dark on the other. Nothing else on the board.
    assert(game.cell[3][3] == kLight);
    assert(game.cell[4][4] == kLight);
    assert(game.cell[3][4] == kDark);
    assert(game.cell[4][3] == kDark);
    assert(discCount(game, kLight) == 2);
    assert(discCount(game, kDark) == 2);
    assert(discCount(game, kEmpty) == kCells - 4);
    // Dark opens. This is the rule of the game, not a coin flip.
    assert(game.turn == kDark);
    assert(game.outcome == Outcome::Running);
    assert(!over(game));
    // Nothing has been played, so there is no last move to point at.
    assert(game.lastColumn == kNoCell && game.lastRow == kNoCell);
    puts("opening position OK");

  } else if (scenario == "legality") {
    Game game;
    start(game);
    // From the opening, dark has exactly four legal moves -- the four cells that
    // pin a light disc against a dark one. Any other empty cell captures
    // nothing and so is not a move at all.
    assert(legalAt(game, 3, 2));
    assert(legalAt(game, 2, 3));
    assert(legalAt(game, 5, 4));
    assert(legalAt(game, 4, 5));
    assert(legalMoveCount(game, kDark) == 4);
    // Occupied cells, empty cells that capture nothing, and off-board
    // coordinates are all equally not moves.
    assert(!legalAt(game, 3, 3));
    assert(!legalAt(game, 0, 0));
    assert(!legalAt(game, -1, 4));
    assert(!legalAt(game, kSize, 4));

    // A run of two is captured; a run broken by a gap is not. Both cases live on
    // one board so a direction scan that forgets to stop at an empty cell cannot
    // pass.
    const char* rows[kSize] = {
        "........",
        "........",
        "........",
        ".XOO.O.X",
        "........",
        "........",
        "........",
        "........",
    };
    layout(game, rows, kDark);
    // (4,3) pins OO against the dark disc at (1,3).
    assert(legalAt(game, 4, 3));
    // (6,3) sits beside a single light disc whose far side is empty, not dark.
    assert(!legalAt(game, 6, 3));
    puts("legal moves must capture OK");

  } else if (scenario == "play") {
    Game game;
    start(game);
    // Dark opens at (3,2), pinning the light disc at (3,3) against (3,4).
    assert(play(game, 3, 2));
    assert(game.cell[3][2] == kDark);
    assert(game.cell[3][3] == kDark);  // flipped
    assert(discCount(game, kDark) == 4);
    assert(discCount(game, kLight) == 1);
    assert(game.lastColumn == 3 && game.lastRow == 2);
    // Light can answer, so the turn simply changes hands.
    assert(game.turn == kLight);
    assert(game.outcome == Outcome::Running);

    // An illegal move must change nothing at all -- not the board, not the turn,
    // not the last-move marker. A caller routes a tap straight here, so every
    // miss on an eight-by-eight grid lands on this path.
    const Game before = game;
    assert(!play(game, 0, 0));
    assert(std::memcmp(&before, &game, sizeof(Game)) == 0);

    // One move flips two rays at once: upward and rightward, each a run of two.
    // A flip loop that stops after the first productive direction fails here.
    const char* rows[kSize] = {
        "........",
        "....X...",
        "....O...",
        "....O...",
        ".....OOX",
        "........",
        "........",
        "O.......",
    };
    layout(game, rows, kDark);
    assert(capturedBy(game, 4, 4, kDark) == 4);
    assert(play(game, 4, 4));
    assert(game.cell[4][4] == kDark);
    assert(game.cell[4][3] == kDark && game.cell[4][2] == kDark);  // upward run
    assert(game.cell[5][4] == kDark && game.cell[6][4] == kDark);  // rightward run
    // The discs that CLOSED each run were already dark and stay dark.
    assert(game.cell[4][1] == kDark && game.cell[7][4] == kDark);
    // The stray light disc in the corner is on no ray and must be untouched.
    assert(game.cell[0][7] == kLight);
    assert(discCount(game, kDark) == 7);
    assert(discCount(game, kLight) == 1);
    puts("placing a disc flips every pinned run OK");

  } else if (scenario == "ending") {
    Game game;

    // Light has no move here, dark has two. Light's single disc at (4,0) caps the
    // dark run on its left, and the cell that would close that run for light is
    // off the board -- that edge is the only thing making the position
    // asymmetric, which is why passing needs a hand-built board to test at all.
    const char* stuck[kSize] = {
        ".OOXO...",
        "........",
        "........",
        "........",
        "........",
        "........",
        "........",
        "........",
    };
    layout(game, stuck, kDark);
    assert(legalMoveCount(game, kLight) == 0);
    assert(legalMoveCount(game, kDark) == 2);

    // Dark plays the left-hand one. Light still cannot answer, so the turn comes
    // STRAIGHT BACK to dark instead of stalling on a side with nothing to do.
    assert(play(game, 0, 0));
    assert(game.cell[1][0] == kDark && game.cell[2][0] == kDark);
    assert(legalMoveCount(game, kLight) == 0);
    assert(game.turn == kDark);
    assert(game.outcome == Outcome::Running);
    assert(!over(game));

    // Dark's next move takes the last light disc. With nothing left to capture
    // neither side can move, so the game ends on disc count rather than waiting
    // for the board to fill -- most Reversi games end with empty cells.
    assert(play(game, 5, 0));
    assert(discCount(game, kLight) == 0);
    assert(discCount(game, kDark) == 6);
    assert(over(game));
    assert(game.outcome == Outcome::DarkWins);
    assert(discCount(game, kEmpty) > 0);

    // A finished game refuses further moves and keeps its result.
    const Game finished = game;
    assert(!play(game, 6, 0));
    assert(!legalAt(game, 6, 0));
    assert(std::memcmp(&finished, &game, sizeof(Game)) == 0);

    // Equal armies with no move available to either side is a draw. The discs
    // are spread so no two of them touch, so no placement can pin anything.
    const char* frozen[kSize] = {
        "X.......",
        "........",
        "O.......",
        "........",
        "X.......",
        "........",
        "O.......",
        "........",
    };
    layout(game, frozen, kDark);
    // settle() is what play() ends with, and a position can already be terminal
    // before anyone moves -- a game restored from storage has to run it too.
    settle(game);
    assert(over(game));
    assert(game.outcome == Outcome::Draw);
    assert(discCount(game, kDark) == 2 && discCount(game, kLight) == 2);

    // The larger army wins regardless of which side it belongs to: the same
    // frozen shape with one disc recoloured hands it to light.
    const char* frozenLight[kSize] = {
        "O.......",
        "........",
        "O.......",
        "........",
        "X.......",
        "........",
        "O.......",
        "........",
    };
    layout(game, frozenLight, kDark);
    settle(game);
    assert(over(game));
    assert(game.outcome == Outcome::LightWins);
    puts("passing, winning on count and drawing OK");
  } else {
    std::fprintf(stderr, "unknown scenario %s\n", scenario.c_str());
    return 1;
  }
  return 0;
}
'''


class ReversiCoreTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        harness = pathlib.Path(cls.tmp.name) / "reversi_core_test.cpp"
        harness.write_text(HARNESS)
        cls.exe = pathlib.Path(cls.tmp.name) / "reversi_core_test"
        subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                        "-I", str(GAME_DIR), str(harness),
                        "-o", str(cls.exe)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_opening_position_is_the_standard_four_discs_with_dark_to_move(self):
        subprocess.run([str(self.exe), "opening"], check=True)

    def test_a_legal_move_must_capture_and_a_broken_run_captures_nothing(self):
        subprocess.run([str(self.exe), "legality"], check=True)

    def test_playing_flips_every_pinned_run_and_an_illegal_move_changes_nothing(self):
        subprocess.run([str(self.exe), "play"], check=True)

    def test_a_stuck_side_passes_and_the_bigger_army_wins_when_both_are_stuck(self):
        subprocess.run([str(self.exe), "ending"], check=True)


if __name__ == "__main__":
    unittest.main()
