#pragma once

#include "MahjongCore.h"

namespace mahjongui {

enum class Screen : uint8_t { Menu, Board, Done, Stuck };

// Session-only state. No heap, timers, saves or second copy of the rules.
struct Flow {
  mahjong::Game game{};
  Screen screen = Screen::Menu;
  int selected = mahjong::kNoSlot;

  void classify() {
    screen = mahjong::won(game) ? Screen::Done : mahjong::deadEnd(game) ? Screen::Stuck : Screen::Board;
  }

  void start(const uint32_t seed) {
    mahjong::deal(game, seed);
    selected = mahjong::kNoSlot;
    classify();
  }

  // False is a rejected pick: neither tile bytes nor selection change.
  bool pick(const int slot) {
    if (screen != Screen::Board || !mahjong::freeSlot(game, slot)) return false;
    if (selected == slot) {
      selected = mahjong::kNoSlot;
      return true;
    }
    if (selected == mahjong::kNoSlot) {
      selected = slot;
      return true;
    }
    if (!mahjong::removePair(game, selected, slot)) return false;
    selected = mahjong::kNoSlot;
    classify();
    return true;
  }

  bool cancel() {
    if (selected == mahjong::kNoSlot) return false;
    selected = mahjong::kNoSlot;
    return true;
  }

  void menu() {
    screen = Screen::Menu;
    selected = mahjong::kNoSlot;
  }
};

}  // namespace mahjongui
