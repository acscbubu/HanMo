#pragma once

// Mahjong Solitaire, the rules. Freestanding: no renderer, no Activity, no
// storage.
//
// A stack of tiles is dealt face up over a multi-layer layout. A tile is FREE
// when nothing rests on top of it and at least one of its long edges -- left or
// right -- has no tile against it; the player removes matching pairs of free
// tiles and wins by emptying the layout. A deal with tiles left but no legal
// pair is a dead end, not a loss on points.
//
// THE TILE SET is the standard 144. Three suits of nine (bamboo, characters,
// circles) in four copies each, four winds in fours, three dragons in fours,
// then four flowers and four seasons as SINGLES. The singles are why matching
// cannot simply be "the same tile": the four flowers match one another and the
// four seasons match one another, and they are the only two groups where
// non-identical tiles pair. Everything else matches on group AND rank.
//
// A tile is one byte, group in the high nibble and rank in the low nibble, so a
// slot array is a plain byte array and a saved game is 144 bytes of it.
//
// Two decisions are documented at length further down because they are the two
// that silently break this game: the half-step COORDINATE CONVENTION the
// free-tile rule is written in, and THE LAYOUT, which is a table of
// coordinates rather than generated shape.

#include <cstdint>

namespace mahjong {

// Matching groups. The order is the order a tile sheet is usually drawn in, and
// it is also the deal order, so a sorted (unshuffled) set reads suits first.
constexpr uint8_t kBamboo = 0;
constexpr uint8_t kCharacters = 1;
constexpr uint8_t kCircles = 2;
constexpr uint8_t kWinds = 3;
constexpr uint8_t kDragons = 4;
constexpr uint8_t kFlowers = 5;
constexpr uint8_t kSeasons = 6;
constexpr int kGroupCount = 7;

// How many distinct tiles each group holds, and how many copies of each exist.
// Kept as two tiny tables rather than a switch because buildTileSet() is then a
// pair of loops that cannot disagree with the counts, and because 14 bytes of
// rodata is cheaper than the branches a switch compiles to.
inline constexpr uint8_t kGroupSize[kGroupCount] = {9, 9, 9, 4, 3, 4, 4};
inline constexpr uint8_t kGroupCopies[kGroupCount] = {4, 4, 4, 4, 4, 1, 1};

constexpr int kTiles = 144;

// An empty slot. 0xFF decodes to group 15, which no lookup accepts, so a stale
// byte cannot be mistaken for a playable tile.
constexpr uint8_t kNoTile = 0xFF;

constexpr uint8_t makeTile(const int group, const int rank) {
  return static_cast<uint8_t>((group << 4) | rank);
}

inline uint8_t tileGroup(const uint8_t tile) { return static_cast<uint8_t>(tile >> 4); }
inline uint8_t tileRank(const uint8_t tile) { return static_cast<uint8_t>(tile & 0x0F); }

// Flowers and seasons are the only groups whose tiles pair without being
// identical. The name is borrowed from card games because that is exactly what
// these eight tiles are: wild WITHIN their own group and nowhere else.
inline bool wildGroup(const uint8_t group) { return group == kFlowers || group == kSeasons; }

// Whether two slot bytes form a legal pair, ignoring where they sit.
//
// Takes raw slot bytes, including kNoTile, because the caller hands over
// whatever two slots the player tapped. Two cleared slots share a group (15)
// and a rank (15), so the kNoTile test has to come FIRST or an emptied layout
// would report moves forever.
inline bool tilesMatch(const uint8_t a, const uint8_t b) {
  if (a == kNoTile || b == kNoTile) return false;
  const uint8_t group = tileGroup(a);
  if (group != tileGroup(b)) return false;
  return wildGroup(group) || tileRank(a) == tileRank(b);
}

// The 144 tiles in canonical order, before any shuffle. Written out rather than
// stored as a constant array: the loops are smaller than the 144 bytes of table
// they replace, and flash is the scarce resource here.
inline void buildTileSet(uint8_t out[kTiles]) {
  int next = 0;
  for (int group = 0; group < kGroupCount; ++group) {
    for (int rank = 0; rank < kGroupSize[group]; ++rank) {
      for (int copy = 0; copy < kGroupCopies[group]; ++copy) {
        out[next++] = makeTile(group, rank);
      }
    }
  }
}

// ---------------------------------------------------------------------------
// COORDINATE CONVENTION
//
// A slot is (layer, x, y) in HALF-TILE steps, and the tile in it occupies the
// 2x2 block of half-cells [x, x+2) x [y, y+2). x grows rightwards, y grows
// DOWNWARDS and layer 0 is the table, with higher layers stacked on it. y runs
// down to match the order the screen draws in -- the same reasoning Reversi
// used for putting row 0 at the top.
//
// Half steps rather than whole tiles because classic layouts offset tiles by
// half a tile: the turtle's cap straddles the two tiles beneath it and its side
// wings sit between rows. Those positions are not expressible on a whole-tile
// grid at all, and a layout table that cannot express them pushes the problem
// into the geometry code instead.
//
// Two slots TOUCH when their footprints overlap, |dx| < 2 and |dy| < 2.
// Everything else is that one test with a different relationship:
//   covered -- a live tile ONE layer up whose footprint overlaps
//   left    -- a live tile on the SAME layer with |dy| < 2 and dx in {-2, -1}
//   right   -- the same with dx in {1, 2}
// dx of exactly +/-2 is flush contact. +/-1 would mean two tiles overlapping on
// one layer, which a well-formed layout never contains; it counts as blocking
// anyway, because a wrong layout table should jam a tile rather than quietly
// hand the player a tile that is buried.
//
// Note what is absent: Y NEIGHBOURS NEVER BLOCK. A tile leaves along its long
// edge, so the tiles above and below it in y are irrelevant, and treating all
// four neighbours alike is the single commonest way to get this rule wrong.
// ---------------------------------------------------------------------------

struct Slot {
  uint8_t layer;
  uint8_t x;
  uint8_t y;
};

// Whether two slots cover any of the same ground. Deliberately ignores `layer`:
// the callers want "same ground, one layer up" and "same ground, same layer"
// and those are different questions about the same 2D overlap.
inline bool footprintsOverlap(const Slot& a, const Slot& b) {
  const int dx = static_cast<int>(a.x) - static_cast<int>(b.x);
  const int dy = static_cast<int>(a.y) - static_cast<int>(b.y);
  return dx > -2 && dx < 2 && dy > -2 && dy < 2;
}

// Whether the tile in slot `index` can be taken: nothing on top of it, and at
// least one long edge clear.
//
// Takes the slot table explicitly instead of reading the shipped layout,
// because the cases where this rule breaks are three tiles wide and a 144-tile
// deal hides them -- and because a second layout then costs nothing.
inline bool freeAmong(const Slot* slots, const uint8_t* tiles, const int count, const int index) {
  if (index < 0 || index >= count || tiles[index] == kNoTile) return false;
  const Slot& here = slots[index];
  bool left = false;
  bool right = false;
  for (int other = 0; other < count; ++other) {
    if (other == index || tiles[other] == kNoTile) continue;
    const Slot& there = slots[other];
    // Only the layer DIRECTLY above can rest on this tile. A tile two layers up
    // may well overhang this one, but it is carried by the layer between, and if
    // that layer is clear here then nothing is actually touching this tile.
    if (there.layer == here.layer + 1 && footprintsOverlap(here, there)) return false;
    if (there.layer != here.layer) continue;
    const int dy = static_cast<int>(there.y) - static_cast<int>(here.y);
    if (dy <= -2 || dy >= 2) continue;
    const int dx = static_cast<int>(there.x) - static_cast<int>(here.x);
    if (dx >= -2 && dx <= -1) left = true;
    if (dx >= 1 && dx <= 2) right = true;
  }
  // One open edge is enough. The scan cannot stop early once both are blocked,
  // because a covering tile found later still overrides an open side.
  return !left || !right;
}

// ---------------------------------------------------------------------------
// THE LAYOUT
//
// Three stacked rectangles: 8 x 10 on the table, 6 x 8 inset one tile on top of
// it, 4 x 4 inset one tile again. 80 + 48 + 16 = 144, so the whole standard set
// is dealt and no tile of it has to be left out.
//
// Not the 144-tile turtle, and the reason is the panel. The turtle is fourteen
// tile columns wide over eight rows; on a 480 x 800 portrait screen that is 34
// pixels of tile width against 100 of height, which no tile face survives. This
// layout is eight columns by ten rows, so a tile cell is 60 x 80 -- the 3:4 of a
// real mahjong tile, upright, on a portrait screen. It opens 44 free tiles, the
// same order as a turtle, so the reshaping does not soften the game: a solid
// slab exposes only its left and right columns, which is as restrictive as the
// turtle's thin upper tiers.
//
// Every slab sits at a whole-tile offset, so no tile in THIS layout straddles
// two below it. The half-step grid is still the right convention: it costs one
// byte per slot, the free-tile rule is written in half-steps regardless, and a
// second layout with a straddling cap then needs no new geometry.
//
// Table order is layer, then y, then x -- a painter's order, back to front, so
// a renderer can walk the table straight through and never draw a buried tile
// over the tile on top of it.
// ---------------------------------------------------------------------------

constexpr int kColumns = 8;
constexpr int kRows = 10;
// The grid is in half-steps, so it is twice the tile count in each direction.
constexpr int kGridWidth = kColumns * 2;
constexpr int kGridHeight = kRows * 2;
constexpr int kLayers = 3;
constexpr int kSlots = kTiles;

// "No such slot". Negative so it cannot be confused with slot 0, which in this
// layout is the top-left tile of the table and a perfectly ordinary target.
constexpr int kNoSlot = -1;

// 144 slots x 3 bytes = 432 bytes of rodata. Deliberately a table and not a
// nest of loops: the parent app needs the coordinates to hit-test taps, a loop
// would have to be run to answer that, and the layout is the one part of this
// game that a designer might want to swap without touching any logic.
//
// `inline`, not plain constexpr. A namespace-scope constexpr array has internal
// linkage, so every translation unit that includes this header would carry its
// own 432 bytes; the activity, the renderer and the save code are three of them.
inline constexpr Slot kLayout[kSlots] = {
    // Layer 0 -- the table, 8 x 10. Its left and right columns are the only
    // ones with an open long edge, which is what makes a solid base playable.
    {0,  0,  0}, {0,  2,  0}, {0,  4,  0}, {0,  6,  0}, {0,  8,  0}, {0, 10,  0}, {0, 12,  0}, {0, 14,  0},
    {0,  0,  2}, {0,  2,  2}, {0,  4,  2}, {0,  6,  2}, {0,  8,  2}, {0, 10,  2}, {0, 12,  2}, {0, 14,  2},
    {0,  0,  4}, {0,  2,  4}, {0,  4,  4}, {0,  6,  4}, {0,  8,  4}, {0, 10,  4}, {0, 12,  4}, {0, 14,  4},
    {0,  0,  6}, {0,  2,  6}, {0,  4,  6}, {0,  6,  6}, {0,  8,  6}, {0, 10,  6}, {0, 12,  6}, {0, 14,  6},
    {0,  0,  8}, {0,  2,  8}, {0,  4,  8}, {0,  6,  8}, {0,  8,  8}, {0, 10,  8}, {0, 12,  8}, {0, 14,  8},
    {0,  0, 10}, {0,  2, 10}, {0,  4, 10}, {0,  6, 10}, {0,  8, 10}, {0, 10, 10}, {0, 12, 10}, {0, 14, 10},
    {0,  0, 12}, {0,  2, 12}, {0,  4, 12}, {0,  6, 12}, {0,  8, 12}, {0, 10, 12}, {0, 12, 12}, {0, 14, 12},
    {0,  0, 14}, {0,  2, 14}, {0,  4, 14}, {0,  6, 14}, {0,  8, 14}, {0, 10, 14}, {0, 12, 14}, {0, 14, 14},
    {0,  0, 16}, {0,  2, 16}, {0,  4, 16}, {0,  6, 16}, {0,  8, 16}, {0, 10, 16}, {0, 12, 16}, {0, 14, 16},
    {0,  0, 18}, {0,  2, 18}, {0,  4, 18}, {0,  6, 18}, {0,  8, 18}, {0, 10, 18}, {0, 12, 18}, {0, 14, 18},
    // Layer 1 -- 6 x 8, inset one tile all round so layer 0's outer ring shows.
    {1,  2,  2}, {1,  4,  2}, {1,  6,  2}, {1,  8,  2}, {1, 10,  2}, {1, 12,  2},
    {1,  2,  4}, {1,  4,  4}, {1,  6,  4}, {1,  8,  4}, {1, 10,  4}, {1, 12,  4},
    {1,  2,  6}, {1,  4,  6}, {1,  6,  6}, {1,  8,  6}, {1, 10,  6}, {1, 12,  6},
    {1,  2,  8}, {1,  4,  8}, {1,  6,  8}, {1,  8,  8}, {1, 10,  8}, {1, 12,  8},
    {1,  2, 10}, {1,  4, 10}, {1,  6, 10}, {1,  8, 10}, {1, 10, 10}, {1, 12, 10},
    {1,  2, 12}, {1,  4, 12}, {1,  6, 12}, {1,  8, 12}, {1, 10, 12}, {1, 12, 12},
    {1,  2, 14}, {1,  4, 14}, {1,  6, 14}, {1,  8, 14}, {1, 10, 14}, {1, 12, 14},
    {1,  2, 16}, {1,  4, 16}, {1,  6, 16}, {1,  8, 16}, {1, 10, 16}, {1, 12, 16},
    // Layer 2 -- 4 x 4, inset one tile from layer 1 and centred on it.
    {2,  4,  6}, {2,  6,  6}, {2,  8,  6}, {2, 10,  6},
    {2,  4,  8}, {2,  6,  8}, {2,  8,  8}, {2, 10,  8},
    {2,  4, 10}, {2,  6, 10}, {2,  8, 10}, {2, 10, 10},
    {2,  4, 12}, {2,  6, 12}, {2,  8, 12}, {2, 10, 12},
};

// The slot at exact grid coordinates, or kNoSlot. A tap resolves to a slot by
// rounding to half-steps and asking here, from the top layer down.
//
// A linear scan, not a reverse index: a 3 x 16 x 20 lookup table would be 960
// bytes to save 144 comparisons on a 2-3 frames-per-second panel, and flash is
// the scarce resource on this device, not cycles.
inline int slotAt(const int layer, const int x, const int y) {
  for (int i = 0; i < kSlots; ++i) {
    if (kLayout[i].layer == layer && kLayout[i].x == x && kLayout[i].y == y) return i;
  }
  return kNoSlot;
}

// One step of the std::minstd_rand recurrence, state = state * 48271 mod
// 2^31-1, written out instead of including <random>: the standard header drags
// in kilobytes of flash for a generator that is one line, and this firmware has
// roughly 1.19 MB of its app slot left to share between four new games.
//
// Deterministic on purpose, and the seed is an ARGUMENT -- never
// std::random_device, never time(). A save then holds the game rather than a
// copy of it, and a deal that turned out to be a dead end can be replayed
// exactly from the number that produced it.
inline uint32_t nextRandom(uint32_t& state) {
  state = static_cast<uint32_t>((static_cast<uint64_t>(state) * 48271u) % 2147483647u);
  return state;
}

// The 144 tiles in deal order for `seed`.
//
// Exposed rather than hidden inside deal() so a test can pin an exact deal; a
// deal that is only observable through a Game cannot be compared against an
// independent reference.
inline void shuffledTiles(const uint32_t seed, uint8_t out[kTiles]) {
  buildTileSet(out);
  // Zero is the one state this recurrence can never leave, and 2^31-1 folds to
  // zero. Both are nudged rather than rejected, because callers pass whatever
  // they have -- an uptime reading, a typed-in number -- and every one of them
  // deserves a game.
  uint32_t state = seed % 2147483647u;
  if (state == 0) state = 1u;
  for (int i = kTiles - 1; i > 0; --i) {
    const int j = static_cast<int>(nextRandom(state) % static_cast<uint32_t>(i + 1));
    const uint8_t swap = out[i];
    out[i] = out[j];
    out[j] = swap;
  }
}

// The whole game: one byte per slot plus the seed that filled them, 148 bytes,
// small enough to save verbatim.
//
// No cached tile count and no stored outcome. Both are a scan of 144 bytes to
// derive, which this panel has time for several thousand times over between
// frames, and a cached copy is a second source of truth that a truncated save
// can put at odds with the board.
struct Game {
  // tile[slot] is the tile in kLayout[slot], or kNoTile once it has been taken.
  uint8_t tile[kSlots];
  uint32_t seed;
};

inline void deal(Game& game, const uint32_t seed) {
  // Deal order IS table order, so the shuffle writes straight into the slots.
  // Layering the deal (fill layer 0 first, then layer 1) would be a second
  // ordering to keep in step with kLayout for no gain: the tiles are random
  // either way.
  shuffledTiles(seed, game.tile);
  game.seed = seed;
}

inline int remaining(const Game& game) {
  int count = 0;
  for (int slot = 0; slot < kSlots; ++slot) {
    if (game.tile[slot] != kNoTile) ++count;
  }
  return count;
}

// Whether the tile in `slot` of the shipped layout can be taken.
inline bool freeSlot(const Game& game, const int slot) {
  return freeAmong(kLayout, game.tile, kSlots, slot);
}

// Every slot holding a tile that can be taken, written into `out` in table
// order; returns how many. `out` must hold kSlots entries.
//
// Exists because availableMoves() and the renderer's highlight both need the
// same list, and because the alternative -- asking freeSlot() about every
// candidate inside a nested loop -- is the O(n^3) version of the same answer.
inline int collectFree(const Game& game, int* out) {
  int count = 0;
  for (int slot = 0; slot < kSlots; ++slot) {
    if (freeSlot(game, slot)) out[count++] = slot;
  }
  return count;
}

// Whether tapping slots `a` and `b` is a legal move: two different slots, both
// holding a free tile, and the two tiles match.
//
// Bounds-checks its arguments because they arrive from a tap that was resolved
// against screen coordinates, and a miss can land on kNoSlot. The a == b test
// is not redundant with the match test: a tile always matches itself.
inline bool canPair(const Game& game, const int a, const int b) {
  if (a == b) return false;
  if (a < 0 || a >= kSlots || b < 0 || b >= kSlots) return false;
  if (!tilesMatch(game.tile[a], game.tile[b])) return false;
  return freeSlot(game, a) && freeSlot(game, b);
}

// Take a matching pair off the layout. False means the move was not legal, and
// then nothing changed at all.
inline bool removePair(Game& game, const int a, const int b) {
  if (!canPair(game, a, b)) return false;
  game.tile[a] = kNoTile;
  game.tile[b] = kNoTile;
  return true;
}

// How many legal pairs the player could play right now.
//
// Counts UNORDERED pairs, so four identical free tiles are six moves rather
// than two: the number answers "how many taps are available", which is what a
// hint and a stuck-game banner both want. Four free tiles that are two separate
// pairs would also be two moves, and conflating the two counts would make the
// number useless for either purpose.
inline int availableMoves(const Game& game) {
  int reachable[kSlots];
  const int count = collectFree(game, reachable);
  int moves = 0;
  for (int i = 0; i < count; ++i) {
    for (int j = i + 1; j < count; ++j) {
      // Both are known free, so only the tile faces are left to check -- going
      // back through canPair() would re-run the geometry count^2 times.
      if (tilesMatch(game.tile[reachable[i]], game.tile[reachable[j]])) ++moves;
    }
  }
  return moves;
}

// The deal is cleared. The only way to win.
//
// Tests the tiles rather than a counter of removals, so a save written
// mid-removal cannot claim a win over a board that still has tiles on it.
inline bool won(const Game& game) { return remaining(game) == 0; }

// Tiles left and nothing legal to play with them.
//
// The tile ORDER within the layout decides this, not the tile set: a random
// deal of a pairable set is frequently unwinnable, which is why this is a
// first-class ending and not an error. Both conditions are needed -- an empty
// layout also has no moves, and calling that a dead end would announce a loss
// at the moment of winning.
inline bool deadEnd(const Game& game) {
  return remaining(game) > 0 && availableMoves(game) == 0;
}

}  // namespace mahjong
