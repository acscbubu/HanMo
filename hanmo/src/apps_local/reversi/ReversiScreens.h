#pragma once

#include "../ui/ToyboxScreen.h"
#include "ReversiCore.h"

namespace reversiui {

namespace fui = freeink::ui;
enum : fui::ActionId { ActionStart = 1, ActionMenu = 2, ActionAgain = 3 };

struct BoardModel {
  const reversi::Game* game = nullptr;
  uint8_t passedSide = reversi::kEmpty;
  int cursor = reversi::kNoCell;
};

// Row-major cell index: the core remains cell[column][row]. A 64-cell board
// uses shared draw/hit geometry, not one entry per cell in the 24-slot table.
fui::Rect cardRect(const fui::DeviceContext& device, int index);
int cellAt(const fui::DeviceContext& device, int x, int y);
void buildMenu(toybox::Screen& screen);
void buildBoard(toybox::Screen& screen, const BoardModel& model);

}  // namespace reversiui
