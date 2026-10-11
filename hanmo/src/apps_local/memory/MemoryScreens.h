#pragma once

#include "../ui/ToyboxScreen.h"
#include "MemoryCore.h"

namespace memoryui {

namespace fui = freeink::ui;

enum : fui::ActionId {
  ActionLevel = 1,
  ActionNext = 2,
  ActionMenu = 3,
  ActionAgain = 4,
};

struct MenuModel {
  int selected = 0;
};

struct BoardModel {
  const memorymatch::Game* game = nullptr;
  int cursor = -1;
};

// Card geometry and its inverse are deliberately shared by drawing and input.
fui::Rect cardRect(const fui::DeviceContext& device, const memorymatch::Game& game, int index);
int cardAt(const fui::DeviceContext& device, const memorymatch::Game& game, int x, int y);

void buildMenu(toybox::Screen& screen, const MenuModel& model);
void buildBoard(toybox::Screen& screen, const BoardModel& model);

}  // namespace memoryui
