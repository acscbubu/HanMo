#pragma once

#include "../ui/ToyboxScreen.h"
#include "SlidePuzzleCore.h"

namespace slidepuzzleui {
namespace fui = freeink::ui;

enum : fui::ActionId { ActionSize = 1, ActionMenu = 2, ActionAgain = 3 };

struct MenuModel {
  int selectedWidth = slidepuzzle::kMinWidth;
};

struct BoardModel {
  const slidepuzzle::Game* game = nullptr;
  bool done = false;
};

// One geometry definition serves both rendering and mapped logical taps.
fui::Rect cellRect(const fui::DeviceContext& device, const slidepuzzle::Game& game, int index);
int cellAt(const fui::DeviceContext& device, const slidepuzzle::Game& game, int x, int y);

void buildMenu(toybox::Screen& screen, const MenuModel& model);
void buildBoard(toybox::Screen& screen, const BoardModel& model);

}  // namespace slidepuzzleui
