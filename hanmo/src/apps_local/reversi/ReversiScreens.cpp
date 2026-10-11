#include "ReversiScreens.h"

#include <algorithm>
#include <cstdio>

namespace reversiui {
namespace {

constexpr int kCellGap = 6;
constexpr int kStatusLine = 28;
constexpr int kStatusHeight = kStatusLine * 3;
constexpr int kActionHeight = toybox::kPillHeight;
constexpr int kHintsHeight = 36;

void chrome(toybox::Screen& screen) {
  fui::HeaderProps header;
  header.title = "REVERSI";
  header.borderEdges = fui::EdgesNone;
  toybox::headerBand(screen, header);
}

void label(toybox::Screen& screen, const fui::Rect box, const char* text, const bool small = true) {
  fui::TextStyle style;
  style.font = small ? toybox::kSmallFont : toybox::kUiFont;
  style.align = fui::TextAlign::Center;
  screen.target().text(toybox::inkCentred(box, small ? toybox::kTileCut : toybox::kUiCut), text, style);
}

fui::Rect actionRect(const fui::DeviceContext& device) {
  const auto safe = device.safeRect();
  return fui::makeRect(static_cast<int16_t>(safe.x + toybox::kMargin),
                       static_cast<int16_t>(safe.bottom() - toybox::kMargin - kHintsHeight - kActionHeight),
                       static_cast<int16_t>(safe.width - toybox::kMargin * 2), kActionHeight);
}

fui::Rect gridRegion(const fui::DeviceContext& device) {
  const auto safe = device.safeRect();
  const int top = std::max(toybox::kBodyTop, static_cast<int>(safe.y));
  const bool landscape = device.width > device.height;
  const int width = landscape ? (safe.width - toybox::kMargin * 3) / 2 : safe.width - toybox::kMargin * 2;
  const int y = top + (landscape ? 0 : kStatusHeight + toybox::kGutter);
  return fui::makeRect(static_cast<int16_t>(safe.x + toybox::kMargin), static_cast<int16_t>(y),
                       static_cast<int16_t>(width), static_cast<int16_t>(actionRect(device).y - toybox::kGutter - y));
}

fui::Rect statusRect(const fui::DeviceContext& device, const int line) {
  const auto safe = device.safeRect();
  const auto grid = gridRegion(device);
  const bool landscape = device.width > device.height;
  const int x = landscape ? grid.right() + toybox::kGutter : safe.x + toybox::kMargin;
  const int y = std::max(toybox::kBodyTop, static_cast<int>(safe.y)) + line * kStatusLine;
  return fui::makeRect(static_cast<int16_t>(x), static_cast<int16_t>(y),
                       static_cast<int16_t>(safe.right() - toybox::kMargin - x), kStatusLine);
}

}  // namespace

fui::Rect cardRect(const fui::DeviceContext& device, const int index) {
  if (index < 0 || index >= reversi::kCells) return {};
  const auto region = gridRegion(device);
  const int side = (std::min(region.width, region.height) - (reversi::kSize - 1) * kCellGap) / reversi::kSize;
  if (side <= 0) return {};
  const int span = reversi::kSize * side + (reversi::kSize - 1) * kCellGap;
  return fui::makeRect(static_cast<int16_t>(region.x + (region.width - span) / 2 + (index % reversi::kSize) * (side + kCellGap)),
                       static_cast<int16_t>(region.y + (region.height - span) / 2 + (index / reversi::kSize) * (side + kCellGap)),
                       static_cast<int16_t>(side), static_cast<int16_t>(side));
}

int cellAt(const fui::DeviceContext& device, const int x, const int y) {
  for (int index = 0; index < reversi::kCells; ++index) {
    const auto card = cardRect(device, index);
    if (!card.empty() && card.contains(x, y)) return index;
  }
  return reversi::kNoCell;
}

void buildMenu(toybox::Screen& screen) {
  chrome(screen);
  const auto device = screen.device();
  const auto safe = device.safeRect();
  const int top = std::max(toybox::kBodyTop, static_cast<int>(safe.y));
  const auto line = [&](const int n) {
    return fui::makeRect(static_cast<int16_t>(safe.x + toybox::kMargin), static_cast<int16_t>(top + n * 40),
                         static_cast<int16_t>(safe.width - toybox::kMargin * 2), 32);
  };
  label(screen, line(0), "LOCAL TWO PLAYER", false);
  label(screen, line(1), "SOLID OPENS / OUTLINE FOLLOWS");
  label(screen, line(2), "CAPTURE AND FLIP / + LEGAL MOVE");
  label(screen, line(3), "MOST DISCS WINS / NO MOVE: PASS");
  fui::ButtonProps start;
  start.label = "START";
  start.action = ActionStart;
  screen.button(start, actionRect(device));
}

void buildBoard(toybox::Screen& screen, const BoardModel& model) {
  if (!model.game) return;
  const auto& game = *model.game;
  chrome(screen);
  const auto device = screen.device();
  char score[48];
  std::snprintf(score, sizeof(score), "SOLID %d   OUTLINE %d", reversi::discCount(game, reversi::kDark),
                reversi::discCount(game, reversi::kLight));
  label(screen, statusRect(device, 0), score);
  const char* turn = game.turn == reversi::kDark ? "SOLID TO MOVE" : "OUTLINE TO MOVE";
  if (reversi::over(game)) {
    turn = game.outcome == reversi::Outcome::DarkWins ? "SOLID WINS" :
           game.outcome == reversi::Outcome::LightWins ? "OUTLINE WINS" : "DRAW";
  }
  label(screen, statusRect(device, 1), turn, false);
  const char* instruction = reversi::over(game) ? "NO MOVES - GAME OVER" :
      model.passedSide == reversi::kLight ? "OUTLINE PASS - NO MOVE" :
      model.passedSide == reversi::kDark ? "SOLID PASS - NO MOVE" : "+ LEGAL MOVE";
  label(screen, statusRect(device, 2), instruction);
  for (int index = 0; index < reversi::kCells; ++index) {
    const auto card = cardRect(device, index);
    if (card.empty()) continue;
    screen.target().stroke(card, fui::Paint::solid(fui::Color::Black), 1);
    const int column = index % reversi::kSize;
    const int row = index / reversi::kSize;
    const auto piece = game.cell[column][row];
    const int16_t cx = static_cast<int16_t>(card.x + card.width / 2);
    const int16_t cy = static_cast<int16_t>(card.y + card.height / 2);
    const int16_t radius = static_cast<int16_t>(std::max(3, card.width / 2 - 5));
    if (piece == reversi::kDark) toybox::disc(screen, cx, cy, radius, fui::Color::Black);
    if (piece == reversi::kLight) toybox::ring(screen, cx, cy, radius, 2, fui::Color::Black, fui::Color::White);
    if (reversi::legalAt(game, column, row)) label(screen, card, "+");
    if (model.cursor == index && !reversi::over(game))
      screen.target().stroke(card.inset(fui::Insets{3, 3, 3, 3}), fui::Paint::solid(fui::Color::Black), 3);
  }
  fui::ButtonProps menu;
  menu.label = "MENU";
  menu.action = ActionMenu;
  const auto base = actionRect(device);
  if (reversi::over(game)) {
    const int16_t width = static_cast<int16_t>((base.width - toybox::kGutter) / 2);
    screen.button(menu, fui::makeRect(base.x, base.y, width, base.height));
    fui::ButtonProps again;
    again.label = "AGAIN";
    again.action = ActionAgain;
    screen.button(again, fui::makeRect(static_cast<int16_t>(base.x + width + toybox::kGutter), base.y,
                                      static_cast<int16_t>(base.width - width - toybox::kGutter), base.height));
  } else screen.button(menu, base);
}

}  // namespace reversiui
