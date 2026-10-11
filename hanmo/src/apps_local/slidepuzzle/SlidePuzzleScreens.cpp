#include "SlidePuzzleScreens.h"

#include <algorithm>
#include <cstdio>

namespace slidepuzzleui {
namespace {
constexpr int16_t kGap = 6;
constexpr int16_t kStatusHeight = 28;
constexpr int16_t kActionHeight = 52;

void chrome(toybox::Screen& screen) {
  fui::HeaderProps header;
  header.title = "SLIDE PUZZLE";
  header.borderEdges = fui::EdgesNone;
  toybox::headerBand(screen, header);
}

void label(toybox::Screen& screen, const fui::Rect box, const char* text, const bool small = true,
           const fui::Color color = fui::Color::Black) {
  fui::TextStyle style;
  style.font = small ? toybox::kSmallFont : toybox::kUiFont;
  style.align = fui::TextAlign::Center;
  style.color = color;
  screen.target().text(toybox::inkCentred(box, small ? toybox::kTileCut : toybox::kUiCut), text, style);
}

fui::Rect bodyRect(const fui::DeviceContext& device) {
  const fui::Rect safe = device.safeRect();
  const int top = std::max<int>(toybox::kBodyTop, safe.y + toybox::kMargin);
  return fui::makeRect(static_cast<int16_t>(safe.x + toybox::kMargin), static_cast<int16_t>(top),
                       static_cast<int16_t>(std::max<int>(0, safe.width - toybox::kMargin * 2)),
                       static_cast<int16_t>(std::max<int>(0, safe.bottom() - toybox::kMargin - top)));
}

fui::Rect footerRect(const fui::DeviceContext& device) {
  const fui::Rect body = bodyRect(device);
  return fui::makeRect(body.x, static_cast<int16_t>(body.bottom() - kActionHeight), body.width, kActionHeight);
}
}  // namespace

fui::Rect cellRect(const fui::DeviceContext& device, const slidepuzzle::Game& game, const int index) {
  if (game.width < slidepuzzle::kMinWidth || game.width > slidepuzzle::kMaxWidth ||
      index < 0 || index >= slidepuzzle::cellCount(game)) return {};
  const fui::Rect body = bodyRect(device);
  const int top = body.y + kStatusHeight + kGap + 24 + toybox::kGutter;
  const int bottom = footerRect(device).y - kGap;
  const int side = (std::min<int>(body.width, bottom - top) - (game.width - 1) * kGap) / game.width;
  if (side <= 0) return {};
  const int extent = side * game.width + (game.width - 1) * kGap;
  return fui::makeRect(static_cast<int16_t>(body.x + (body.width - extent) / 2 +
                                           (index % game.width) * (side + kGap)),
                       static_cast<int16_t>(top + (bottom - top - extent) / 2 +
                                            (index / game.width) * (side + kGap)),
                       static_cast<int16_t>(side), static_cast<int16_t>(side));
}

int cellAt(const fui::DeviceContext& device, const slidepuzzle::Game& game, const int x, const int y) {
  for (int index = 0; index < slidepuzzle::cellCount(game); ++index) {
    const fui::Rect cell = cellRect(device, game, index);
    if (!cell.empty() && x >= cell.x && x < cell.right() && y >= cell.y && y < cell.bottom()) return index;
  }
  return -1;
}

void buildMenu(toybox::Screen& screen, const MenuModel& model) {
  chrome(screen);
  const fui::Rect body = bodyRect(screen.device());
  const int selected = slidepuzzle::supportedWidth(model.selectedWidth);
  char selectedLabel[32];
  std::snprintf(selectedLabel, sizeof(selectedLabel), "SELECTED: %d X %d", selected, selected);
  label(screen, fui::makeRect(body.x, body.y, body.width, kStatusHeight), selectedLabel);
  const int count = slidepuzzle::kMaxWidth - slidepuzzle::kMinWidth + 1;
  const int top = body.y + kStatusHeight + toybox::kGutter;
  const int height = std::min<int>(112, (body.bottom() - top - kGap * (count - 1)) / count);
  for (int width = slidepuzzle::kMinWidth; width <= slidepuzzle::kMaxWidth; ++width) {
    const fui::Rect row = fui::makeRect(body.x,
        static_cast<int16_t>(top + (width - slidepuzzle::kMinWidth) * (height + kGap)),
        body.width, static_cast<int16_t>(height));
    fui::ButtonProps button;
    button.action = ActionSize;
    button.value = static_cast<int16_t>(width);
    button.state = width == selected ? fui::StateSelected : fui::StateNormal;
    button.styles = toybox::rowStyles();
    screen.button(button, row);
    char size[16];
    std::snprintf(size, sizeof(size), "%d X %d", width, width);
    label(screen, row, size, false, width == selected ? fui::Color::White : fui::Color::Black);
  }
}

void buildBoard(toybox::Screen& screen, const BoardModel& model) {
  if (model.game == nullptr) return;
  chrome(screen);
  const slidepuzzle::Game& game = *model.game;
  const fui::Rect body = bodyRect(screen.device());
  char status[64];
  std::snprintf(status, sizeof(status), "%d X %d   %u MOVES", game.width, game.width,
                static_cast<unsigned>(game.moves));
  label(screen, fui::makeRect(body.x, body.y, body.width, kStatusHeight), status);
  label(screen, fui::makeRect(body.x, static_cast<int16_t>(body.y + kStatusHeight + kGap), body.width, 24),
        model.done ? "DONE - PUZZLE SOLVED" : "TAP A TILE NEXT TO THE BLANK");
  for (int index = 0; index < slidepuzzle::cellCount(game); ++index) {
    const fui::Rect cell = cellRect(screen.device(), game, index);
    screen.target().fill(cell, fui::Paint::solid(fui::Color::White));
    screen.target().stroke(cell, fui::Paint::solid(fui::Color::Black), 1);
    if (game.tile[index] != slidepuzzle::kEmpty) {
      char number[8];
      std::snprintf(number, sizeof(number), "%u", static_cast<unsigned>(game.tile[index]));
      label(screen, cell, number, false);
    }
  }
  fui::ButtonProps menu;
  menu.label = "MENU";
  menu.action = ActionMenu;
  const fui::Rect footer = footerRect(screen.device());
  if (!model.done) {
    screen.button(menu, footer);
  } else {
    const int16_t width = static_cast<int16_t>((footer.width - kGap) / 2);
    screen.button(menu, fui::makeRect(footer.x, footer.y, width, footer.height));
    fui::ButtonProps again;
    again.label = "AGAIN";
    again.action = ActionAgain;
    screen.button(again, fui::makeRect(static_cast<int16_t>(footer.x + width + kGap), footer.y,
                                      static_cast<int16_t>(footer.width - width - kGap), footer.height));
  }
}

}  // namespace slidepuzzleui
