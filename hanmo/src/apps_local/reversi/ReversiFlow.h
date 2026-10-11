#pragma once

#include <cstdint>

namespace reversi {

enum class Screen : uint8_t { Menu, Board, Done };

constexpr Screen back(const Screen) { return Screen::Menu; }
constexpr bool leavesApp(const Screen screen) { return screen == Screen::Menu; }

}  // namespace reversi
