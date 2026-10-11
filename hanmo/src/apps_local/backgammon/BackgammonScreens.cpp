#include "BackgammonScreens.h"

#include <algorithm>
#include <cstdio>

namespace backgammonui {
namespace bg = backgammon;
namespace {
constexpr int kGap = 6;
constexpr int kLine = 24;
constexpr int kControl = 44;
constexpr int kFooter = 52;
constexpr int kHints = 36;
constexpr int kColumns = bg::kPoints / 2;

fui::Rect box(int x, int y, int w, int h) {
  return fui::makeRect(static_cast<int16_t>(x), static_cast<int16_t>(y),
                       static_cast<int16_t>(w), static_cast<int16_t>(h));
}
struct Layout {
  fui::Rect status, instruction, dice, piles, board, footer;
};
Layout layout(const fui::DeviceContext& d) {
  const auto safe = d.safeRect();
  const int x = safe.x + toybox::kMargin;
  const int w = std::max(0, safe.width - toybox::kMargin * 2);
  const int top = std::max<int>(toybox::kBodyTop, safe.y + toybox::kMargin);
  Layout l;
  l.status = box(x, top, w, kLine);
  l.instruction = box(x, l.status.bottom() + kGap, w, kLine);
  l.dice = box(x, l.instruction.bottom() + kGap, w, kControl);
  l.piles = box(x, l.dice.bottom() + kGap, w, kControl);
  l.footer = box(x, safe.bottom() - toybox::kMargin - kHints - kFooter, w, kFooter);
  // In a short orientation, dice and BAR/OFF share one row. Point geometry
  // consumes this same layout, so paint and input cannot choose different grids.
  if (l.footer.y - kGap - l.piles.bottom() - kGap < 2 * 44 + kGap) {
    const int half = (w - kGap) / 2;
    l.piles = box(x + half + kGap, l.dice.y, half, kControl);
    l.dice.width = static_cast<int16_t>(half);
  }
  const int y = l.piles.bottom() + kGap;
  l.board = box(x, y, w, std::max(0, l.footer.y - kGap - y));
  return l;
}
fui::Rect divided(fui::Rect row, int index, int count) {
  const int w = (row.width - (count - 1) * kGap) / count;
  return w > 0 ? box(row.x + index * (w + kGap), row.y, w, row.height) : fui::Rect{};
}
void chrome(toybox::Screen& screen) {
  fui::HeaderProps props;
  props.title = "BACKGAMMON";
  toybox::headerBand(screen, props);
}
void label(toybox::Screen& screen, fui::Rect rect, const char* text) {
  fui::TextStyle style;
  style.font = toybox::kSmallFont;
  style.align = fui::TextAlign::Center;
  screen.target().text(toybox::inkCentred(rect, toybox::kTileCut), text, style);
}
void button(toybox::Screen& s, fui::Rect rect, const char* text, fui::ActionId id,
            bool enabled = true, int value = 0, bool selected = false) {
  if (rect.empty()) return;
  fui::ButtonProps props;
  props.label = text;
  props.action = id;
  props.value = static_cast<int16_t>(value);
  props.text.font = toybox::kSmallFont;
  props.text.align = fui::TextAlign::Center;
  props.state = selected ? fui::StateSelected : fui::StateNormal;
  props.enabled = enabled;
  s.button(props, rect);
}
void point(toybox::Screen& screen, const Flow& flow, int at) {
  const auto r = pointRect(screen.device(), at);
  if (r.empty()) return;
  const auto ink = fui::Paint::solid(fui::Color::Black);
  screen.target().stroke(r, ink, 1);
  char text[16];
  std::snprintf(text, sizeof(text), "%d", at + 1);
  label(screen, box(r.x, r.y + 2, r.width, 18), text);
  const int count = flow.game.point[at] < 0 ? -flow.game.point[at] : flow.game.point[at];
  const bool light = flow.game.point[at] > 0;
  // Exact total is always printed, even when the bounded picture cannot hold it.
  std::snprintf(text, sizeof(text), "%c%d", count == 0 ? '-' : (light ? 'L' : 'D'), count);
  label(screen, box(r.x, r.bottom() - 22, r.width, 20), text);
  const int radius = std::max(1, std::min({10, (r.width - 8) / 2, (r.height - 46) / 2}));
  const int pitch = radius * 2 + 2;
  const int capacity = std::max(0, std::min(5, (r.height - 44) / pitch));
  for (int i = 0; i < std::min(count, capacity); ++i) {
    const int cy = r.y + 23 + radius + i * pitch;
    if (light) toybox::ring(screen, r.x + r.width / 2, cy, radius, 2, fui::Color::Black, fui::Color::White);
    else toybox::disc(screen, r.x + r.width / 2, cy, radius, fui::Color::Black);
  }
  if (flow.legalSource(at)) toybox::bracket(screen, r.inset(fui::Insets{2,2,2,2}), 6, 1);
  if (flow.from == at || flow.target() == at)
    screen.target().stroke(r.inset(fui::Insets{3,3,3,3}), ink, 2);
}
}

fui::Rect pointRect(const fui::DeviceContext& d, int at) {
  if (!bg::inside(at)) return {};
  const auto board = layout(d).board;
  const int w = (board.width - (kColumns - 1) * kGap) / kColumns;
  const int h = (board.height - kGap) / 2;
  if (w <= 0 || h < 44) return {};
  const int col = at >= kColumns ? at - kColumns : kColumns - 1 - at;
  const int row = at >= kColumns ? 0 : 1;
  return box(board.x + col * (w + kGap), board.y + row * (h + kGap), w, h);
}
int pointAt(const fui::DeviceContext& d, int x, int y) {
  for (int at = 0; at < bg::kPoints; ++at) {
    const auto r = pointRect(d, at);
    if (!r.empty() && r.contains(x, y)) return at;
  }
  return kNoPoint;
}
void buildMenu(toybox::Screen& screen) {
  chrome(screen);
  const auto l = layout(screen.device());
  label(screen, l.status, "LOCAL TWO PLAYERS");
  label(screen, l.instruction, "LIGHT: 1->24 / DARK: 24->1");
  button(screen, l.dice, "START", ActionStart);
}
void buildBoard(toybox::Screen& screen, const BoardModel& model) {
  if (!model.flow) return;
  chrome(screen);
  const auto& flow = *model.flow;
  const auto l = layout(screen.device());
  const bool done = bg::over(flow.game);
  label(screen, divided(l.status, 0, 2), done ? (flow.game.outcome == bg::Outcome::LightWins ? "LIGHT WINS" : "DARK WINS") :
        (flow.opening ? "OPENING ROLL" : (flow.game.turn == bg::kLight ? "LIGHT TO PLAY" : "DARK TO PLAY")));
  char text[80];
  if (flow.openingLight != 0)
    std::snprintf(text, sizeof(text), "OPEN L%d D%d", flow.openingLight, flow.openingDark);
  else std::snprintf(text, sizeof(text), "%d USES LEFT", bg::pendingCount(flow.game));
  label(screen, divided(l.status, 1, 2), text);
  if (done) std::snprintf(text, sizeof(text), "DONE - AGAIN OR MENU");
  else if (flow.opening) std::snprintf(text, sizeof(text), flow.openingLight != 0 ?
      "OPENING TIE - ROLL AGAIN" : "ONE DIE EACH - HIGHER STARTS");
  else if (!flow.rolled) std::snprintf(text, sizeof(text), "ROLL TO BEGIN TURN");
  else if (flow.canEnd()) std::snprintf(text, sizeof(text), "NO LEGAL MOVES - END TURN");
  else if (flow.from != kNoPoint) {
    if (flow.target() == kOff) std::snprintf(text, sizeof(text), "FROM %d -> OFF", flow.from + 1);
    else if (flow.from == bg::kBar) std::snprintf(text, sizeof(text), "FROM BAR -> TO %d", flow.target() + 1);
    else std::snprintf(text, sizeof(text), "FROM %d -> TO %d", flow.from + 1, flow.target() + 1);
  } else if (flow.game.bar[flow.game.turn] && flow.pips()) {
    std::snprintf(text, sizeof(text), "BAR FIRST - CHOOSE BAR");
  } else std::snprintf(text, sizeof(text), "CHOOSE DIE, THEN FROM");
  label(screen, l.instruction, text);
  for (int i = 0; i < bg::kMaxPendingDice; ++i) {
    if (flow.game.die[i]) std::snprintf(text, sizeof(text), "D%d: %d", i + 1, flow.game.die[i]);
    else std::snprintf(text, sizeof(text), "D%d: -", i + 1);
    button(screen, divided(l.dice, i, bg::kMaxPendingDice), text, ActionDie,
           flow.canChooseDie(i), i, flow.dieSlot == i);
  }
  std::snprintf(text, sizeof(text), "BAR L%d D%d", flow.game.bar[bg::kLight], flow.game.bar[bg::kDark]);
  button(screen, divided(l.piles, 0, 2), text, ActionBar, flow.legalSource(bg::kBar), 0, flow.from == bg::kBar);
  std::snprintf(text, sizeof(text), "OFF L%d D%d", flow.game.off[bg::kLight], flow.game.off[bg::kDark]);
  button(screen, divided(l.piles, 1, 2), text, ActionOff, flow.target() == kOff);
  for (int at = 0; at < bg::kPoints; ++at) point(screen, flow, at);
  button(screen, divided(l.footer, 0, 2), "MENU", ActionMenu);
  if (done) button(screen, divided(l.footer, 1, 2), "AGAIN", ActionAgain);
  else button(screen, divided(l.footer, 1, 2), flow.canRoll() ? "ROLL" : "END TURN",
              flow.canRoll() ? ActionRoll : ActionEnd, flow.canRoll() || flow.canEnd());
}
}  // namespace backgammonui
