#include "MahjongScreens.h"

#include <cstdio>

namespace mahjongui {
namespace {
constexpr int kGap = 6;
constexpr int kStatusHeight = 24;
constexpr int kHintReserve = 32;

void chrome(toybox::Screen& screen) {
  fui::HeaderProps props;
  props.title = "MAHJONG SOLITAIRE";
  props.borderEdges = fui::EdgesNone;
  toybox::headerBand(screen, props);
}

void label(toybox::Screen& screen, const fui::Rect box, const char* text, const bool small = true) {
  fui::TextStyle style;
  style.font = small ? toybox::kSmallFont : toybox::kUiFont;
  style.align = fui::TextAlign::Center;
  screen.target().text(toybox::inkCentred(box, small ? toybox::kTileCut : toybox::kUiCut), text, style);
}

fui::Rect footerRect(const fui::DeviceContext& device) {
  const fui::Rect safe = device.safeRect();
  return fui::makeRect(safe.x + toybox::kMargin,
                       safe.bottom() - toybox::kMargin - kHintReserve - toybox::kPillHeight,
                       safe.width - toybox::kMargin * 2, toybox::kPillHeight);
}
}  // namespace

fui::Rect tileRect(const fui::DeviceContext& device, const int slot) {
  if (slot < 0 || slot >= mahjong::kSlots) return {};
  const auto safe = device.safeRect();
  const int top = (safe.y > toybox::kBodyTop ? safe.y : toybox::kBodyTop) + kStatusHeight * 2 + kGap;
  const int bottom = footerRect(device).y - kGap;
  const int width = (safe.width - toybox::kMargin * 2 - (mahjong::kColumns - 1) * kGap) / mahjong::kColumns;
  const int height = (bottom - top - (mahjong::kRows - 1) * kGap) / mahjong::kRows;
  // This one upright layout is portrait-only on the target. Do not offer
  // tiny, unreadable cells when the user rotates the device or safe area shrinks.
  if (width < 44 || height < 44) return {};
  const int boardWidth = mahjong::kColumns * width + (mahjong::kColumns - 1) * kGap;
  const auto& here = mahjong::kLayout[slot];
  return fui::makeRect(safe.x + (safe.width - boardWidth) / 2 + here.x * (width + kGap) / 2,
                       top + here.y * (height + kGap) / 2, width, height);
}

bool visibleSlot(const mahjong::Game& game, const int slot) {
  if (slot < 0 || slot >= mahjong::kSlots || game.tile[slot] == mahjong::kNoTile) return false;
  for (int other = slot + 1; other < mahjong::kSlots; ++other) {
    if (game.tile[other] != mahjong::kNoTile && mahjong::kLayout[other].layer > mahjong::kLayout[slot].layer &&
        mahjong::footprintsOverlap(mahjong::kLayout[slot], mahjong::kLayout[other])) return false;
  }
  return true;
}

int tileAt(const fui::DeviceContext& device, const mahjong::Game& game, const int x, const int y) {
  // The core table is painter ordered. Reverse it: a blocked top tile must
  // never let a tap fall through to an underlying free tile.
  for (int slot = mahjong::kSlots - 1; slot >= 0; --slot) {
    if (!visibleSlot(game, slot)) continue;
    const auto box = tileRect(device, slot);
    if (!box.empty() && box.contains(x, y)) return slot;
  }
  return mahjong::kNoSlot;
}

void tileMarker(const uint8_t tile, char out[4]) {
  constexpr char groups[] = "BCOWDFS";
  const uint8_t group = mahjong::tileGroup(tile);
  const uint8_t rank = mahjong::tileRank(tile);
  if (group >= mahjong::kGroupCount || rank >= mahjong::kGroupSize[group]) {
    out[0] = '?'; out[1] = '\0'; return;
  }
  out[0] = groups[group]; out[1] = static_cast<char>('1' + rank); out[2] = '\0';
}

void buildMenu(toybox::Screen& screen) {
  chrome(screen);
  const auto safe = screen.device().safeRect();
  const int top = safe.y > toybox::kBodyTop ? safe.y : toybox::kBodyTop;
  const auto line = [&](const int row) { return fui::makeRect(safe.x + toybox::kMargin, top + row * 32,
                                                              safe.width - toybox::kMargin * 2, 24); };
  label(screen, line(0), "8 X 10 / 3 LAYERS / 144 TILES");
  label(screen, line(1), "RANDOM DEALS MAY HAVE NO SOLUTION");
  label(screen, line(3), "MATCH FREE TILES WITH ONE OPEN SIDE");
  label(screen, line(4), "THICK EDGE = FREE / L1-L3 = DEPTH");
  if (line(9).bottom() + kGap < footerRect(screen.device()).y) {
    label(screen, line(6), "B BAMBOO / C CHARACTERS / O CIRCLES");
    label(screen, line(7), "W WINDS / D DRAGONS");
    label(screen, line(8), "F FLOWERS MATCH ANY F");
    label(screen, line(9), "S SEASONS MATCH ANY S");
  } else {
    label(screen, line(5), "B/C/O SUITS / W WINDS / D DRAGONS");
    label(screen, line(6), "F FLOWERS / S SEASONS: MATCH GROUP");
  }
  fui::ButtonProps start;
  start.label = "START"; start.action = ActionStart;
  screen.button(start, footerRect(screen.device()));
}

void buildBoard(toybox::Screen& screen, const BoardModel& model) {
  if (!model.game) return;
  const auto& game = *model.game;
  chrome(screen);
  const auto safe = screen.device().safeRect();
  const int top = safe.y > toybox::kBodyTop ? safe.y : toybox::kBodyTop;
  char progress[64];
  std::snprintf(progress, sizeof(progress), "%d LEFT / %d PAIRS", mahjong::remaining(game), mahjong::availableMoves(game));
  label(screen, fui::makeRect(safe.x + toybox::kMargin, top, safe.width - toybox::kMargin * 2, kStatusHeight), progress);
  label(screen, fui::makeRect(safe.x + toybox::kMargin, top + kStatusHeight, safe.width - toybox::kMargin * 2,
                              kStatusHeight), mahjong::won(game) ? "DONE" : mahjong::deadEnd(game) ? "NO PAIRS" :
                              model.selected != mahjong::kNoSlot ? "PICK A MATCH / BACK CANCELS" : "PICK A FREE TILE");
  if (tileRect(screen.device(), 0).empty())
    label(screen, fui::makeRect(safe.x + toybox::kMargin, top + kStatusHeight * 3,
                                safe.width - toybox::kMargin * 2, kStatusHeight),
          "USE PORTRAIT FOR READABLE TILES");
  for (int slot = 0; slot < mahjong::kSlots; ++slot) {
    if (!visibleSlot(game, slot)) continue;
    const auto box = tileRect(screen.device(), slot);
    if (box.empty()) continue;
    screen.target().fill(box, fui::Paint::solid(fui::Color::White));
    screen.target().stroke(box, fui::Paint::solid(fui::Color::Black), mahjong::freeSlot(game, slot) ? 2 : 1);
    if (model.selected == slot)
      screen.target().stroke(box.inset(fui::Insets{3, 3, 3, 3}), fui::Paint::solid(fui::Color::Black), 3);
    char marker[4]; tileMarker(game.tile[slot], marker);
    label(screen, fui::makeRect(box.x, box.y, box.width, box.height - 18), marker);
    const char depth[] = {'L', static_cast<char>('1' + mahjong::kLayout[slot].layer), '\0'};
    label(screen, fui::makeRect(box.x, box.bottom() - 18, box.width, 18), depth);
  }
  const auto footer = footerRect(screen.device());
  const int width = (footer.width - kGap) / 2;
  fui::ButtonProps menu; menu.label = "MENU"; menu.action = ActionMenu;
  screen.button(menu, fui::makeRect(footer.x, footer.y, width, footer.height));
  fui::ButtonProps fresh; fresh.label = mahjong::won(game) ? "AGAIN" : "NEW"; fresh.action = ActionNew;
  screen.button(fresh, fui::makeRect(footer.x + width + kGap, footer.y, footer.width - width - kGap, footer.height));
}
}  // namespace mahjongui
