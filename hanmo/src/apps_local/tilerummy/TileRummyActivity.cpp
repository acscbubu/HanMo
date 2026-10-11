#include "TileRummyActivity.h"

#include <Logging.h>
#include <Memory.h>

#include "../../components/UITheme.h"
#include "../Shelf.h"
#include "../ui/ToyboxFonts.h"
#include "../ui/ToyboxSeed.h"
#include "../ui/ToyboxTheme.h"

namespace {
namespace fui = freeink::ui;
namespace ui = tilerummyui;
namespace tr = tilerummy;
uint8_t nextOption(uint8_t value, const uint8_t* options, int count) {
  for (int i = 0; i < count; ++i)
    if (options[i] == value) return options[(i + 1) % count];
  return options[0];
}
}  // namespace
std::unique_ptr<Activity> TileRummyActivity::create(GfxRenderer& r, MappedInputManager& input) {
  // Only Activity lifetime needs the heap; all game/editor state is fixed-size.
  auto activity = makeUniqueNoThrow<TileRummyActivity>(r, input);
  if (!activity) LOG_ERR("TILERUMMY", "Activity allocation failed");
  return activity;
}
void TileRummyActivity::onEnter() {
  Activity::onEnter();
  toybox::ensureFonts(renderer);
  flow.screen = ui::Screen::Menu;
  focus = -1;
  interactionsReady = false;
  requestUpdate();
}
void TileRummyActivity::startGame() {
  if (flow.begin(toybox::seed())) {
    focus = -1;
    interactionsReady = false;
    requestUpdate();
  }
}
void TileRummyActivity::routeAction(const fui::ActionEvent& event) {
  if (event.action == ui::ActionMenu) {
    if (flow.screen == ui::Screen::Menu) {
      shelf::leave(renderer, mappedInput);
      return;
    }
    flow.menu();
    focus = -1;
    interactionsReady = false;
    requestUpdate();
    return;
  }
  if (flow.screen == ui::Screen::Menu) {
    switch (event.action) {
      case ui::ActionStart:
        startGame();
        return;
      case ui::ActionPlayers:
        flow.settings.players = flow.settings.players == tr::kMaxPlayers ? tr::kMinPlayers : flow.settings.players + 1;
        break;
      case ui::ActionHand:
        flow.settings.startingHand =
            nextOption(flow.settings.startingHand, tr::kStartingHandOptions, tr::kStartingHandOptionCount);
        break;
      case ui::ActionMeld:
        flow.settings.meldMinimum =
            nextOption(flow.settings.meldMinimum, tr::kMeldMinimumOptions, tr::kMeldMinimumOptionCount);
        break;
      case ui::ActionJokers:
        flow.settings.jokers = (flow.settings.jokers + 1) % (tr::kMaxJokers + 1);
        break;
      default:
        return;
    }
    requestUpdate();
    return;
  }
  if (flow.screen == ui::Screen::Done) {
    if (event.action == ui::ActionAgain) startGame();
    return;
  }
  if (flow.screen == ui::Screen::Handoff) {
    if (event.action == ui::ActionReady) {
      flow.ready();
      focus = -1;
      interactionsReady = false;
      requestUpdate();
    }
    return;
  }
  if (!flow.live()) return;
  switch (event.action) {
    case ui::ActionView:
      if (event.value < 0 || event.value > 2) return;
      flow.setView(static_cast<ui::View>(event.value));
      break;
    case ui::ActionSet:
      flow.changeSet(event.value);
      break;
    case ui::ActionPage:
      flow.changePage(event.value);
      break;
    case ui::ActionNewGroup:
      flow.newSet(false);
      break;
    case ui::ActionNewRun:
      flow.newSet(true);
      break;
    case ui::ActionAdd:
      flow.addSelected();
      break;
    case ui::ActionRemove:
      flow.removeSelected();
      break;
    case ui::ActionReturn:
      flow.returnSelected();
      break;
    case ui::ActionMove:
      flow.moveSelected(event.value);
      break;
    case ui::ActionUndo:
      flow.undo();
      break;
    case ui::ActionCancel:
      flow.cancel();
      break;
    case ui::ActionPlay:
      flow.commit();
      break;
    case ui::ActionDraw:
      flow.draw();
      break;
    default:
      return;
  }
  focus = -1;
  requestUpdate();
}
int TileRummyActivity::visibleTiles() const {
  if (flow.screen != ui::Screen::Board) return 0;
  const int remaining = flow.itemCount() - flow.page * ui::kPageTiles;
  return remaining < 0 ? 0 : remaining < ui::kPageTiles ? remaining : ui::kPageTiles;
}
void TileRummyActivity::loop() {
  using Button = MappedInputManager::Button;
  if (mappedInput.wasReleased(Button::Back)) {
    if (flow.screen == ui::Screen::Menu)
      shelf::leave(renderer, mappedInput);
    else {
      flow.menu();
      focus = -1;
      interactionsReady = false;
      requestUpdate();
    }
    return;
  }
  if (!interactionsReady || !surfaceRevealed()) return;
  const int tiles = visibleTiles(), count = tiles + static_cast<int>(interactions.count());
  // Physical focus visits the same geometrical tile seats and real registered
  // controls. Confirm fires their exact ActionEvent, not a separate rules path.
  const bool previous = mappedInput.wasReleased(Button::Up) || mappedInput.wasReleased(Button::Left);
  const bool next = mappedInput.wasReleased(Button::Down) || mappedInput.wasReleased(Button::Right);
  if ((previous || next) && count) {
    focus = focus < 0 ? (previous ? count - 1 : 0) : (focus + (previous ? count - 1 : 1)) % count;
    requestUpdate();
    return;
  }
  if (mappedInput.wasReleased(Button::Confirm)) {
    if (focus < 0 || focus >= count) return;
    if (focus < tiles) {
      if (flow.select(flow.page * ui::kPageTiles + focus)) requestUpdate();
    } else {
      const auto hit = interactions.data()[focus - tiles];
      routeAction(fui::ActionEvent{hit.action, hit.value});
    }
    return;
  }
  int x = 0, y = 0;
  if (!mappedInput.wasScreenTapped(x, y)) return;
  focus = -1;
  const auto device = toybox::makeTarget(renderer).deviceContext();
  const int tile = ui::tileAt(device, flow, x, y);
  if (tile >= 0) {
    if (flow.select(tile)) requestUpdate();
    return;
  }
  fui::InputSnapshot input{};
  input.touchReleased = true;
  input.touchX = static_cast<int16_t>(x);
  input.touchY = static_cast<int16_t>(y);
  routeAction(interactions.route(input));
}
uint32_t TileRummyActivity::surfaceMeaning() const {
  uint32_t meaning = paintclock::kMeaningSeed;
  const auto mix = [&](uint32_t value) { meaning = paintclock::mixMeaning(meaning, value); };
  mix(static_cast<uint32_t>(flow.screen));
  mix(static_cast<uint32_t>(flow.view));
  mix(flow.page);
  mix(flow.activeSet + 1);
  mix(flow.game.turn);
  mix(flow.live());
  mix(flow.game.melded[flow.game.turn]);
  mix(flow.blocked);
  mix(tr::over(flow.game));
  mix(flow.itemCount());
  mix(flow.draft.table.setCount);
  mix(flow.draft.loose.count);
  mix(flow.game.poolCount > 0);
  mix(flow.setEditable());
  mix(flow.undoReady);
  mix(flow.canAdd());
  mix(flow.canRemove());
  mix(flow.canReturn());
  mix(flow.canRemove() && flow.selected > 0);
  mix(flow.canRemove() && flow.selected + 1 < flow.itemCount());
  // Visible availability drives live tile taps, not tile faces or local cursor.
  if (flow.view == ui::View::Hand)
    for (int i = flow.page * ui::kPageTiles; i < flow.itemCount() && i < (flow.page + 1) * ui::kPageTiles; ++i)
      mix(flow.handAvailable(i));
  const auto device = toybox::makeTarget(renderer).deviceContext();
  mix(device.width);
  mix(device.height);
  mix(device.safeArea.top);
  mix(device.safeArea.right);
  mix(device.safeArea.bottom);
  mix(device.safeArea.left);
  return meaning;
}
void TileRummyActivity::render(RenderLock&&) {
  renderer.clearScreen();
  auto target = toybox::makeTarget(renderer);
  const auto device = target.deviceContext();
  const fui::InputSnapshot input{};
  interactionsReady = false;
  toybox::Frame frame(target, device, input, interactions);
  toybox::Screen surface(frame);
  if (flow.screen == ui::Screen::Menu)
    ui::buildMenu(surface, ui::MenuModel{&flow});
  else
    ui::buildBoard(surface, ui::BoardModel{&flow});
  const int tiles = visibleTiles();
  fui::Rect focused{};
  if (focus >= 0 && focus < tiles)
    focused = ui::tileRect(device, flow, flow.page * ui::kPageTiles + focus);
  else if (focus >= tiles && focus - tiles < static_cast<int>(interactions.count()))
    focused = interactions.data()[focus - tiles].rect;
  if (!focused.empty())
    target.stroke(focused.inset(fui::Insets{3, 3, 3, 3}), fui::Paint::solid(fui::Color::Black), 2, 0, fui::CornersAll);
  interactionsReady = true;
  toybox::reportOverflow(interactions, "TILE RUMMY");
  const auto labels = mappedInput.mapLabels("BACK", "SELECT", "PREV", "NEXT");
  GUI.drawButtonHints(renderer, labels.btn1, labels.btn2, labels.btn3, labels.btn4);
  renderer.displayBuffer();
}
