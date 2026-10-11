#include "MemoryScreens.h"

#include <cstdio>

namespace memoryui {
namespace {

constexpr int16_t kCardGap = 6;
constexpr int16_t kProgressHeight = 28;
constexpr int16_t kInstructionHeight = 20;
constexpr int16_t kFooterGap = 8;
constexpr int16_t kActionHeight = 52;

void chrome(toybox::Screen& screen) {
  fui::HeaderProps header;
  header.title = "MEMORY MATCH";
  header.borderEdges = fui::EdgesNone;
  toybox::headerBand(screen, header);
}

void label(toybox::Screen& screen, const fui::Rect box, const char* text, const bool small,
           const fui::Color color = fui::Color::Black) {
  fui::TextStyle style;
  style.font = small ? toybox::kSmallFont : toybox::kUiFont;
  style.align = fui::TextAlign::Center;
  style.color = color;
  screen.target().text(toybox::inkCentred(box, small ? toybox::kTileCut : toybox::kUiCut), text, style);
}

fui::Rect actionRect(const fui::DeviceContext& device) {
  const fui::Rect safe = device.safeRect();
  return fui::makeRect(static_cast<int16_t>(safe.x + toybox::kMargin),
                       static_cast<int16_t>(safe.bottom() - toybox::kMargin - kActionHeight),
                       static_cast<int16_t>(safe.width - toybox::kMargin * 2), kActionHeight);
}

}  // namespace

fui::Rect cardRect(const fui::DeviceContext& device, const memorymatch::Game& game, const int index) {
  if (!memorymatch::onBoard(game, index)) return fui::Rect{};
  const fui::Rect safe = device.safeRect();
  const int top = toybox::kBodyTop + kProgressHeight + kInstructionHeight + kFooterGap * 2;
  const int bottom = actionRect(device).y - kFooterGap * 2;
  const int columns = memorymatch::columnCount(game);
  const int rows = memorymatch::rowCount(game);
  const int width = (safe.width - toybox::kMargin * 2 - (columns - 1) * kCardGap) / columns;
  const int height = (bottom - top - (rows - 1) * kCardGap) / rows;
  if (width <= 0 || height <= 0) return fui::Rect{};
  const int boardWidth = columns * width + (columns - 1) * kCardGap;
  return fui::makeRect(static_cast<int16_t>(safe.x + (safe.width - boardWidth) / 2 +
                                          (index % columns) * (width + kCardGap)),
                       static_cast<int16_t>(top + (index / columns) * (height + kCardGap)),
                       static_cast<int16_t>(width), static_cast<int16_t>(height));
}

int cardAt(const fui::DeviceContext& device, const memorymatch::Game& game, const int x, const int y) {
  for (int index = 0; index < memorymatch::cellCount(game); ++index) {
    const fui::Rect card = cardRect(device, game, index);
    if (!card.empty() && x >= card.x && x < card.right() && y >= card.y && y < card.bottom()) return index;
  }
  return memorymatch::kNoCell;
}

void buildMenu(toybox::Screen& screen, const MenuModel& model) {
  chrome(screen);
  const fui::Rect safe = screen.device().safeRect();
  const fui::Rect body = fui::makeRect(static_cast<int16_t>(safe.x + toybox::kMargin), toybox::kBodyTop,
                                       static_cast<int16_t>(safe.width - toybox::kMargin * 2),
                                       static_cast<int16_t>(safe.bottom() - toybox::kMargin - toybox::kBodyTop));
  const int count = memorymatch::kLevelCount;
  const int16_t rowGap = toybox::kGutter;
  const int16_t rowHeight = static_cast<int16_t>((body.height - rowGap * (count - 1) - 34) / count);
  const int selected = model.selected < 0 || model.selected >= count ? 0 : model.selected;
  label(screen, fui::makeRect(body.x, body.y, body.width, 24), "TAP A LEVEL TO START", true);
  for (int level = 0; level < count; ++level) {
    const fui::Rect row = fui::makeRect(body.x, static_cast<int16_t>(body.y + 28 + level * (rowHeight + rowGap)),
                                        body.width, rowHeight);
    fui::ButtonProps props;
    props.action = ActionLevel;
    props.value = static_cast<int16_t>(level);
    props.state = level == selected ? fui::StateSelected : fui::StateNormal;
    props.styles = toybox::rowStyles();
    screen.button(props, row);
    const fui::Color color = level == selected ? fui::Color::White : fui::Color::Black;
    label(screen, fui::makeRect(row.x, static_cast<int16_t>(row.y + row.height / 2 - 30), row.width, 28),
          memorymatch::kLevels[level].name, false, color);
    char detail[64];
    const memorymatch::Level& choice = memorymatch::kLevels[level];
    std::snprintf(detail, sizeof(detail), "%d CARDS / %d PAIRS / %d X %d", memorymatch::cellsIn(choice),
                  memorymatch::pairsIn(choice), choice.columns, choice.rows);
    label(screen, fui::makeRect(row.x, static_cast<int16_t>(row.y + row.height / 2 + 6), row.width, 22), detail, true,
          color);
  }
}

void buildBoard(toybox::Screen& screen, const BoardModel& model) {
  if (model.game == nullptr) return;
  const memorymatch::Game& game = *model.game;
  chrome(screen);
  const fui::DeviceContext device = screen.device();
  char progress[64];
  std::snprintf(progress, sizeof(progress), "%d/%d PAIRS   %d MOVES", game.matchedPairs, memorymatch::pairCount(game),
                static_cast<int>(game.moves));
  label(screen, fui::makeRect(toybox::kMargin, toybox::kChromeHeight,
                              static_cast<int16_t>(device.width - toybox::kMargin * 2), kProgressHeight), progress, true);
  label(screen, fui::makeRect(toybox::kMargin, static_cast<int16_t>(toybox::kChromeHeight + kProgressHeight),
                              static_cast<int16_t>(device.width - toybox::kMargin * 2), kInstructionHeight),
        memorymatch::awaitingMismatch(game) ? "MISMATCH - PRESS NEXT" :
        memorymatch::complete(game) ? "COMPLETE - TAP AGAIN" : "SELECT A CARD", true);
  for (int index = 0; index < memorymatch::cellCount(game); ++index) {
    const fui::Rect card = cardRect(device, game, index);
    const bool up = memorymatch::faceUp(game, index);
    screen.target().fill(card, up ? fui::Paint::solid(fui::Color::White) : fui::Paint::dither(fui::Color::LightGray));
    const bool matched = memorymatch::isMatched(game, index);
    screen.target().stroke(card, fui::Paint::solid(fui::Color::Black), matched ? 3 : 1);
    if (matched) screen.target().stroke(card.inset(fui::Insets{10, 10, 10, 10}), fui::Paint::solid(fui::Color::Black), 1);
    if (up) {
      char symbol[8];
      std::snprintf(symbol, sizeof(symbol), "%d", static_cast<int>(memorymatch::faceAt(game, index)) + 1);
      label(screen, card, symbol, false);
    }
    if (model.cursor == index)
      screen.target().stroke(card.inset(fui::Insets{4, 4, 4, 4}), fui::Paint::solid(fui::Color::Black), 3);
  }
  const fui::Rect base = actionRect(device);
  fui::ButtonProps menu;
  menu.label = "MENU";
  menu.action = ActionMenu;
  if (memorymatch::awaitingMismatch(game) || memorymatch::complete(game)) {
    const int16_t width = static_cast<int16_t>((base.width - kFooterGap) / 2);
    screen.button(menu, fui::makeRect(base.x, base.y, width, base.height));
    fui::ButtonProps extra;
    extra.label = memorymatch::awaitingMismatch(game) ? "NEXT" : "AGAIN";
    extra.action = memorymatch::awaitingMismatch(game) ? ActionNext : ActionAgain;
    screen.button(extra, fui::makeRect(static_cast<int16_t>(base.x + width + kFooterGap), base.y,
                                       static_cast<int16_t>(base.width - width - kFooterGap), base.height));
  } else {
    screen.button(menu, base);
  }
}

}  // namespace memoryui
