"""Compile the actual Memory Match rules with host g++ and drive real boards through them.

Freestanding core, same shape as reversi/ReversiCore.h: no renderer, no Activity,
no storage, and -- the point of this one -- no clock and no implicit RNG, so a
host harness can assert an exact shuffled layout and step the mismatch state
machine by hand.
"""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
GAME_DIR = ROOT / "src/apps_local/memory"

HARNESS = r'''
#include "MemoryCore.h"

#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>

using namespace memorymatch;

// Every pair id on the board appears exactly twice and nothing else appears at
// all. This is the property a shuffle must never break, and unlike the golden
// layouts below it survives anyone retuning the generator on purpose.
static void assertDealtInPairs(const Game& game) {
  int seen[kMaxPairs] = {0};
  for (int i = 0; i < cellCount(game); ++i) {
    const int face = game.face[i];
    assert(face >= 0 && face < pairCount(game));
    ++seen[face];
  }
  for (int face = 0; face < pairCount(game); ++face) assert(seen[face] == 2);
}

static void assertFaces(const Game& game, const uint8_t* expected, const int count) {
  assert(cellCount(game) == count);
  for (int i = 0; i < count; ++i) assert(game.face[i] == expected[i]);
  // Cells past the end of this level are not part of the board at all, so a
  // renderer that walks the whole kMaxCells buffer can tell them apart instead
  // of drawing a stale card left by a bigger level.
  for (int i = count; i < kMaxCells; ++i) {
    assert(game.face[i] == kNoFace);
    assert(!onBoard(game, i));
  }
}

// Whole-state equality, field by field rather than one memcmp of the struct,
// because padding bytes a copy need not reproduce would turn into a failure
// blamed on the rules. Used for the "changes nothing" assertions: the caller
// routes every raw tap at these functions, so a refused tap must leave the game
// exactly as it was.
static bool identical(const Game& a, const Game& b) {
  if (std::memcmp(a.face, b.face, sizeof(a.face)) != 0) return false;
  if (std::memcmp(a.matched, b.matched, sizeof(a.matched)) != 0) return false;
  return a.firstPick == b.firstPick && a.secondPick == b.secondPick && a.moves == b.moves &&
         a.matchedPairs == b.matchedPairs && a.level == b.level && a.phase == b.phase;
}

// Match every pair with no wasted attempt, by reading the dealt faces. Written
// against the board rather than a fixed index order so one routine solves any
// level in the table, which is the only way the hardest grid gets tested too.
static void solvePerfectly(Game& game) {
  for (int face = 0; face < pairCount(game); ++face) {
    int first = kNoCell;
    int second = kNoCell;
    for (int i = 0; i < cellCount(game); ++i) {
      if (game.face[i] != face) continue;
      if (first == kNoCell)
        first = i;
      else
        second = i;
    }
    assert(first != kNoCell && second != kNoCell);
    assert(expose(game, first));
    assert(expose(game, second));
    // A pair found in one attempt never parks the game in a mismatch.
    assert(!awaitingMismatch(game));
  }
}

int main(int argc, char** argv) {
  assert(argc == 2);
  const std::string scenario = argv[1];

  if (scenario == "levels") {
    // The device owner's requirement, as assertions: at least four named
    // levels, the easiest about twelve cards, the hardest at least thirty.
    assert(kLevelCount >= 4);
    assert(cellsIn(kLevels[0]) <= 12);
    assert(cellsIn(kLevels[kLevelCount - 1]) >= 30);

    // Every level divides into pairs and fits a 480x800 portrait panel with
    // cards big enough to tap. These two are what tableValid() exists to
    // guarantee, checked here as well because a static_assert that someone
    // comments out stops being a test.
    for (int i = 0; i < kLevelCount; ++i) {
      assert(cellsIn(kLevels[i]) % 2 == 0);
      assert(kLevels[i].columns >= 1 && kLevels[i].columns <= kMaxColumns);
      assert(kLevels[i].rows >= 1 && kLevels[i].rows <= kMaxRows);
      // Ordered easiest first, so the chooser can list the table as it stands.
      if (i > 0) assert(cellsIn(kLevels[i]) > cellsIn(kLevels[i - 1]));
    }
    assert(levelTableValid());

    // The validator has to REJECT, or it is only an expensive way of saying
    // true. Each bad table below breaks exactly one rule.
    const Level odd[] = {{"ODD", 3, 3}};
    assert(!tableValid(odd, 1));
    const Level wide[] = {{"WIDE", kMaxColumns + 1, 2}};
    assert(!tableValid(wide, 1));
    const Level tall[] = {{"TALL", 2, kMaxRows + 1}};
    assert(!tableValid(tall, 1));
    const Level empty[] = {{"EMPTY", 0, 4}};
    assert(!tableValid(empty, 1));
    const Level unordered[] = {{"BIG", 4, 4}, {"SMALL", 3, 4}};
    assert(!tableValid(unordered, 2));
    const Level nameless[] = {{"", 3, 4}};
    assert(!tableValid(nameless, 1));
    puts("level table OK");

  } else if (scenario == "deal") {
    Game game;

    // The exact layout for one seed. Computed from the documented LCG
    // independently of this core, so if the generator is ever swapped the test
    // disagrees loudly rather than silently re-blessing whatever came out.
    const uint8_t easy12345[] = {0, 2, 1, 5, 0, 4, 4, 3, 1, 5, 3, 2};
    start(game, 0, 12345u);
    assert(cellCount(game) == 12);
    assert(pairCount(game) == 6);
    assert(columnCount(game) == 3);
    assert(rowCount(game) == 4);
    assertFaces(game, easy12345, 12);
    assertDealtInPairs(game);

    // A fresh deal is entirely face down and nothing is in progress.
    for (int i = 0; i < cellCount(game); ++i) {
      assert(!faceUp(game, i));
      assert(!isMatched(game, i));
    }
    assert(game.moves == 0);
    assert(game.matchedPairs == 0);
    assert(game.firstPick == kNoCell && game.secondPick == kNoCell);
    assert(game.phase == Phase::Ready);
    assert(!complete(game));
    assert(!awaitingMismatch(game));

    // Row-major, reading order, which is also the order the grid is drawn in.
    assert(indexAt(game, 0, 0) == 0);
    assert(indexAt(game, 2, 0) == 2);
    assert(indexAt(game, 0, 1) == 3);
    assert(indexAt(game, 2, 3) == 11);
    assert(indexAt(game, 3, 0) == kNoCell);
    assert(indexAt(game, 0, 4) == kNoCell);
    assert(indexAt(game, -1, 0) == kNoCell);

    // Deterministic: the same seed deals the same board every time, which is
    // what lets a saved game be restored from a seed instead of 48 bytes.
    Game again;
    start(again, 0, 12345u);
    assertFaces(again, easy12345, 12);

    // ...and a different seed deals a different board, so the seed is actually
    // being used rather than decorating a fixed deck.
    const uint8_t easy12346[] = {0, 3, 1, 2, 4, 4, 0, 2, 5, 1, 5, 3};
    start(game, 0, 12346u);
    assertFaces(game, easy12346, 12);

    // Seed zero is a legitimate seed. A purely multiplicative generator would
    // be stuck at zero forever and deal the unshuffled deck; this one has a
    // non-zero increment, and that is the only reason the caller need not
    // special-case the seed it happens to have stored.
    const uint8_t easyZero[] = {2, 2, 3, 0, 0, 5, 1, 4, 5, 4, 3, 1};
    start(game, 0, 0u);
    assertFaces(game, easyZero, 12);
    assertDealtInPairs(game);

    // A bigger level deals a bigger board through the same code path.
    const uint8_t hard7[] = {11, 2, 8, 8, 3, 1, 3, 4, 7, 0, 5, 4,
                             1, 11, 9, 5, 10, 2, 7, 6, 9, 6, 10, 0};
    start(game, 2, 7u);
    assert(cellCount(game) == 24);
    assert(pairCount(game) == 12);
    assert(columnCount(game) == 4 && rowCount(game) == 6);
    assertFaces(game, hard7, 24);
    assertDealtInPairs(game);

    // An out-of-range level falls back to the easiest rather than reading off
    // the end of the table. A stale level index saved by an older build whose
    // table had more entries is exactly how this arrives.
    start(game, kLevelCount, 12345u);
    assert(game.level == 0);
    assertFaces(game, easy12345, 12);
    start(game, -1, 12345u);
    assert(game.level == 0);
    puts("deterministic deal OK");

  } else if (scenario == "match") {
    Game game;
    start(game, 0, 12345u);
    // Board dealt by seed 12345 on EASY, from the deal scenario:
    //   index 0 1 2 3 4 5 6 7 8 9 10 11
    //   face  0 2 1 5 0 4 4 3 1 5  3  2
    // So (0,4) is a pair and (0,1) is not.

    // The first card of a move exposes but settles nothing. In particular it
    // does NOT count as a move: a move is one COMPLETED pair attempt, so a
    // player who taps one card and walks away has not spent anything.
    assert(expose(game, 0));
    assert(game.phase == Phase::OneExposed);
    assert(game.firstPick == 0);
    assert(game.secondPick == kNoCell);
    assert(faceUp(game, 0));
    assert(!isMatched(game, 0));
    assert(game.moves == 0);
    assert(game.matchedPairs == 0);
    assert(!awaitingMismatch(game));

    // The partner completes the attempt. Matching cards stay face up for good
    // and the player keeps going, so the core lands straight back in Ready with
    // nothing for the caller to acknowledge -- only a mismatch needs that.
    assert(expose(game, 4));
    assert(game.moves == 1);
    assert(game.matchedPairs == 1);
    assert(isMatched(game, 0) && isMatched(game, 4));
    assert(faceUp(game, 0) && faceUp(game, 4));
    assert(game.phase == Phase::Ready);
    assert(!awaitingMismatch(game));
    assert(!complete(game));
    // The pick slots are cleared: a solved card is face up because it is
    // matched, never because it is still being looked at.
    assert(game.firstPick == kNoCell && game.secondPick == kNoCell);
    // Nothing else on the board moved.
    for (int i = 0; i < cellCount(game); ++i) {
      if (i == 0 || i == 4) continue;
      assert(!faceUp(game, i));
    }

    // A second pair goes through the same path, which is what "the player
    // continues" means: no turn changes hands and no state has to be cleared
    // between pairs.
    assert(expose(game, 2));
    assert(expose(game, 8));
    assert(game.moves == 2);
    assert(game.matchedPairs == 2);
    assert(isMatched(game, 2) && isMatched(game, 8));
    assert(game.phase == Phase::Ready);
    puts("a matching pair stays up and the player continues OK");

  } else if (scenario == "mismatch") {
    Game game;
    start(game, 0, 12345u);
    // Seed 12345 on EASY: face 0 2 1 5 0 4 4 3 1 5 3 2, so 0 and 1 differ.
    assert(expose(game, 0));
    assert(expose(game, 1));

    // Two cards up and wrong is a DECLARED state, not a pause. The attempt is
    // already counted, both faces are visible, and neither card is solved.
    assert(game.phase == Phase::Mismatched);
    assert(awaitingMismatch(game));
    assert(game.moves == 1);
    assert(game.matchedPairs == 0);
    assert(game.firstPick == 0 && game.secondPick == 1);
    assert(faceUp(game, 0) && faceUp(game, 1));
    assert(!isMatched(game, 0) && !isMatched(game, 1));

    // Nothing happens on its own. The core has no clock, so the two cards stay
    // up for as long as the caller leaves them up -- the whole point on a panel
    // whose fast refresh is already 300-500 ms. Taps that arrive meanwhile are
    // refused and change NOTHING, so a player hammering the glass cannot skip
    // past the faces they are meant to be memorising.
    const Game held = game;
    assert(!expose(game, 2));
    assert(identical(held, game));
    assert(!expose(game, 0));
    assert(identical(held, game));
    assert(!expose(game, 1));
    assert(identical(held, game));

    // The caller resolving it is the only thing that ends the state.
    assert(resolveMismatch(game));
    assert(game.phase == Phase::Ready);
    assert(!awaitingMismatch(game));
    assert(!faceUp(game, 0) && !faceUp(game, 1));
    assert(!isMatched(game, 0) && !isMatched(game, 1));
    assert(game.firstPick == kNoCell && game.secondPick == kNoCell);
    // Resolving is not itself a move: the attempt was counted when the second
    // card went up, and acknowledging it must not charge the player twice.
    assert(game.moves == 1);
    assert(game.matchedPairs == 0);

    // Resolving again does nothing. A second tap arriving one frame later is
    // ordinary on this panel, and it must not clear a pick the player has since
    // made.
    const Game settled = game;
    assert(!resolveMismatch(game));
    assert(identical(settled, game));

    // Nor is it callable in the other phases.
    assert(expose(game, 3));
    assert(game.phase == Phase::OneExposed);
    const Game midMove = game;
    assert(!resolveMismatch(game));
    assert(identical(midMove, game));

    // Play carries straight on from where it stopped, and the cards that were
    // turned back down are still available to match.
    assert(expose(game, 9));  // face 5 pairs 3 with 9
    assert(game.matchedPairs == 1);
    assert(game.moves == 2);
    assert(expose(game, 0));
    assert(expose(game, 4));
    assert(game.matchedPairs == 2);
    assert(game.moves == 3);
    puts("a mismatch waits for the caller to resolve it OK");

  } else if (scenario == "completion") {
    // Perfect play on the easiest board: six pairs, six moves, nothing left
    // face down. Driven off the dealt faces rather than a hardcoded order so the
    // same routine solves any level in the table.
    Game game;
    start(game, 0, 12345u);
    solvePerfectly(game);
    assert(game.matchedPairs == pairCount(game));
    assert(game.moves == 6);
    assert(complete(game));
    assert(game.phase == Phase::Done);
    assert(!awaitingMismatch(game));
    for (int i = 0; i < cellCount(game); ++i) {
      assert(isMatched(game, i));
      assert(faceUp(game, i));
    }

    // A finished game accepts nothing more. Completion is detected on the last
    // pair itself, not on the tap after it, so the app can repaint the win once
    // instead of once per stray tap on a panel that costs half a second a frame.
    const Game finished = game;
    assert(!expose(game, 0));
    assert(!resolveMismatch(game));
    assert(identical(finished, game));

    // Mismatches cost moves but not progress: the same board solved with one
    // wrong attempt first takes exactly one extra move.
    start(game, 0, 12345u);
    assert(expose(game, 0));
    assert(expose(game, 1));
    assert(resolveMismatch(game));
    solvePerfectly(game);
    assert(complete(game));
    assert(game.moves == 7);

    // The hardest level completes through the same code path: eighteen pairs,
    // eighteen moves. This is what makes the level table more than a cosmetic
    // setting -- nothing about finishing is tied to a particular grid.
    start(game, kLevelCount - 1, 99u);
    assert(cellCount(game) == 36);
    assert(pairCount(game) == 18);
    assert(!complete(game));
    solvePerfectly(game);
    assert(complete(game));
    assert(game.moves == 18);
    assert(game.matchedPairs == 18);
    puts("the board completes when every pair is matched OK");

  } else if (scenario == "rejections") {
    Game game;
    start(game, 0, 12345u);

    // The same card tapped twice is not a pair. Without this the face would be
    // compared with itself, every tap-tap would "match", and the board would
    // solve itself in six taps -- so the refusal is a rule, not politeness.
    assert(expose(game, 0));
    const Game oneUp = game;
    assert(!expose(game, 0));
    assert(identical(oneUp, game));
    assert(game.phase == Phase::OneExposed);
    assert(game.moves == 0);
    assert(!isMatched(game, 0));

    // Off-board indexes are refused from mid-move too, and change nothing. The
    // app maps a touch to a cell and hands the result straight over, so a tap in
    // the margin of a 3x4 board arrives here as an out-of-range index.
    assert(!expose(game, -1));
    assert(!expose(game, cellCount(game)));
    assert(!expose(game, kMaxCells));
    assert(!expose(game, 1000));
    assert(identical(oneUp, game));

    // Index 12 is a real cell on EXPERT and not on EASY. The face buffer is
    // sized for the largest level, so this is the index that would quietly read
    // a leftover slot if the bound came from the buffer instead of the level.
    assert(cellCount(game) == 12);
    assert(!expose(game, 12));
    assert(identical(oneUp, game));

    // Finish the pair, then try the solved cards again: already face up for good
    // means not selectable, otherwise a matched card could be paired a second
    // time and matchedPairs would run past pairCount.
    assert(expose(game, 4));
    assert(game.matchedPairs == 1);
    const Game solvedOne = game;
    assert(!expose(game, 0));
    assert(!expose(game, 4));
    assert(identical(solvedOne, game));

    // A matched card is equally unavailable as the SECOND card of a move, which
    // is the case a guard placed only on the first pick would miss.
    assert(expose(game, 2));
    const Game midMove = game;
    assert(!expose(game, 0));
    assert(identical(midMove, game));
    assert(game.phase == Phase::OneExposed);
    assert(game.firstPick == 2);

    // From a fresh deal the same refusals hold in Ready, where there is no pick
    // to compare against at all.
    start(game, 0, 12345u);
    const Game fresh = game;
    assert(!expose(game, -1));
    assert(!expose(game, 12));
    assert(identical(fresh, game));
    assert(game.phase == Phase::Ready);
    puts("illegal taps are refused and change nothing OK");

  } else if (scenario == "bounds") {
    Game game;
    start(game, 0, 12345u);

    // The core knows every face from the moment it deals; hiding a card is the
    // RENDERER's job, driven by faceUp(). Keeping the face readable while the
    // card is down is what lets the app draw the whole grid in one pass instead
    // of tracking a second shadow copy of the layout.
    assert(faceAt(game, 0) == 0);
    assert(faceAt(game, 1) == 2);
    assert(!faceUp(game, 1));

    // Off this level's board every accessor gives the safe answer rather than
    // reading the buffer, which is sized for the largest level and therefore
    // holds 36 slots a 3x4 game must never show.
    assert(faceAt(game, 12) == kNoFace);
    assert(faceAt(game, kMaxCells) == kNoFace);
    assert(faceAt(game, -1) == kNoFace);
    assert(!faceUp(game, 12));
    assert(!faceUp(game, -1));
    assert(!isMatched(game, 12));
    assert(!isMatched(game, -1));

    // On the largest level that same index 12 is a real cell with a real face,
    // so the bound is genuinely the level's and not a constant.
    start(game, kLevelCount - 1, 99u);
    assert(faceAt(game, 12) != kNoFace);
    assert(faceAt(game, cellCount(game) - 1) != kNoFace);
    assert(faceAt(game, cellCount(game)) == kNoFace);
    puts("accessors stay inside the level's board OK");

  } else {
    std::fprintf(stderr, "unknown scenario %s\n", scenario.c_str());
    return 1;
  }
  return 0;
}
'''


class MemoryCoreTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        harness = pathlib.Path(cls.tmp.name) / "memory_core_test.cpp"
        harness.write_text(HARNESS)
        cls.exe = pathlib.Path(cls.tmp.name) / "memory_core_test"
        subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                        "-I", str(GAME_DIR), str(harness),
                        "-o", str(cls.exe)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_level_table_is_four_plus_even_levels_that_fit_the_panel(self):
        subprocess.run([str(self.exe), "levels"], check=True)

    def test_a_seed_deals_an_exact_shuffled_board_of_pairs(self):
        subprocess.run([str(self.exe), "deal"], check=True)

    def test_a_matching_pair_stays_face_up_and_the_player_continues(self):
        subprocess.run([str(self.exe), "match"], check=True)

    def test_a_mismatch_waits_for_an_explicit_resolve_with_no_timer(self):
        subprocess.run([str(self.exe), "mismatch"], check=True)

    def test_the_board_completes_when_every_pair_is_matched(self):
        subprocess.run([str(self.exe), "completion"], check=True)

    def test_illegal_taps_are_refused_and_change_nothing(self):
        subprocess.run([str(self.exe), "rejections"], check=True)

    def test_accessors_stay_inside_the_levels_board(self):
        subprocess.run([str(self.exe), "bounds"], check=True)


if __name__ == "__main__":
    unittest.main()
