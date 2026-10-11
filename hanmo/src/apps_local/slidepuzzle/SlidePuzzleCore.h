#pragma once

// The sliding number puzzle, the rules. Freestanding: no renderer, no Activity,
// no storage.
//
// A square grid of numbered tiles with one cell left empty. A tile orthogonally
// adjacent to that empty cell slides into it; nothing else moves, ever. The
// puzzle is solved when the tiles read 1..n-1 in reading order with the empty
// cell last -- which is exactly the layout `reset` builds, so the goal is the
// start position and needs no separate description.
//
// The board is a flat `tile[row * width + column]`, **row 0 at the top**,
// matching the order the screen draws in and the order the win condition is
// stated in. Reversi and Connect Four use `cell[column][row]` because a disc
// game scans rays and columns; this puzzle never scans a direction, it indexes
// single cells and compares the whole array against reading order, so the flat
// row-major array is the shape that makes the rules shortest.
//
// `width` lives in the struct rather than in a constant, because the two sizes
// are the game's difficulty levels and every function has to serve both.
// `kMaxCells` sizes the array for the largest board; a 3x3 game simply leaves
// the tail unused rather than paying for a second struct.
//
// One move is one slide and one redraw. The panel manages two or three frames
// a second, so nothing here describes a tile in motion: a slide is a swap of
// two cells, and the app repaints the result.
//
// A dealt board is always SOLVABLE. Exactly half of all arrangements cannot be
// reached from the solved one by sliding, and they look no different from the
// half that can, so `shuffle` tests for it instead of trusting a permutation.
// The deal comes from an explicit seed and nothing else, so one seed is one
// board on every device and a position from a bug report can be replayed.

#include <cstdint>

namespace slidepuzzle {

constexpr int kMinWidth = 3;
constexpr int kMaxWidth = 4;
constexpr int kMaxCells = kMaxWidth * kMaxWidth;

// The empty cell. Zero, so a cleared board is already all-gap and a tile value
// is its own printable number.
constexpr uint8_t kEmpty = 0;

// Where a TILE travels, not where the gap travels. The two readings are exact
// opposites and both sound natural at a call site, so the one the player means
// -- "push this tile up" -- is the one the name carries.
enum class Direction : uint8_t {
  Up,
  Down,
  Left,
  Right,
};

struct Game {
  // tile[row * width + column], row 0 at the top. kEmpty for the gap.
  uint8_t tile[kMaxCells];
  // 3 or 4. The board is square, so this is the height too.
  uint8_t width;
  // The gap the compiler would leave here anyway, named so that something
  // writes it. `moves` is two bytes wide and wants an even offset, so a hole
  // opens after `width` whether or not it is declared -- and a hole nobody
  // writes makes two identical positions compare UNEQUAL under memcmp. The
  // app compares a stored game against the running one that way, so the byte
  // is declared and zeroed rather than left to the stack.
  uint8_t reserved;
  // Slides accepted so far. The only score this game has.
  uint16_t moves;
};

// No implicit padding anywhere: sixteen cells, width, the named spare, and a
// two-byte counter. If a future field reopens a hole, this fails at compile
// time instead of becoming a test that fails once a week.
static_assert(sizeof(Game) == kMaxCells + 4, "Game must contain no unwritten bytes");

inline int cellCount(const Game& game) { return game.width * game.width; }

inline bool inside(const Game& game, const int column, const int row) {
  return column >= 0 && column < game.width && row >= 0 && row < game.width;
}

inline int indexAt(const Game& game, const int column, const int row) {
  return row * game.width + column;
}

inline uint8_t tileAt(const Game& game, const int column, const int row) {
  if (!inside(game, column, row)) return kEmpty;
  return game.tile[indexAt(game, column, row)];
}

// Where the gap is. Searched rather than cached: sixteen cells cost nothing to
// scan, and a stored index is one more thing that can disagree with the board
// after a restore or a hand-built test position.
inline int emptyIndex(const Game& game) {
  const int cells = cellCount(game);
  for (int index = 0; index < cells; ++index) {
    if (game.tile[index] == kEmpty) return index;
  }
  return cells - 1;
}

inline int emptyColumn(const Game& game) { return emptyIndex(game) % game.width; }
inline int emptyRow(const Game& game) { return emptyIndex(game) / game.width; }

// Tiles in reading order with the gap last. The goal and the start are the same
// position, so this is also what `reset` writes.
inline bool solved(const Game& game) {
  const int cells = cellCount(game);
  for (int index = 0; index < cells - 1; ++index) {
    if (game.tile[index] != index + 1) return false;
  }
  return game.tile[cells - 1] == kEmpty;
}

// The nearest width the game actually offers.
//
// Every entry point goes through this rather than trusting its argument,
// because the size is a difficulty SETTING: it arrives from a stored
// preference that a half-finished write can leave as anything at all. A width
// of 9 would have `reset` lay out 81 tiles through a 16-cell array, which is
// the only way this core can scribble outside its own struct.
inline int supportedWidth(const int width) {
  if (width < kMinWidth) return kMinWidth;
  if (width > kMaxWidth) return kMaxWidth;
  return width;
}

inline void reset(Game& game, const int width) {
  game.width = static_cast<uint8_t>(supportedWidth(width));
  const int cells = cellCount(game);
  for (int index = 0; index < cells - 1; ++index) {
    game.tile[index] = static_cast<uint8_t>(index + 1);
  }
  game.tile[cells - 1] = kEmpty;
  // Wipe the cells a smaller board does not use. Nothing reads past
  // cellCount(), so this looks pointless -- but the app persists and compares
  // whole Game structs, and a 3x3 board left holding tiles 10..15 in its tail
  // would make two identical positions compare unequal byte for byte.
  for (int index = cells; index < kMaxCells; ++index) game.tile[index] = kEmpty;
  game.reserved = 0;
  game.moves = 0;
}

// Whether the tile at (column, row) shares an edge with the gap.
//
// The test is squared distance, not |dc| + |dr|, because the three rejections
// then read off one number: a diagonal is 2, a tile two cells away is 4, and
// the gap itself is 0. That last one is why there is no separate "this is not
// a tile" check -- the gap is always exactly zero cells from the gap.
//
// Distance also rules out the mistake this game invites most: tapping a tile
// further along the gap's own row does NOT shove the row along, it does
// nothing at all.
inline bool canSlide(const Game& game, const int column, const int row) {
  if (!inside(game, column, row)) return false;
  const int dc = column - emptyColumn(game);
  const int dr = row - emptyRow(game);
  return dc * dc + dr * dr == 1;
}

// Move the tile at (column, row) into the gap. False means the slide was not
// legal, and then NOTHING changed -- not the board, not the move count. The app
// routes a raw tap in here and most of a board's cells are not next to the gap,
// so the rejected path runs more often than the accepted one.
inline bool slide(Game& game, const int column, const int row) {
  if (!canSlide(game, column, row)) return false;
  const int from = indexAt(game, column, row);
  const int to = emptyIndex(game);
  game.tile[to] = game.tile[from];
  game.tile[from] = kEmpty;
  ++game.moves;
  return true;
}

// Pairs of tiles standing in the wrong order: for every pair, the larger
// number appearing first in reading order. The gap takes no part -- it is not
// a number, and counting it would make the answer depend on where it happens
// to sit rather than on how the tiles are arranged.
inline int inversions(const Game& game) {
  const int cells = cellCount(game);
  int count = 0;
  for (int first = 0; first < cells; ++first) {
    if (game.tile[first] == kEmpty) continue;
    for (int second = first + 1; second < cells; ++second) {
      if (game.tile[second] == kEmpty) continue;
      if (game.tile[first] > game.tile[second]) ++count;
    }
  }
  return count;
}

// Whether any sequence of slides can reach the solved board. Half of all
// arrangements cannot, and they are indistinguishable from the rest by eye, so
// this is the difference between a puzzle and an hour of wasted effort.
//
// Why parity decides it. A horizontal slide swaps a tile with the gap, and the
// gap is not counted, so the reading order of the TILES is unchanged and the
// inversion count cannot move. A vertical slide carries one tile past the
// width-1 tiles lying between its old and new cell, so the count changes by
// width-1 ones, up or down -- a change whose parity is the parity of width-1.
//
//   Odd width:  width-1 is even, so inversion parity never changes at all. The
//               solved board has zero inversions, so solvable means even.
//   Even width: width-1 is odd, so every vertical slide flips the inversion
//               parity -- and moves the gap one row, flipping that too. Their
//               SUM is what stays put. The solved board has zero inversions
//               with the gap on the last row, width-1, which is odd for an
//               even width, so solvable means the sum is odd.
//
// The second case is the one naive implementations drop, because on an odd
// board the gap's row genuinely does not matter and the rule looks complete
// without it.
inline bool solvable(const Game& game) {
  const int parity = inversions(game) & 1;
  if (game.width % 2 != 0) return parity == 0;
  return (parity + emptyRow(game)) % 2 == 1;
}

// A 32-bit linear congruential generator, Numerical Recipes' constants. Tiny
// and exactly reproducible, which is the entire requirement: a board must be
// replayable from its seed on a desk as well as on the device, so the engine
// is written out here rather than taken from the standard library, whose
// generators drag in a header this core does not include and whose
// distributions are not specified to produce identical values across
// implementations.
inline uint32_t nextRandom(uint32_t& state) {
  state = state * 1664525u + 1013904223u;
  return state;
}

// A value in [0, bound). Scaled from the TOP bits, not taken modulo: the low
// bits of a power-of-two-modulus LCG have very short periods -- bit 0 simply
// alternates -- so `% bound` would deal out a board that visibly cycles.
inline int randomBelow(uint32_t& state, const int bound) {
  const uint64_t scaled = static_cast<uint64_t>(nextRandom(state)) * static_cast<uint32_t>(bound);
  return static_cast<int>(scaled >> 32);
}

// Swap the first two numbered tiles on the board, whichever they are.
//
// This exists for one reason: it flips solvability. Exchanging two elements of
// a permutation changes the inversion count by an odd number, and because the
// GAP is left where it is, the gap's row -- the other half of the even-width
// rule -- does not move. So an unreachable arrangement becomes reachable, and
// the board still looks exactly as random as it did.
inline void flipParity(Game& game) {
  const int cells = cellCount(game);
  int first = -1;
  for (int index = 0; index < cells; ++index) {
    if (game.tile[index] == kEmpty) continue;
    if (first < 0) {
      first = index;
      continue;
    }
    const uint8_t held = game.tile[first];
    game.tile[first] = game.tile[index];
    game.tile[index] = held;
    return;
  }
}

// Deal a starting position for `width`, derived from `seed` alone, that the
// player can actually finish and has not already finished.
inline void shuffle(Game& game, const int width, const uint32_t seed) {
  uint32_t state = seed;
  do {
    reset(game, width);
    const int cells = cellCount(game);
    // Fisher-Yates over the whole board, gap included: the gap is a cell like
    // any other and a start position with it in the middle is normal play.
    for (int index = cells - 1; index > 0; --index) {
      const int pick = randomBelow(state, index + 1);
      const uint8_t held = game.tile[index];
      game.tile[index] = game.tile[pick];
      game.tile[pick] = held;
    }
    // Half of all arrangements cannot be solved, so a bare permutation deals
    // an impossible board on about every second seed -- and it looks like any
    // other board while the player fails to solve it. Repair the parity
    // instead of re-drawing until a reachable board turns up: re-drawing
    // throws away half the seeds and makes the cost of a deal a coin flip,
    // while one swap fixes it in constant time and keeps the distribution
    // even across the reachable half.
    if (!solvable(game)) flipParity(game);
    // The one case worth re-drawing for. A board that arrives already solved
    // is not a puzzle, and it is reachable: the repair swap can land on it.
    // `state` deliberately carries over between attempts rather than being
    // re-seeded, or the second attempt would deal the first board again.
  } while (solved(game));
  game.moves = 0;
}

// The cell a tile must start in to travel `direction` into the gap: the
// opposite side of the gap from the way it is going. Pushing a tile UP means
// taking the tile BELOW the gap, and getting that backwards is the single
// likeliest bug in a directional control scheme.
inline void slideSource(const Game& game, const Direction direction, int& column, int& row) {
  column = emptyColumn(game);
  row = emptyRow(game);
  switch (direction) {
    case Direction::Up:
      ++row;
      break;
    case Direction::Down:
      --row;
      break;
    case Direction::Left:
      ++column;
      break;
    case Direction::Right:
      --column;
      break;
  }
}

inline bool canSlideToward(const Game& game, const Direction direction) {
  int column = 0;
  int row = 0;
  slideSource(game, direction, column, row);
  return canSlide(game, column, row);
}

inline bool slideToward(Game& game, const Direction direction) {
  int column = 0;
  int row = 0;
  slideSource(game, direction, column, row);
  return slide(game, column, row);
}

}  // namespace slidepuzzle
