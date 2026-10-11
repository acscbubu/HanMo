#include "MahjongActivity.h"

#include <Memory.h>

#include "../Shelf.h"
#include "../../components/UITheme.h"
#include "../ui/ToyboxFonts.h"
#include "../ui/ToyboxSeed.h"
#include "../ui/ToyboxTheme.h"

namespace fui = freeink::ui;
namespace ui = mahjongui;

std::unique_ptr<Activity> MahjongActivity::create(GfxRenderer& renderer, MappedInputManager& mappedInput) {
  // Activity lifetime crosses dispatch frames; bounded game and controls live
  // inside this single nothrow allocation. Factory caller handles nullptr.
  return makeUniqueNoThrow<MahjongActivity>(renderer, mappedInput);
}

void MahjongActivity::onEnter() {
  Activity::onEnter();
  toybox::ensureFonts(renderer);
  flow.screen = ui::Screen::Menu;
  flow.selected = mahjong::kNoSlot;
  interactionsReady = false;
  requestUpdate();
}

void MahjongActivity::startDeal() {
  flow.start(toybox::seed());
  interactionsReady = false;
  requestUpdate();
}

void MahjongActivity::routeAction(const fui::ActionEvent& event) {
  if (event.action == ui::ActionStart && flow.screen == ui::Screen::Menu) startDeal();
  else if (event.action == ui::ActionNew && flow.screen != ui::Screen::Menu) startDeal();
  else if (event.action == ui::ActionMenu && flow.screen != ui::Screen::Menu) {
    flow.menu();
    interactionsReady = false;
    requestUpdate();
  }
}

void MahjongActivity::loop() {
  if (mappedInput.wasReleased(MappedInputManager::Button::Back)) {
    if (flow.screen == ui::Screen::Menu) shelf::leave(renderer, mappedInput);
    else if (flow.cancel()) requestUpdate();
    else {
      flow.menu();
      interactionsReady = false;
      requestUpdate();
    }
    return;
  }
  int x = 0, y = 0;
  if (!mappedInput.wasScreenTapped(x, y) || !interactionsReady || !surfaceRevealed()) return;
  if (flow.screen == ui::Screen::Board) {
    const auto device = toybox::makeTarget(renderer).deviceContext();
    const int slot = ui::tileAt(device, flow.game, x, y);
    if (slot != mahjong::kNoSlot) {
      if (flow.pick(slot)) requestUpdate();
      return;
    }
  }
  fui::InputSnapshot input{};
  input.touchReleased = true; input.touchX = static_cast<int16_t>(x); input.touchY = static_cast<int16_t>(y);
  routeAction(interactions.route(input));
}

uint32_t MahjongActivity::surfaceMeaning() const {
  auto meaning = paintclock::mixMeaning(paintclock::kMeaningSeed, static_cast<uint32_t>(flow.screen));
  meaning = paintclock::mixMeaning(meaning, mahjong::kColumns);
  meaning = paintclock::mixMeaning(meaning, mahjong::kRows);
  meaning = paintclock::mixMeaning(meaning, mahjong::kLayers);
  const auto device = toybox::makeTarget(renderer).deviceContext();
  meaning = paintclock::mixMeaning(meaning, static_cast<uint32_t>(device.orientation));
  const auto safe = device.safeRect();
  for (const int value : {device.width, device.height, safe.x, safe.y, safe.width, safe.height})
    meaning = paintclock::mixMeaning(meaning, static_cast<uint32_t>(value));
  const bool live = flow.screen == ui::Screen::Board && !ui::tileRect(device, 0).empty();
  // Tile contents and local selection do not change the fixed core layout.
  return paintclock::mixMeaning(meaning, live ? 1u : 0u);
}

void MahjongActivity::render(RenderLock&&) {
  renderer.clearScreen();
  auto target = toybox::makeTarget(renderer);
  const auto device = target.deviceContext();
  const fui::InputSnapshot noInput{};
  interactionsReady = false;
  toybox::Frame frame(target, device, noInput, interactions);
  toybox::Screen surface(frame);
  if (flow.screen == ui::Screen::Menu) ui::buildMenu(surface);
  else ui::buildBoard(surface, ui::BoardModel{&flow.game, flow.selected});
  interactionsReady = true;
  toybox::reportOverflow(interactions, "Mahjong Solitaire");
  const auto labels = mappedInput.mapLabels("Back", "", "", "");
  GUI.drawButtonHints(renderer, labels.btn1, labels.btn2, labels.btn3, labels.btn4);
  renderer.displayBuffer();
}
