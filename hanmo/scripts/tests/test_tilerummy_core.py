"""Compile the actual tile-rummy rules with host g++ and push real tile sets through them.

Freestanding core, same shape as reversi/ReversiCore.h: no renderer, no Activity,
no storage, so the rules can be driven directly from a host harness.

Sets are written as text -- "R7 B7 K7", "R1 R2 R3", "J" for a joker -- because a
list of numeric tile ids is unreadable, and a test that cannot be read cannot be
audited for whether it checks the rule it claims to.
"""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
GAME_DIR = ROOT / "src/apps_local/tilerummy"

HARNESS = r'''
#include "TileRummyCore.h"

#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

using namespace tilerummy;

// Count every tile kind in a span, so a test can state the exact multiset it
// expects instead of trusting an order.
static void census(const Tile* tiles, const int count, int* seen) {
  for (int kind = 0; kind < kTileKinds; ++kind) seen[kind] = 0;
  for (int i = 0; i < count; ++i) {
    assert(tiles[i] < kTileKinds);
    ++seen[tiles[i]];
  }
}

// Colour letters for the text notation: Red, Blue, Yellow, blacK.
static const char kColourLetters[] = "RBYK";

// "R7" -> red seven, "J" -> joker. Asserts rather than reports, because a
// malformed literal in a test is a mistake in the test, not a case under test.
static Tile parseTile(const std::string& word) {
  assert(!word.empty());
  if (word == "J") return kJoker;
  const char* found = std::strchr(kColourLetters, word[0]);
  assert(found != nullptr && *found != '\0');
  const int colour = static_cast<int>(found - kColourLetters);
  const int number = std::atoi(word.c_str() + 1);
  assert(number >= 1 && number <= kNumbers);
  return makeTile(colour, number);
}

// "R7 B7 K7" -> a list of tiles, in the order written. Order matters for runs,
// so the notation preserves it.
static int parseTiles(const std::string& text, Tile* out, const int capacity) {
  int count = 0;
  size_t at = 0;
  while (at < text.size()) {
    while (at < text.size() && text[at] == ' ') ++at;
    const size_t start = at;
    while (at < text.size() && text[at] != ' ') ++at;
    if (at > start) {
      assert(count < capacity);
      out[count++] = parseTile(text.substr(start, at - start));
    }
  }
  return count;
}

static Set parseSet(const std::string& text) {
  Set set;
  for (int i = 0; i < kMaxSetTiles; ++i) set.tiles[i] = kNoTile;
  set.count = static_cast<uint8_t>(parseTiles(text, set.tiles, kMaxSetTiles));
  return set;
}

// "R7 B7 K7 | R1 R2 R3" -> the whole table, sets separated by a bar. This is the
// shape the core is handed: the complete proposed arrangement, all at once.
//
// Unused slots are filled in rather than left as whatever was on the stack, so
// two tables built from the same text compare equal byte for byte -- which is
// how these tests check that a refused move changed nothing at all.
static Table parseTable(const std::string& text) {
  Table table;
  for (int i = 0; i < kMaxSets; ++i) {
    for (int j = 0; j < kMaxSetTiles; ++j) table.sets[i].tiles[j] = kNoTile;
    table.sets[i].count = 0;
  }
  table.setCount = 0;
  size_t at = 0;
  while (true) {
    const size_t bar = text.find('|', at);
    const std::string part = bar == std::string::npos ? text.substr(at) : text.substr(at, bar - at);
    const Set set = parseSet(part);
    if (set.count > 0) {
      assert(table.setCount < kMaxSets);
      table.sets[table.setCount++] = set;
    }
    if (bar == std::string::npos) break;
    at = bar + 1;
  }
  return table;
}

// Stack a hand or a table deliberately. The deal is random and the rules under
// test are about particular tiles, so the fixture names them.
static void setHand(Game& game, const int player, const std::string& text) {
  Hand& hand = game.hands[player];
  for (int i = 0; i < kMaxHand; ++i) hand.tiles[i] = kNoTile;
  hand.count = static_cast<uint8_t>(parseTiles(text, hand.tiles, kMaxHand));
}

static void setTable(Game& game, const std::string& text) { game.table = parseTable(text); }

static SetProblem problemOf(const std::string& text) { return checkSet(parseSet(text)).problem; }
static int scoreOf(const std::string& text) { return setScore(parseSet(text)); }
static int impliedOf(const std::string& text, const int index) { return impliedValue(parseSet(text), index); }

int main(int argc, char** argv) {
  assert(argc == 2);
  const std::string scenario = argv[1];

  if (scenario == "tiles") {
    // Every numbered tile survives the one-byte encoding, and the 52 ids are
    // distinct and dense -- that density is what lets a census be a flat array
    // and therefore what keeps the conservation check linear.
    bool seen[kTileKinds];
    for (int kind = 0; kind < kTileKinds; ++kind) seen[kind] = false;
    for (int colour = 0; colour < kColours; ++colour) {
      for (int number = 1; number <= kNumbers; ++number) {
        const Tile tile = makeTile(colour, number);
        assert(tile < kDistinctNumbered);
        assert(tileColour(tile) == colour);
        assert(tileNumber(tile) == number);
        assert(!seen[tile]);
        seen[tile] = true;
      }
    }
    assert(kDistinctNumbered == 52);
    assert(makeTile(kRed, 1) == 0);
    assert(makeTile(kBlack, 13) == kDistinctNumbered - 1);
    // The colour constants are the order the ids are built in, so a renderer
    // walking colours and a census walking ids agree.
    assert(kRed == 0 && kBlue == 1 && kYellow == 2 && kBlack == 3);

    // The joker sits outside that range and has NO colour and NO number of its
    // own: it has only the ones of whatever it stands in for.
    assert(isJoker(kJoker));
    assert(kJoker == kDistinctNumbered);
    assert(tileColour(kJoker) == -1);
    assert(tileNumber(kJoker) == 0);
    assert(!isJoker(makeTile(kBlack, 13)));

    // kNoTile must not be mistaken for a tile, which is exactly why it is not
    // zero: zero is the red one.
    assert(kNoTile != makeTile(kRed, 1));
    assert(!isJoker(kNoTile));
    assert(tileColour(kNoTile) == -1);
    assert(tileNumber(kNoTile) == 0);
    puts("the one-byte tile encoding round-trips OK");

  } else if (scenario == "pool") {
    const Settings settings = defaultSettings();
    Tile pool[kMaxTiles];
    const int count = composePool(pool, settings);
    // 1..13 in four colours, twice over, plus the two default jokers.
    assert(count == kMaxTiles);
    assert(count == 106);

    int seen[kTileKinds];
    census(pool, count, seen);
    for (int colour = 0; colour < kColours; ++colour) {
      for (int number = 1; number <= kNumbers; ++number) {
        assert(seen[makeTile(colour, number)] == kCopies);
      }
    }
    assert(seen[kJoker] == kMaxJokers);

    // Shuffling is a permutation and nothing else: a shuffle that re-rolled
    // tiles instead of swapping them would still look plausible on screen.
    shufflePool(pool, count, 20261006u);
    int shuffled[kTileKinds];
    census(pool, count, shuffled);
    assert(std::memcmp(seen, shuffled, sizeof(seen)) == 0);
    // ...and it actually moves something, or the assertion above is vacuous.
    Tile ordered[kMaxTiles];
    composePool(ordered, settings);
    assert(std::memcmp(ordered, pool, static_cast<size_t>(count)) != 0);

    // Same seed, same deal. This is the whole reason the seed is a parameter:
    // a failure found on the device has to be replayable on the host.
    Tile first[kMaxTiles];
    Tile again[kMaxTiles];
    Tile other[kMaxTiles];
    composePool(first, settings);
    shufflePool(first, count, 7u);
    composePool(again, settings);
    shufflePool(again, count, 7u);
    assert(std::memcmp(first, again, static_cast<size_t>(count)) == 0);
    composePool(other, settings);
    shufflePool(other, count, 8u);
    assert(std::memcmp(first, other, static_cast<size_t>(count)) != 0);

    // Jokers off removes exactly the jokers and leaves every numbered tile.
    Settings strict = settings;
    strict.jokers = 0;
    const int strictCount = composePool(pool, strict);
    assert(strictCount == kNumberedTiles);
    assert(strictCount == 104);
    census(pool, strictCount, shuffled);
    assert(shuffled[kJoker] == 0);
    for (int colour = 0; colour < kColours; ++colour) {
      for (int number = 1; number <= kNumbers; ++number) {
        assert(shuffled[makeTile(colour, number)] == kCopies);
      }
    }
    puts("pool composition and deterministic shuffle OK");

  } else if (scenario == "group") {
    // Three or four tiles of one number in DIFFERENT colours, and the score is
    // the sum of the tile values.
    assert(problemOf("R7 B7 K7") == SetProblem::Ok);
    assert(checkSet(parseSet("R7 B7 K7")).kind == SetKind::Group);
    assert(scoreOf("R7 B7 K7") == 21);
    assert(problemOf("R7 B7 Y7 K7") == SetProblem::Ok);
    assert(scoreOf("R7 B7 Y7 K7") == 28);
    assert(scoreOf("R13 B13 K13") == 39);
    assert(scoreOf("R1 B1 Y1 K1") == 4);
    // Colour order is irrelevant to a group -- a group has no ordering.
    assert(problemOf("K7 R7 B7") == SetProblem::Ok);
    assert(scoreOf("K7 R7 B7") == 21);

    // THE classic bug. Two copies of every tile exist, so a naive "same number"
    // test accepts a second red seven and calls three tiles a group.
    assert(problemOf("R7 R7 B7") == SetProblem::DuplicateColour);
    assert(scoreOf("R7 R7 B7") == 0);
    assert(problemOf("R7 B7 B7 K7") == SetProblem::DuplicateColour);
    // ...including the all-one-colour case, which is what a duplicate-blind
    // implementation would happily score as 28.
    assert(problemOf("R7 R7 R7 R7") == SetProblem::DuplicateColour);

    // Four colours exist, so five tiles of one number cannot be a group at all;
    // say so by length rather than by whichever duplicate is noticed first.
    assert(problemOf("R7 B7 Y7 K7 R7") == SetProblem::GroupTooLong);

    // Two tiles are not a set, however well they match.
    assert(problemOf("R7 B7") == SetProblem::TooFewTiles);
    assert(problemOf("R7") == SetProblem::TooFewTiles);

    // Same colours, unrelated numbers: neither one number nor one colour.
    assert(problemOf("R7 B9 K2") == SetProblem::NotASet);
    puts("groups need different colours OK");

  } else if (scenario == "run") {
    // Three or more consecutive numbers in ONE colour, scored as the sum of the
    // tile values.
    assert(problemOf("R1 R2 R3") == SetProblem::Ok);
    assert(checkSet(parseSet("R1 R2 R3")).kind == SetKind::Run);
    assert(scoreOf("R1 R2 R3") == 6);
    assert(scoreOf("R11 R12 R13") == 36);
    assert(scoreOf("B4 B5 B6 B7 B8") == 30);
    // The longest run there is: every number in one colour, 1+2+...+13.
    assert(scoreOf("K1 K2 K3 K4 K5 K6 K7 K8 K9 K10 K11 K12 K13") == 91);
    assert(checkSet(parseSet("K1 K2 K3 K4 K5 K6 K7 K8 K9 K10 K11 K12 K13")).kind == SetKind::Run);

    // RUNS DO NOT WRAP. 13 is the end of the line, not the neighbour of 1.
    assert(problemOf("R12 R13 R1") == SetProblem::RunBroken);
    assert(problemOf("K13 K1 K2") == SetProblem::RunBroken);

    // A gap is not consecutive, and the second copy of a tile cannot stand in
    // the next seat either.
    assert(problemOf("R1 R2 R4") == SetProblem::RunBroken);
    assert(problemOf("R5 R5 R6") == SetProblem::RunBroken);

    // Descending is not a run. The set is judged exactly as the player laid it
    // out, which is also what makes a joker's value unambiguous (see "joker").
    assert(problemOf("R3 R2 R1") == SetProblem::RunBroken);

    // Consecutive numbers across colours are not a run.
    assert(problemOf("R1 B2 R3") == SetProblem::NotASet);
    assert(problemOf("R1 R2 B3") == SetProblem::NotASet);
    puts("runs are consecutive, one colour, and never wrap OK");

  } else if (scenario == "joker") {
    // A joker substitutes for any tile and scores the value of the tile it
    // stands in for. The same joker is worth 13 in one group and 1 in another,
    // so an implementation that gave jokers a fixed value fails one of these.
    assert(problemOf("R7 B7 J") == SetProblem::Ok);
    assert(checkSet(parseSet("R7 B7 J")).kind == SetKind::Group);
    assert(scoreOf("R7 B7 J") == 21);
    assert(scoreOf("R13 B13 J") == 39);
    assert(scoreOf("R1 B1 J") == 3);
    assert(scoreOf("R7 B7 Y7 J") == 28);
    assert(impliedOf("R7 B7 J", 2) == 7);
    assert(impliedOf("R1 B1 J", 2) == 1);

    // In a run the joker's value comes from the SEAT it occupies, which is why
    // the same two tiles plus a joker score differently depending on where the
    // player put it.
    assert(scoreOf("R7 R8 J") == 24);
    assert(impliedOf("R7 R8 J", 2) == 9);
    assert(scoreOf("J R7 R8") == 21);
    assert(impliedOf("J R7 R8", 0) == 6);
    assert(scoreOf("R7 J R9") == 24);
    assert(impliedOf("R7 J R9", 1) == 8);
    assert(scoreOf("J R2 R3") == 6);
    assert(impliedOf("J R2 R3", 0) == 1);
    // A real tile reports its own value through the same accessor, so the UI
    // has one code path for labelling a seat.
    assert(impliedOf("R7 R8 J", 0) == 7);
    assert(impliedOf("R7 R8 J", 1) == 8);

    // The implied tile must EXIST. There is no 0 and no 14, so a joker cannot
    // extend a run past either end -- the no-wrap rule again, now for jokers.
    assert(problemOf("J R1 R2") == SetProblem::RunOutOfRange);
    assert(problemOf("R12 R13 J") == SetProblem::RunOutOfRange);
    assert(scoreOf("R12 R13 J") == 0);

    // A joker in a group needs a colour no other tile of that group is using.
    // Two reds leave it nowhere to stand even though "same number" holds...
    assert(problemOf("R7 R7 J") == SetProblem::DuplicateColour);
    // ...and with all four colours already present there is no fifth colour for
    // the joker to be.
    assert(problemOf("R7 B7 Y7 K7 J") == SetProblem::GroupTooLong);

    // All jokers resolves to nothing at all: there is no tile to take a number
    // or a colour from, so the set is not a set.
    assert(problemOf("J J J") == SetProblem::AllJokers);
    assert(scoreOf("J J J") == 0);
    assert(impliedOf("J J J", 0) == 0);

    // One known tile and two jokers is read as a GROUP, the reading that
    // assumes least: the jokers' numbers are forced by the known tile, whereas
    // a run would additionally assume the player meant them as neighbours.
    assert(checkSet(parseSet("R5 J J")).kind == SetKind::Group);
    assert(scoreOf("R5 J J") == 15);
    assert(scoreOf("R13 J J") == 39);

    // Jokers do not rescue an arrangement that is neither a group nor a run.
    assert(problemOf("R7 B9 J") == SetProblem::NotASet);
    assert(problemOf("R7 J") == SetProblem::TooFewTiles);
    puts("jokers score as the tile they stand in for OK");

  } else if (scenario == "table") {
    // The core is handed the COMPLETE proposed arrangement and judges it. It
    // never searches for a way to re-partition the table -- that search is
    // combinatorial and this device has neither the RAM nor the frame rate for
    // it -- so every one of these checks is one linear pass.
    Table table = parseTable("R7 B7 K7 | R1 R2 R3 | B5 Y5 K5 J");
    TableCheck check = checkTable(table);
    assert(check.ok);
    assert(check.failedSet == kNoSet);
    assert(check.problem == SetProblem::Ok);
    assert(tableTileCount(table) == 10);
    assert(tableScore(table) == 21 + 6 + 20);

    // One broken set in the middle: the index AND the reason come back, because
    // "the table is invalid" cannot be rendered as a pointer at anything.
    table = parseTable("R7 B7 K7 | R1 R2 R4 | B5 Y5 K5");
    check = checkTable(table);
    assert(!check.ok);
    assert(check.failedSet == 1);
    assert(check.problem == SetProblem::RunBroken);

    // The FIRST failure is reported. With two broken sets the player gets one
    // thing to fix, and fixing it reveals the next.
    table = parseTable("R7 R7 B7 | R1 R2 R4");
    check = checkTable(table);
    assert(!check.ok);
    assert(check.failedSet == 0);
    assert(check.problem == SetProblem::DuplicateColour);

    // An empty table is valid. The game starts there, so an emptiness special
    // case anywhere else would be a bug waiting for the first turn.
    Table empty;
    empty.setCount = 0;
    assert(checkTable(empty).ok);
    assert(tableTileCount(empty) == 0);
    assert(tableScore(empty) == 0);

    // Table manipulation falls out of judging a final state. Splitting a run to
    // reuse one of its tiles is simply a DIFFERENT arrangement: the four red
    // tiles below are the same four before and after, and both tables are valid.
    assert(checkTable(parseTable("R4 R5 R6 R7")).ok);
    assert(checkTable(parseTable("R5 R6 R7 | R4 B4 Y4")).ok);
    assert(tableTileCount(parseTable("R5 R6 R7 | R4 B4 Y4")) == 6);
    assert(tableScore(parseTable("R5 R6 R7 | R4 B4 Y4")) == 18 + 12);
    // ...and an arrangement that strands tiles is rejected by the same pass,
    // with no notion of "but they could be put back somewhere".
    check = checkTable(parseTable("R4 B4 Y4 | R5 R6"));
    assert(!check.ok);
    assert(check.failedSet == 1);
    assert(check.problem == SetProblem::TooFewTiles);

    // The fixed set array is sized for the most sets the tiles could ever form:
    // 35 sets of three, with one tile over that cannot make a set on its own.
    assert(kMaxSets == 35);
    assert(kMaxSets * kMinSetTiles <= kMaxTiles);
    assert((kMaxSets + 1) * kMinSetTiles > kMaxTiles);
    puts("the table reports which set fails and why OK");

  } else if (scenario == "settings") {
    // The defaults are the standard game: two players, fourteen tiles each, a
    // thirty-point opening and both jokers.
    const Settings fallback = defaultSettings();
    assert(fallback.players == 2);
    assert(fallback.startingHand == 14);
    assert(fallback.meldMinimum == 30);
    assert(fallback.jokers == 2);
    assert(settingsValid(fallback));
    assert(tileCount(fallback) == 106);

    // Two to four players.
    Settings settings = fallback;
    for (int n = kMinPlayers; n <= kMaxPlayers; ++n) {
      settings.players = static_cast<uint8_t>(n);
      assert(settingsValid(settings));
    }
    settings.players = kMinPlayers - 1;
    assert(!settingsValid(settings));
    settings.players = kMaxPlayers + 1;
    assert(!settingsValid(settings));

    // Starting hand: a quick game at one end and a long one at the other.
    settings = fallback;
    settings.startingHand = kMinStartingHand;
    assert(settingsValid(settings));
    settings.startingHand = kMaxStartingHand;
    assert(settingsValid(settings));
    settings.startingHand = kMinStartingHand - 1;
    assert(!settingsValid(settings));
    settings.startingHand = kMaxStartingHand + 1;
    assert(!settingsValid(settings));

    // Initial meld minimum: easier and harder than the standard thirty.
    settings = fallback;
    settings.meldMinimum = kMinMeld;
    assert(settingsValid(settings));
    settings.meldMinimum = kMaxMeld;
    assert(settingsValid(settings));
    settings.meldMinimum = kMinMeld - 1;
    assert(!settingsValid(settings));
    settings.meldMinimum = kMaxMeld + 1;
    assert(!settingsValid(settings));

    // Jokers: none, one or two. NONE is a legitimate setting that makes the
    // game strictly harder, not an error, and it changes the tile count.
    settings = fallback;
    settings.jokers = 0;
    assert(settingsValid(settings));
    assert(tileCount(settings) == 104);
    settings.jokers = 1;
    assert(settingsValid(settings));
    assert(tileCount(settings) == 105);
    settings.jokers = kMaxJokers + 1;
    assert(!settingsValid(settings));

    // The hardest legal combination must still leave tiles in the pool to draw
    // from: four players on the longest hand cannot eat the whole box.
    settings = fallback;
    settings.players = kMaxPlayers;
    settings.startingHand = kMaxStartingHand;
    settings.jokers = 0;
    assert(settingsValid(settings));
    assert(kMaxPlayers * kMaxStartingHand < kNumberedTiles);
    // ...and a hand size that would, if the bound above were lifted, is refused
    // by the pool check rather than silently dealing from an empty pool.
    assert(!dealFits(kMaxPlayers, 30, 0));

    // Every value the settings screen offers must be one the core accepts, and
    // the lists must be ordered, so a chooser that walks them gets increasing
    // difficulty for free instead of trusting whoever edits the table next.
    assert(kStartingHandOptionCount >= 3);
    for (int i = 0; i < kStartingHandOptionCount; ++i) {
      settings = fallback;
      settings.startingHand = kStartingHandOptions[i];
      assert(settingsValid(settings));
      if (i > 0) assert(kStartingHandOptions[i] > kStartingHandOptions[i - 1]);
    }
    assert(kMeldMinimumOptionCount >= 3);
    for (int i = 0; i < kMeldMinimumOptionCount; ++i) {
      settings = fallback;
      settings.meldMinimum = kMeldMinimumOptions[i];
      assert(settingsValid(settings));
      if (i > 0) assert(kMeldMinimumOptions[i] > kMeldMinimumOptions[i - 1]);
    }
    // The default has to be selectable, or the settings screen cannot show the
    // state the game actually starts in.
    bool sawHand = false;
    for (int i = 0; i < kStartingHandOptionCount; ++i) {
      if (kStartingHandOptions[i] == fallback.startingHand) sawHand = true;
    }
    assert(sawHand);
    bool sawMeld = false;
    for (int i = 0; i < kMeldMinimumOptionCount; ++i) {
      if (kMeldMinimumOptions[i] == fallback.meldMinimum) sawMeld = true;
    }
    assert(sawMeld);
    puts("settings are bounded and every offered option is accepted OK");

  } else if (scenario == "deal") {
    const Settings settings = defaultSettings();
    Game game;
    assert(start(game, settings, 20261006u));
    // Two hands of fourteen come off a pool of 106, leaving 78 face down.
    assert(game.poolCount == 78);
    assert(game.poolCount == tileCount(settings) - settings.players * settings.startingHand);
    for (int p = 0; p < settings.players; ++p) assert(game.hands[p].count == settings.startingHand);
    assert(game.table.setCount == 0);
    assert(game.turn == 0);
    assert(!game.melded[0] && !game.melded[1]);
    assert(game.winner == kNoPlayer);
    assert(!over(game));

    // NOTHING is created or lost by dealing: the hands plus the pool are exactly
    // the composed pool, every number twice in every colour plus the jokers.
    int seen[kTileKinds];
    for (int kind = 0; kind < kTileKinds; ++kind) seen[kind] = 0;
    for (int i = 0; i < game.poolCount; ++i) ++seen[game.pool[i]];
    for (int p = 0; p < settings.players; ++p) {
      for (int i = 0; i < game.hands[p].count; ++i) ++seen[game.hands[p].tiles[i]];
    }
    for (int colour = 0; colour < kColours; ++colour) {
      for (int number = 1; number <= kNumbers; ++number) assert(seen[makeTile(colour, number)] == kCopies);
    }
    assert(seen[kJoker] == settings.jokers);

    // THE EXACT DEAL for one seed, so a failure reported from the device can be
    // replayed here. These values were derived from the documented generator and
    // deal order by hand, not read back out of this implementation, so they
    // catch a change to either.
    assert(game.hands[0].tiles[0] == makeTile(kBlack, 13));  // K13
    assert(game.hands[0].tiles[1] == makeTile(kRed, 12));  // R12
    assert(game.hands[0].tiles[2] == makeTile(kBlack, 3));   // K3
    assert(game.hands[1].tiles[0] == makeTile(kRed, 7));   // R7
    assert(game.hands[1].tiles[1] == makeTile(kBlack, 5));   // K5
    // Round-robin, one tile at a time: the two hands alternate down the pool, so
    // the second player's first tile is the pool tile below the first player's.
    assert(game.hands[0].tiles[13] == makeTile(kRed, 8));   // R8
    assert(game.hands[1].tiles[13] == makeTile(kYellow, 13));  // Y13
    assert(game.pool[game.poolCount - 1] == makeTile(kYellow, 6));  // Y6, next to be drawn

    // Same seed, same deal, tile for tile.
    Game replay;
    assert(start(replay, settings, 20261006u));
    assert(std::memcmp(&game.hands[0], &replay.hands[0], sizeof(Hand)) == 0);
    assert(std::memcmp(&game.hands[1], &replay.hands[1], sizeof(Hand)) == 0);
    // A different seed deals a different game.
    Game elsewhere;
    assert(start(elsewhere, settings, 20261007u));
    assert(std::memcmp(&game.hands[0], &elsewhere.hands[0], sizeof(Hand)) != 0);

    // The whole state scales with the settings: four players, a quick seven-tile
    // hand and no jokers at all.
    Settings quick = defaultSettings();
    quick.players = 4;
    quick.startingHand = 7;
    quick.jokers = 0;
    assert(settingsValid(quick));
    assert(start(game, quick, 99u));
    for (int p = 0; p < quick.players; ++p) assert(game.hands[p].count == 7);
    assert(game.poolCount == 104 - 28);
    for (int i = 0; i < game.poolCount; ++i) assert(!isJoker(game.pool[i]));

    // Invalid settings refuse to start and leave the game exactly as it was,
    // because the caller routes a stored settings blob straight in here.
    Game kept;
    assert(start(kept, settings, 5u));
    const Game before = kept;
    Settings broken = settings;
    broken.players = kMaxPlayers + 1;
    assert(!start(kept, broken, 5u));
    assert(std::memcmp(&before, &kept, sizeof(Game)) == 0);

    // Drawing takes the top tile of the pool into the hand and ends the turn.
    assert(start(game, settings, 42u));
    const int pool = game.poolCount;
    const Tile top = game.pool[pool - 1];
    assert(top == makeTile(kRed, 8));  // R8, from the same hand-derived deal
    assert(drawTile(game));
    assert(game.hands[0].count == 15);
    assert(game.hands[0].tiles[14] == top);
    assert(game.poolCount == pool - 1);
    assert(game.turn == 1);
    // ...and the turn wraps round the table rather than running off the end.
    assert(drawTile(game));
    assert(game.hands[1].count == 15);
    assert(game.turn == 0);

    // An exhausted pool cannot be drawn from, and the refusal changes nothing.
    game.poolCount = 0;
    const Game dry = game;
    assert(!drawTile(game));
    assert(std::memcmp(&dry, &game, sizeof(Game)) == 0);
    puts("the deal is exact, reproducible and conserves every tile OK");

  } else if (scenario == "meld") {
    const Settings settings = defaultSettings();  // minimum 30
    Game game;
    assert(start(game, settings, 1u));
    setHand(game, 0, "R10 B10 K10 R1 R2 R3 R7 B7 K7");
    assert(!game.melded[0]);
    assert(game.table.setCount == 0);

    // Three tens is exactly thirty, and the threshold is "at least", so the
    // standard opening is legal rather than one point short.
    MoveResult result = checkPlay(game, parseTable("R10 B10 K10"));
    assert(result.problem == MoveProblem::Ok);
    assert(result.meldScore == 30);
    assert(result.added == 3);

    // Six points is not an opening, and the result says how far short it fell so
    // the UI can show "21 of 30" rather than just refusing.
    result = checkPlay(game, parseTable("R1 R2 R3"));
    assert(result.problem == MoveProblem::MeldTooSmall);
    assert(result.meldScore == 6);
    result = checkPlay(game, parseTable("R7 B7 K7"));
    assert(result.problem == MoveProblem::MeldTooSmall);
    assert(result.meldScore == 21);

    // Every set laid down in the SAME turn counts towards the total: six and
    // thirty clear the bar together where six alone does not.
    result = checkPlay(game, parseTable("R1 R2 R3 | R10 B10 K10"));
    assert(result.problem == MoveProblem::Ok);
    assert(result.meldScore == 36);
    assert(result.added == 6);

    // The threshold follows the setting and nothing else does: the same
    // arrangement passes at twenty and fails at forty.
    Settings easier = settings;
    easier.meldMinimum = 20;
    Game easy;
    assert(start(easy, easier, 1u));
    setHand(easy, 0, "R10 B10 K10 R1 R2 R3 R7 B7 K7");
    result = checkPlay(easy, parseTable("R7 B7 K7"));
    assert(result.problem == MoveProblem::Ok);
    assert(result.meldScore == 21);

    Settings harder = settings;
    harder.meldMinimum = 40;
    Game hard;
    assert(start(hard, harder, 1u));
    setHand(hard, 0, "R10 B10 K10 R1 R2 R3 R7 B7 K7");
    result = checkPlay(hard, parseTable("R1 R2 R3 | R10 B10 K10"));
    assert(result.problem == MoveProblem::MeldTooSmall);
    assert(result.meldScore == 36);

    // A joker counts towards the opening at the value it stands in for, so it is
    // worth 13 in this group and the opening clears with two real tiles.
    setHand(game, 0, "R13 B13 J R11 R12");
    result = checkPlay(game, parseTable("R13 B13 J"));
    assert(result.problem == MoveProblem::Ok);
    assert(result.meldScore == 39);
    // ...and 13 again at the top of this run, for 36.
    result = checkPlay(game, parseTable("R11 R12 J"));
    assert(result.problem == MoveProblem::Ok);
    assert(result.meldScore == 36);

    // TILES ALREADY ON THE TABLE DO NOT COUNT. Before their opening meld a
    // player may not use the table at all, which is both the real rule and what
    // makes "only the sets they lay down this turn" exact.
    setTable(game, "B4 Y4 K4");
    setHand(game, 0, "R4 R10 B10 K10");
    result = checkPlay(game, parseTable("B4 Y4 K4 R4"));
    assert(result.problem == MoveProblem::TableUsedBeforeMeld);
    // The same four tiles laid as the player's OWN set is a legal opening, and
    // the twelve points already on the table are not added to it.
    Table opening = parseTable("B4 Y4 K4 | R10 B10 K10");
    result = checkPlay(game, opening);
    assert(result.problem == MoveProblem::Ok);
    assert(result.meldScore == 30);
    assert(result.added == 3);
    assert(tableScore(game.table) == 12);

    // Committing it spends the opening rule, moves the tiles out of the hand and
    // passes the turn.
    assert(play(game, opening));
    assert(game.melded[0]);
    assert(game.hands[0].count == 1);
    assert(game.hands[0].tiles[0] == makeTile(kRed, 4));  // the R4 is what is left
    assert(game.table.setCount == 2);
    assert(game.turn == 1);

    // Now the table is usable: that last tile joins the group of fours, which
    // was refused as an opening a moment ago.
    game.turn = 0;
    result = checkPlay(game, parseTable("B4 Y4 K4 R4 | R10 B10 K10"));
    assert(result.problem == MoveProblem::Ok);
    assert(result.added == 1);
    // The opening total is not computed any more -- the rule is spent, not
    // re-applied at one tile per turn.
    assert(result.meldScore == 0);
    puts("the first meld must reach the minimum from its own tiles OK");

  } else if (scenario == "commit") {
    const Settings settings = defaultSettings();
    Game game;
    assert(start(game, settings, 7u));
    setTable(game, "R4 R5 R6 R7");
    setHand(game, 0, "B4 Y4 Y9");
    game.melded[0] = true;

    // The manoeuvre the core gets for FREE by judging a final state: the run is
    // split and its loose tile becomes part of a new group. No search, no
    // re-partitioning, just a different proposed table.
    Table proposed = parseTable("R5 R6 R7 | R4 B4 Y4");
    MoveResult result = checkPlay(game, proposed);
    assert(result.problem == MoveProblem::Ok);
    assert(result.added == 2);
    assert(play(game, proposed));
    assert(game.table.setCount == 2);
    assert(game.hands[0].count == 1);
    // The tiles that stayed keep their order in the hand, so the player's layout
    // does not scramble every time they play.
    assert(game.hands[0].tiles[0] == makeTile(kYellow, 9));
    assert(game.turn == 1);

    // Conservation, both directions. The table may gain tiles from the hand and
    // nothing else: no tile may appear from nowhere...
    setHand(game, 1, "K1 K2 K3");
    game.melded[1] = true;
    game.turn = 1;
    result = checkPlay(game, parseTable("R5 R6 R7 | R4 B4 Y4 | K2 K3 K4"));
    assert(result.problem == MoveProblem::TileNotInHand);
    // ...and no tile already on the table may quietly vanish.
    result = checkPlay(game, parseTable("R5 R6 R7"));
    assert(result.problem == MoveProblem::TileRemovedFromTable);

    // Handing back the table unchanged is not a turn. The player who plays
    // nothing has to draw instead, and this is the check that makes "draw or
    // play" a real choice.
    result = checkPlay(game, game.table);
    assert(result.problem == MoveProblem::NothingPlayed);
    assert(result.added == 0);

    // An invalid set is still reported by index and reason through the move
    // result, so the UI has one place to look.
    result = checkPlay(game, parseTable("R5 R6 R7 | R4 B4 Y4 | K1 K2 K2"));
    assert(result.problem == MoveProblem::InvalidSet);
    assert(result.failedSet == 2);
    assert(result.setProblem == SetProblem::RunBroken);

    // A set count beyond the fixed array is refused rather than read past the
    // end: the proposal can arrive from storage, so the bound is checked.
    Table overflowing = parseTable("R5 R6 R7 | R4 B4 Y4");
    overflowing.setCount = kMaxSets + 1;
    assert(checkPlay(game, overflowing).problem == MoveProblem::TooManySets);

    // Every refusal leaves the game untouched byte for byte, because a caller
    // routes a tap straight into play().
    const Game untouched = game;
    assert(!play(game, parseTable("R5 R6 R7")));
    assert(!play(game, game.table));
    assert(!play(game, overflowing));
    assert(std::memcmp(&untouched, &game, sizeof(Game)) == 0);

    // WINNING: the player who places their last tile wins, and the turn stops
    // with them rather than moving on to someone with nothing to answer.
    proposed = parseTable("R5 R6 R7 | R4 B4 Y4 | K1 K2 K3");
    assert(play(game, proposed));
    assert(game.hands[1].count == 0);
    assert(over(game));
    assert(game.winner == 1);
    assert(game.turn == 1);

    // A finished game refuses everything and keeps its result.
    const Game finished = game;
    assert(checkPlay(game, parseTable("R5 R6 R7 | R4 B4 Y4 | K1 K2 K3")).problem == MoveProblem::GameOver);
    assert(!play(game, proposed));
    assert(!drawTile(game));
    assert(std::memcmp(&finished, &game, sizeof(Game)) == 0);
    puts("a play conserves tiles and emptying a hand wins OK");

  } else {
    std::fprintf(stderr, "unknown scenario %s\n", scenario.c_str());
    return 1;
  }
  return 0;
}
'''


class TileRummyCoreTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        harness = pathlib.Path(cls.tmp.name) / "tilerummy_core_test.cpp"
        harness.write_text(HARNESS)
        cls.exe = pathlib.Path(cls.tmp.name) / "tilerummy_core_test"
        subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                        "-I", str(GAME_DIR), str(harness),
                        "-o", str(cls.exe)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_one_byte_tile_encoding_round_trips_for_every_tile(self):
        subprocess.run([str(self.exe), "tiles"], check=True)

    def test_a_fresh_pool_holds_every_tile_twice_plus_the_configured_jokers(self):
        subprocess.run([str(self.exe), "pool"], check=True)

    def test_a_group_is_one_number_in_different_colours_never_a_repeated_colour(self):
        subprocess.run([str(self.exe), "group"], check=True)

    def test_a_run_is_consecutive_numbers_in_one_colour_and_never_wraps_past_13(self):
        subprocess.run([str(self.exe), "run"], check=True)

    def test_a_joker_scores_as_the_tile_it_stands_in_for_not_a_fixed_value(self):
        subprocess.run([str(self.exe), "joker"], check=True)

    def test_validating_a_table_names_the_set_that_fails_and_the_reason(self):
        subprocess.run([str(self.exe), "table"], check=True)

    def test_settings_are_bounded_and_every_offered_option_is_accepted(self):
        subprocess.run([str(self.exe), "settings"], check=True)

    def test_the_deal_is_exact_reproducible_and_conserves_every_tile(self):
        subprocess.run([str(self.exe), "deal"], check=True)

    def test_the_first_meld_must_reach_the_minimum_from_its_own_tiles(self):
        subprocess.run([str(self.exe), "meld"], check=True)

    def test_a_play_conserves_tiles_and_emptying_a_hand_wins(self):
        subprocess.run([str(self.exe), "commit"], check=True)


if __name__ == "__main__":
    unittest.main()
