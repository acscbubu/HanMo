"""Compile the actual Backgammon rules with host g++ and replay exact positions.

Freestanding core, same shape as reversi/ReversiCore.h: no renderer, no Activity,
no storage -- and no clock. Every die value the core acts on arrives as a
parameter, which is the whole reason a test can state a position plus a roll and
get the same answer on every run.
"""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
GAME_DIR = ROOT / "src/apps_local/backgammon"

HARNESS = r'''
#include "BackgammonCore.h"

#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>

using namespace backgammon;

// Build a position from two rows of twelve tokens: points 0..11 then 12..23,
// each token '.' for an empty point or a side letter and a count, "L3" for
// three light checkers and "D5" for five dark ones.
//
// Reading a position as text is the only way these tests stay auditable -- a
// list of checker assignments hides which shape is being tested, and a
// backgammon position has far too many of them to hold in your head.
static void parseRow(Game& game, const char* text, const int first) {
  const char* cursor = text;
  for (int i = 0; i < kPoints / 2; ++i) {
    while (*cursor == ' ') ++cursor;
    assert(*cursor != '\0');
    const int at = first + i;
    if (*cursor == '.') {
      setCheckers(game, at, kLight, 0);
      ++cursor;
      continue;
    }
    const char who = *cursor++;
    assert(who == 'L' || who == 'D');
    int count = 0;
    while (*cursor >= '0' && *cursor <= '9') count = count * 10 + (*cursor++ - '0');
    assert(count > 0 && count <= kCheckers);
    setCheckers(game, at, who == 'L' ? kLight : kDark, count);
  }
  while (*cursor == ' ') ++cursor;
  // A row that is not exactly twelve tokens is a typo in the test, not a
  // position worth running.
  assert(*cursor == '\0');
}

static void layout(Game& game, const char* top, const char* bottom, const uint8_t turn,
                   const int lightBar = 0, const int darkBar = 0) {
  parseRow(game, top, 0);
  parseRow(game, bottom, kPoints / 2);
  game.bar[kLight] = static_cast<uint8_t>(lightBar);
  game.bar[kDark] = static_cast<uint8_t>(darkBar);
  // Borne-off counts are DERIVED, never written by a scenario: whatever is not
  // on the board or the bar is already off. Fifteen checkers a side then holds
  // by construction, so no scenario can quietly test an impossible position.
  for (int side = kLight; side < kSides; ++side) {
    const uint8_t who = static_cast<uint8_t>(side);
    const int seen = game.bar[side] + onBoard(game, who);
    assert(seen <= kCheckers);
    game.off[side] = static_cast<uint8_t>(kCheckers - seen);
  }
  game.turn = turn;
  game.outcome = Outcome::Running;
  for (int i = 0; i < kMaxPendingDice; ++i) game.die[i] = 0;
}

int main(int argc, char** argv) {
  assert(argc == 2);
  const std::string scenario = argv[1];

  if (scenario == "opening") {
    Game game;
    start(game);
    // The standard opening, stated in each side's OWN point numbering: two on
    // the 24-point, five on the 13, three on the 8, five on the 6. Light runs
    // up the indices, so its 24-point is index 0; dark runs down them, so its
    // 24-point is index 23.
    assert(checkersAt(game, 0, kLight) == 2);
    assert(checkersAt(game, 11, kLight) == 5);
    assert(checkersAt(game, 16, kLight) == 3);
    assert(checkersAt(game, 18, kLight) == 5);
    assert(checkersAt(game, 23, kDark) == 2);
    assert(checkersAt(game, 12, kDark) == 5);
    assert(checkersAt(game, 7, kDark) == 3);
    assert(checkersAt(game, 5, kDark) == 5);
    assert(onBoard(game, kLight) == kCheckers);
    assert(onBoard(game, kDark) == kCheckers);

    // The position is a mirror, which is the only reason it is fair. Stated as
    // a reflection of the whole board rather than as eight more literals, so a
    // single misplaced stack cannot hide behind the four assertions above.
    for (int at = 0; at < kPoints; ++at) {
      assert(checkersAt(game, at, kLight) == checkersAt(game, kPoints - 1 - at, kDark));
    }

    assert(game.bar[kLight] == 0 && game.bar[kDark] == 0);
    assert(game.off[kLight] == 0 && game.off[kDark] == 0);
    assert(game.turn == kLight);
    assert(game.outcome == Outcome::Running);
    assert(!over(game));
    // No dice until a caller hands some in. The core never rolls for itself.
    assert(pendingCount(game) == 0);

    // The two sides travel in OPPOSITE directions, and that fact lives in
    // exactly one place. Asserting the two values AND their relation so a
    // change that makes both sides agree cannot slip through.
    assert(direction(kLight) == 1);
    assert(direction(kDark) == -1);
    assert(direction(kLight) == -direction(kDark));

    // Distance to off is the same arithmetic read through that direction, so
    // both sides' 24-point really is twenty-four pips from home.
    assert(pipsToOff(kLight, 0) == 24);
    assert(pipsToOff(kLight, 23) == 1);
    assert(pipsToOff(kDark, 23) == 24);
    assert(pipsToOff(kDark, 0) == 1);
    puts("opening position OK");

  } else if (scenario == "move") {
    Game game;
    start(game);
    // Dice arrive from outside. A value that is not a die face is not a roll.
    assert(!beginTurn(game, 0, 4));
    assert(!beginTurn(game, 7, 4));
    assert(pendingCount(game) == 0);

    assert(beginTurn(game, 3, 5));
    assert(pendingCount(game) == 2);
    // A second roll on top of an unfinished turn is not a thing the game has.
    assert(!beginTurn(game, 2, 2));

    // Light travels UP the indices, so its back checker on 0 lands on 3.
    assert(destination(kLight, 0, 3) == 3);
    assert(canMoveFrom(game, 0, 3));
    assert(play(game, 0, 3));
    assert(checkersAt(game, 0, kLight) == 1);
    assert(checkersAt(game, 3, kLight) == 1);
    assert(onBoard(game, kLight) == kCheckers);  // nothing created, nothing lost
    assert(pendingCount(game) == 1);
    // A turn is both dice, so the turn does not change hands after one move,
    // and it may not be handed over while a playable die is still owed --
    // using as many dice as you legally can is compulsory in backgammon.
    assert(game.turn == kLight);
    assert(!endTurn(game));

    // An illegal move changes NOTHING -- not the board, not the dice. A caller
    // routes a raw tap in here, so the rejected path runs more often than the
    // accepted one and must not leave the position half-applied.
    const Game before = game;
    assert(!play(game, 4, 5));   // no light checker on 4
    assert(!play(game, 0, 2));   // no 2 was rolled
    assert(!play(game, 11, 3));  // the 3 has already been spent
    assert(std::memcmp(&before, &game, sizeof(Game)) == 0);

    assert(play(game, 11, 5));  // 11 -> 16, onto light's own stack of three
    assert(checkersAt(game, 16, kLight) == 4);
    assert(pendingCount(game) == 0);
    assert(endTurn(game));
    assert(game.turn == kDark);

    // Dark travels DOWN the indices. The same roll, the same call shape, the
    // mirrored destination: this is the asymmetry itself, tested rather than
    // assumed, and a core that moved both sides the same way fails right here.
    assert(beginTurn(game, 3, 5));
    assert(destination(kDark, 23, 3) == 20);
    assert(canMoveFrom(game, 23, 3));
    // Stated once more as a pure reflection: one point, one die, two sides,
    // destinations on opposite sides of the source.
    assert(destination(kLight, 12, 5) == 17);
    assert(destination(kDark, 12, 5) == 7);
    assert(play(game, 23, 3));
    assert(checkersAt(game, 23, kDark) == 1);
    assert(checkersAt(game, 20, kDark) == 1);
    assert(play(game, 12, 5));  // 12 -> 7, onto dark's own stack of three
    assert(checkersAt(game, 7, kDark) == 4);
    assert(onBoard(game, kDark) == kCheckers);
    assert(endTurn(game));
    assert(game.turn == kLight);
    puts("a move runs in that side's own direction OK");

  } else if (scenario == "blocking") {
    Game game;
    // Light's lone runner on 8 faces a blot on 10, a made point on 11 and a
    // three-stack on 12. Everything else is there so each side owns exactly
    // fifteen checkers and the position is one play could actually reach.
    layout(game,
           //  0  1  2  3  4  5  6  7  8  9 10 11
           ".  .  .  .  .  .  .  .  L1 .  D1 D2",
           // 12 13 14 15 16 17 18 19 20 21 22 23
           "D3 .  .  .  .  .  L5 .  D4 L4 D5 L5",
           kLight);

    // Two or more enemy checkers closes a point. Exactly one does not -- that
    // is a blot, and a blot is a destination. The threshold IS the rule.
    assert(blockedFor(game, 11, kLight));
    assert(blockedFor(game, 12, kLight));
    assert(!blockedFor(game, 10, kLight));
    assert(!blockedFor(game, 9, kLight));

    assert(!canMoveFrom(game, 8, 3));  // 11, two dark
    assert(!canMoveFrom(game, 8, 4));  // 12, three dark
    assert(canMoveFrom(game, 8, 2));   // 10, a single dark checker
    assert(canMoveFrom(game, 8, 1));   // 9, empty

    // Your own points are never blocked and there is no stack limit, so a
    // five-stack happily becomes a six.
    assert(canMoveFrom(game, 18, 3));
    assert(canMoveFrom(game, 18, 5));
    assert(beginTurn(game, 3, 5));
    const Game before = game;
    assert(!play(game, 8, 3));  // still blocked with the die in hand
    assert(std::memcmp(&before, &game, sizeof(Game)) == 0);
    assert(play(game, 18, 5));
    assert(checkersAt(game, 23, kLight) == 6);

    // The exact reflection of that position, dark to move. Every index is
    // 23 minus its counterpart above, so a direction bug cannot pass both.
    layout(game,
           //  0  1  2  3  4  5  6  7  8  9 10 11
           "D5 L5 D4 L4 .  D5 .  .  .  .  .  L3",
           // 12 13 14 15 16 17 18 19 20 21 22 23
           "L2 L1 .  D1 .  .  .  .  .  .  .  . ",
           kDark);
    assert(onBoard(game, kLight) == kCheckers);
    assert(onBoard(game, kDark) == kCheckers);

    assert(blockedFor(game, 12, kDark));
    assert(blockedFor(game, 11, kDark));
    assert(!blockedFor(game, 13, kDark));
    assert(!blockedFor(game, 14, kDark));

    assert(!canMoveFrom(game, 15, 3));  // 12, two light
    assert(!canMoveFrom(game, 15, 4));  // 11, three light
    assert(canMoveFrom(game, 15, 2));   // 13, a single light checker
    assert(canMoveFrom(game, 15, 1));   // 14, empty
    assert(canMoveFrom(game, 5, 3));    // 2, dark's own four-stack
    assert(canMoveFrom(game, 5, 5));    // 0, dark's own five-stack
    puts("two or more enemy checkers close a point OK");

  } else if (scenario == "hit") {
    Game game;
    // Light's runner on 8, a lone dark checker on 10 two pips ahead of it.
    layout(game,
           //  0  1  2  3  4  5  6  7  8  9 10 11
           ".  .  .  .  .  .  .  .  L1 .  D1 D2",
           // 12 13 14 15 16 17 18 19 20 21 22 23
           "D3 .  .  .  .  .  L5 .  D4 L4 D5 L5",
           kLight);
    assert(beginTurn(game, 2, 6));
    assert(play(game, 8, 2));
    // The blot is gone from the board and sitting on the bar -- not captured
    // and not removed: it re-enters later, and its owner still owns fifteen.
    assert(checkersAt(game, 10, kLight) == 1);
    assert(checkersAt(game, 10, kDark) == 0);
    assert(game.bar[kDark] == 1);
    assert(game.bar[kLight] == 0);
    assert(onBoard(game, kDark) == kCheckers - 1);
    assert(onBoard(game, kDark) + game.bar[kDark] + game.off[kDark] == kCheckers);
    assert(onBoard(game, kLight) + game.bar[kLight] + game.off[kLight] == kCheckers);

    // Moving on to an empty point hits nothing, so the bar must not grow again.
    assert(play(game, 10, 6));
    assert(checkersAt(game, 16, kLight) == 1);
    assert(game.bar[kDark] == 1);

    // The exact reflection: dark's runner on 15, a lone light checker on 13.
    layout(game,
           //  0  1  2  3  4  5  6  7  8  9 10 11
           "D5 L5 D4 L4 .  D5 .  .  .  .  .  L3",
           // 12 13 14 15 16 17 18 19 20 21 22 23
           "L2 L1 .  D1 .  .  .  .  .  .  .  . ",
           kDark);
    assert(beginTurn(game, 2, 1));
    assert(play(game, 15, 2));
    assert(checkersAt(game, 13, kDark) == 1);
    assert(checkersAt(game, 13, kLight) == 0);
    assert(game.bar[kLight] == 1);
    assert(game.bar[kDark] == 0);
    assert(onBoard(game, kLight) == kCheckers - 1);

    // A MADE point is never hit. The 1 is still owed, so this move is refused
    // on the board alone: two light checkers on 12 close it, and neither of
    // them goes anywhere.
    const Game before = game;
    assert(hasPending(game, 1));
    assert(!play(game, 13, 1));
    assert(std::memcmp(&before, &game, sizeof(Game)) == 0);
    assert(checkersAt(game, 12, kLight) == 2);
    assert(game.bar[kLight] == 1);
    puts("landing on a lone enemy checker sends it to the bar OK");

  } else if (scenario == "bar") {
    Game game;
    // Light has one checker on the bar. Dark holds light's 3-point with a made
    // point and has left a blot on light's 5-point.
    layout(game,
           //  0  1  2  3  4  5  6  7  8  9 10 11
           ".  .  D2 .  D1 .  .  .  L1 .  .  . ",
           // 12 13 14 15 16 17 18 19 20 21 22 23
           ".  .  .  .  .  .  L5 .  .  L4 .  L4",
           kLight, /*lightBar=*/1);
    assert(game.bar[kLight] == 1);

    // Entry is the same destination arithmetic as any other move, read through
    // the same direction: light enters on pips - 1, counting up from the edge.
    assert(entryPoint(kLight, 1) == 0);
    assert(entryPoint(kLight, 3) == 2);
    assert(entryPoint(kLight, 6) == 5);
    assert(!canMoveFrom(game, kBar, 3));  // 2 is a made dark point
    assert(canMoveFrom(game, kBar, 5));   // 4 is a dark blot, so entry hits it
    assert(canMoveFrom(game, kBar, 1));   // 0 is empty

    // THE OBLIGATION: nothing else may move while a checker waits on the bar,
    // even a move that would be perfectly legal on its own. 8 -> 9 is empty.
    assert(!canMoveFrom(game, 8, 1));
    assert(!canMoveFrom(game, 18, 1));

    assert(beginTurn(game, 3, 1));
    const Game before = game;
    assert(!play(game, 8, 1));
    assert(std::memcmp(&before, &game, sizeof(Game)) == 0);
    // The 3 cannot come in, so the only move on the board is the 1.
    assert(!play(game, kBar, 3));
    assert(play(game, kBar, 1));
    assert(game.bar[kLight] == 0);
    assert(checkersAt(game, 0, kLight) == 1);
    assert(onBoard(game, kLight) == kCheckers);
    // With the bar clear the rest of the roll is ordinary again.
    assert(canMoveFrom(game, 8, 3));
    assert(play(game, 8, 3));
    assert(checkersAt(game, 11, kLight) == 1);
    assert(endTurn(game));
    assert(game.turn == kDark);

    // Entry HITS like any other arrival: coming in on a blot sends it away.
    layout(game,
           //  0  1  2  3  4  5  6  7  8  9 10 11
           ".  .  D2 .  D1 .  .  .  L1 .  .  . ",
           // 12 13 14 15 16 17 18 19 20 21 22 23
           ".  .  .  .  .  .  L5 .  .  L4 .  L4",
           kLight, /*lightBar=*/1);
    assert(beginTurn(game, 5, 5));
    assert(play(game, kBar, 5));
    assert(checkersAt(game, 4, kLight) == 1);
    assert(game.bar[kDark] == 1);
    assert(game.bar[kLight] == 0);

    // All six entry points closed: the turn is DANCED away. The dice stay
    // visible until the turn is handed over, so the board can still show the
    // player the roll they could not use.
    layout(game,
           //  0  1  2  3  4  5  6  7  8  9 10 11
           "D2 D2 D2 D2 D2 D2 .  .  L4 .  .  . ",
           // 12 13 14 15 16 17 18 19 20 21 22 23
           ".  .  .  .  .  .  L5 .  .  L5 .  . ",
           kLight, /*lightBar=*/1);
    assert(beginTurn(game, 6, 4));
    assert(!hasAnyLegalMove(game));
    assert(pendingCount(game) == 2);
    assert(endTurn(game));
    assert(pendingCount(game) == 0);
    assert(game.turn == kDark);
    assert(game.bar[kLight] == 1);

    // The exact reflection, dark on the bar: dark enters counting DOWN from the
    // far edge, so the same die lands on the mirrored point.
    layout(game,
           //  0  1  2  3  4  5  6  7  8  9 10 11
           "D4 .  D4 .  .  D5 .  .  .  .  .  . ",
           // 12 13 14 15 16 17 18 19 20 21 22 23
           ".  .  .  D1 .  .  .  L1 .  L2 .  . ",
           kDark, /*lightBar=*/0, /*darkBar=*/1);
    assert(entryPoint(kDark, 1) == 23);
    assert(entryPoint(kDark, 3) == 21);
    assert(entryPoint(kDark, 6) == 18);
    assert(entryPoint(kLight, 3) + entryPoint(kDark, 3) == kPoints - 1);
    assert(!canMoveFrom(game, kBar, 3));  // 21 is a made light point
    assert(canMoveFrom(game, kBar, 5));   // 19 is a light blot
    assert(canMoveFrom(game, kBar, 1));   // 23 is empty
    assert(!canMoveFrom(game, 15, 1));    // the obligation, mirrored
    assert(beginTurn(game, 5, 2));
    assert(play(game, kBar, 5));
    assert(checkersAt(game, 19, kDark) == 1);
    assert(game.bar[kDark] == 0);
    assert(game.bar[kLight] == 1);
    puts("a checker on the bar must re-enter before anything else moves OK");

  } else if (scenario == "doubles") {
    Game game;
    start(game);
    // A mixed roll owes two moves.
    assert(beginTurn(game, 3, 5));
    assert(pendingCount(game) == 2);
    assert(play(game, 11, 3));
    assert(play(game, 11, 5));
    assert(endTurn(game));
    assert(game.turn == kDark);

    // A DOUBLE owes FOUR moves of that value, not two. Dark's turn here, so
    // the four moves run down the indices.
    assert(beginTurn(game, 2, 2));
    assert(pendingCount(game) == 4);
    for (int i = 0; i < kMaxPendingDice; ++i) assert(game.die[i] == 2);
    assert(play(game, 23, 2));  // 21
    assert(play(game, 12, 2));  // 10
    assert(play(game, 7, 2));   // 5, dark's own stack
    assert(pendingCount(game) == 1);
    assert(!endTurn(game));     // a fourth 2 is still owed and still playable
    assert(play(game, 5, 2));   // 3
    assert(pendingCount(game) == 0);
    assert(checkersAt(game, 21, kDark) == 1);
    assert(checkersAt(game, 10, kDark) == 1);
    assert(checkersAt(game, 5, kDark) == 5);  // one arrived, one left
    assert(checkersAt(game, 3, kDark) == 1);
    assert(onBoard(game, kDark) == kCheckers);
    // Four moves is the whole roll; a fifth is not owed.
    assert(!play(game, 3, 2));
    assert(endTurn(game));
    assert(game.turn == kLight);

    // Light's mirror of the same double, from the opening.
    start(game);
    assert(beginTurn(game, 2, 2));
    assert(pendingCount(game) == 4);
    assert(play(game, 0, 2));
    assert(play(game, 11, 2));
    assert(play(game, 16, 2));
    assert(play(game, 18, 2));
    assert(checkersAt(game, 2, kLight) == 1);
    assert(checkersAt(game, 13, kLight) == 1);
    assert(checkersAt(game, 18, kLight) == 5);  // one arrived, one left
    assert(checkersAt(game, 20, kLight) == 1);
    assert(onBoard(game, kLight) == kCheckers);
    assert(endTurn(game));

    // A double is not a promise of four moves. Light owns one checker it can
    // shuffle once and a thirteen-stack it may not bear off (two checkers are
    // still outside home), and dark's wall closes everything else, so three of
    // the four 1s are FORFEITED -- and stay on show until the turn is handed
    // over.
    layout(game,
           //  0  1  2  3  4  5  6  7  8  9 10 11
           "D5 .  .  .  .  .  .  .  .  .  .  . ",
           // 12 13 14 15 16 17 18 19 20 21 22 23
           ".  .  .  .  L1 L1 D2 D2 D2 D2 D2 L13",
           kLight);
    assert(onBoard(game, kLight) == kCheckers);
    assert(onBoard(game, kDark) == kCheckers);
    assert(beginTurn(game, 1, 1));
    assert(pendingCount(game) == 4);
    assert(play(game, 16, 1));
    assert(checkersAt(game, 17, kLight) == 2);
    assert(!hasAnyLegalMove(game));
    assert(pendingCount(game) == 3);
    assert(endTurn(game));
    assert(pendingCount(game) == 0);
    assert(game.turn == kDark);
    puts("a double grants four moves of that value OK");

  } else if (scenario == "bearoff") {
    Game game;
    // The home quadrant is the last six points of a side's OWN track, so the
    // two sides' homes are at opposite ends of the board.
    assert(inHome(kLight, 18) && inHome(kLight, 23));
    assert(!inHome(kLight, 17) && !inHome(kLight, 0));
    assert(inHome(kDark, 5) && inHome(kDark, 0));
    assert(!inHome(kDark, 6) && !inHome(kDark, 23));

    // Light with all fifteen accounted for inside 18..23.
    layout(game,
           //  0  1  2  3  4  5  6  7  8  9 10 11
           ".  .  .  .  .  D5 .  .  .  .  .  . ",
           // 12 13 14 15 16 17 18 19 20 21 22 23
           ".  .  .  .  .  .  L2 .  L1 .  .  L3",
           kLight);
    assert(allHome(game, kLight));
    assert(game.off[kLight] == 9);

    // An EXACT die lifts a checker off: four pips from the 4-point.
    assert(pipsToOff(kLight, 20) == 4);
    assert(beginTurn(game, 4, 3));
    assert(canMoveFrom(game, 20, 4));
    assert(play(game, 20, 4));
    assert(checkersAt(game, 20, kLight) == 0);
    assert(game.off[kLight] == 10);
    assert(onBoard(game, kLight) + game.off[kLight] == kCheckers);
    // A die shorter than the distance is an ordinary move inside home, not a
    // bear-off: three pips from the 6-point reaches the 3-point.
    assert(play(game, 18, 3));
    assert(checkersAt(game, 21, kLight) == 1);
    assert(game.off[kLight] == 10);

    // ONE checker outside home and nothing may come off, however exact the
    // die. This is the rule that makes a late hit so expensive.
    layout(game,
           //  0  1  2  3  4  5  6  7  8  9 10 11
           ".  .  .  .  .  D5 .  .  L1 .  .  . ",
           // 12 13 14 15 16 17 18 19 20 21 22 23
           ".  .  .  .  .  .  L2 .  L1 .  .  L3",
           kLight);
    assert(!allHome(game, kLight));
    assert(pipsToOff(kLight, 23) == 1);
    assert(!canMoveFrom(game, 23, 1));
    assert(!canMoveFrom(game, 20, 4));
    assert(beginTurn(game, 4, 1));
    const Game before = game;
    assert(!play(game, 20, 4));
    assert(std::memcmp(&before, &game, sizeof(Game)) == 0);
    // The checker outside home can still walk; only bearing off is barred.
    assert(play(game, 8, 4));
    assert(checkersAt(game, 12, kLight) == 1);

    // A checker on the BAR is not home either, even with the board itself all
    // home: the fifteen must ALL be in the quadrant, not merely the ones you
    // can see on the board.
    layout(game,
           //  0  1  2  3  4  5  6  7  8  9 10 11
           ".  .  .  .  .  D5 .  .  .  .  .  . ",
           // 12 13 14 15 16 17 18 19 20 21 22 23
           ".  .  .  .  .  .  L2 .  L1 .  .  L2",
           kLight, /*lightBar=*/1);
    assert(!allHome(game, kLight));
    assert(!canMoveFrom(game, 23, 1));

    // The exact reflection, dark bearing off at the other end of the board.
    layout(game,
           //  0  1  2  3  4  5  6  7  8  9 10 11
           "D3 .  .  D1 .  D2 .  .  .  .  .  . ",
           // 12 13 14 15 16 17 18 19 20 21 22 23
           ".  .  .  .  .  .  L5 .  .  .  .  . ",
           kDark);
    assert(allHome(game, kDark));
    assert(game.off[kDark] == 9);
    assert(pipsToOff(kDark, 3) == 4);
    assert(beginTurn(game, 4, 3));
    assert(canMoveFrom(game, 3, 4));
    assert(play(game, 3, 4));
    assert(checkersAt(game, 3, kDark) == 0);
    assert(game.off[kDark] == 10);
    assert(onBoard(game, kDark) + game.off[kDark] == kCheckers);
    assert(play(game, 5, 3));  // 5 -> 2, an ordinary move inside dark's home
    assert(checkersAt(game, 2, kDark) == 1);
    assert(game.off[kDark] == 10);
    puts("bearing off needs all fifteen home OK");

  } else if (scenario == "overshoot") {
    Game game;
    // Light all home on its 6-, 4- and 2-points. Four pips, not five, take the
    // 4-point checker off exactly.
    layout(game,
           //  0  1  2  3  4  5  6  7  8  9 10 11
           ".  .  .  .  .  D5 .  .  .  .  .  . ",
           // 12 13 14 15 16 17 18 19 20 21 22 23
           ".  .  .  .  .  .  L1 .  L1 .  L1 . ",
           kLight);
    assert(allHome(game, kLight));
    assert(game.off[kLight] == 12);
    assert(pipsToOff(kLight, 18) == 6);
    assert(pipsToOff(kLight, 20) == 4);
    assert(pipsToOff(kLight, 22) == 2);

    // FORBIDDEN: a 5 overshoots the 4-point, and the 6-point checker is
    // further from home, so the 5 belongs to that one instead.
    assert(anyFurtherFromHome(game, kLight, 20));
    assert(!canMoveFrom(game, 20, 5));
    assert(!canMoveFrom(game, 22, 5));
    assert(!canMoveFrom(game, 22, 6));
    // The exact dice are unaffected by any of this.
    assert(canMoveFrom(game, 18, 6));
    assert(canMoveFrom(game, 20, 4));
    assert(canMoveFrom(game, 22, 2));

    assert(beginTurn(game, 6, 5));
    const Game before = game;
    assert(!play(game, 20, 5));
    assert(std::memcmp(&before, &game, sizeof(Game)) == 0);
    assert(play(game, 18, 6));
    assert(game.off[kLight] == 13);

    // ALLOWED: the same 5 from the same point, legal now only because nothing
    // of light's sits further from home any more. One position, both answers.
    assert(!anyFurtherFromHome(game, kLight, 20));
    assert(canMoveFrom(game, 20, 5));
    assert(play(game, 20, 5));
    assert(game.off[kLight] == 14);
    assert(onBoard(game, kLight) == 1);
    assert(checkersAt(game, 22, kLight) == 1);

    // The exact reflection, dark on its own 6-, 4- and 2-points.
    layout(game,
           //  0  1  2  3  4  5  6  7  8  9 10 11
           ".  D1 .  D1 .  D1 .  .  .  .  .  . ",
           // 12 13 14 15 16 17 18 19 20 21 22 23
           ".  .  .  .  .  .  L5 .  .  .  .  . ",
           kDark);
    assert(allHome(game, kDark));
    assert(pipsToOff(kDark, 5) == 6);
    assert(pipsToOff(kDark, 3) == 4);
    assert(pipsToOff(kDark, 1) == 2);

    assert(anyFurtherFromHome(game, kDark, 3));
    assert(!canMoveFrom(game, 3, 5));
    assert(!canMoveFrom(game, 1, 5));
    assert(canMoveFrom(game, 5, 6));
    assert(canMoveFrom(game, 3, 4));

    assert(beginTurn(game, 6, 5));
    assert(!play(game, 3, 5));
    assert(play(game, 5, 6));
    assert(game.off[kDark] == 13);
    assert(!anyFurtherFromHome(game, kDark, 3));
    assert(canMoveFrom(game, 3, 5));
    assert(play(game, 3, 5));
    assert(game.off[kDark] == 14);
    assert(onBoard(game, kDark) == 1);
    puts("an oversized die bears off only from the rearmost checker OK");

  } else if (scenario == "win") {
    Game game;
    // Light's last checker sits on its 1-point; fourteen are already off.
    layout(game,
           //  0  1  2  3  4  5  6  7  8  9 10 11
           "D2 .  .  .  .  .  .  .  .  .  .  . ",
           // 12 13 14 15 16 17 18 19 20 21 22 23
           ".  .  .  .  .  .  .  .  .  .  .  L1",
           kLight);
    assert(game.off[kLight] == kCheckers - 1);
    assert(!over(game));
    assert(beginTurn(game, 1, 2));
    assert(play(game, 23, 1));
    assert(game.off[kLight] == kCheckers);
    assert(onBoard(game, kLight) == 0);
    assert(over(game));
    assert(game.outcome == Outcome::LightWins);

    // A finished game accepts nothing more, and the 2 still owed does not let
    // play continue past the win. The result is final even though the roll is
    // not spent.
    const Game finished = game;
    assert(pendingCount(game) == 1);
    assert(!play(game, 0, 2));
    assert(!canMoveFrom(game, 0, 2));
    assert(!endTurn(game));
    assert(!beginTurn(game, 3, 3));
    assert(std::memcmp(&finished, &game, sizeof(Game)) == 0);

    // The reflection: dark's last checker on dark's own 1-point.
    layout(game,
           //  0  1  2  3  4  5  6  7  8  9 10 11
           "D1 .  .  .  .  .  .  .  .  .  .  . ",
           // 12 13 14 15 16 17 18 19 20 21 22 23
           ".  .  .  .  .  .  .  .  .  .  .  L2",
           kDark);
    assert(game.off[kDark] == kCheckers - 1);
    assert(beginTurn(game, 1, 2));
    assert(play(game, 0, 1));
    assert(game.off[kDark] == kCheckers);
    assert(over(game));
    assert(game.outcome == Outcome::DarkWins);

    // Fourteen off is not a win. Bearing off the fifteenth is the only thing
    // that ends a game, so a position one checker short must still be running.
    layout(game,
           //  0  1  2  3  4  5  6  7  8  9 10 11
           "D1 .  .  .  .  .  .  .  .  .  .  . ",
           // 12 13 14 15 16 17 18 19 20 21 22 23
           ".  .  .  .  .  .  .  .  .  .  .  L1",
           kDark);
    assert(game.off[kLight] == kCheckers - 1);
    assert(game.off[kDark] == kCheckers - 1);
    assert(!over(game));
    assert(game.outcome == Outcome::Running);
    puts("bearing off all fifteen wins OK");

  } else if (scenario == "listing") {
    Game game;
    int8_t sources[kMaxLegalMoves];
    start(game);

    // From the opening a 1 can be played by three of light's four stacks: the
    // 13-point is shut out because dark's five checkers sit one pip ahead.
    assert(legalMoves(game, 1, sources) == 3);
    assert(sources[0] == 0 && sources[1] == 16 && sources[2] == 18);
    // A 6 is the opposite case: the 13-point frees up, and the stack on light's
    // own 6-point has nowhere to go because bearing off needs all fifteen home.
    assert(legalMoves(game, 6, sources) == 3);
    assert(sources[0] == 0 && sources[1] == 11 && sources[2] == 16);
    // A 2 leaves every stack a move.
    assert(legalMoves(game, 2, sources) == 4);
    assert(sources[0] == 0 && sources[1] == 11 && sources[2] == 16 && sources[3] == 18);
    // Values that are not die faces list nothing rather than guessing.
    assert(legalMoves(game, 0, sources) == 0);
    assert(legalMoves(game, 7, sources) == 0);
    // "Can this die be played at all" only needs the count, so the output
    // array is optional.
    assert(legalMoves(game, 1, nullptr) == 3);

    // Dark's mirror of the same roll on the same board, reported in BOARD
    // order rather than dark's own order, because board indices are what the
    // renderer draws.
    start(game);
    game.turn = kDark;
    assert(legalMoves(game, 1, sources) == 3);
    assert(sources[0] == 5 && sources[1] == 7 && sources[2] == 23);
    assert(legalMoves(game, 6, sources) == 3);
    assert(sources[0] == 7 && sources[1] == 12 && sources[2] == 23);

    // On the bar the list collapses to the single legal source, kBar, and to
    // nothing at all when entry is shut.
    layout(game,
           //  0  1  2  3  4  5  6  7  8  9 10 11
           ".  .  D2 .  D1 .  .  .  L1 .  .  . ",
           // 12 13 14 15 16 17 18 19 20 21 22 23
           ".  .  .  .  .  .  L5 .  .  L4 .  L4",
           kLight, /*lightBar=*/1);
    assert(legalMoves(game, 3, sources) == 0);
    assert(legalMoves(game, 1, sources) == 1);
    assert(sources[0] == kBar);
    assert(legalMoves(game, 5, sources) == 1);
    assert(sources[0] == kBar);

    // Bearing off appears in the list exactly where it is legal: a 5 or a 6 is
    // only playable by the rearmost checker, while a 2 gives two ordinary
    // moves and one bear-off.
    layout(game,
           //  0  1  2  3  4  5  6  7  8  9 10 11
           ".  .  .  .  .  D5 .  .  .  .  .  . ",
           // 12 13 14 15 16 17 18 19 20 21 22 23
           ".  .  .  .  .  .  L1 .  L1 .  L1 . ",
           kLight);
    assert(legalMoves(game, 5, sources) == 1);
    assert(sources[0] == 18);
    assert(legalMoves(game, 6, sources) == 1);
    assert(sources[0] == 18);
    assert(legalMoves(game, 2, sources) == 3);
    assert(sources[0] == 18 && sources[1] == 20 && sources[2] == 22);

    // The listing is enough on its own to drive a whole turn, which is what the
    // UI actually does with it: highlight, tap, repeat until the roll is spent.
    start(game);
    assert(beginTurn(game, 2, 2));
    while (hasAnyLegalMove(game)) {
      const int count = legalMoves(game, 2, sources);
      assert(count > 0 && count <= kMaxLegalMoves);
      assert(play(game, sources[0], 2));
    }
    assert(pendingCount(game) == 0);
    assert(onBoard(game, kLight) == kCheckers);
    assert(endTurn(game));
    assert(game.turn == kDark);
    puts("the legal moves for a die value are listable OK");

  } else if (scenario == "dice") {
    // The roll helper is driven entirely by a seed the caller owns. Same seed,
    // same dice, for ever -- which is what lets the tests above state exact
    // positions and what would let a finished game be replayed from storage.
    constexpr int kRolls = 40;
    int firstA[kRolls];
    int firstB[kRolls];
    uint32_t state = 12345u;
    for (int i = 0; i < kRolls; ++i) {
      rollDice(state, firstA[i], firstB[i]);
      // Die faces, not raw generator output.
      assert(firstA[i] >= 1 && firstA[i] <= kFaces);
      assert(firstB[i] >= 1 && firstB[i] <= kFaces);
      // Whatever comes out must be acceptable to the rules, including doubles.
      Game game;
      start(game);
      assert(beginTurn(game, firstA[i], firstB[i]));
      assert(pendingCount(game) == (firstA[i] == firstB[i] ? kMaxPendingDice : 2));
    }

    uint32_t replay = 12345u;
    for (int i = 0; i < kRolls; ++i) {
      int a = 0;
      int b = 0;
      rollDice(replay, a, b);
      assert(a == firstA[i] && b == firstB[i]);
    }

    // A different seed must actually give a different game, or "seeded" would
    // be a decoration.
    uint32_t other = 999u;
    bool differs = false;
    for (int i = 0; i < kRolls; ++i) {
      int a = 0;
      int b = 0;
      rollDice(other, a, b);
      if (a != firstA[i] || b != firstB[i]) differs = true;
    }
    assert(differs);

    // Every face has to be reachable. A modulo written against the wrong bound
    // produces dice that are still in range and still deterministic but can
    // never show a six, and nothing else here would notice.
    int seen[kFaces + 1] = {0};
    uint32_t wide = 7u;
    for (int i = 0; i < 600; ++i) {
      int a = 0;
      int b = 0;
      rollDice(wide, a, b);
      ++seen[a];
      ++seen[b];
    }
    for (int face = 1; face <= kFaces; ++face) assert(seen[face] > 0);

    // A zero seed is the multiplicative generator's fixed point, so it must be
    // handled rather than silently returning the same roll for ever.
    uint32_t zero = 0u;
    int zeroA = 0;
    int zeroB = 0;
    rollDice(zero, zeroA, zeroB);
    int nextA = 0;
    int nextB = 0;
    rollDice(zero, nextA, nextB);
    assert(zero != 0u);
    assert(zeroA != nextA || zeroB != nextB);
    puts("dice come from an explicit seed OK");

  // @@SCENARIOS@@
  } else {
    std::fprintf(stderr, "unknown scenario %s\n", scenario.c_str());
    return 1;
  }
  return 0;
}
'''


class BackgammonCoreTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        harness = pathlib.Path(cls.tmp.name) / "backgammon_core_test.cpp"
        harness.write_text(HARNESS)
        cls.exe = pathlib.Path(cls.tmp.name) / "backgammon_core_test"
        subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                        "-I", str(GAME_DIR), str(harness),
                        "-o", str(cls.exe)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_opening_position_is_the_standard_mirror_with_opposite_directions(self):
        subprocess.run([str(self.exe), "opening"], check=True)

    def test_a_move_runs_the_pips_in_that_sides_own_direction(self):
        subprocess.run([str(self.exe), "move"], check=True)

    def test_a_point_with_two_or_more_enemy_checkers_is_blocked_for_both_sides(self):
        subprocess.run([str(self.exe), "blocking"], check=True)

    def test_landing_on_a_single_enemy_checker_hits_it_to_the_bar_for_both_sides(self):
        subprocess.run([str(self.exe), "hit"], check=True)

    def test_a_checker_on_the_bar_must_re_enter_before_anything_else_moves(self):
        subprocess.run([str(self.exe), "bar"], check=True)

    def test_a_double_grants_four_moves_of_that_value_and_a_mixed_roll_two(self):
        subprocess.run([str(self.exe), "doubles"], check=True)

    def test_bearing_off_is_only_allowed_once_all_fifteen_are_home_for_both_sides(self):
        subprocess.run([str(self.exe), "bearoff"], check=True)

    def test_an_oversized_die_bears_off_only_when_no_checker_is_further_back(self):
        subprocess.run([str(self.exe), "overshoot"], check=True)

    def test_a_side_wins_by_bearing_off_all_fifteen_checkers(self):
        subprocess.run([str(self.exe), "win"], check=True)

    def test_legal_moves_for_a_die_value_are_listed_as_sources_for_the_ui(self):
        subprocess.run([str(self.exe), "listing"], check=True)

    def test_the_roll_helper_is_seeded_and_replays_identically(self):
        subprocess.run([str(self.exe), "dice"], check=True)

    # @@METHODS@@

if __name__ == "__main__":
    unittest.main()
