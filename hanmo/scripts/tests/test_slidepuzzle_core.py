"""Compile the actual sliding-puzzle rules with host g++ and drive real boards through them.

Freestanding core, same shape as reversi/ReversiCore.h: no renderer, no Activity,
no storage, so the rules can be driven directly from a host harness.
"""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
GAME_DIR = ROOT / "src/apps_local/slidepuzzle"

HARNESS = r'''
#include "SlidePuzzleCore.h"

#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

using namespace slidepuzzle;

// Every arrangement of a 3x3 board: 9! of them, small enough to enumerate.
constexpr int kStates = 362880;

// Lay out a board from a list of tile values in reading order, gap written as
// 0. Reading a position as a literal row of numbers is the only way these
// tests stay auditable; a sequence of slides hides which shape is being tested,
// and most of the positions below are deliberately unreachable by sliding.
static void place(Game& game, const int width, const uint8_t* tiles) {
  game.width = static_cast<uint8_t>(width);
  for (int index = 0; index < width * width; ++index) game.tile[index] = tiles[index];
  game.moves = 0;
}

// A dense 0..9!-1 number for a 3x3 arrangement, its Lehmer code. Used so the
// exhaustive search can mark visited positions in a flat array instead of
// hashing boards, which keeps the whole state space in a few hundred kilobytes.
static int rankOf(const Game& game) {
  int rank = 0;
  for (int index = 0; index < 9; ++index) {
    int smaller = 0;
    for (int later = index + 1; later < 9; ++later) {
      if (game.tile[later] < game.tile[index]) ++smaller;
    }
    rank = rank * (9 - index) + smaller;
  }
  return rank;
}

// The inverse, so the search can be checked against EVERY arrangement rather
// than only the ones it happened to visit.
static void unrank(Game& game, int rank) {
  uint8_t pool[9] = {0, 1, 2, 3, 4, 5, 6, 7, 8};
  int remaining = 9;
  for (int index = 0; index < 9; ++index) {
    int block = 1;
    for (int factor = 2; factor < remaining; ++factor) block *= factor;
    const int pick = rank / block;
    rank %= block;
    game.tile[index] = pool[pick];
    for (int shift = pick; shift < remaining - 1; ++shift) pool[shift] = pool[shift + 1];
    --remaining;
  }
  for (int index = 9; index < kMaxCells; ++index) game.tile[index] = kEmpty;
  game.width = 3;
  game.moves = 0;
}

int main(int argc, char** argv) {
  assert(argc == 2);
  const std::string scenario = argv[1];

  if (scenario == "layout") {
    Game game;
    reset(game, 4);
    // The solved board IS the starting layout: 1..15 in reading order with the
    // gap last. Everything else in the core is defined against this shape.
    assert(game.width == 4);
    assert(cellCount(game) == 16);
    for (int index = 0; index < 15; ++index) assert(game.tile[index] == index + 1);
    assert(game.tile[15] == kEmpty);
    assert(emptyIndex(game) == 15);
    assert(game.moves == 0);
    assert(solved(game));

    // The size lives in the struct, so the same functions have to serve a
    // smaller board without a second set of constants.
    reset(game, 3);
    assert(game.width == 3);
    assert(cellCount(game) == 9);
    for (int index = 0; index < 8; ++index) assert(game.tile[index] == index + 1);
    assert(game.tile[8] == kEmpty);
    assert(emptyIndex(game) == 8);
    assert(solved(game));

    // Row-major: moving one step right advances by one, one step down by width.
    assert(tileAt(game, 0, 0) == 1);
    assert(tileAt(game, 2, 0) == 3);
    assert(tileAt(game, 0, 1) == 4);
    assert(tileAt(game, 2, 2) == kEmpty);
    assert(emptyColumn(game) == 2 && emptyRow(game) == 2);

    // Ascending tiles are NOT the win condition: the gap has to be home too.
    // Tiles 1..7 sit in place here and only 8 is displaced, so a check that
    // merely reads "the numbers increase" declares a win while the player is
    // still looking at an unfinished puzzle.
    const uint8_t nearly[9] = {1, 2, 3, 4, 5, 6, 7, 0, 8};
    place(game, 3, nearly);
    assert(!solved(game));

    // A width the game does not offer is clamped, never obeyed. The size
    // arrives from a persisted setting that a half-written file can corrupt,
    // and a width of 9 would write 81 tiles through a 16-cell array -- the
    // one way this core can reach past its own memory.
    reset(game, 9);
    assert(game.width == kMaxWidth);
    assert(solved(game));
    reset(game, 1);
    assert(game.width == kMinWidth);
    assert(solved(game));
    shuffle(game, 0, 3u);
    assert(game.width == kMinWidth);
    assert(solvable(game));
    puts("solved layout for every size OK");

  } else if (scenario == "adjacency") {
    Game game;
    reset(game, 4);
    // Gap bottom right. Its two orthogonal neighbours move, and nothing else
    // does -- not the diagonal, not a tile further along the same row or
    // column. A row-shoving implementation passes every "a tile moved" test
    // and fails here.
    assert(canSlide(game, 3, 2));
    assert(canSlide(game, 2, 3));
    assert(!canSlide(game, 2, 2));
    assert(!canSlide(game, 3, 1));
    assert(!canSlide(game, 0, 3));
    // The gap is not a tile, and off-board taps are not moves.
    assert(!canSlide(game, 3, 3));
    assert(!canSlide(game, -1, 3));
    assert(!canSlide(game, 4, 3));
    assert(!canSlide(game, 3, 4));

    assert(slide(game, 3, 2));
    assert(tileAt(game, 3, 3) == 12);
    assert(tileAt(game, 3, 2) == kEmpty);
    assert(emptyColumn(game) == 3 && emptyRow(game) == 2);
    // The cell the tile came from is now the gap, so the move is reversible --
    // this puzzle has no captures and no dead ends.
    assert(canSlide(game, 3, 3));
    assert(slide(game, 3, 3));
    assert(solved(game));
    puts("only an orthogonal neighbour of the gap slides OK");

  } else if (scenario == "direction") {
    Game game;
    reset(game, 4);
    // A Direction names where the TILE travels, not where the gap travels. The
    // two conventions are exact opposites and both read naturally, so the
    // choice is pinned here: with the gap in the bottom-right corner the only
    // vertical move is a tile coming DOWN into it.
    assert(canSlideToward(game, Direction::Down));
    assert(!canSlideToward(game, Direction::Up));
    assert(canSlideToward(game, Direction::Right));
    assert(!canSlideToward(game, Direction::Left));

    assert(slideToward(game, Direction::Down));
    assert(tileAt(game, 3, 3) == 12);
    assert(tileAt(game, 3, 2) == kEmpty);
    assert(game.moves == 1);

    // A refused direction costs nothing at all, the move count included. The
    // gap sits against the right edge now, so no tile can travel left into it.
    const Game before = game;
    assert(!slideToward(game, Direction::Left));
    assert(std::memcmp(&before, &game, sizeof(Game)) == 0);

    assert(slideToward(game, Direction::Up));
    assert(solved(game));
    assert(game.moves == 2);
    puts("a direction names where the tile travels OK");

  } else if (scenario == "parity") {
    Game game;

    // Inversions are counted over the tiles alone, in reading order, ignoring
    // the gap: a pair is inverted when the larger number comes first.
    reset(game, 4);
    assert(inversions(game) == 0);
    assert(solvable(game));

    // The 14-15 puzzle, the famous one Sam Loyd offered a prize for. A single
    // swap away from solved, one inversion, and no sequence of slides reaches
    // it. Exactly half of all arrangements are in this class, so a shuffle
    // that merely permutes tiles hands the player an impossible board half the
    // time -- and it looks perfectly ordinary while they fail to solve it.
    const uint8_t loyd[16] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15, 14, 0};
    place(game, 4, loyd);
    assert(inversions(game) == 1);
    assert(!solvable(game));

    // Even width needs the gap's row as well as the inversion count. This
    // board is one slide from solved -- tile 12 pulled down -- so it must be
    // solvable, yet it has an ODD number of inversions (12 now follows 13, 14
    // and 15). Judging it on inversion parity alone, the rule odd widths use,
    // would reject a position that play can reach in one move.
    const uint8_t pulled[16] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 0, 13, 14, 15, 12};
    place(game, 4, pulled);
    assert(inversions(game) == 3);
    assert(emptyRow(game) == 2);
    assert(solvable(game));

    // Odd width ignores the gap's row entirely. Same even inversion count,
    // gap on two different rows, both solvable -- one of them is the solved
    // board itself and the other is one slide away from it.
    reset(game, 3);
    assert(inversions(game) == 0);
    assert(emptyRow(game) == 2);
    assert(solvable(game));

    const uint8_t nudged[9] = {1, 2, 3, 4, 5, 0, 7, 8, 6};
    place(game, 3, nudged);
    assert(inversions(game) == 2);
    assert(emptyRow(game) == 1);
    assert(solvable(game));

    // One transposition flips the parity and nothing else: unsolvable on an
    // odd board however the gap sits.
    const uint8_t swapped[9] = {2, 1, 3, 4, 5, 6, 7, 8, 0};
    place(game, 3, swapped);
    assert(inversions(game) == 1);
    assert(!solvable(game));

    const uint8_t swappedHighGap[9] = {2, 1, 3, 4, 0, 5, 6, 7, 8};
    place(game, 3, swappedHighGap);
    assert(inversions(game) == 1);
    assert(emptyRow(game) == 1);
    assert(!solvable(game));

    // Sliding never changes solvability -- that is the whole point of the
    // invariant -- so a reachable position stays solvable however far it is
    // walked from home.
    reset(game, 4);
    assert(slide(game, 3, 2) && slide(game, 2, 2) && slide(game, 2, 3));
    assert(!solved(game));
    assert(solvable(game));
    puts("inversion parity separates solvable from unsolvable OK");

  } else if (scenario == "determinism") {
    // A seed is the whole of the randomness. Two shuffles with one seed are
    // the same board, so a player can be handed "puzzle 1234" and a failing
    // board from a bug report can be replayed exactly.
    Game first;
    shuffle(first, 4, 20261006u);
    assert(first.width == 4);
    assert(first.moves == 0);

    // Shuffled from a DIFFERENT prior state, to prove the result depends on
    // the seed alone and not on whatever the struct happened to hold.
    Game again;
    reset(again, 3);
    assert(slide(again, 2, 1));
    shuffle(again, 4, 20261006u);
    assert(std::memcmp(&first, &again, sizeof(Game)) == 0);

    // Every tile exactly once, and exactly one gap: a shuffle rearranges the
    // board, it does not invent or lose tiles.
    int seen[kMaxCells] = {0};
    for (int index = 0; index < cellCount(first); ++index) {
      assert(first.tile[index] < kMaxCells);
      ++seen[first.tile[index]];
    }
    for (int value = 0; value < cellCount(first); ++value) assert(seen[value] == 1);

    // The exact board seed 20261006 deals, frozen. This is what makes a bug
    // report replayable: if an edit to the generator changes what "puzzle
    // 20261006" means, that is a behaviour change and has to be a deliberate
    // one. The checks under it are what keep the frozen row meaningful rather
    // than merely stable -- 50 inversions with the gap on row 1 sums to odd,
    // which is what solvability on an even board requires.
    const uint8_t expected[16] = {9, 14, 5, 1, 2, 15, 6, 0, 10, 12, 11, 3, 7, 4, 13, 8};
    for (int index = 0; index < 16; ++index) assert(first.tile[index] == expected[index]);
    assert(inversions(first) == 50);
    assert(emptyRow(first) == 1);
    assert(solvable(first) && !solved(first));

    // Distinct seeds must give distinct boards, or the seed is decoration and
    // the difficulty levels all look the same.
    Game boards[8];
    for (int seed = 0; seed < 8; ++seed) shuffle(boards[seed], 4, static_cast<uint32_t>(seed + 1));
    for (int a = 0; a < 8; ++a) {
      for (int b = a + 1; b < 8; ++b) {
        assert(std::memcmp(boards[a].tile, boards[b].tile, kMaxCells) != 0);
      }
    }

    // The smaller board is shuffled by the same code with the same promise.
    Game small;
    Game smallAgain;
    shuffle(small, 3, 7u);
    shuffle(smallAgain, 3, 7u);
    assert(small.width == 3);
    assert(std::memcmp(&small, &smallAgain, sizeof(Game)) == 0);
    const uint8_t expectedSmall[9] = {0, 2, 7, 4, 1, 6, 5, 8, 3};
    for (int index = 0; index < 9; ++index) assert(small.tile[index] == expectedSmall[index]);
    assert(solvable(small) && !solved(small));
    puts("one seed gives one board OK");

  } else if (scenario == "guarantee") {
    // The promise a shuffle has to keep, checked over a wide span of seeds
    // rather than one: a dealt board is always reachable from solved, and is
    // never already solved. A plain permutation keeps neither -- half of all
    // arrangements of a 4x4 board cannot be solved at all -- and the failure
    // is invisible on the device, so the seed count here is the test.
    constexpr uint32_t kSeeds = 2000;
    int unreachable = 0;
    int alreadySolved = 0;
    uint32_t firstBadSeed = 0;
    int firstBadWidth = 0;

    for (int width = kMinWidth; width <= kMaxWidth; ++width) {
      int gapSeen[kMaxCells] = {0};
      for (uint32_t seed = 0; seed < kSeeds; ++seed) {
        Game game;
        shuffle(game, width, seed);
        assert(game.width == width);
        assert(game.moves == 0);

        int seen[kMaxCells] = {0};
        for (int index = 0; index < cellCount(game); ++index) ++seen[game.tile[index]];
        for (int value = 0; value < cellCount(game); ++value) assert(seen[value] == 1);

        if (!solvable(game)) {
          if (unreachable == 0) {
            firstBadSeed = seed;
            firstBadWidth = width;
          }
          ++unreachable;
        }
        if (solved(game)) ++alreadySolved;
        ++gapSeen[emptyIndex(game)];
      }
      // The gap is shuffled like everything else. A shuffle that permutes the
      // numbered tiles and leaves the gap parked in the last cell would pass
      // every other assertion in this file.
      for (int index = 0; index < width * width; ++index) assert(gapSeen[index] > 0);
    }

    if (unreachable != 0) {
      std::fprintf(stderr, "%d of %u dealt boards cannot be solved, first at width %d seed %u\n",
                   unreachable, kSeeds * 2, firstBadWidth, firstBadSeed);
    }
    assert(unreachable == 0);
    assert(alreadySolved == 0);
    puts("every dealt board is solvable and none is already solved OK");

  } else if (scenario == "reachable") {
    // The parity rule, checked against reality instead of against itself.
    //
    // A 3x3 board has 9! = 362880 arrangements, few enough to walk all of
    // them. Breadth-first from the solved board using nothing but slide()
    // marks exactly the positions real play can reach; `solvable()` claims to
    // predict that set from an inversion count. Nothing in this walk mentions
    // inversions, so agreement between the two is a proof and not a tautology.
    std::vector<bool> reached(kStates, false);
    std::vector<Game> frontier;
    frontier.reserve(kStates / 2);

    Game goal;
    reset(goal, 3);
    reached[rankOf(goal)] = true;
    frontier.push_back(goal);

    for (size_t head = 0; head < frontier.size(); ++head) {
      const Game current = frontier[head];
      const Direction directions[4] = {Direction::Up, Direction::Down, Direction::Left, Direction::Right};
      for (const Direction direction : directions) {
        Game next = current;
        if (!slideToward(next, direction)) continue;
        // The move count is part of the struct but not part of the position;
        // leaving it in would make the same board look like a new state.
        next.moves = 0;
        const int rank = rankOf(next);
        if (reached[rank]) continue;
        reached[rank] = true;
        frontier.push_back(next);
      }
    }

    // Exactly half the arrangements, which is the claim the whole shuffle
    // rests on: the other 181440 are real boards that no sequence of slides
    // can ever untangle.
    assert(frontier.size() == kStates / 2);

    int disagreements = 0;
    int firstDisagreement = -1;
    for (int rank = 0; rank < kStates; ++rank) {
      Game board;
      unrank(board, rank);
      if (solvable(board) != reached[rank]) {
        if (disagreements == 0) firstDisagreement = rank;
        ++disagreements;
      }
    }
    if (disagreements != 0) {
      std::fprintf(stderr, "parity rule disagrees with real play on %d of %d boards, first rank %d\n",
                   disagreements, kStates, firstDisagreement);
    }
    assert(disagreements == 0);

    // And the boards the game actually deals are in the reachable half -- not
    // because a predicate says so, but because the search walked to them.
    for (uint32_t seed = 0; seed < 2000; ++seed) {
      Game dealt;
      shuffle(dealt, 3, seed);
      if (!reached[rankOf(dealt)]) {
        std::fprintf(stderr, "dealt board for 3x3 seed %u is not reachable by sliding\n", seed);
      }
      assert(reached[rankOf(dealt)]);
    }

    // 4x4 cannot be walked -- 16!/2 is ten trillion positions -- so the claim
    // is checked from the other end there: a long random walk away from the
    // solved board stays inside the set the rule accepts, every single step.
    Game walk;
    reset(walk, 4);
    uint32_t state = 99u;
    for (int step = 0; step < 200000; ++step) {
      slideToward(walk, static_cast<Direction>(randomBelow(state, 4)));
      assert(solvable(walk));
    }
    // The walk really did leave home, so the assertion above was not just
    // reading the solved board two hundred thousand times.
    assert(!solved(walk));
    puts("exhaustive search agrees with the parity rule OK");

  } else if (scenario == "bytes") {
    // Two games holding the same position must be the same BYTES.
    //
    // Several assertions in this file prove "nothing changed" with memcmp,
    // and the app stores and compares whole Game structs; both are quietly
    // wrong if the struct contains a byte that no function writes. Poisoning
    // the two structs with different patterns first is what makes such a hole
    // visible at all -- on a quiet stack the unwritten byte is usually the
    // same in both copies, and the bug shows up later as a test that fails
    // once a week.
    Game poisoned;
    Game clean;
    std::memset(&poisoned, 0xAA, sizeof(Game));
    std::memset(&clean, 0x55, sizeof(Game));
    reset(poisoned, 4);
    reset(clean, 4);
    assert(std::memcmp(&poisoned, &clean, sizeof(Game)) == 0);

    std::memset(&poisoned, 0xAA, sizeof(Game));
    std::memset(&clean, 0x55, sizeof(Game));
    shuffle(poisoned, 3, 12345u);
    shuffle(clean, 3, 12345u);
    assert(std::memcmp(&poisoned, &clean, sizeof(Game)) == 0);

    // The same must hold after play, or a saved game and a replayed game
    // compare unequal while showing the same board. One of the two vertical
    // moves is always available: the gap cannot be in the top and the bottom
    // row at once.
    assert(slideToward(poisoned, Direction::Up) || slideToward(poisoned, Direction::Down));
    assert(slideToward(clean, Direction::Up) || slideToward(clean, Direction::Down));
    assert(std::memcmp(&poisoned, &clean, sizeof(Game)) == 0);
    puts("equal positions are equal bytes OK");

  } else {
    std::fprintf(stderr, "unknown scenario %s\n", scenario.c_str());
    return 1;
  }
  return 0;
}
'''


class SlidePuzzleCoreTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        harness = pathlib.Path(cls.tmp.name) / "slidepuzzle_core_test.cpp"
        harness.write_text(HARNESS)
        cls.exe = pathlib.Path(cls.tmp.name) / "slidepuzzle_core_test"
        subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                        "-I", str(GAME_DIR), str(harness),
                        "-o", str(cls.exe)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_reset_lays_out_the_solved_board_for_every_supported_size(self):
        subprocess.run([str(self.exe), "layout"], check=True)

    def test_only_a_tile_orthogonally_adjacent_to_the_gap_can_slide(self):
        subprocess.run([str(self.exe), "adjacency"], check=True)

    def test_a_direction_names_where_the_tile_travels_not_the_gap(self):
        subprocess.run([str(self.exe), "direction"], check=True)

    def test_inversion_parity_separates_solvable_boards_from_unsolvable_ones(self):
        subprocess.run([str(self.exe), "parity"], check=True)

    def test_one_seed_gives_one_board_and_different_seeds_differ(self):
        subprocess.run([str(self.exe), "determinism"], check=True)

    def test_every_dealt_board_is_solvable_and_never_already_solved(self):
        subprocess.run([str(self.exe), "guarantee"], check=True)

    def test_exhaustive_search_of_the_3x3_space_agrees_with_the_parity_rule(self):
        subprocess.run([str(self.exe), "reachable"], check=True)

    def test_two_games_in_the_same_position_are_identical_byte_for_byte(self):
        subprocess.run([str(self.exe), "bytes"], check=True)

    def test_the_core_draws_randomness_from_nothing_but_the_seed(self):
        # A seeded shuffle is only reproducible if there is no second source of
        # randomness anywhere in the file. Reading the source is the only way
        # to prove a NEGATIVE like this; no runtime assertion can.
        source = (GAME_DIR / "SlidePuzzleCore.h").read_text()
        for banned in ("random_device", "<random>", "<ctime>", "time(", "rand()",
                       "srand", "chrono", "millis", "esp_random"):
            # assertFalse, not assertNotIn: a failing assertNotIn prints the
            # whole header into the report and buries the one word that matters.
            self.assertFalse(banned in source,
                             f"{banned} appears in the core and would make a seed unreplayable")
        # Freestanding, like the other rules cores: one standard header.
        self.assertEqual(
            [line for line in source.splitlines() if line.startswith("#include")],
            ["#include <cstdint>"])


if __name__ == "__main__":
    unittest.main()
