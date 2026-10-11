#include "TileRummyScreens.h"

#include <cstdio>

// ASCII identities intentionally fit the shared monochrome tile font.
namespace tilerummyui {
namespace {
constexpr int kGap = 6, kButtonH = 44, kStatusH = 72, kHintReserve = 32;
int bodyTop(const fui::DeviceContext& d) {
  return d.safeRect().y > toybox::kBodyTop ? d.safeRect().y : toybox::kBodyTop;
}
fui::Rect body(const fui::DeviceContext& d) {
  const auto safe = d.safeRect();
  return fui::makeRect(safe.x + toybox::kMargin, bodyTop(d), safe.width - 2 * toybox::kMargin,
                       safe.bottom() - bodyTop(d) - toybox::kMargin - kHintReserve);
}
int columns(const fui::DeviceContext& d) { return body(d).width >= 8 * 44 + 7 * kGap ? 8 : 4; }
int footerColumns(const fui::DeviceContext& d) { return body(d).width >= 640 ? 8 : 4; }
fui::Rect footer(const fui::DeviceContext& d) {
  const auto b = body(d);
  const int rows = 16 / footerColumns(d);
  const int h = rows * kButtonH + (rows - 1) * kGap;
  return fui::makeRect(b.x, b.bottom() - h, b.width, h);
}
fui::Rect cell(fui::Rect grid, int cols, int index, int h) {
  const int w = (grid.width - (cols - 1) * kGap) / cols;
  return fui::makeRect(grid.x + index % cols * (w + kGap), grid.y + index / cols * (h + kGap), w, h);
}
void chrome(toybox::Screen& s) {
  fui::HeaderProps props;
  props.title = "TILE RUMMY";
  props.borderEdges = fui::EdgesNone;
  toybox::headerBand(s, props);
}
void label(toybox::Screen& s, fui::Rect r, const char* text, bool small = true, fui::Color color = fui::Color::Black) {
  fui::TextStyle style;
  style.font = small ? toybox::kSmallFont : toybox::kUiFont;
  style.align = fui::TextAlign::Center;
  style.color = color;
  // Replacement typefaces may be wider: retain the complete tile identity
  // inside its border instead of clipping the last digit.
  if (!small && s.target().measureText(style.font, text, style).width > r.width - 8) {
    small = true;
    style.font = toybox::kSmallFont;
  }
  s.target().text(toybox::inkCentred(r, small ? toybox::kTileCut : toybox::kUiCut), text, style);
}
void button(toybox::Screen& s, fui::Rect r, const char* text, fui::ActionId action, int value = 0, bool enabled = true,
            bool selected = false) {
  fui::ButtonProps p;
  p.action = action;
  p.value = static_cast<int16_t>(value);
  p.enabled = enabled;
  p.state = !enabled ? fui::StateDisabled : selected ? fui::StateSelected : fui::StateNormal;
  s.button(p, r);
  label(s, r, text, true, fui::Color::White);
}
const char* reason(tr::SetProblem p) {
  switch (p) {
    case tr::SetProblem::TooFewTiles:
      return "NEED 3 TILES";
    case tr::SetProblem::DuplicateColour:
      return "REPEATED LETTER";
    case tr::SetProblem::GroupTooLong:
      return "GROUP MAX 4";
    case tr::SetProblem::RunBroken:
      return "RUN NOT IN ORDER";
    case tr::SetProblem::RunOutOfRange:
      return "RUN OUTSIDE 1-13";
    case tr::SetProblem::AllJokers:
      return "NEED NUMBERED TILE";
    case tr::SetProblem::NotASet:
      return "MIXED NUMBER/LETTER";
    default:
      return "VALID SET";
  }
}
void message(const Flow& f, char* text, size_t size) {
  const char* note = "NEW SET, SELECT TILE, ADD";
  switch (f.note) {
    case Note::Group:
      note = "GROUP: SAME NUMBER, 3-4 LETTERS";
      break;
    case Note::Run:
      note = "RUN: ONE LETTER, ORDERED 1-13";
      break;
    case Note::Locked:
      note = "INITIAL MELD FIRST - TABLE LOCKED";
      break;
    case Note::Full:
      note = "SET LIMIT - REUSE EMPTY SET";
      break;
    case Note::Loose:
      note = "LOOSE TILES: ADD OR RETURN";
      break;
    case Note::EmptyPool:
      note = "POOL EMPTY: PLAY OR EXPLICIT PASS";
      break;
    case Note::Verdict:
      switch (f.result.problem) {
        case tr::MoveProblem::InvalidSet:
          std::snprintf(text, size, "SET %d: %s", f.result.failedSet + 1, reason(f.result.setProblem));
          return;
        case tr::MoveProblem::MeldTooSmall:
          std::snprintf(text, size, "INITIAL MELD %d / %d", f.result.meldScore, f.game.settings.meldMinimum);
          return;
        case tr::MoveProblem::TableUsedBeforeMeld:
          note = "INITIAL MELD MUST USE YOUR HAND";
          break;
        case tr::MoveProblem::TileRemovedFromTable:
          note = "TABLE TILE MISSING - RESTORE IT";
          break;
        case tr::MoveProblem::TileNotInHand:
          note = "TILE NOT AVAILABLE IN YOUR HAND";
          break;
        case tr::MoveProblem::NothingPlayed:
          note = "ADD AT LEAST ONE HAND TILE";
          break;
        case tr::MoveProblem::TooManySets:
          note = "TOO MANY SETS";
          break;
        case tr::MoveProblem::GameOver:
          note = "GAME OVER";
          break;
        default:
          note = "READY TO PLAY";
          break;
      }
      break;
    default:
      break;
  }
  std::snprintf(text, size, "%s", note);
}
}  // namespace

void tileText(tr::Tile tile, char* out, size_t capacity) {
  if (tr::isJoker(tile))
    std::snprintf(out, capacity, "J");
  else if (tile < tr::kDistinctNumbered)
    std::snprintf(out, capacity, "%c%d", "RBYK"[tr::tileColour(tile)], tr::tileNumber(tile));
  else
    std::snprintf(out, capacity, "?");
}
fui::Rect tileRect(const fui::DeviceContext& d, const Flow& f, int index) {
  if (f.screen != Screen::Board || index < f.page * kPageTiles || index >= (f.page + 1) * kPageTiles || index < 0 ||
      index >= f.itemCount())
    return {};
  const auto b = body(d);
  const int top = b.y + kStatusH + kButtonH + 2 * kGap;
  const int cols = columns(d), rows = kPageTiles / cols;
  const int h = (footer(d).y - kGap - top - (rows - 1) * kGap) / rows;
  if (h <= 0) return {};
  return cell(fui::makeRect(b.x, top, b.width, h * rows + (rows - 1) * kGap), cols, index - f.page * kPageTiles, h);
}
int tileAt(const fui::DeviceContext& d, const Flow& f, int x, int y) {
  const int first = f.page * kPageTiles;
  for (int i = first; i < f.itemCount() && i < first + kPageTiles; ++i) {
    const auto box = tileRect(d, f, i);
    if (!box.empty() && box.contains(x, y)) return i;
  }
  return -1;
}
void buildMenu(toybox::Screen& s, const MenuModel& model) {
  if (!model.flow) return;
  chrome(s);
  const auto b = body(s.device());
  const auto& settings = model.flow->settings;
  const int cols = columns(s.device()) == 8 ? 2 : 1;
  const int rows = 6 / cols, h = (b.height - 48 - (rows - 1) * kGap) / rows;
  label(s, fui::makeRect(b.x, b.y, b.width, 24), "LOCAL HOT-SEAT / NO AUTOMATIC SOLVER");
  label(s, fui::makeRect(b.x, b.y + 24, b.width, 24), "TAP SETTINGS TO CYCLE; START TO DEAL");
  char text[64];
  const auto grid = fui::makeRect(b.x, b.y + 48, b.width, b.height - 48);
  std::snprintf(text, sizeof(text), "PLAYERS: %d (2-4)", settings.players);
  button(s, cell(grid, cols, 0, h), text, ActionPlayers);
  std::snprintf(text, sizeof(text), "STARTING HAND: %d", settings.startingHand);
  button(s, cell(grid, cols, 1, h), text, ActionHand);
  std::snprintf(text, sizeof(text), "INITIAL MELD MINIMUM: %d", settings.meldMinimum);
  button(s, cell(grid, cols, 2, h), text, ActionMeld);
  std::snprintf(text, sizeof(text), "JOKERS: %d (0-2)", settings.jokers);
  button(s, cell(grid, cols, 3, h), text, ActionJokers);
  button(s, cell(grid, cols, 4, h), "START", ActionStart);
  button(s, cell(grid, cols, 5, h), "EXIT", ActionMenu);
}
void buildBoard(toybox::Screen& s, const BoardModel& model) {
  if (!model.flow) return;
  const auto& f = *model.flow;
  chrome(s);
  const auto b = body(s.device());
  char text[96];
  if (f.screen == Screen::Handoff || f.screen == Screen::Done) {
    if (f.screen == Screen::Handoff)
      std::snprintf(text, sizeof(text), "PLAYER %d - YOUR TURN", f.game.turn + 1);
    else if (f.blocked)
      std::snprintf(text, sizeof(text), "BLOCKED - ALL PLAYERS PASSED");
    else
      std::snprintf(text, sizeof(text), "PLAYER %d WINS", f.game.winner + 1);
    label(s, fui::makeRect(b.x, b.y + 32, b.width, 44), text, false);
    label(s, fui::makeRect(b.x, b.y + 82, b.width, 24),
          f.screen == Screen::Handoff ? "PASS DEVICE; READY REVEALS YOUR HAND" : "AGAIN USES THE SAME SETTINGS");
    const auto grid = fui::makeRect(b.x, b.bottom() - kButtonH, b.width, kButtonH);
    button(s, cell(grid, 2, 0, kButtonH), "MENU", ActionMenu);
    button(s, cell(grid, 2, 1, kButtonH), f.screen == Screen::Handoff ? "READY" : "AGAIN",
           f.screen == Screen::Handoff ? ActionReady : ActionAgain);
    return;
  }
  std::snprintf(text, sizeof(text), "PLAYER %d/%d  HAND %d  POOL %d  %s %d", f.game.turn + 1, f.game.settings.players,
                f.game.hands[f.game.turn].count, f.game.poolCount,
                f.game.melded[f.game.turn] ? "MELDED / MIN" : "INITIAL MIN", f.game.settings.meldMinimum);
  label(s, fui::makeRect(b.x, b.y, b.width, 24), text);
  std::snprintf(text, sizeof(text), "SET %d/%d %s  PAGE %d/%d  LOOSE %d", f.activeSet + 1, f.draft.table.setCount,
                f.validSet() && !f.setEditable() ? "LOCKED" : "DRAFT", f.page + 1, f.pageCount(), f.draft.loose.count);
  label(s, fui::makeRect(b.x, b.y + 24, b.width, 24), text);
  message(f, text, sizeof(text));
  label(s, fui::makeRect(b.x, b.y + 48, b.width, 24), text);
  const auto tabs = fui::makeRect(b.x, b.y + kStatusH, b.width, kButtonH);
  const char* names[] = {"HAND", "TABLE", "LOOSE"};
  for (int i = 0; i < 3; ++i)
    button(s, cell(tabs, 3, i, kButtonH), names[i], ActionView, i, f.live(), i == static_cast<int>(f.view));
  for (int i = f.page * kPageTiles; i < f.itemCount() && i < (f.page + 1) * kPageTiles; ++i) {
    const auto box = tileRect(s.device(), f, i);
    const bool available = f.view != View::Hand || f.handAvailable(i);
    s.target().fill(box, available ? fui::Paint::solid(fui::Color::White) : fui::Paint::dither(fui::Color::LightGray));
    s.target().stroke(box, fui::Paint::solid(fui::Color::Black), 1);
    char identity[8];
    tileText(f.itemTile(i), identity, sizeof(identity));
    label(s, box, identity, false);
    if (i == f.selected) s.target().stroke(box.inset(fui::Insets{4, 4, 4, 4}), fui::Paint::solid(fui::Color::Black), 3);
  }
  const auto grid = footer(s.device());
  const int cols = footerColumns(s.device());
  button(s, cell(grid, cols, 0, kButtonH), "< SET", ActionSet, -1, f.live() && f.activeSet > 0);
  button(s, cell(grid, cols, 1, kButtonH), "SET >", ActionSet, 1, f.live() && f.activeSet + 1 < f.draft.table.setCount);
  button(s, cell(grid, cols, 2, kButtonH), "NEW GROUP", ActionNewGroup, 0, f.live());
  button(s, cell(grid, cols, 3, kButtonH), "NEW RUN", ActionNewRun, 0, f.live());
  button(s, cell(grid, cols, 4, kButtonH), "ADD", ActionAdd, 0, f.canAdd());
  button(s, cell(grid, cols, 5, kButtonH), "REMOVE", ActionRemove, 0, f.canRemove());
  button(s, cell(grid, cols, 6, kButtonH), "RETURN", ActionReturn, 0, f.canReturn());
  button(s, cell(grid, cols, 7, kButtonH), "< MOVE", ActionMove, -1, f.canRemove() && f.selected > 0);
  button(s, cell(grid, cols, 8, kButtonH), "MOVE >", ActionMove, 1, f.canRemove() && f.selected + 1 < f.itemCount());
  button(s, cell(grid, cols, 9, kButtonH), "UNDO", ActionUndo, 0, f.live() && f.undoReady);
  button(s, cell(grid, cols, 10, kButtonH), "CANCEL", ActionCancel, 0, f.live());
  button(s, cell(grid, cols, 11, kButtonH), "PLAY", ActionPlay, 0, f.live());
  button(s, cell(grid, cols, 12, kButtonH), f.game.poolCount ? "DRAW" : "PASS EMPTY", ActionDraw, 0, f.live());
  button(s, cell(grid, cols, 13, kButtonH), "MENU", ActionMenu);
  button(s, cell(grid, cols, 14, kButtonH), "< PAGE", ActionPage, -1, f.live() && f.page > 0);
  button(s, cell(grid, cols, 15, kButtonH), "PAGE >", ActionPage, 1, f.live() && f.page + 1 < f.pageCount());
}
}  // namespace tilerummyui
