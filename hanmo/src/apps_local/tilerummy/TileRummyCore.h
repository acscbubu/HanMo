#pragma once

// A rummy-family tile game, the rules. Freestanding: no renderer, no Activity,
// no storage.
//
// One hundred and four numbered tiles -- 1 to 13 in four colours, two copies of
// each -- plus up to two jokers. Players build SETS: a GROUP is three or four
// tiles of one number in different colours, a RUN is three or more consecutive
// numbers in one colour. A player's first contribution to the table must be
// worth at least a configured minimum. Whoever plays their last tile wins.
//
// VALIDATION, NOT SOLVING. This is the load-bearing design decision, and the
// obvious alternative was rejected on purpose. A solver that searches for some
// way to re-partition the table into valid sets is a combinatorial search over
// up to 106 tiles; this device has roughly 170 KB of free RAM and a panel that
// manages 2-3 frames per second, so there is nowhere to put the search and no
// time to run it. Instead the PLAYER arranges tiles into sets by tapping and the
// core judges the arrangement they hand in: given the complete list of sets now
// on the table, is every one of them valid, and if not, WHICH one and WHY -- so
// the UI can point at the offending set. Table manipulation then falls out for
// free, because rearranging is just proposing a different final state, and every
// check in this file is linear in the number of tiles.
//
// Colours are named red/blue/yellow/black because that is the language the rules
// are written in, not because the panel can show them: this screen has one ink,
// so the renderer separates colours by hatching or a letter badge. The core
// deliberately keeps the rule vocabulary rather than renaming colours after
// their appearance (Reversi renamed its sides light/dark for exactly the
// opposite reason -- there the drawing WAS the distinction).

#include <cstdint>

namespace tilerummy {

constexpr int kColours = 4;
constexpr int kNumbers = 13;

// The four colours, in the order tile ids are built from. A rule-level identity,
// not a drawing instruction: the panel has one ink, so the renderer tells them
// apart by hatch or badge and these names only have to match the rules anyone
// reading this file already knows.
constexpr int kRed = 0;
constexpr int kBlue = 1;
constexpr int kYellow = 2;
constexpr int kBlack = 3;

// Two copies of every numbered tile. This is the detail that makes the naive
// group test wrong: "three tiles of the same number" happily accepts two red
// sevens, because a second red seven really is in the box.
constexpr int kCopies = 2;
constexpr int kMaxJokers = 2;

constexpr int kNumberedTiles = kColours * kNumbers * kCopies;  // 104
constexpr int kMaxTiles = kNumberedTiles + kMaxJokers;         // 106

// A tile is one byte: `colour * kNumbers + (number - 1)` for a numbered tile,
// giving a dense 0..51, with the joker taking the next id.
//
// Dense ids are the point. The two copies of a tile are indistinguishable in
// play -- nothing in the rules can tell one red seven from the other -- so the
// id carries no copy index and a multiset of tiles is just a count per id. That
// turns "does this proposed table use exactly the tiles that were available"
// into one pass over a 53-entry array of counts, which is what keeps table
// manipulation linear instead of combinatorial. Packing colour and number into
// separate nibbles would have been marginally easier to read in a debugger and
// would have cost a sparse 0..0xD3 range that no flat array can index cheaply.
using Tile = uint8_t;

constexpr int kDistinctNumbered = kColours * kNumbers;  // 52
constexpr Tile kJoker = static_cast<Tile>(kDistinctNumbered);
constexpr int kTileKinds = kDistinctNumbered + 1;  // 53, every id a census needs
// Not a tile. 0xFF rather than 0, because 0 is a perfectly good tile (red 1).
constexpr Tile kNoTile = 0xFF;

inline bool isJoker(const Tile tile) { return tile == kJoker; }

inline Tile makeTile(const int colour, const int number) {
  return static_cast<Tile>(colour * kNumbers + (number - 1));
}

// -1 for a joker: a joker has no colour of its own, only the colour of whatever
// it stands in for, and a caller that forgets that gets an obviously wrong
// answer instead of a plausible red.
inline int tileColour(const Tile tile) {
  if (isJoker(tile) || tile >= kDistinctNumbered) return -1;
  return tile / kNumbers;
}

// 0 for a joker, for the same reason: no real tile is numbered zero.
inline int tileNumber(const Tile tile) {
  if (isJoker(tile) || tile >= kDistinctNumbered) return 0;
  return tile % kNumbers + 1;
}

// A SET as laid out on the table: up to thirteen tiles, because the longest
// possible run is 1 through 13 and a group can never exceed the four colours.
constexpr int kMinSetTiles = 3;
constexpr int kMaxSetTiles = kNumbers;

struct Set {
  Tile tiles[kMaxSetTiles];
  uint8_t count;
};

enum class SetKind : uint8_t {
  None,
  Group,
  Run,
};

// Why a set is not a set. The UI needs to point at the offending set and say
// what is wrong with it, so these are reasons a player can act on, not a single
// boolean -- "invalid" on a table of a dozen sets is useless feedback.
enum class SetProblem : uint8_t {
  Ok,
  TooFewTiles,      // fewer than three tiles
  NotASet,          // neither one number nor one colour
  DuplicateColour,  // a group holding two tiles of the same colour
  GroupTooLong,     // more tiles of one number than there are colours
  RunBroken,        // one colour, but not consecutive as laid out
  RunOutOfRange,    // the run would need a 0 or a 14, and neither tile exists
  AllJokers,        // nothing in the set says what the jokers stand for
};

// Problem, kind and score from ONE pass, so a score can never disagree with the
// verdict that produced it.
struct SetCheck {
  SetProblem problem;
  SetKind kind;
  int score;
  // What the set's FIRST seat counts as: the group's number, or the number the
  // run starts on. Zero unless the set is valid. Carried out of the check so
  // impliedValue() does not have to re-derive the joker resolution and then
  // possibly disagree with the score computed here.
  int lowNumber;
};

inline SetCheck checkSet(const Set& set) {
  if (set.count < kMinSetTiles) return {SetProblem::TooFewTiles, SetKind::None, 0, 0};

  // Everything about this set is read off its real tiles; the jokers take
  // whatever is left over. Hence the first non-joker, which is the anchor for
  // both readings.
  int anchor = -1;
  for (int i = 0; i < set.count && anchor < 0; ++i) {
    if (!isJoker(set.tiles[i])) anchor = i;
  }
  // A set of nothing but jokers has no anchor to resolve against, so it is not a
  // set at all. Unreachable with the two jokers the box holds -- three jokers
  // would be needed -- but checkSet() judges whatever the UI assembles, and the
  // resolution below indexes `anchor`, which must never be -1.
  if (anchor < 0) return {SetProblem::AllJokers, SetKind::None, 0, 0};

  // Classification is by the tiles themselves rather than by a kind the caller
  // declares: the player taps tiles together and never says "this is a group".
  const int number = tileNumber(set.tiles[anchor]);
  const int colour = tileColour(set.tiles[anchor]);
  bool oneNumber = true;
  bool oneColour = true;
  for (int i = anchor + 1; i < set.count; ++i) {
    if (isJoker(set.tiles[i])) continue;
    if (tileNumber(set.tiles[i]) != number) oneNumber = false;
    if (tileColour(set.tiles[i]) != colour) oneColour = false;
  }
  if (!oneNumber && !oneColour) return {SetProblem::NotASet, SetKind::None, 0, 0};

  // With a single real tile both readings hold, and the group is taken. It is
  // the reading that ASSUMES LESS: the jokers' numbers are forced by the known
  // tile, while a run would additionally assume the player meant the jokers as
  // that tile's neighbours in sequence. Two real tiles always decide it
  // outright, so this tie-break only bites on one tile plus both jokers.
  if (oneNumber) {
    // Four colours exist, so a fifth tile of one number is not a group that
    // happens to repeat a colour -- it cannot be a group at all, and reporting
    // the length is more useful than naming whichever duplicate was noticed.
    //
    // This length cap is also the whole of the joker-colour rule: a joker must
    // stand for a colour no other tile of the group is using, and with at most
    // four tiles and no two real tiles sharing a colour there is always a free
    // colour left. Any arrangement that would force a joker onto a taken colour
    // must therefore trip either this cap or the duplicate scan below, so a
    // third explicit test for it would be dead code.
    if (set.count > kColours) return {SetProblem::GroupTooLong, SetKind::None, 0, 0};

    bool used[kColours] = {false, false, false, false};
    for (int i = 0; i < set.count; ++i) {
      if (isJoker(set.tiles[i])) continue;
      const int seat = tileColour(set.tiles[i]);
      if (used[seat]) return {SetProblem::DuplicateColour, SetKind::None, 0, 0};
      used[seat] = true;
    }
    // Every tile in a group, joker included, is worth the group's number -- that
    // is what "a joker scores the value of the tile it stands in for" means
    // here, and it is why there is no constant joker value anywhere in the file.
    return {SetProblem::Ok, SetKind::Group, number * set.count, number};
  }

  // A run is judged exactly as the player laid it out, left to right -- the core
  // never sorts the set. That is not laziness about ordering: once a joker is in
  // the set, the ARRANGEMENT is the only thing that says what the joker stands
  // for. "R7 R8 J" is 7-8-9 and "J R7 R8" is 6-7-8, and they score differently,
  // so a core that reordered tiles would have to guess which run the player
  // meant and then score its own guess. The UI may offer a sort button; the
  // rules do not get to.
  const int start = number - anchor;
  for (int i = 0; i < set.count; ++i) {
    if (isJoker(set.tiles[i])) continue;
    if (tileNumber(set.tiles[i]) != start + i) return {SetProblem::RunBroken, SetKind::None, 0, 0};
  }
  // Runs do NOT wrap, and the reason is simply that the tile the seat needs has
  // to exist: 12-13-J wants a 14 and J-1-2 wants a 0. Checked AFTER the seat
  // scan on purpose, so a real tile in the wrong place is reported as a broken
  // run -- the player's fix is to move that tile -- while a run only a
  // non-existent tile could complete is reported as out of range.
  if (start < 1 || start + set.count - 1 > kNumbers) {
    return {SetProblem::RunOutOfRange, SetKind::None, 0, 0};
  }
  int score = 0;
  for (int i = 0; i < set.count; ++i) score += start + i;
  return {SetProblem::Ok, SetKind::Run, score, start};
}

inline bool setValid(const Set& set) { return checkSet(set).problem == SetProblem::Ok; }

// Zero for an invalid set, not a partial sum. A caller adding up a table must
// not be able to accumulate points from an arrangement the rules reject.
inline int setScore(const Set& set) {
  const SetCheck check = checkSet(set);
  return check.problem == SetProblem::Ok ? check.score : 0;
}

// What the tile in seat `index` counts as: its own number, or the number the
// joker sitting there stands in for. Zero when the set is not valid.
//
// A NUMBER and not a Tile, deliberately. A joker in a run has a fully determined
// tile -- colour and number both -- but a joker in a group has only a determined
// number: "R7 B7 J" is as happily the yellow seven as the black one, and nothing
// in the rules or the score distinguishes them. Returning a Tile would mean
// inventing a colour the rules never fixed and then showing the player that
// invention as if it were the answer.
inline int impliedValue(const Set& set, const int index) {
  if (index < 0 || index >= set.count) return 0;
  const SetCheck check = checkSet(set);
  if (check.problem != SetProblem::Ok) return 0;
  return check.kind == SetKind::Run ? check.lowNumber + index : check.lowNumber;
}

// The TABLE: every set currently in front of the players, as they arranged it.
//
// Sized for the most sets the tiles could ever form -- 35 sets of three, with
// one tile left over that cannot make a set on its own -- so the array can never
// be the thing that stops a legal arrangement. Fixed size, no heap: this runs on
// a device with roughly 170 KB free, and a std::vector of sets would be both an
// allocation per rearrangement and a fragmentation risk on a turn-based game
// that rearranges constantly.
constexpr int kMaxSets = kMaxTiles / kMinSetTiles;  // 35
static_assert(kMaxSets * kMinSetTiles <= kMaxTiles, "set array must fit the tiles");
static_assert((kMaxSets + 1) * kMinSetTiles > kMaxTiles, "set array is larger than the tiles need");

// Not a set index. -1 rather than 0, because set 0 is a real set.
constexpr int8_t kNoSet = -1;

struct Table {
  Set sets[kMaxSets];
  uint8_t setCount;
};

// The verdict on a whole table: valid, or the FIRST set that is not and why.
// A bare boolean would be unusable -- the UI has to outline the offending set
// and name the fault, and on a table of a dozen sets "invalid" tells the player
// nothing they can act on.
struct TableCheck {
  bool ok;
  int8_t failedSet;
  SetProblem problem;
};

// THE central operation of this core, and the reason there is no solver here.
//
// The player rearranges the table by tapping and then hands in the complete
// proposed arrangement; this judges it in one linear pass. The obvious
// alternative -- "here is a loose tile, find a re-partition of the table that
// absorbs it" -- is a combinatorial search over up to 106 tiles, which neither
// the free RAM nor a 2-3 FPS panel can pay for, and which would also take the
// interesting decisions away from the player. Judging a finished state instead
// makes table manipulation free: any rearrangement the player can express is
// just a different argument to this function.
inline TableCheck checkTable(const Table& table) {
  for (int i = 0; i < table.setCount; ++i) {
    const SetCheck check = checkSet(table.sets[i]);
    // The FIRST failure, not all of them: the player fixes one set at a time,
    // and fixing it reveals the next.
    if (check.problem != SetProblem::Ok) return {false, static_cast<int8_t>(i), check.problem};
  }
  return {true, kNoSet, SetProblem::Ok};
}

inline int tableTileCount(const Table& table) {
  int count = 0;
  for (int i = 0; i < table.setCount; ++i) count += table.sets[i].count;
  return count;
}

inline int tableScore(const Table& table) {
  int score = 0;
  for (int i = 0; i < table.setCount; ++i) score += setScore(table.sets[i]);
  return score;
}

// CONFIGURABLE SETTINGS. Four knobs, each with validated bounds, in the same
// spirit as the memory game's card count: one set of rules covering a ten-minute
// two-player game and a long four-player one without a second implementation.
struct Settings {
  uint8_t players;       // kMinPlayers..kMaxPlayers
  uint8_t startingHand;  // kMinStartingHand..kMaxStartingHand
  uint8_t meldMinimum;   // kMinMeld..kMaxMeld, the first-meld threshold
  uint8_t jokers;        // 0..kMaxJokers; zero is harder, not broken
};

constexpr int kMinPlayers = 2;
// Four, because the physical game seats four and because every per-player array
// in Game is sized by this -- raising it costs RAM whether or not anyone uses it.
constexpr int kMaxPlayers = 4;

// Fourteen is the standard hand. Seven makes a short game for someone who has
// ten minutes, eighteen makes a long one; below three a player could not even
// hold a set, and the upper end is capped so four players still leave a pool.
constexpr int kMinStartingHand = 7;
constexpr int kMaxStartingHand = 18;

// Thirty is the standard opening requirement. Twenty lets a beginner get started
// a turn or two sooner; fifty keeps experienced players in their hands for
// longer, which is the whole difficulty of the opening.
constexpr int kMinMeld = 20;
constexpr int kMaxMeld = 50;

// What the settings screen offers, easiest first. The test walks these and
// insists every one is accepted by settingsValid() and that they increase, so a
// chooser gets monotone difficulty for free rather than trusting the next edit.
constexpr uint8_t kStartingHandOptions[] = {7, 10, 14, 18};
constexpr int kStartingHandOptionCount = static_cast<int>(sizeof(kStartingHandOptions));
constexpr uint8_t kMeldMinimumOptions[] = {20, 30, 40, 50};
constexpr int kMeldMinimumOptionCount = static_cast<int>(sizeof(kMeldMinimumOptions));

inline Settings defaultSettings() {
  Settings settings;
  settings.players = 2;
  settings.startingHand = 14;
  settings.meldMinimum = 30;
  settings.jokers = kMaxJokers;
  return settings;
}

// How many tiles are in play. The only quantity the pool, and therefore the
// whole game, scales by.
inline int tileCount(const Settings& settings) { return kNumberedTiles + settings.jokers; }

// Whether a deal leaves anything to draw from. Takes loose numbers rather than a
// Settings so a test can probe combinations the bounds would otherwise forbid --
// a check that can only ever see legal input proves nothing about the next time
// someone widens a bound.
//
// One full round of draws is the reserve. A game that begins with an empty pool
// cannot run its own turn loop: the first player who cannot meld has nothing to
// take, and "draw or play" stops being a choice on move one.
inline bool dealFits(const int players, const int startingHand, const int jokers) {
  return players * (startingHand + 1) <= kNumberedTiles + jokers;
}

inline bool settingsValid(const Settings& settings) {
  if (settings.players < kMinPlayers || settings.players > kMaxPlayers) return false;
  if (settings.startingHand < kMinStartingHand || settings.startingHand > kMaxStartingHand) return false;
  if (settings.meldMinimum < kMinMeld || settings.meldMinimum > kMaxMeld) return false;
  if (settings.jokers > kMaxJokers) return false;
  return dealFits(settings.players, settings.startingHand, settings.jokers);
}

// Lay out a fresh pool in canonical order: every numbered tile kCopies times,
// then the jokers. Returns the tile count, which is what scales with settings.
inline int composePool(Tile* pool, const Settings& settings) {
  int count = 0;
  for (int copy = 0; copy < kCopies; ++copy) {
    for (int colour = 0; colour < kColours; ++colour) {
      for (int number = 1; number <= kNumbers; ++number) {
        pool[count++] = makeTile(colour, number);
      }
    }
  }
  const int jokers = settings.jokers > kMaxJokers ? kMaxJokers : settings.jokers;
  for (int i = 0; i < jokers; ++i) pool[count++] = kJoker;
  return count;
}

// A 32-bit linear congruential generator, the Numerical Recipes constants.
//
// Hand-rolled rather than <random>: std::mt19937 costs 2.5 KB of state on a
// device with ~170 KB free and <random> drags in far more flash than a shuffle
// is worth, while std::random_device and time() are both disqualified outright
// because a deal nobody can reproduce is a bug report nobody can act on. An LCG
// is a poor generator for statistics and a perfectly good one for shuffling 106
// tiles in front of a human.
inline uint32_t nextRandom(uint32_t& state) {
  state = state * 1664525u + 1013904223u;
  return state;
}

// Fisher-Yates, downward, in place. Every permutation reachable, no tile
// created or destroyed -- the pool after a shuffle is the same multiset as
// before, which the test checks rather than assumes.
inline void shufflePool(Tile* pool, const int count, const uint32_t seed) {
  uint32_t state = seed;
  for (int i = count - 1; i > 0; --i) {
    const uint32_t pick = nextRandom(state) % static_cast<uint32_t>(i + 1);
    const Tile swap = pool[i];
    pool[i] = pool[pick];
    pool[pick] = swap;
  }
}

// A hand sized for the whole box. That looks absurdly generous next to an
// eighteen-tile deal, but a player who never melds keeps drawing, and the real
// ceiling is "the starting hand plus everything left in the pool". Working out
// a tighter bound per settings would save 150 bytes across four players and
// introduce an overflow to reason about on every draw; this way the array simply
// cannot overflow, and the saving is not worth the proof.
constexpr int kMaxHand = kMaxTiles;

struct Hand {
  Tile tiles[kMaxHand];
  uint8_t count;
};

// Not a player. -1, because player 0 is a real player.
constexpr int8_t kNoPlayer = -1;

// The WHOLE game, one plain struct, no heap anywhere: 1,036 bytes measured, of
// which the table is 491 and the four hands 428. Affordable on a device with
// roughly 170 KB free, and a fixed footprint is worth more than a tight one when
// the alternative is allocating on every rearrangement of the table.
struct Game {
  Settings settings;
  // The face-down pool. Drawing takes pool[poolCount - 1] and decrements, so a
  // draw is one read and no shifting; the order below that index is untouched,
  // which is also what makes a seeded game replayable to the last tile.
  Tile pool[kMaxTiles];
  Hand hands[kMaxPlayers];
  Table table;
  uint8_t poolCount;
  uint8_t turn;
  // Whether each player has made their opening meld. Per player, not global:
  // the threshold is a toll each player pays once, and one player melding says
  // nothing about the others.
  bool melded[kMaxPlayers];
  int8_t winner;
};

inline bool over(const Game& game) { return game.winner != kNoPlayer; }

inline int handCount(const Game& game, const int player) {
  if (player < 0 || player >= game.settings.players) return 0;
  return game.hands[player].count;
}

// Deal a new game. False, and the game is left exactly as it was, when the
// settings are not ones this core can deal -- the caller hands a stored settings
// blob straight in, and a corrupt one must not produce a half-dealt game.
inline bool start(Game& game, const Settings& settings, const uint32_t seed) {
  if (!settingsValid(settings)) return false;

  game.settings = settings;
  const int count = composePool(game.pool, settings);
  shufflePool(game.pool, count, seed);
  // Clear the tail of the pool array and every unused hand slot. Not needed by
  // any rule, but it keeps the whole struct byte-comparable, which is how the
  // tests check that a rejected action changed nothing at all.
  for (int i = count; i < kMaxTiles; ++i) game.pool[i] = kNoTile;
  for (int p = 0; p < kMaxPlayers; ++p) {
    for (int i = 0; i < kMaxHand; ++i) game.hands[p].tiles[i] = kNoTile;
    game.hands[p].count = 0;
    game.melded[p] = false;
  }
  game.poolCount = static_cast<uint8_t>(count);

  // Round-robin, one tile at a time, the way a human deals -- not whole hands at
  // once. It costs nothing and it means a player watching the deal on screen
  // sees something they recognise.
  for (int round = 0; round < settings.startingHand; ++round) {
    for (int p = 0; p < settings.players; ++p) {
      game.hands[p].tiles[game.hands[p].count++] = game.pool[--game.poolCount];
    }
  }

  for (int i = 0; i < kMaxSets; ++i) game.table.sets[i].count = 0;
  game.table.setCount = 0;
  game.turn = 0;
  game.winner = kNoPlayer;
  return true;
}

inline void passTurn(Game& game) {
  game.turn = static_cast<uint8_t>((game.turn + 1) % game.settings.players);
}

// Take one tile and end the turn. False when the pool is empty or the game is
// over, and then nothing changed: a caller wires a button straight to this.
//
// An empty pool does NOT end the game here. Play continues on the tiles already
// out, and whoever empties their hand still wins; a core that declared a draw
// the moment the pool ran dry would cut short the most interesting phase.
inline bool drawTile(Game& game) {
  if (over(game) || game.poolCount == 0) return false;
  Hand& hand = game.hands[game.turn];
  hand.tiles[hand.count++] = game.pool[--game.poolCount];
  passTurn(game);
  return true;
}

// Why a proposed turn is refused. Separate from SetProblem because a turn can be
// made of perfectly valid sets and still be impossible -- a tile conjured out of
// nowhere, or an opening that falls short.
enum class MoveProblem : uint8_t {
  Ok,
  GameOver,
  TooManySets,           // more sets than the fixed array holds
  InvalidSet,            // some set is not a set; see failedSet and setProblem
  TileRemovedFromTable,  // a tile that was on the table is missing from the proposal
  TileNotInHand,         // the proposal uses a tile the player does not hold
  NothingPlayed,         // the proposal is the table as it already stands
  TableUsedBeforeMeld,   // an un-melded player altered the existing table
  MeldTooSmall,          // the opening meld does not reach the minimum
};

struct MoveResult {
  MoveProblem problem;
  // Only meaningful for InvalidSet. Set to kNoSet / Ok otherwise so a caller
  // cannot read a stale index out of a result that is about something else.
  int8_t failedSet;
  SetProblem setProblem;
  // How many tiles would leave the hand, and what the sets laid down THIS TURN
  // are worth. The score is zero once the player has melded: the threshold is a
  // one-off toll, not a per-turn quota, and reporting a number there would
  // invite a UI that shows it. Both are filled in even when the move is refused
  // for being too small, so the UI can say "21 of 30".
  int added;
  int meldScore;
};

// Count tiles by kind into a 53-entry census. The whole conservation argument
// rests on this: the two copies of a tile are indistinguishable, so "the same
// tiles" is just "the same counts", and comparing two multisets is linear.
inline void countTiles(const Tile* tiles, const int count, int* seen) {
  for (int i = 0; i < count; ++i) {
    if (tiles[i] < kTileKinds) ++seen[tiles[i]];
  }
}

inline void clearCensus(int* seen) {
  for (int kind = 0; kind < kTileKinds; ++kind) seen[kind] = 0;
}

inline void countTable(const Table& table, int* seen) {
  for (int i = 0; i < table.setCount; ++i) countTiles(table.sets[i].tiles, table.sets[i].count, seen);
}

// Judge a proposed turn WITHOUT changing anything.
//
// The player hands in the complete table they have arranged; this answers
// whether that is a legal thing to have done, and if not, which part of it was
// not. Pure, so the UI can call it on every tap to decide whether the commit
// button is live, and so play() cannot possibly apply a different rule than the
// one the player was shown.
//
// Four questions in order, each a single linear pass:
//   1. is every set a set?
//   2. is the table's own content all still there?
//   3. did the extra tiles come from this player's hand?
//   4. if this is their opening, is it big enough, and is it all their own?
// There is no fifth question of the form "could these tiles be arranged some
// other way" -- that is the search this core refuses to do.
inline MoveResult checkPlay(const Game& game, const Table& proposed) {
  MoveResult result = {MoveProblem::Ok, kNoSet, SetProblem::Ok, 0, 0};
  if (over(game)) {
    result.problem = MoveProblem::GameOver;
    return result;
  }
  // A proposal can arrive from storage, so the bound is checked rather than
  // assumed: the loops below would otherwise read past the set array.
  if (proposed.setCount > kMaxSets) {
    result.problem = MoveProblem::TooManySets;
    return result;
  }

  const TableCheck table = checkTable(proposed);
  if (!table.ok) {
    result.problem = MoveProblem::InvalidSet;
    result.failedSet = table.failedSet;
    result.setProblem = table.problem;
    return result;
  }

  int want[kTileKinds];
  int have[kTileKinds];
  clearCensus(want);
  clearCensus(have);
  countTable(proposed, want);
  countTable(game.table, have);

  const Hand& hand = game.hands[game.turn];
  int handCensus[kTileKinds];
  clearCensus(handCensus);
  countTiles(hand.tiles, hand.count, handCensus);

  for (int kind = 0; kind < kTileKinds; ++kind) {
    const int delta = want[kind] - have[kind];
    if (delta < 0) {
      // Tiles do not leave the table. A player may re-partition it however they
      // like, but they cannot take anything back off it -- without this, "move
      // these three tiles into my hand" would validate perfectly.
      result.problem = MoveProblem::TileRemovedFromTable;
      return result;
    }
    if (delta > handCensus[kind]) {
      result.problem = MoveProblem::TileNotInHand;
      return result;
    }
    result.added += delta;
  }

  if (result.added == 0) {
    // The table as it stands is not a turn. This is what makes "play or draw" a
    // real choice rather than a free pass.
    result.problem = MoveProblem::NothingPlayed;
    return result;
  }

  if (!game.melded[game.turn]) {
    // Before their opening meld a player may not use the table AT ALL -- not
    // rearrange it, not lay off onto it. That is the rule as played, and it is
    // also what makes "counted only from the sets they lay down that turn"
    // precise: the existing sets must come back untouched and in place, so
    // everything after them is exactly what this player just put down.
    if (proposed.setCount < game.table.setCount) {
      result.problem = MoveProblem::TableUsedBeforeMeld;
      return result;
    }
    for (int i = 0; i < game.table.setCount; ++i) {
      const Set& before = game.table.sets[i];
      const Set& after = proposed.sets[i];
      if (before.count != after.count) {
        result.problem = MoveProblem::TableUsedBeforeMeld;
        return result;
      }
      for (int j = 0; j < before.count; ++j) {
        if (before.tiles[j] != after.tiles[j]) {
          result.problem = MoveProblem::TableUsedBeforeMeld;
          return result;
        }
      }
    }
    for (int i = game.table.setCount; i < proposed.setCount; ++i) {
      result.meldScore += setScore(proposed.sets[i]);
    }
    if (result.meldScore < game.settings.meldMinimum) {
      result.problem = MoveProblem::MeldTooSmall;
      return result;
    }
  }
  return result;
}

// Commit a proposed turn. False, and the game is left exactly as it was, for
// every reason checkPlay() can name -- a caller wires a button straight here, so
// the rejected path runs far more often than the accepted one.
inline bool play(Game& game, const Table& proposed) {
  if (checkPlay(game, proposed).problem != MoveProblem::Ok) return false;

  // Which tiles to take out of the hand: the difference between the two tables,
  // recomputed here rather than carried out of checkPlay(). It is one more pass
  // over 53 counters, and it buys a removal that cannot disagree with the check
  // that permitted the move.
  int need[kTileKinds];
  int had[kTileKinds];
  clearCensus(need);
  clearCensus(had);
  countTable(proposed, need);
  countTable(game.table, had);
  for (int kind = 0; kind < kTileKinds; ++kind) need[kind] -= had[kind];

  // Compact the hand in one pass, keeping the order of what stays. The player
  // arranged those tiles; a removal that swapped the last tile into the gap
  // would reshuffle their layout on every turn.
  Hand& hand = game.hands[game.turn];
  uint8_t keep = 0;
  for (int i = 0; i < hand.count; ++i) {
    const Tile tile = hand.tiles[i];
    if (tile < kTileKinds && need[tile] > 0) {
      --need[tile];
      continue;
    }
    hand.tiles[keep++] = tile;
  }
  for (int i = keep; i < hand.count; ++i) hand.tiles[i] = kNoTile;
  hand.count = keep;

  game.table = proposed;
  game.melded[game.turn] = true;

  // Placing your last tile wins, and the turn stays with the winner: there is
  // nobody for it to pass to in a finished game, and the UI reads `turn` to
  // decide whose hand to show.
  if (hand.count == 0) {
    game.winner = static_cast<int8_t>(game.turn);
    return true;
  }
  passTurn(game);
  return true;
}

}  // namespace tilerummy
