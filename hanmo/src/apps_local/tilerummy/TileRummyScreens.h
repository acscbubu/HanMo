#pragma once
#include <cstddef>

#include "../ui/ToyboxScreen.h"
#include "TileRummyFlow.h"

namespace tilerummyui {
namespace fui = freeink::ui;
enum : fui::ActionId {
  ActionStart = 100,
  ActionPlayers,
  ActionHand,
  ActionMeld,
  ActionJokers,
  ActionMenu,
  ActionAgain,
  ActionReady,
  ActionView,
  ActionSet,
  ActionNewGroup,
  ActionNewRun,
  ActionAdd,
  ActionRemove,
  ActionReturn,
  ActionMove,
  ActionUndo,
  ActionCancel,
  ActionPlay,
  ActionDraw,
  ActionPage
};
struct MenuModel {
  const Flow* flow = nullptr;
};
struct BoardModel {
  const Flow* flow = nullptr;
};
void tileText(tr::Tile tile, char* out, size_t capacity);
fui::Rect tileRect(const fui::DeviceContext& device, const Flow& flow, int index);
int tileAt(const fui::DeviceContext& device, const Flow& flow, int x, int y);
void buildMenu(toybox::Screen& screen, const MenuModel& model);
void buildBoard(toybox::Screen& screen, const BoardModel& model);
}  // namespace tilerummyui
