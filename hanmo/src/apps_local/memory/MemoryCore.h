#pragma once

// Memory Match, the rules. Freestanding: no renderer, no Activity, no storage.
//
// A grid of cards lies face down in shuffled pairs. The player exposes one card,
// then a second. A matching pair stays face up for good and the player keeps the
// turn; a mismatched pair goes back face down. The game ends when every pair is
// matched, and a move is one COMPLETED pair attempt.
//
// The grid size is CONFIGURABLE, which is the whole reason this game earns a
// place: the same rules give a four-year-old a six-pair board and an adult an
// eighteen-pair one, with no second implementation.
//
// Nothing here reads a clock. The panel manages two or three frames a second,
// so a core that waited out a mismatch would be waiting on the slowest part of
// the device; instead "two cards are up and wrong" is a declared PHASE and the
// caller decides when to end it. That also makes the whole state machine
// steppable from a host test, which a timer never is.

#include <cstdint>

namespace memorymatch {

// The panel is 480x800 portrait. Six columns leaves 80 px per card and eight
// rows leaves 100 px, both comfortably above the ~44 px a finger needs on a
// capacitive e-ink panel, so these are the bounds every level must respect
// rather than a guess at what looks nice.
constexpr int kMaxColumns = 6;
constexpr int kMaxRows = 8;
constexpr int kMaxCells = kMaxColumns * kMaxRows;
constexpr int kMaxPairs = kMaxCells / 2;

struct Level {
  // A stable ASCII key, NOT display text. The core localises nothing (see
  // reversi/ReversiCore.h: user-visible strings live in the Activity), so the
  // caller maps this to a translated label and may also use it as a save-slot
  // id -- which is why it must never be renamed for cosmetic reasons.
  const char* name;
  uint8_t columns;
  uint8_t rows;
};

constexpr int cellsIn(const Level& level) { return level.columns * level.rows; }
constexpr int pairsIn(const Level& level) { return cellsIn(level) / 2; }

// The difficulty table, easiest first. Cards, not columns, are what makes a
// level hard, so the table grows the cell count monotonically and tableValid()
// enforces it: a chooser that lists this table in order must get increasing
// difficulty for free instead of trusting whoever edits it next.
constexpr Level kLevels[] = {
    {"EASY", 3, 4},    // 12 cards,  6 pairs
    {"MEDIUM", 4, 4},  // 16 cards,  8 pairs
    {"HARD", 4, 6},    // 24 cards, 12 pairs
    {"EXPERT", 6, 6},  // 36 cards, 18 pairs
};
constexpr int kLevelCount = static_cast<int>(sizeof(kLevels) / sizeof(kLevels[0]));

// Whether a difficulty table is one this core can actually deal.
//
// Takes the table as an argument rather than reading kLevels directly so a test
// can hand it a deliberately broken table and watch it say no. A validator that
// only ever sees the one good table proves nothing about the next edit.
constexpr bool tableValid(const Level* levels, const int count) {
  if (levels == nullptr || count < 1) return false;
  for (int i = 0; i < count; ++i) {
    const Level& level = levels[i];
    if (level.name == nullptr || level.name[0] == '\0') return false;
    if (level.columns < 1 || level.columns > kMaxColumns) return false;
    if (level.rows < 1 || level.rows > kMaxRows) return false;
    // Odd grids cannot be dealt at all: one card would have no partner, so the
    // game could never complete. This is a hard error, not a rounded-down board.
    if (cellsIn(level) % 2 != 0) return false;
    if (i > 0 && cellsIn(level) <= cellsIn(levels[i - 1])) return false;
  }
  return true;
}

constexpr bool levelTableValid() { return tableValid(kLevels, kLevelCount); }

// Checked at COMPILE time, so a bad table cannot reach a device at all.
static_assert(levelTableValid(), "difficulty table must be even, ordered and fit the panel");
static_assert(kLevelCount >= 4, "the owner asked for at least four difficulty levels");
static_assert(cellsIn(kLevels[0]) <= 12, "the easiest level should be about twelve cards");
static_assert(cellsIn(kLevels[kLevelCount - 1]) >= 30, "the hardest level must be at least thirty cards");
static_assert(cellsIn(kLevels[kLevelCount - 1]) <= kMaxCells, "no level may exceed the panel grid");

// A cell index that is not a cell, for the two pick slots and for indexAt().
constexpr int8_t kNoCell = -1;
// A card slot that is not part of the current level's grid. The face buffer is
// always kMaxCells long so that editing kLevels never touches the struct, which
// leaves the tail of a small board needing a value that cannot be mistaken for
// pair id 0.
constexpr uint8_t kNoFace = 0xFF;

enum class Phase : uint8_t {
  // Nothing exposed; the next tap starts a move.
  Ready,
  // One card up, waiting for its partner.
  OneExposed,
  // Two cards up and they do NOT match. The caller must call resolveMismatch()
  // before play continues -- this is the state that replaces a timer, and it
  // exists so the player gets to look at the two faces for as long as they like
  // on a panel that cannot animate the flip back anyway.
  Mismatched,
  // Every pair matched.
  Done,
};

struct Game {
  // Pair id per cell, row-major: index = row * columns + column. Flat rather
  // than cell[column][row] like Reversi, because the grid size is chosen at
  // runtime and the shuffle works on a flat deck -- one coordinate system for
  // dealing and for drawing beats two that must agree.
  uint8_t face[kMaxCells];
  // Non-zero once a card has been matched and is face up for good.
  uint8_t matched[kMaxCells];
  // The cards exposed so far this move, kNoCell when none. Kept as indexes
  // rather than flags inside `matched` so a mismatched pair can be drawn face
  // up without being recorded as solved.
  int8_t firstPick;
  int8_t secondPick;
  // Completed pair attempts. uint16_t because a bad run on the 18-pair board can
  // pass 255 attempts and a wrapped score is worse than a big one.
  uint16_t moves;
  uint8_t matchedPairs;
  uint8_t level;
  Phase phase;
};

inline const Level& levelOf(const Game& game) { return kLevels[game.level]; }
inline int columnCount(const Game& game) { return levelOf(game).columns; }
inline int rowCount(const Game& game) { return levelOf(game).rows; }
inline int cellCount(const Game& game) { return cellsIn(levelOf(game)); }
inline int pairCount(const Game& game) { return pairsIn(levelOf(game)); }

inline bool onBoard(const Game& game, const int index) { return index >= 0 && index < cellCount(game); }

// Flat index for a grid position, kNoCell when it is off this level's board.
// Callers map a touch to a column and row and come straight here.
inline int indexAt(const Game& game, const int column, const int row) {
  if (column < 0 || column >= columnCount(game)) return kNoCell;
  if (row < 0 || row >= rowCount(game)) return kNoCell;
  return row * columnCount(game) + column;
}

// The pair id on a card, kNoFace when the index is not a cell of this level.
//
// Answers for face-DOWN cards too. The core has nothing to hide -- concealment
// is the renderer's job, gated on faceUp() -- and keeping the face readable is
// what lets the app walk the whole grid in one pass instead of maintaining a
// second shadow copy of the layout.
inline uint8_t faceAt(const Game& game, const int index) {
  return onBoard(game, index) ? game.face[index] : kNoFace;
}

inline bool isMatched(const Game& game, const int index) {
  return onBoard(game, index) && game.matched[index] != 0;
}

// Whether the renderer should show this card's face: solved for good, or one of
// the cards exposed in the move under way. The two reasons are deliberately
// answered by one function, because a card looks identical either way and a
// caller that had to combine them would eventually get it wrong in one of the
// several places that ask.
inline bool faceUp(const Game& game, const int index) {
  if (!onBoard(game, index)) return false;
  return game.matched[index] != 0 || index == game.firstPick || index == game.secondPick;
}

inline bool complete(const Game& game) { return game.phase == Phase::Done; }

// Whether the caller owes the core a resolveMismatch(). The app polls this to
// decide whether the next tap means "flip these back" instead of "expose a card".
inline bool awaitingMismatch(const Game& game) { return game.phase == Phase::Mismatched; }

// One step of a linear congruential generator, state carried in the caller's
// variable.
//
// Hand-rolled rather than std::minstd_rand: this core includes only <cstdint>
// like its neighbours, and dragging <random> into firmware to perform at most 47
// swaps would cost flash and tie the dealt layout to whatever libstdc++ the
// toolchain ships. Never std::random_device or time() -- the seed arrives from
// outside precisely so a layout can be reproduced in a test and restored from
// storage.
inline uint32_t nextRandom(uint32_t& state) {
  // Numerical Recipes' constants. The non-zero increment is the part that
  // matters here: a purely multiplicative generator seeded with 0 stays at 0
  // forever, which would deal the unshuffled deck to any caller whose stored
  // seed happened to be zero.
  state = state * 1664525u + 1013904223u;
  // The low bits of a power-of-two-modulus LCG have very short periods -- the
  // bottom bit alternates -- so the roll uses the top half of the word.
  return state >> 16;
}

// Deal a level face down in shuffled pairs. `seed` is the entire source of
// randomness and is never replaced by a clock reading, so the same seed always
// produces the same board.
inline void start(Game& game, const int level, const uint32_t seed) {
  // Clamp rather than reject. The level index arrives from stored settings, and
  // a build whose table lost an entry must still be able to start a game rather
  // than read off the end of kLevels.
  game.level = static_cast<uint8_t>(level >= 0 && level < kLevelCount ? level : 0);
  const int cells = cellCount(game);

  for (int i = 0; i < kMaxCells; ++i) {
    game.face[i] = i < cells ? static_cast<uint8_t>(i / 2) : kNoFace;
    game.matched[i] = 0;
  }

  // Fisher-Yates over the dealt cells only, walking down so each roll picks from
  // the part of the deck not yet placed. Seeding the deck in pair order first
  // means the pair counts are correct by construction and the shuffle can only
  // move cards, never create or lose one.
  uint32_t state = seed;
  for (int i = cells - 1; i > 0; --i) {
    const int j = static_cast<int>(nextRandom(state) % static_cast<uint32_t>(i + 1));
    const uint8_t held = game.face[i];
    game.face[i] = game.face[j];
    game.face[j] = held;
  }

  game.firstPick = kNoCell;
  game.secondPick = kNoCell;
  game.moves = 0;
  game.matchedPairs = 0;
  game.phase = Phase::Ready;
}

inline bool expose(Game& game, const int index) {
  // Only the two phases that are mid-move accept a card.
  //
  // An unresolved mismatch blocks everything, because otherwise the two wrong
  // faces could be replaced before the player had seen them -- the one thing a
  // memory game must not do, and with a 300-500 ms refresh stray taps land in
  // that window as a matter of course rather than as an edge case. A finished
  // board blocks everything for the plainer reason that there is nothing left
  // to turn over.
  if (game.phase != Phase::Ready && game.phase != Phase::OneExposed) return false;

  // The bound is the LEVEL's cell count, not the buffer's. The face buffer is
  // always kMaxCells long so that editing kLevels never touches the struct,
  // which means a 3x4 board has 36 readable slots that are not cells.
  if (!onBoard(game, index)) return false;
  // Already face up for good. Allowing it would let one card join a second pair
  // and push matchedPairs past pairCount, which is what completion is compared
  // against.
  if (game.matched[index] != 0) return false;
  // The same card tapped twice is not a pair: its face would be compared with
  // itself, every double tap would "match", and the board would solve itself.
  if (index == game.firstPick) return false;

  if (game.phase == Phase::Ready) {
    game.firstPick = static_cast<int8_t>(index);
    game.phase = Phase::OneExposed;
    return true;
  }

  game.secondPick = static_cast<int8_t>(index);
  // The attempt is counted here and only here: a move is a completed pair
  // attempt, so it is the SECOND card that costs the player something.
  ++game.moves;
  if (game.face[index] == game.face[game.firstPick]) {
    game.matched[game.firstPick] = 1;
    game.matched[index] = 1;
    ++game.matchedPairs;
    // A matched pair needs no acknowledgement -- the cards simply stay up and
    // the same player goes again -- so the pick slots are released immediately.
    game.firstPick = kNoCell;
    game.secondPick = kNoCell;
    // Settled on the pair that finishes the board, not on the tap after it, so
    // the app repaints the win exactly once -- at half a second a frame, a
    // completion noticed one event late is a visible stall.
    game.phase = game.matchedPairs == pairCount(game) ? Phase::Done : Phase::Ready;
  } else {
    game.phase = Phase::Mismatched;
  }
  return true;
}

// Turn a mismatched pair back face down. False when there is no mismatch to
// resolve, and then nothing changed.
//
// This is the function that replaces the timer every other implementation of
// this game uses. The caller decides when it fires -- the next tap, a button, a
// countdown it runs itself -- and because the decision lives entirely outside
// the rules, a host test can step the position one event at a time. Returning
// false rather than asserting lets the app route an unconditional "acknowledge"
// gesture here without first asking what phase it is in.
inline bool resolveMismatch(Game& game) {
  if (game.phase != Phase::Mismatched) return false;
  game.firstPick = kNoCell;
  game.secondPick = kNoCell;
  game.phase = Phase::Ready;
  return true;
}

}  // namespace memorymatch
