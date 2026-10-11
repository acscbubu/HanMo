#pragma once

// Reversi, the rules. Freestanding: no renderer, no Activity, no storage.
//
// Eight by eight. A move must capture: you place a disc so that one or more
// straight lines of the opponent's discs are pinned between it and a disc of
// yours, and every pinned disc flips. A side with no capturing move passes, and
// when neither side can move the game is over and the larger army wins.
//
// The board is `cell[column][row]` with **row 0 at the top**, matching the order
// the screen draws in. Connect Four put row 0 at the bottom because gravity runs
// that way and it made the drop scan start at zero; Reversi has no gravity, so
// the only reason left to pick a direction is the one the renderer already uses.
//
// Sides are named for how they are DRAWN -- outlined and solid -- rather than
// black and white, following Checkers and Connect Four: this panel has one ink,
// and filled means whose, never whose turn.

#include <cstdint>

namespace reversi {

constexpr int kSize = 8;
constexpr int kCells = kSize * kSize;

constexpr uint8_t kEmpty = 0;
constexpr uint8_t kLight = 1;
constexpr uint8_t kDark = 2;

constexpr int8_t kNoCell = -1;

enum class Outcome : uint8_t {
  Running,
  LightWins,
  DarkWins,
  Draw,
};

struct Game {
  // cell[column][row], row 0 at the top. kEmpty, kLight or kDark.
  uint8_t cell[kSize][kSize];
  // Where the last disc was placed, so the board can point at it. Sixty-four
  // identical discs do not otherwise say what just changed, and on a board where
  // a single move can flip a dozen discs "what did they play" is the first thing
  // the other player asks.
  int8_t lastColumn;
  int8_t lastRow;
  uint8_t turn;
  Outcome outcome;
};

inline uint8_t other(const uint8_t side) { return side == kLight ? kDark : kLight; }

inline bool inside(const int column, const int row) {
  return column >= 0 && column < kSize && row >= 0 && row < kSize;
}

inline bool over(const Game& game) { return game.outcome != Outcome::Running; }

inline int discCount(const Game& game, const uint8_t side) {
  int count = 0;
  for (int column = 0; column < kSize; ++column) {
    for (int row = 0; row < kSize; ++row) {
      if (game.cell[column][row] == side) ++count;
    }
  }
  return count;
}

inline void start(Game& game) {
  for (int column = 0; column < kSize; ++column) {
    for (int row = 0; row < kSize; ++row) game.cell[column][row] = kEmpty;
  }
  // The standard opening: the four central cells, each colour on one diagonal.
  // Derived from the centre rather than written as literal 3s and 4s so the
  // relationship to the board survives anyone changing kSize.
  constexpr int low = kSize / 2 - 1;
  constexpr int high = kSize / 2;
  game.cell[low][low] = kLight;
  game.cell[high][high] = kLight;
  game.cell[low][high] = kDark;
  game.cell[high][low] = kDark;

  game.lastColumn = kNoCell;
  game.lastRow = kNoCell;
  // Dark opens. That is the rule of the game, not a coin flip, and unlike
  // Connect Four it costs the opener nothing: Reversi is not a solved
  // first-player win.
  game.turn = kDark;
  game.outcome = Outcome::Running;
}

// How many of the opponent's discs a disc of `side` placed at (column, row)
// would flip along direction (dc, dr).
//
// Zero unless a disc of `side` CLOSES the run. Running off the board captures
// nothing, and so does reaching an empty cell -- that second case is the whole
// of "a broken run is not a move", and it is why the loop condition tests the
// cell contents rather than only the bounds.
inline int capturedToward(const Game& game, const int column, const int row, const int dc, const int dr,
                          const uint8_t side) {
  const uint8_t them = other(side);
  int run = 0;
  int c = column + dc;
  int r = row + dr;
  while (inside(c, r) && game.cell[c][r] == them) {
    ++run;
    c += dc;
    r += dr;
  }
  if (run == 0 || !inside(c, r) || game.cell[c][r] != side) return 0;
  return run;
}

// Total discs a move at (column, row) would flip for `side`, across all eight
// directions. All eight are searched, not four: unlike a win line, a capture and
// its reverse are different captures, and one move legitimately flips runs on
// several rays at once.
inline int capturedBy(const Game& game, const int column, const int row, const uint8_t side) {
  if (!inside(column, row) || game.cell[column][row] != kEmpty) return 0;
  int total = 0;
  for (int dc = -1; dc <= 1; ++dc) {
    for (int dr = -1; dr <= 1; ++dr) {
      if (dc == 0 && dr == 0) continue;
      total += capturedToward(game, column, row, dc, dr, side);
    }
  }
  return total;
}

// Capturing something is the entire definition of a legal move, so there is no
// separate emptiness or bounds test here to fall out of step with it: capturedBy
// already answers zero for an occupied cell and for anything off the board.
inline bool legalFor(const Game& game, const int column, const int row, const uint8_t side) {
  return capturedBy(game, column, row, side) > 0;
}

inline bool legalAt(const Game& game, const int column, const int row) {
  if (over(game)) return false;
  return legalFor(game, column, row, game.turn);
}

inline int legalMoveCount(const Game& game, const uint8_t side) {
  int count = 0;
  for (int column = 0; column < kSize; ++column) {
    for (int row = 0; row < kSize; ++row) {
      if (legalFor(game, column, row, side)) ++count;
    }
  }
  return count;
}

// Bring `turn` and `outcome` up to date for whoever is now due to move.
//
// Three cases, in order: the side to move has a move and simply takes it; it has
// none and the opponent does, so the turn goes straight back and that skipped
// side is the PASS; or neither side can move, which ends the game on disc count.
// A Reversi game usually ends with empty cells still on the board, so waiting for
// a full board would hang on most real finishes.
//
// play() ends with this, and a game restored from storage must run it too,
// because a position can already be terminal before anyone touches it.
inline void settle(Game& game) {
  if (legalMoveCount(game, game.turn) > 0) return;

  const uint8_t them = other(game.turn);
  if (legalMoveCount(game, them) > 0) {
    game.turn = them;
    return;
  }

  const int light = discCount(game, kLight);
  const int dark = discCount(game, kDark);
  game.outcome = light > dark ? Outcome::LightWins : dark > light ? Outcome::DarkWins : Outcome::Draw;
}

// Place a disc for the side to move and flip everything it pins. False means the
// move was not legal, and then NOTHING changed -- callers route a raw tap in
// here, so on a sixty-four cell grid the rejected path runs more often than the
// accepted one and must leave the game untouched rather than half-applied.
inline bool play(Game& game, const int column, const int row) {
  if (over(game) || !legalFor(game, column, row, game.turn)) return false;

  const uint8_t side = game.turn;
  game.cell[column][row] = side;
  // Re-walk each direction instead of remembering the runs from the legality
  // test: the scan is eight short rays on an eight-wide board, and the duplicate
  // work buys a flip that cannot disagree with the rule that allowed the move.
  for (int dc = -1; dc <= 1; ++dc) {
    for (int dr = -1; dr <= 1; ++dr) {
      if (dc == 0 && dr == 0) continue;
      int run = capturedToward(game, column, row, dc, dr, side);
      int c = column + dc;
      int r = row + dr;
      for (; run > 0; --run) {
        game.cell[c][r] = side;
        c += dc;
        r += dr;
      }
    }
  }

  game.lastColumn = static_cast<int8_t>(column);
  game.lastRow = static_cast<int8_t>(row);
  game.turn = other(side);
  settle(game);
  return true;
}

}  // namespace reversi
