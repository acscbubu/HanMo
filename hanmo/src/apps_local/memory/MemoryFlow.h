#pragma once

// Memory Match navigation. The rules remain in MemoryCore; this small flow
// keeps Back and the activity's screen transitions total and host-testable.

#include <cstdint>

#include "MemoryCore.h"

namespace memorymatch {

enum class Screen : uint8_t {
  Menu,
  Board,
  Done,
};

constexpr Screen back(const Screen screen) {
  switch (screen) {
    case Screen::Menu:
      return Screen::Menu;
    case Screen::Board:
      return Screen::Menu;
    case Screen::Done:
      return Screen::Menu;
  }
  return Screen::Menu;
}

constexpr bool leavesApp(const Screen screen) { return screen == Screen::Menu; }
constexpr bool acceptsCard(const Screen screen) { return screen == Screen::Board; }
inline Screen screenFor(const Game& game) { return complete(game) ? Screen::Done : Screen::Board; }

}  // namespace memorymatch
