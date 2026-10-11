"""Compile the actual Mahjong Solitaire rules with host g++ and drive real layouts through them.

Freestanding core, same shape as reversi/ReversiCore.h: no renderer, no Activity,
no storage, so the rules can be exercised directly from a host harness.
"""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
GAME_DIR = ROOT / "src/apps_local/mahjong"

HARNESS = r'''
#include "MahjongCore.h"

#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>

using namespace mahjong;

// Strip the layout bare so a scenario can put three tiles on it and reason
// about them. Hand-placed positions are the only way these tests stay
// auditable; asserting about slot 97 of a 144-tile deal would not be readable.
static void clearBoard(Game& game) {
  for (int slot = 0; slot < kSlots; ++slot) game.tile[slot] = kNoTile;
  game.seed = 0;
}

static void place(Game& game, const int layer, const int x, const int y, const uint8_t tile) {
  const int slot = slotAt(layer, x, y);
  assert(slot != kNoSlot);
  game.tile[slot] = tile;
}

int main(int argc, char** argv) {
  assert(argc == 2);
  const std::string scenario = argv[1];

  if (scenario == "tileset") {
    uint8_t set[kTiles];
    buildTileSet(set);

    // The standard 144: three suits of nine in fours, four winds in fours,
    // three dragons in fours, then four flowers and four seasons as singles.
    int perGroup[kGroupCount] = {0, 0, 0, 0, 0, 0, 0};
    int perTile[256];
    std::memset(perTile, 0, sizeof(perTile));
    for (int i = 0; i < kTiles; ++i) {
      assert(tileGroup(set[i]) < kGroupCount);
      assert(tileRank(set[i]) < kGroupSize[tileGroup(set[i])]);
      ++perGroup[tileGroup(set[i])];
      ++perTile[set[i]];
    }
    assert(perGroup[kBamboo] == 36);
    assert(perGroup[kCharacters] == 36);
    assert(perGroup[kCircles] == 36);
    assert(perGroup[kWinds] == 16);
    assert(perGroup[kDragons] == 12);
    assert(perGroup[kFlowers] == 4);
    assert(perGroup[kSeasons] == 4);

    // Each suit, wind and dragon identity appears exactly four times; each
    // flower and each season appears exactly once. That difference is the whole
    // reason flowers and seasons need their own matching rule.
    for (int rank = 0; rank < 9; ++rank) {
      assert(perTile[makeTile(kBamboo, rank)] == 4);
      assert(perTile[makeTile(kCharacters, rank)] == 4);
      assert(perTile[makeTile(kCircles, rank)] == 4);
    }
    for (int rank = 0; rank < 4; ++rank) {
      assert(perTile[makeTile(kWinds, rank)] == 4);
      assert(perTile[makeTile(kFlowers, rank)] == 1);
      assert(perTile[makeTile(kSeasons, rank)] == 1);
    }
    for (int rank = 0; rank < 3; ++rank) assert(perTile[makeTile(kDragons, rank)] == 4);

    // Every MATCHING group holds an even number of tiles, so a full layout can
    // in principle be cleared to the last pair. An odd group would leave a tile
    // that can never be removed however well the deal is played.
    for (int group = 0; group < kGroupCount; ++group) assert(perGroup[group] % 2 == 0);

    // The packing has to survive a round trip, because the slot array stores
    // these bytes and nothing else.
    for (int group = 0; group < kGroupCount; ++group) {
      for (int rank = 0; rank < kGroupSize[group]; ++rank) {
        const uint8_t tile = makeTile(group, rank);
        assert(tileGroup(tile) == group);
        assert(tileRank(tile) == rank);
        assert(tile != kNoTile);
      }
    }
    puts("standard 144-tile set OK");

  } else if (scenario == "matching") {
    // A suit tile pairs only with its own rank. "Same group, any rank" is the
    // commonest misreading of the rules, and it would make the game trivial.
    assert(tilesMatch(makeTile(kBamboo, 4), makeTile(kBamboo, 4)));
    assert(!tilesMatch(makeTile(kBamboo, 4), makeTile(kBamboo, 5)));
    // The same rank in a different suit is a different tile.
    assert(!tilesMatch(makeTile(kBamboo, 4), makeTile(kCircles, 4)));
    assert(!tilesMatch(makeTile(kCharacters, 0), makeTile(kCircles, 0)));
    // Honours behave like suits: identical, or no pair.
    assert(tilesMatch(makeTile(kWinds, 2), makeTile(kWinds, 2)));
    assert(!tilesMatch(makeTile(kWinds, 2), makeTile(kWinds, 3)));
    assert(tilesMatch(makeTile(kDragons, 1), makeTile(kDragons, 1)));
    assert(!tilesMatch(makeTile(kDragons, 0), makeTile(kDragons, 2)));
    assert(!tilesMatch(makeTile(kWinds, 0), makeTile(kDragons, 0)));

    // The exception, and the only one: every flower pairs with every other
    // flower and every season with every other season. Each of those eight
    // tiles is unique, so without this rule none of them could ever be removed.
    for (int a = 0; a < 4; ++a) {
      for (int b = 0; b < 4; ++b) {
        assert(tilesMatch(makeTile(kFlowers, a), makeTile(kFlowers, b)));
        assert(tilesMatch(makeTile(kSeasons, a), makeTile(kSeasons, b)));
        // Flowers and seasons are TWO groups, not one pool of bonus tiles. A
        // single pooled group would let a flower take a season.
        assert(!tilesMatch(makeTile(kFlowers, a), makeTile(kSeasons, b)));
      }
    }
    assert(wildGroup(kFlowers));
    assert(wildGroup(kSeasons));
    for (int group = kBamboo; group <= kDragons; ++group) {
      assert(!wildGroup(static_cast<uint8_t>(group)));
    }

    // A cleared slot matches nothing, not even another cleared slot: pair
    // legality is asked about raw slot bytes, and two empty slots must never
    // read as a move.
    assert(!tilesMatch(kNoTile, kNoTile));
    assert(!tilesMatch(kNoTile, makeTile(kFlowers, 0)));
    assert(!tilesMatch(makeTile(kBamboo, 0), kNoTile));
    puts("suits match on rank, flowers and seasons match within group OK");

  } else if (scenario == "freetile") {
    // Hand-built arrangements rather than the shipped layout: the free-tile
    // rule is pure geometry, and every case where implementations get it wrong
    // is three tiles wide, where a 144-tile deal would hide it.

    // Three tiles flush in a row on one layer. The middle one is pinned.
    {
      const Slot slots[3] = {{0, 0, 0}, {0, 2, 0}, {0, 4, 0}};
      uint8_t tiles[3] = {makeTile(kBamboo, 0), makeTile(kBamboo, 1), makeTile(kBamboo, 2)};
      assert(freeAmong(slots, tiles, 3, 0));
      assert(!freeAmong(slots, tiles, 3, 1));
      assert(freeAmong(slots, tiles, 3, 2));
      // Taking the left-hand tile away frees the middle one, and the slot it
      // left behind is not itself free: an empty slot has no tile to remove.
      tiles[0] = kNoTile;
      assert(!freeAmong(slots, tiles, 3, 0));
      assert(freeAmong(slots, tiles, 3, 1));
    }

    // Blocked from above. Both tiles underneath have a clear outer edge and are
    // STILL not free -- something resting on top beats an open side. The
    // covering tile straddles them on the half-step grid instead of lining up
    // with either, so an "equal x" cover test would miss both.
    {
      const Slot slots[3] = {{0, 0, 0}, {0, 2, 0}, {1, 1, 0}};
      uint8_t tiles[3] = {makeTile(kCircles, 0), makeTile(kCircles, 0), makeTile(kWinds, 0)};
      assert(!freeAmong(slots, tiles, 3, 0));
      assert(!freeAmong(slots, tiles, 3, 1));
      assert(freeAmong(slots, tiles, 3, 2));
      tiles[2] = kNoTile;
      assert(freeAmong(slots, tiles, 3, 0));
      assert(freeAmong(slots, tiles, 3, 1));
    }

    // Tiles stacked in Y on one layer never block each other: only the LONG
    // edges matter, because a tile is slid out sideways. An implementation that
    // treats all four neighbours alike fails here and nowhere else.
    {
      const Slot slots[2] = {{0, 4, 0}, {0, 4, 2}};
      uint8_t tiles[2] = {makeTile(kDragons, 0), makeTile(kDragons, 0)};
      assert(freeAmong(slots, tiles, 2, 0));
      assert(freeAmong(slots, tiles, 2, 1));
    }

    // Half-step neighbours block. The middle tile is pinned by two tiles that
    // share only half its height; comparing rows for equality rather than for
    // overlap would call it free.
    {
      const Slot slots[3] = {{0, 2, 1}, {0, 4, 2}, {0, 6, 3}};
      uint8_t tiles[3] = {makeTile(kBamboo, 8), makeTile(kBamboo, 8), makeTile(kCircles, 8)};
      assert(!freeAmong(slots, tiles, 3, 1));
      assert(freeAmong(slots, tiles, 3, 0));
      assert(freeAmong(slots, tiles, 3, 2));
    }

    // A FULL tile of vertical offset is not an overlap. The same three columns
    // as above, stepped twice as far, touch nothing at all.
    {
      const Slot slots[3] = {{0, 2, 0}, {0, 4, 2}, {0, 6, 4}};
      uint8_t tiles[3] = {makeTile(kWinds, 1), makeTile(kWinds, 1), makeTile(kWinds, 2)};
      assert(freeAmong(slots, tiles, 3, 0));
      assert(freeAmong(slots, tiles, 3, 1));
      assert(freeAmong(slots, tiles, 3, 2));
    }

    // Only the layer DIRECTLY above can block. The layer-2 tile here overhangs
    // the layer-0 tile, but the layer-1 tile between them does not, so nothing
    // is resting on the bottom tile and it lifts straight out.
    {
      const Slot slots[3] = {{0, 0, 0}, {1, 2, 0}, {2, 1, 0}};
      uint8_t tiles[3] = {makeTile(kCharacters, 0), makeTile(kCharacters, 1),
                          makeTile(kCharacters, 2)};
      assert(freeAmong(slots, tiles, 3, 0));
      assert(!freeAmong(slots, tiles, 3, 1));
      assert(freeAmong(slots, tiles, 3, 2));
    }
    puts("free-tile rule: covered beats an open side, sides on long edges only OK");

  } else if (scenario == "layout") {
    // The shipped layout is a table of coordinates and a table cannot check
    // itself. Everything asserted here is a property the rules and the renderer
    // both rely on.
    assert(kSlots == kTiles);
    assert(kSlots == 144);
    assert(kLayers == 3);

    int perLayer[kLayers] = {0, 0, 0};
    uint8_t minX = 255;
    uint8_t maxX = 0;
    uint8_t minY = 255;
    uint8_t maxY = 0;
    for (int i = 0; i < kSlots; ++i) {
      const Slot& slot = kLayout[i];
      assert(slot.layer < kLayers);
      assert(slot.x + 2 <= kGridWidth);
      assert(slot.y + 2 <= kGridHeight);
      ++perLayer[slot.layer];
      if (slot.x < minX) minX = slot.x;
      if (slot.x > maxX) maxX = slot.x;
      if (slot.y < minY) minY = slot.y;
      if (slot.y > maxY) maxY = slot.y;
    }
    assert(perLayer[0] == 80);
    assert(perLayer[1] == 48);
    assert(perLayer[2] == 16);

    // The table fills the declared grid exactly. A renderer scales a tile to
    // kGridWidth/kGridHeight half-steps and would letterbox or clip otherwise.
    assert(minX == 0);
    assert(maxX + 2 == kGridWidth);
    assert(minY == 0);
    assert(maxY + 2 == kGridHeight);
    assert(kColumns * 2 == kGridWidth);
    assert(kRows * 2 == kGridHeight);

    // No two tiles share ground on one layer. Two slots in the same place would
    // leave one of them permanently unreachable, and the free-tile rule would
    // report both as blocked by each other.
    for (int a = 0; a < kSlots; ++a) {
      for (int b = a + 1; b < kSlots; ++b) {
        if (kLayout[a].layer != kLayout[b].layer) continue;
        assert(!footprintsOverlap(kLayout[a], kLayout[b]));
      }
    }

    // Nothing floats: EVERY half-cell under an upper tile is covered by a tile
    // on the layer below. "Overlaps something below" is the weaker test layouts
    // usually get checked with, and it happily accepts a tile balanced on one
    // corner of one neighbour.
    for (int i = 0; i < kSlots; ++i) {
      const Slot& slot = kLayout[i];
      if (slot.layer == 0) continue;
      for (int dx = 0; dx < 2; ++dx) {
        for (int dy = 0; dy < 2; ++dy) {
          const int cx = slot.x + dx;
          const int cy = slot.y + dy;
          bool supported = false;
          for (int j = 0; j < kSlots && !supported; ++j) {
            const Slot& under = kLayout[j];
            if (under.layer + 1 != slot.layer) continue;
            supported = cx >= under.x && cx < under.x + 2 && cy >= under.y && cy < under.y + 2;
          }
          assert(supported);
        }
      }
    }

    // slotAt is how a tap becomes a slot index, so it has to be exact rather
    // than nearest.
    for (int i = 0; i < kSlots; ++i) {
      const Slot& slot = kLayout[i];
      assert(slotAt(slot.layer, slot.x, slot.y) == i);
    }
    assert(slotAt(0, 1, 0) == kNoSlot);   // odd half-step, between two slots
    assert(slotAt(2, 0, 0) == kNoSlot);   // the top layer is inset
    assert(slotAt(kLayers, 0, 0) == kNoSlot);
    puts("layout table: 144 slots, no overlaps, nothing floating OK");

  } else if (scenario == "deal") {
    // Determinism first: a seed has to name a deal, or a save cannot be resumed
    // and a reported bug cannot be replayed.
    uint8_t first[kTiles];
    uint8_t second[kTiles];
    shuffledTiles(1u, first);
    shuffledTiles(1u, second);
    assert(std::memcmp(first, second, kTiles) == 0);
    shuffledTiles(2u, second);
    assert(std::memcmp(first, second, kTiles) != 0);

    // The exact deal for seed 20261006. These bytes come from a separate
    // reference implementation of the same recurrence in the test generator,
    // not from recording what this header happens to produce, so a changed
    // multiplier or a Fisher-Yates loop run the other way fails here.
    uint8_t pinned[kTiles];
    shuffledTiles(20261006u, pinned);
    const uint8_t expectHead[8] = {0x00, 0x04, 0x14, 0x04, 0x18, 0x41, 0x13, 0x41};
    for (int i = 0; i < 8; ++i) assert(pinned[i] == expectHead[i]);
    const uint8_t expectTail[4] = {0x62, 0x23, 0x33, 0x02};
    for (int i = 0; i < 4; ++i) assert(pinned[kTiles - 4 + i] == expectTail[i]);
    // A digest over all 144, so the pin covers the middle of the deal too.
    uint32_t digest = 2166136261u;
    for (int i = 0; i < kTiles; ++i) {
      digest = (digest ^ static_cast<uint32_t>(pinned[i])) * 16777619u;
    }
    assert(digest == 0xE34A52CBu);

    // Seed 0 must still deal a shuffled game. A generator that latches at zero
    // would hand out the sorted set, which is both unmistakable and unplayable
    // as a surprise.
    uint8_t zeroSeed[kTiles];
    uint8_t sorted[kTiles];
    shuffledTiles(0u, zeroSeed);
    buildTileSet(sorted);
    assert(std::memcmp(zeroSeed, sorted, kTiles) != 0);
    assert(zeroSeed[0] == 0x20);

    // A shuffle PERMUTES: every identity still appears the right number of
    // times, or the deal would no longer be fully pairable.
    int perTile[256];
    std::memset(perTile, 0, sizeof(perTile));
    for (int i = 0; i < kTiles; ++i) ++perTile[pinned[i]];
    int perTileSorted[256];
    std::memset(perTileSorted, 0, sizeof(perTileSorted));
    for (int i = 0; i < kTiles; ++i) ++perTileSorted[sorted[i]];
    assert(std::memcmp(perTile, perTileSorted, sizeof(perTile)) == 0);

    // The deal lands on the layout in table order and keeps its seed, so the
    // whole game state is 144 bytes plus the seed that produced it.
    Game game;
    deal(game, 7u);
    assert(game.seed == 7u);
    assert(remaining(game) == kTiles);
    for (int i = 0; i < kSlots; ++i) assert(game.tile[i] != kNoTile);
    uint8_t expected[kTiles];
    shuffledTiles(7u, expected);
    assert(std::memcmp(game.tile, expected, kTiles) == 0);
    puts("the deal is a pure function of its seed OK");

  } else if (scenario == "removal") {
    Game game;
    clearBoard(game);
    // Three tiles flush in the top row of the table. The outer two are a pair;
    // between them sits a bamboo 1 that is pinned.
    place(game, 0, 0, 0, makeTile(kCircles, 3));
    place(game, 0, 2, 0, makeTile(kBamboo, 0));
    place(game, 0, 4, 0, makeTile(kCircles, 3));
    const int left = slotAt(0, 0, 0);
    const int mid = slotAt(0, 2, 0);
    const int right = slotAt(0, 4, 0);
    assert(remaining(game) == 3);
    assert(freeSlot(game, left));
    assert(!freeSlot(game, mid));
    assert(freeSlot(game, right));

    assert(canPair(game, left, right));
    assert(!canPair(game, left, mid));
    // A tile cannot pair with itself however free it is. The app sends two slot
    // indices and a double tap on one tile is not a move.
    assert(!canPair(game, left, left));
    // Indices off the end are refused, not read.
    assert(!canPair(game, left, kNoSlot));
    assert(!canPair(game, kSlots, left));

    assert(availableMoves(game) == 1);
    int freeList[kSlots];
    assert(collectFree(game, freeList) == 2);
    assert(freeList[0] == left);
    assert(freeList[1] == right);

    // Removing a pair empties both slots and touches nothing else.
    assert(removePair(game, left, right));
    assert(game.tile[left] == kNoTile);
    assert(game.tile[right] == kNoTile);
    assert(game.tile[mid] == makeTile(kBamboo, 0));
    assert(remaining(game) == 1);
    assert(availableMoves(game) == 0);
    // The same removal a second time is refused: the slots are empty now.
    assert(!removePair(game, left, right));

    // An illegal removal must change NOTHING. The app routes a pair of taps
    // straight here, so on a 144-slot layout the rejected path runs far more
    // often than the accepted one and may not leave a half-applied board.
    clearBoard(game);
    place(game, 0, 0, 0, makeTile(kFlowers, 0));
    place(game, 0, 2, 0, makeTile(kSeasons, 1));
    const Game before = game;
    assert(!removePair(game, slotAt(0, 0, 0), slotAt(0, 2, 0)));
    assert(std::memcmp(&before, &game, sizeof(Game)) == 0);

    // Two DIFFERENT flowers are a legal pair, so the move count has to be built
    // on the matching rule and not on tile identity.
    clearBoard(game);
    place(game, 0, 0, 0, makeTile(kFlowers, 0));
    place(game, 0, 2, 0, makeTile(kFlowers, 3));
    assert(availableMoves(game) == 1);
    assert(removePair(game, slotAt(0, 0, 0), slotAt(0, 2, 0)));
    assert(remaining(game) == 0);

    // Four identical free tiles are SIX pairs, not two moves. The count is of
    // taps the player could legally make, which is what a hint button and a
    // "no moves left" banner are both asking about. Stacked in y, so none of
    // them blocks another.
    clearBoard(game);
    place(game, 0, 0, 0, makeTile(kWinds, 1));
    place(game, 0, 0, 2, makeTile(kWinds, 1));
    place(game, 0, 0, 4, makeTile(kWinds, 1));
    place(game, 0, 0, 6, makeTile(kWinds, 1));
    assert(collectFree(game, freeList) == 4);
    assert(availableMoves(game) == 6);
    puts("pair legality, removal and the available-move count OK");

  } else if (scenario == "ending") {
    Game game;
    int freeList[kSlots];

    // An empty layout is the win. It also has no moves, and that must NOT read
    // as a dead end: the two endings share "no legal pair" and are told apart
    // only by whether anything is left.
    clearBoard(game);
    assert(remaining(game) == 0);
    assert(won(game));
    assert(!deadEnd(game));
    assert(availableMoves(game) == 0);

    // The last pair, played out. Two seasons, which are different tiles.
    clearBoard(game);
    place(game, 0, 0, 0, makeTile(kSeasons, 0));
    place(game, 0, 2, 0, makeTile(kSeasons, 2));
    assert(!won(game));
    assert(!deadEnd(game));
    assert(availableMoves(game) == 1);
    assert(removePair(game, slotAt(0, 0, 0), slotAt(0, 2, 0)));
    assert(won(game));
    assert(!deadEnd(game));

    // Two tiles left that do not match: the plain dead end.
    clearBoard(game);
    place(game, 0, 0, 0, makeTile(kBamboo, 0));
    place(game, 0, 2, 0, makeTile(kCircles, 0));
    assert(!won(game));
    assert(availableMoves(game) == 0);
    assert(deadEnd(game));

    // The dead end that matters: a matching pair IS still on the layout and the
    // game is over anyway, because neither of the two is free. A dead-end test
    // that looks for matching tiles instead of matching FREE tiles calls this
    // position playable and leaves the player staring at it.
    clearBoard(game);
    place(game, 0, 0, 0, makeTile(kBamboo, 0));
    place(game, 0, 2, 0, makeTile(kWinds, 0));
    place(game, 0, 4, 0, makeTile(kBamboo, 1));
    place(game, 0, 6, 0, makeTile(kWinds, 0));
    place(game, 0, 8, 0, makeTile(kBamboo, 2));
    assert(tilesMatch(game.tile[slotAt(0, 2, 0)], game.tile[slotAt(0, 6, 0)]));
    assert(collectFree(game, freeList) == 2);
    assert(availableMoves(game) == 0);
    assert(deadEnd(game));
    assert(!won(game));
    // Opening one end is not enough -- one of the pair is free, the other is
    // still pinned -- and opening both revives the position. No tile moved.
    game.tile[slotAt(0, 0, 0)] = kNoTile;
    assert(deadEnd(game));
    game.tile[slotAt(0, 8, 0)] = kNoTile;
    assert(!deadEnd(game));
    assert(availableMoves(game) == 1);

    // The same thing one layer up: a matching pair where one of the two is
    // buried rather than pinned, so being covered alone is enough to kill a
    // position.
    clearBoard(game);
    place(game, 0, 2, 2, makeTile(kDragons, 0));
    place(game, 0, 4, 2, makeTile(kDragons, 0));
    place(game, 1, 2, 2, makeTile(kBamboo, 5));
    assert(collectFree(game, freeList) == 2);
    assert(availableMoves(game) == 0);
    assert(deadEnd(game));
    game.tile[slotAt(1, 2, 2)] = kNoTile;
    assert(!deadEnd(game));
    assert(availableMoves(game) == 1);

    // A full deal always has a move, and that is provable rather than lucky:
    // the layout opens 44 free tiles while the set has only 36 MATCHING classes
    // (27 suit ranks, 4 winds, 3 dragons, flowers, seasons), so two of those 44
    // must share one.
    for (uint32_t seed = 1; seed <= 20; ++seed) {
      deal(game, seed);
      assert(remaining(game) == kTiles);
      assert(!won(game));
      assert(!deadEnd(game));
      assert(collectFree(game, freeList) == 44);
      assert(availableMoves(game) >= 1);
    }

    // Play real deals greedily to a standstill. Whichever way they end, exactly
    // one of the two endings holds, the tile count only ever drops by two, and
    // every deal gets at least one move played.
    int solved = 0;
    for (uint32_t seed = 1; seed <= 40; ++seed) {
      deal(game, seed);
      for (;;) {
        const int count = collectFree(game, freeList);
        int a = kNoSlot;
        int b = kNoSlot;
        for (int i = 0; i < count && a == kNoSlot; ++i) {
          for (int j = i + 1; j < count; ++j) {
            if (tilesMatch(game.tile[freeList[i]], game.tile[freeList[j]])) {
              a = freeList[i];
              b = freeList[j];
              break;
            }
          }
        }
        if (a == kNoSlot) break;
        const int countBefore = remaining(game);
        assert(removePair(game, a, b));
        assert(remaining(game) == countBefore - 2);
      }
      assert(remaining(game) <= kTiles - 2);
      assert(remaining(game) % 2 == 0);
      assert(availableMoves(game) == 0);
      assert(won(game) != deadEnd(game));
      if (won(game)) ++solved;
    }
    // Greedy first-match play is not a solver, so how many it clears is
    // reported and not asserted; the invariants above are the test.
    std::printf("win and dead end OK (greedy play cleared %d of 40 deals)\n", solved);

  } else {
    std::fprintf(stderr, "unknown scenario %s\n", scenario.c_str());
    return 1;
  }
  return 0;
}
'''


class MahjongCoreTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        harness = pathlib.Path(cls.tmp.name) / "mahjong_core_test.cpp"
        harness.write_text(HARNESS)
        cls.exe = pathlib.Path(cls.tmp.name) / "mahjong_core_test"
        subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                        "-I", str(GAME_DIR), str(harness),
                        "-o", str(cls.exe)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_tile_set_is_the_standard_144_with_evenly_pairable_groups(self):
        subprocess.run([str(self.exe), "tileset"], check=True)

    def test_suits_pair_only_on_rank_while_flowers_and_seasons_pair_within_group(self):
        subprocess.run([str(self.exe), "matching"], check=True)

    def test_a_tile_is_free_only_when_uncovered_and_open_on_one_long_edge(self):
        subprocess.run([str(self.exe), "freetile"], check=True)

    def test_the_layout_table_fills_its_grid_without_overlaps_or_floating_tiles(self):
        subprocess.run([str(self.exe), "layout"], check=True)

    def test_the_deal_is_a_pure_function_of_an_explicit_integer_seed(self):
        subprocess.run([str(self.exe), "deal"], check=True)

    def test_only_matching_free_tiles_pair_and_an_illegal_removal_changes_nothing(self):
        subprocess.run([str(self.exe), "removal"], check=True)

    def test_an_empty_layout_wins_while_tiles_with_no_reachable_pair_are_a_dead_end(self):
        subprocess.run([str(self.exe), "ending"], check=True)


if __name__ == "__main__":
    unittest.main()
