#pragma once

#include "../ui/ToyboxScreen.h"
#include "MahjongFlow.h"

namespace mahjongui {
namespace fui = freeink::ui;

enum : fui::ActionId { ActionStart = 1, ActionNew, ActionMenu };
struct BoardModel {
  const mahjong::Game* game = nullptr;
  int selected = mahjong::kNoSlot;
};

fui::Rect tileRect(const fui::DeviceContext& device, int slot);
bool visibleSlot(const mahjong::Game& game, int slot);
int tileAt(const fui::DeviceContext& device, const mahjong::Game& game, int x, int y);
void tileMarker(uint8_t tile, char out[4]);
void buildMenu(toybox::Screen& screen);
void buildBoard(toybox::Screen& screen, const BoardModel& model);

}  // namespace mahjongui
