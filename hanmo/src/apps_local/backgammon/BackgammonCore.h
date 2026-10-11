#pragma once

// Backgammon, the rules. Freestanding: no renderer, no Activity, no storage.
//
// Twenty-four points, fifteen checkers a side. Roll two dice and move a checker
// the pips on one die along your own track; a DOUBLE is four moves of that
// value, not two. A point holding two or more enemy checkers is closed to you; a
// point holding exactly one is open, and landing there HITS that checker onto
// the bar. A side with anything on the bar must bring it back before it may
// move anything else. Once all fifteen of your checkers are home you may bear
// them off, and getting all fifteen off wins.
//
// The board is `point[24]`, one SIGNED count per point: positive is that many
// light checkers, negative is that many dark ones, zero is empty. A point can
// never hold both sides at once -- that is a rule of the game, not a storage
// convenience -- so a signed count makes the mixed point inexpressible, the same
// way Connect Four made a floating disc inexpressible. The bar and the borne-off
// pile are separate counters because they are not points: you cannot be hit on
// the bar and nothing is ever blocked there.
//
// **The two sides travel in opposite directions, and that lives in exactly one
// place: direction().** Light runs 0 -> 23 and bears off past 23; dark runs
// 23 -> 0 and bears off past -1. Every other piece of movement arithmetic is
// written once in terms of `direction(side)`, so there is no second copy of the
// asymmetry to fall out of step. Point indices are therefore absolute board
// positions, NOT either player's 1..24 numbering -- a player's own numbering is
// pipsToOff(), which is the only place the two numberings are reconciled.
//
// Sides are named for how they are DRAWN -- outlined and solid -- rather than
// black and white, following Checkers, Connect Four and Reversi: this panel has
// one ink, and filled means whose, never whose turn.
//
// Dice are PARAMETERS. The core never reads a clock and never owns a global
// generator, so a host test can replay any position exactly; the optional
// rollDice() below takes a seed the caller supplies.

#include <cstdint>

namespace backgammon {

constexpr int kPoints = 24;
constexpr int kCheckers = 15;
constexpr int kFaces = 6;
// The home quadrant is six points deep because the largest die face is six:
// every checker that is home can be taken off by a single die, and no checker
// outside home ever can be.
constexpr int kHomeSize = 6;
// Four, not two: a double is played as four moves of the same value.
constexpr int kMaxPendingDice = 4;

// The two sides double as indices into bar[] and off[], so they start at zero.
// There is no kEmpty to collide with here -- an empty point is a zero COUNT in
// a signed array, not a side label.
constexpr uint8_t kLight = 0;
constexpr uint8_t kDark = 1;
constexpr int kSides = 2;

// Stands in for "a checker on the bar" wherever a source point is expected.
// Negative so it can never collide with a real point index.
constexpr int kBar = -1;

// Upper bound on the sources one die value can have: every point, plus the bar.
// The two cases are mutually exclusive in practice -- a side on the bar has no
// other legal source -- but a caller sizing a buffer should not have to know
// that to be safe.
constexpr int kMaxLegalMoves = kPoints + 1;

enum class Outcome : uint8_t {
  Running,
  LightWins,
  DarkWins,
};

struct Game {
  // point[index]: >0 that many light checkers, <0 that many dark, 0 empty.
  int8_t point[kPoints];
  // Hit checkers waiting to re-enter, indexed by side.
  uint8_t bar[kSides];
  // Checkers borne off, indexed by side. Fifteen wins.
  uint8_t off[kSides];
  // The move values still owed on this turn, 0 for a slot already spent or
  // never filled. Values rather than "two dice plus a counter" because a double
  // owes four moves of one number and a mixed roll owes two different numbers,
  // and because dice can be FORFEITED when nothing legal remains for them.
  uint8_t die[kMaxPendingDice];
  uint8_t turn;
  Outcome outcome;
};

inline uint8_t other(const uint8_t side) { return side == kLight ? kDark : kLight; }

// The one direction value per side. Everything about movement -- destinations,
// entry from the bar, distance to off, which checker is "furthest back" -- is
// derived from this, so a mirrored position behaves identically for both sides
// by construction rather than by a second code path that has to agree.
inline int direction(const uint8_t side) { return side == kLight ? 1 : -1; }

inline bool inside(const int at) { return at >= 0 && at < kPoints; }

inline bool over(const Game& game) { return game.outcome != Outcome::Running; }

// The notional point just BEFORE the start of a side's track, which is where a
// checker on the bar comes from. Derived from direction() rather than written
// out per side, so the asymmetry still lives in exactly one function.
inline int barOrigin(const uint8_t side) { return direction(side) > 0 ? -1 : kPoints; }

// The notional point just PAST the end of a side's track, which is where a
// checker goes when it is borne off.
//
// It is the opponent's bar origin, and that is not a coincidence worth hiding:
// the two tracks are the same twenty-four points walked in opposite
// directions, so where you finish is where they start.
inline int offEdge(const uint8_t side) { return barOrigin(other(side)); }

// How many pips `side` needs to take a checker on `at` off the board.
//
// This is also that side's own 1..24 numbering of the point, which is why the
// opening position can be stated once and mirrored: both sides' "6-point" is
// the point six pips from off. Written through direction() and offEdge()
// instead of as one formula per side -- the two numberings are reconciled
// HERE and nowhere else, and a second copy is the bug this whole arrangement
// exists to prevent.
inline int pipsToOff(const uint8_t side, const int at) {
  return direction(side) * (offEdge(side) - at);
}

inline int checkersAt(const Game& game, const int at, const uint8_t side) {
  if (!inside(at)) return 0;
  const int count = game.point[at];
  if (side == kLight) return count > 0 ? count : 0;
  return count < 0 ? -count : 0;
}

inline int onBoard(const Game& game, const uint8_t side) {
  int count = 0;
  for (int at = 0; at < kPoints; ++at) count += checkersAt(game, at, side);
  return count;
}

inline int pendingCount(const Game& game) {
  int count = 0;
  for (int i = 0; i < kMaxPendingDice; ++i) {
    if (game.die[i] != 0) ++count;
  }
  return count;
}

// Put `count` checkers of `side` on a point. Kept as the single writer of
// point[] so the sign convention is applied in one place; callers deal in
// counts and never in signs.
inline void setCheckers(Game& game, const int at, const uint8_t side, const int count) {
  if (!inside(at)) return;
  game.point[at] = static_cast<int8_t>(side == kLight ? count : -count);
}

inline void start(Game& game) {
  for (int at = 0; at < kPoints; ++at) game.point[at] = 0;
  // The standard opening, written in each side's OWN numbering and placed
  // through direction(): two on the 24-point, five on the 13, three on the 8,
  // five on the 6. Spelling it this way rather than as eight board indices is
  // what makes the mirror a consequence instead of a coincidence.
  constexpr int kOpening[4][2] = {{24, 2}, {13, 5}, {8, 3}, {6, 5}};
  for (int side = kLight; side < kSides; ++side) {
    const uint8_t who = static_cast<uint8_t>(side);
    for (const auto& stack : kOpening) {
      // pipsToOff() inverted: the board index this side calls `stack[0]`. One
      // expression for both sides, so the mirror cannot be typed in wrong.
      const int at = offEdge(who) - direction(who) * stack[0];
      setCheckers(game, at, who, stack[1]);
    }
    game.bar[side] = 0;
    game.off[side] = 0;
  }
  for (int i = 0; i < kMaxPendingDice; ++i) game.die[i] = 0;
  // Placeholder seat for a board with no active roll; not an opening result.
  // beginOpeningTurn() chooses the higher of one supplied die per seat.
  game.turn = kLight;
  game.outcome = Outcome::Running;
}

// ---------------------------------------------------------------------------
// Bearing off
//
// Ahead of the movement rules because canMoveFrom() routes every off-board
// destination straight into them: running past the end of your own track is
// not an error to reject, it is a bear-off to judge.
// ---------------------------------------------------------------------------

// `at` is in that side's home quadrant: the last six points of its own track.
// Read through pipsToOff() rather than compared against literal 18 and 5, so
// the two homes stay each other's mirror by construction.
inline bool inHome(const uint8_t side, const int at) {
  return inside(at) && pipsToOff(side, at) <= kHomeSize;
}

// All fifteen of that side's checkers are home or already off. The precondition
// for bearing off, and the reason a late hit is so expensive: one checker sent
// to the bar makes this false again until it has walked the whole board back.
//
// The bar is checked first and separately, because a checker on the bar is NOT
// at any point index -- a scan over points alone would call a position with a
// hit checker fully home.
inline bool allHome(const Game& game, const uint8_t side) {
  if (game.bar[side] > 0) return false;
  for (int at = 0; at < kPoints; ++at) {
    if (checkersAt(game, at, side) > 0 && !inHome(side, at)) return false;
  }
  return true;
}

// Whether `side` still has a checker further from home than `at`.
//
// This is the whole content of the over-shoot rule, so it is its own function
// rather than a loop buried inside the bear-off test: the UI calls it directly
// to grey out an oversized die. The bar needs no mention -- allHome() has
// already refused any side with a checker on it.
inline bool anyFurtherFromHome(const Game& game, const uint8_t side, const int at) {
  const int need = pipsToOff(side, at);
  for (int rear = 0; rear < kPoints; ++rear) {
    if (checkersAt(game, rear, side) > 0 && pipsToOff(side, rear) > need) return true;
  }
  return false;
}

// Whether `pips` from `at` legally takes a checker OFF for `side`.
//
// Safe to call with `at` == kBar: checkersAt() answers zero off the board, so a
// side with a checker on the bar can never reach this as a bear-off.
inline bool canBearOffFrom(const Game& game, const int at, const uint8_t side, const int pips) {
  if (!allHome(game, side)) return false;
  if (checkersAt(game, at, side) == 0) return false;
  const int need = pipsToOff(side, at);
  if (pips == need) return true;
  // A die LARGER than the distance may still lift a checker off, but only when
  // nothing of yours sits further from home -- otherwise the over-shoot has to
  // be spent walking that rearmost checker up instead, and a player who could
  // overshoot freely would finish several rolls early.
  //
  // A die SMALLER than the distance never arrives here: its destination is
  // still on the board, so canMoveFrom() treats it as the ordinary move it is.
  return pips > need && !anyFurtherFromHome(game, side, at);
}

// ---------------------------------------------------------------------------
// Moving
// ---------------------------------------------------------------------------

// Where a move of `pips` from `from` lands. A checker on the bar starts from
// barOrigin(), which makes entry the SAME arithmetic as any other move rather
// than a second formula: light comes in on -1 + pips, dark on 24 - pips, which
// is each side's own 1..6 points.
//
// Off-board results are not errors: running past the end of your own track is
// what bearing off IS, and the bear-off rules decide whether it was allowed.
inline int destination(const uint8_t side, const int from, const int pips) {
  const int at = from == kBar ? barOrigin(side) : from;
  return at + direction(side) * pips;
}

// The point a checker on the bar comes in on with `pips`. Named separately
// because the UI asks it directly when a side is on the bar, but it is the same
// destination() call -- entry is not a special movement rule, only a special
// starting place.
inline int entryPoint(const uint8_t side, const int pips) { return destination(side, kBar, pips); }

// A point is CLOSED to you when the enemy holds two or more checkers on it.
// Two, not one: a lone enemy checker is a blot, and landing on it is legal --
// it is the hit. This threshold is the whole difference between the two cases.
inline bool blockedFor(const Game& game, const int at, const uint8_t side) {
  return checkersAt(game, at, other(side)) >= 2;
}

// Whether the side to move could play `pips` from `from`, by the rules of the
// board alone. Deliberately ignores the pending roll and turn obligations,
// so bounded turn analysis can inspect one transition without recursing into
// itself. UI selection/highlights and accepted play use canPlayFrom() instead.
inline bool canMoveFrom(const Game& game, const int from, const int pips) {
  if (over(game)) return false;
  if (pips < 1 || pips > kFaces) return false;
  const uint8_t side = game.turn;
  if (from == kBar) {
    if (game.bar[side] == 0) return false;
  } else {
    // THE BAR COMES FIRST, and it is checked here rather than at the turn level
    // because the rule is about the POSITION, not about this move: while a
    // checker waits on the bar the side has exactly one legal source. Letting
    // an otherwise-fine board move slip past this test is the classic way an
    // engine lets a player abandon a hit checker.
    if (game.bar[side] > 0) return false;
    if (!inside(from) || checkersAt(game, from, side) == 0) return false;
  }
  const int to = destination(side, from, pips);
  if (!inside(to)) return canBearOffFrom(game, from, side, pips);
  return !blockedFor(game, to, side);
}

// Add or remove a single checker. Counts in, signs left to setCheckers().
inline void liftFrom(Game& game, const int at, const uint8_t side) {
  setCheckers(game, at, side, checkersAt(game, at, side) - 1);
}

inline void dropOn(Game& game, const int at, const uint8_t side) {
  setCheckers(game, at, side, checkersAt(game, at, side) + 1);
}

inline bool hasPending(const Game& game, const int pips) {
  for (int i = 0; i < kMaxPendingDice; ++i) {
    if (game.die[i] == pips) return true;
  }
  return false;
}

// Spend one owed die of that value. Returns false when none is owed.
inline bool spendDie(Game& game, const int pips) {
  for (int i = 0; i < kMaxPendingDice; ++i) {
    if (game.die[i] == pips) {
      game.die[i] = 0;
      return true;
    }
  }
  return false;
}

// Whether `at` holds exactly one enemy checker: a blot, the only thing a move
// can hit. Separate from blockedFor() rather than derived from it because the
// two thresholds are different rules and a renderer wants to warn about blots
// it is leaving behind as well as ones it can hit.
inline bool blotFor(const Game& game, const int at, const uint8_t side) {
  return checkersAt(game, at, other(side)) == 1;
}

// Record a win once a side has all fifteen off. Separate from play() so a game
// restored from storage can run it too: a position can already be terminal
// before anyone touches it.
inline void settle(Game& game) {
  if (game.off[kLight] >= kCheckers) {
    game.outcome = Outcome::LightWins;
  } else if (game.off[kDark] >= kCheckers) {
    game.outcome = Outcome::DarkWins;
  }
}

// Internal board transition for a move already checked by canMoveFrom().
// Search and accepted play share this writer, so hits/off/dice cannot diverge.
inline void applyMove(Game& game, const int from, const int pips) {
  const uint8_t side = game.turn;
  const int to = destination(side, from, pips);
  if (from == kBar) {
    --game.bar[side];
  } else {
    liftFrom(game, from, side);
  }
  if (!inside(to)) {
    // The checker has left the game: nothing to hit and nowhere to land.
    ++game.off[side];
  } else {
    // The hit comes BEFORE the arrival, because the destination holds a signed
    // count: dropping first would flip the sign and silently destroy the enemy
    // checker instead of relocating it. A hit checker is never lost -- bar plus
    // board plus borne-off is always fifteen.
    if (blotFor(game, to, side)) {
      setCheckers(game, to, other(side), 0);
      ++game.bar[other(side)];
    }
    dropOn(game, to, side);
  }
  spendDie(game, pips);
  // Settled here, not left to the caller: the game is over the instant the
  // fifteenth checker leaves, and a turn with dice still owed must not be able
  // to play on past the win.
  settle(game);
}

// Examine ONLY the remaining roll, not later turns or strategic outcomes.
// At most four transitions, fixed-size stack copies, no allocation. Duplicate
// die values are visited once; stop as soon as every remaining die is usable.
constexpr int kMaxTurnSearchDepth = kMaxPendingDice;
inline int maxUsableDice(const Game& game, const int depth = 0) {
  if (over(game) || depth >= kMaxTurnSearchDepth) return 0;
  const int remaining = pendingCount(game);
  int best = 0;
  for (int i = 0; i < kMaxPendingDice; ++i) {
    const int pips = game.die[i];
    if (pips == 0) continue;
    bool duplicate = false;
    for (int j = 0; j < i; ++j) {
      if (game.die[j] == pips) duplicate = true;
    }
    if (duplicate) continue;
    for (int from = kBar; from < kPoints; ++from) {
      if (!canMoveFrom(game, from, pips)) continue;
      Game next = game;
      applyMove(next, from, pips);
      const int used = 1 + maxUsableDice(next, depth + 1);
      if (used > best) best = used;
      if (best == remaining) return best;
    }
  }
  return best;
}

// Turn legality is stronger than board legality: do not strand a usable die
// by picking the wrong order/source. A final bear-off ends play immediately.
inline bool canPlayFrom(const Game& game, const int from, const int pips) {
  if (!hasPending(game, pips) || !canMoveFrom(game, from, pips)) return false;
  Game next = game;
  applyMove(next, from, pips);
  if (over(next)) return true;
  const int maximum = maxUsableDice(game);
  if (1 + maxUsableDice(next, 1) != maximum) return false;
  // A mixed roll with only one usable move must spend the larger face.
  // Check the current board, not merely the largest pending value: a larger
  // die that cannot enter/move does not invalidate the smaller legal one.
  if (maximum == 1) {
    for (int i = 0; i < kMaxPendingDice; ++i) {
      if (game.die[i] <= pips) continue;
      for (int source = kBar; source < kPoints; ++source) {
        if (canMoveFrom(game, source, game.die[i])) return false;
      }
    }
  }
  return true;
}

// Rejections leave all bytes untouched, including dice and outcome.
inline bool play(Game& game, const int from, const int pips) {
  if (!canPlayFrom(game, from, pips)) return false;
  applyMove(game, from, pips);
  return true;
}

// ---------------------------------------------------------------------------
// Turns
// ---------------------------------------------------------------------------

// Hand this turn's roll in. A DOUBLE fills all four slots, because four moves
// of that value is the rule; spelling it here means nothing downstream has to
// know a double is special.
//
// Refused while a turn is unfinished, so a caller cannot re-roll out of a
// position it dislikes.
inline bool beginTurn(Game& game, const int dieA, const int dieB) {
  if (over(game)) return false;
  if (dieA < 1 || dieA > kFaces || dieB < 1 || dieB > kFaces) return false;
  if (pendingCount(game) != 0) return false;
  for (int i = 0; i < kMaxPendingDice; ++i) game.die[i] = 0;
  if (dieA == dieB) {
    // FOUR moves of that value. This is the one place a double is special, and
    // keeping it here means play(), endTurn() and the move generator never have
    // to know what a double is -- they only ever see a list of owed values.
    for (int i = 0; i < kMaxPendingDice; ++i) game.die[i] = static_cast<uint8_t>(dieA);
  } else {
    game.die[0] = static_cast<uint8_t>(dieA);
    game.die[1] = static_cast<uint8_t>(dieB);
  }
  return true;
}

// One die per seat. Ties/invalid inputs change nothing: the caller shows the
// tie and requests another contest. The higher seat plays BOTH original dice,
// not a fresh roll. This explicit operation owns no RNG or retry loop.
inline bool beginOpeningTurn(Game& game, const int lightDie, const int darkDie) {
  if (over(game) || pendingCount(game) != 0) return false;
  if (lightDie < 1 || lightDie > kFaces || darkDie < 1 || darkDie > kFaces) return false;
  if (lightDie == darkDie) return false;
  game.turn = lightDie > darkDie ? kLight : kDark;
  return beginTurn(game, lightDie, darkDie);
}

// Every legal source for one die value, in board order, written into `out` as
// point indices with kBar for the bar. Returns how many; `out` may be null when
// only the count is wanted.
//
// Board-only SOURCES, not destinations; UI uses turnLegalMoves() below.
// and a destination list would merge two different sources that happen to land
// on the same point -- which is exactly the pair of choices a player needs to
// see separately. Board order, not the moving side's own order, because board
// indices are what the renderer draws.
inline int legalMoves(const Game& game, const int pips, int8_t* out) {
  int count = 0;
  for (int from = kBar; from < kPoints; ++from) {
    if (!canMoveFrom(game, from, pips)) continue;
    if (out != nullptr) out[count] = static_cast<int8_t>(from);
    ++count;
  }
  return count;
}

// Turn-legal source list, distinct from the board-only legalMoves().
inline int turnLegalMoves(const Game& game, const int pips, int8_t* out) {
  int count = 0;
  for (int from = kBar; from < kPoints; ++from) {
    if (!canPlayFrom(game, from, pips)) continue;
    if (out != nullptr) out[count] = static_cast<int8_t>(from);
    ++count;
  }
  return count;
}

// Whether any owed die has a legal move. False means the rest of the roll is
// forfeited -- a real and common outcome, not an error.
inline bool hasAnyLegalMove(const Game& game) {
  for (int i = 0; i < kMaxPendingDice; ++i) {
    if (game.die[i] == 0) continue;
    // Starts at kBar, not at 0: a side on the bar has no legal source on the
    // board at all, so a scan over points alone would call every danced turn a
    // dead one and a legal entry would never be found.
    for (int from = kBar; from < kPoints; ++from) {
      if (canMoveFrom(game, from, game.die[i])) return true;
    }
  }
  return false;
}

// Hand the turn over. Refused while an owed die still has a legal move: in
// backgammon you must use as many dice as you legally can, so a player may not
// decline a move merely because it hurts them.
//
// Unusable dice are left visible in `die` until here rather than cleared the
// moment they become dead, so the board can still show the player the 5 they
// could not play -- a turn that silently loses half a roll looks like a bug.
inline bool endTurn(Game& game) {
  if (over(game)) return false;
  if (hasAnyLegalMove(game)) return false;
  for (int i = 0; i < kMaxPendingDice; ++i) game.die[i] = 0;
  game.turn = other(game.turn);
  return true;
}

// ---------------------------------------------------------------------------
// Dice (optional)
// ---------------------------------------------------------------------------
//
// Nothing above this line rolls anything: beginTurn() takes the two values as
// parameters, so the rules are a pure function of position plus roll. These two
// helpers exist only for callers that would rather not own a generator, and
// they take the seed BY REFERENCE -- store that one uint32_t with the game and
// the whole match is replayable.
//
// A hand-written multiplicative LCG, not std::minstd_rand, so the header keeps
// its single <cstdint> include: <random> is a heavy dependency for six faces of
// a die, and nothing here needs distribution quality. Deliberately NOT seeded
// from a clock or std::random_device anywhere -- an unreproducible rules core
// cannot be tested against an exact position.
inline uint32_t nextRandom(uint32_t& state) {
  // Zero is this generator's fixed point: left alone it would return zero for
  // ever and every die would come up the same.
  if (state == 0) state = 1u;
  constexpr uint32_t kMultiplier = 48271u;
  constexpr uint32_t kModulus = 2147483647u;
  state = static_cast<uint32_t>((static_cast<uint64_t>(state) * kMultiplier) % kModulus);
  return state;
}

// Two dice, each 1..kFaces. Equal values are a double, and beginTurn() is what
// turns that into four moves -- this helper has no opinion about it.
inline void rollDice(uint32_t& state, int& dieA, int& dieB) {
  dieA = static_cast<int>(nextRandom(state) % kFaces) + 1;
  dieB = static_cast<int>(nextRandom(state) % kFaces) + 1;
}

}  // namespace backgammon
