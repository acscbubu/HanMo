#include "BackgammonActivity.h"

#include <Memory.h>
#include "../Shelf.h"
#include "../../components/UITheme.h"
#include "../ui/ToyboxFonts.h"
#include "../ui/ToyboxSeed.h"
#include "../ui/ToyboxTheme.h"

namespace ui = backgammonui;
namespace fui = freeink::ui;

std::unique_ptr<Activity> BackgammonActivity::create(GfxRenderer& renderer, MappedInputManager& mappedInput) {
  return makeUniqueNoThrow<BackgammonActivity>(renderer, mappedInput);
}
void BackgammonActivity::onEnter() {
  Activity::onEnter();
  toybox::ensureFonts(renderer);
  flow = ui::Flow{};
  interactionsReady = false;
  requestUpdate();
}
void BackgammonActivity::routeAction(const fui::ActionEvent& event) {
  bool changed = false;
  switch (event.action) {
    case ui::ActionStart:
      if (flow.screen == ui::Mode::Menu) { flow.start(toybox::seed()); changed = true; }
      break;
    case ui::ActionRoll: changed = flow.roll(); break;
    case ui::ActionDie: changed = flow.chooseDie(event.value); break;
    case ui::ActionBar: changed = flow.pick(backgammon::kBar); break;
    case ui::ActionOff: changed = flow.pick(ui::kOff); break;
    case ui::ActionEnd: changed = flow.end(); break;
    case ui::ActionAgain:
      if (flow.screen == ui::Mode::Done) { flow.start(toybox::seed()); changed = true; }
      break;
    case ui::ActionMenu: changed = flow.menu(); break;
    default: break;
  }
  if (changed) { interactionsReady = false; requestUpdate(); }
}
void BackgammonActivity::loop() {
  if (mappedInput.wasReleased(MappedInputManager::Button::Back)) {
    if (flow.screen == ui::Mode::Menu) shelf::leave(renderer, mappedInput);
    else { flow.menu(); interactionsReady = false; requestUpdate(); }
    return;
  }
  fui::InputSnapshot input{};
  int x = 0, y = 0;
  if (!interactionsReady || !mappedInput.wasScreenTapped(x, y)) return;
  if (flow.screen == ui::Mode::Board) {
    const auto device = toybox::makeTarget(renderer).deviceContext();
    const int at = ui::pointAt(device, x, y);
    if (at != ui::kNoPoint) {
      if (surfaceRevealed() && flow.pick(at)) { interactionsReady = false; requestUpdate(); }
      return;
    }
  }
  input.touchReleased = true;
  input.touchX = static_cast<int16_t>(x);
  input.touchY = static_cast<int16_t>(y);
  routeAction(interactions.route(input));
}
uint32_t BackgammonActivity::surfaceMeaning() const {
  uint32_t meaning = paintclock::kMeaningSeed;
  const auto mix = [&meaning](uint32_t value) { meaning = paintclock::mixMeaning(meaning, value); };
  mix(static_cast<uint32_t>(flow.screen));
  const auto device = toybox::makeTarget(renderer).deviceContext();
  const auto safe = device.safeRect();
  mix(device.width); mix(device.height);
  mix(safe.x); mix(safe.y); mix(safe.width); mix(safe.height);
  mix(flow.game.turn);
  mix(flow.rolled ? 1u : 0u);
  mix(flow.live() ? 1u : 0u);
  mix(flow.canEnd() ? 1u : 0u);
  mix(flow.game.bar[flow.game.turn] != 0 ? 1u : 0u);
  for (const auto die : flow.game.die) mix(die);
  mix(flow.pips());
  // FROM is not a cosmetic cursor: it turns a point tap into a destination move.
  mix(static_cast<uint32_t>(flow.from));
  return meaning;
}
void BackgammonActivity::render(RenderLock&&) {
  renderer.clearScreen();
  auto target = toybox::makeTarget(renderer);
  const auto device = target.deviceContext();
  const fui::InputSnapshot noInput{};
  interactionsReady = false;
  toybox::Frame frame(target, device, noInput, interactions);
  toybox::Screen screen(frame);
  if (flow.screen == ui::Mode::Menu) ui::buildMenu(screen);
  else ui::buildBoard(screen, ui::BoardModel{&flow});
  interactionsReady = true;
  toybox::reportOverflow(interactions, "Backgammon");
  const auto labels = mappedInput.mapLabels("Back", "", "", "");
  GUI.drawButtonHints(renderer, labels.btn1, labels.btn2, labels.btn3, labels.btn4);
  renderer.displayBuffer();
}
