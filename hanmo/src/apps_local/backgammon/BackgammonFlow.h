#pragma once

#include "BackgammonCore.h"

namespace backgammonui {
// UI bookkeeping only. The rules and all checker/dice writes stay in the core.
enum class Mode : uint8_t { Menu, Board, Done };
constexpr int kNoPoint = -2;
constexpr int kOff = -3;
struct Flow {
  Mode screen = Mode::Menu;
  backgammon::Game game{};
  uint32_t rng = 1u;
  bool rolled = false;
  bool opening = true;
  uint8_t openingLight = 0, openingDark = 0;
  int dieSlot = -1;
  int from = kNoPoint;
  void start(uint32_t seed) {
    backgammon::start(game);
    rng = seed;
    rolled = false;
    opening = true;
    openingLight = openingDark = 0;
    dieSlot = -1;
    from = kNoPoint;
    screen = Mode::Board;
  }
  bool canRoll() const { return screen == Mode::Board && !backgammon::over(game) && !rolled; }
  bool roll() {
    if (!canRoll()) return false;
    int a = 0, b = 0;
    backgammon::rollDice(rng, a, b);
    if (opening) {
      openingLight = static_cast<uint8_t>(a);
      openingDark = static_cast<uint8_t>(b);
      // One visible contest per tap: a tie stays unrolled, never a double.
      if (a == b) return true;
      if (!backgammon::beginOpeningTurn(game, a, b)) return false;
      opening = false;
    } else if (!backgammon::beginTurn(game, a, b)) return false;
    rolled = true;
    return true;
  }
  int pips() const {
    return dieSlot >= 0 && dieSlot < backgammon::kMaxPendingDice ? game.die[dieSlot] : 0;
  }
  bool live() const { return screen == Mode::Board && rolled && !backgammon::over(game); }
  bool legalSource(int at) const { return live() && pips() != 0 && backgammon::canPlayFrom(game, at, pips()); }
  int target() const {
    if (from == kNoPoint || !legalSource(from)) return kNoPoint;
    const int to = backgammon::destination(game.turn, from, pips());
    return backgammon::inside(to) ? to : kOff;
  }
  bool canChooseDie(int slot) const {
    return live() && slot >= 0 && slot < backgammon::kMaxPendingDice && game.die[slot] != 0 &&
           backgammon::turnLegalMoves(game, game.die[slot], nullptr) != 0;
  }
  bool chooseDie(int slot) {
    if (!canChooseDie(slot)) return false;
    dieSlot = slot;
    from = kNoPoint;
    return true;
  }
  bool pick(int at) {
    if (!live()) return false;
    if (from != kNoPoint && at == target()) {
      if (!backgammon::play(game, from, pips())) return false;
      from = kNoPoint;
      if (pips() == 0) dieSlot = -1;
      if (backgammon::over(game)) screen = Mode::Done;
      return true;
    }
    if (!legalSource(at)) return false;
    from = at;
    return true;
  }
  bool canEnd() const { return live() && !backgammon::hasAnyLegalMove(game); }
  bool end() {
    if (!canEnd() || !backgammon::endTurn(game)) return false;
    openingLight = openingDark = 0;
    rolled = false;
    dieSlot = -1;
    from = kNoPoint;
    return true;
  }
  bool menu() {
    if (screen == Mode::Menu) return false;
    screen = Mode::Menu;
    from = kNoPoint;
    dieSlot = -1;
    return true;
  }
};
}  // namespace backgammonui
