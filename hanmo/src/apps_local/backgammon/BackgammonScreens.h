#pragma once

#include "../ui/ToyboxScreen.h"
#include "BackgammonFlow.h"

namespace backgammonui {
namespace fui = freeink::ui;
enum : fui::ActionId {
  ActionStart = 1, ActionRoll, ActionDie, ActionBar, ActionOff, ActionEnd, ActionAgain, ActionMenu
};
struct BoardModel { const Flow* flow = nullptr; };
fui::Rect pointRect(const fui::DeviceContext& device, int point);
int pointAt(const fui::DeviceContext& device, int x, int y);
void buildMenu(toybox::Screen& screen);
void buildBoard(toybox::Screen& screen, const BoardModel& model);
}  // namespace backgammonui
