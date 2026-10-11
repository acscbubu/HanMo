#include "SlidePuzzleActivity.h"

#include <Memory.h>

#include "../../components/UITheme.h"
#include "../Shelf.h"
#include "../ui/ToyboxFonts.h"
#include "../ui/ToyboxSeed.h"
#include "../ui/ToyboxTheme.h"

namespace {
namespace fui = freeink::ui;
namespace sp = slidepuzzle;
namespace ui = slidepuzzleui;
}  // namespace

std::unique_ptr<Activity> SlidePuzzleActivity::create(GfxRenderer& renderer, MappedInputManager& mappedInput) {
  // ActivityManager owns this object across frames; stack storage cannot outlive the factory.
  auto activity = makeUniqueNoThrow<SlidePuzzleActivity>(renderer, mappedInput);
  if (!activity) LOG_ERR("SLIDE", "OOM: SlidePuzzleActivity");
  return activity;
}

void SlidePuzzleActivity::onEnter() {
  Activity::onEnter();
  toybox::ensureFonts(renderer);
  selectedWidth = sp::kMinWidth;
  goTo(sp::Screen::Menu);
}

void SlidePuzzleActivity::goTo(const sp::Screen next) {
  screen = next;
  interactionsReady = false;
  requestUpdate();
}

void SlidePuzzleActivity::startGame(const int width) {
  selectedWidth = sp::supportedWidth(width);
  sp::shuffle(game, selectedWidth, toybox::seed());
  goTo(sp::Screen::Board);
}

void SlidePuzzleActivity::routeAction(const fui::ActionEvent& event) {
  switch (event.action) {
    case ui::ActionSize:
      if (screen == sp::Screen::Menu) startGame(event.value);
      return;
    case ui::ActionMenu:
      if (screen != sp::Screen::Menu) goTo(sp::Screen::Menu);
      return;
    case ui::ActionAgain:
      if (screen == sp::Screen::Done) startGame(selectedWidth);
      return;
    default:
      return;
  }
}

void SlidePuzzleActivity::routeCellTap(const int x, const int y) {
  if (screen != sp::Screen::Board || sp::solved(game) || !surfaceRevealed()) return;
  const fui::DeviceContext device = toybox::makeTarget(renderer).deviceContext();
  const int index = ui::cellAt(device, game, x, y);
  if (index < 0 || !sp::slide(game, index % game.width, index / game.width)) return;
  if (sp::solved(game)) {
    goTo(sp::Screen::Done);
  } else {
    requestUpdate();
  }
}

void SlidePuzzleActivity::loop() {
  if (mappedInput.wasReleased(MappedInputManager::Button::Back)) {
    if (screen == sp::Screen::Menu) {
      shelf::leave(renderer, mappedInput);
    } else {
      goTo(sp::Screen::Menu);
    }
    return;
  }
  fui::InputSnapshot input{};
  int x = 0;
  int y = 0;
  if (!interactionsReady || !mappedInput.wasScreenTapped(x, y)) return;
  input.touchReleased = true;
  input.touchX = static_cast<int16_t>(x);
  input.touchY = static_cast<int16_t>(y);
  const fui::ActionEvent event = interactions.route(input);
  if (event.action != fui::NO_ACTION) {
    routeAction(event);
    return;
  }
  routeCellTap(x, y);
}

uint32_t SlidePuzzleActivity::surfaceMeaning() const {
  const uint32_t mode = paintclock::mixMeaning(paintclock::kMeaningSeed, static_cast<uint32_t>(screen));
  const uint32_t size = paintclock::mixMeaning(mode, static_cast<uint32_t>(game.width));
  return paintclock::mixMeaning(size, screen == sp::Screen::Board && !sp::solved(game) ? 1u : 0u);
}

void SlidePuzzleActivity::render(RenderLock&&) {
  renderer.clearScreen();
  fui::GfxRendererTarget target = toybox::makeTarget(renderer);
  const fui::DeviceContext device = target.deviceContext();
  const fui::InputSnapshot noInput{};
  interactionsReady = false;
  toybox::Frame frame(target, device, noInput, interactions);
  toybox::Screen surface(frame);
  if (screen == sp::Screen::Menu) {
    ui::buildMenu(surface, ui::MenuModel{selectedWidth});
  } else {
    ui::buildBoard(surface, ui::BoardModel{&game, screen == sp::Screen::Done});
  }
  interactionsReady = true;
  toybox::reportOverflow(interactions, "Slide Puzzle");
  const auto labels = mappedInput.mapLabels("Back", "", "", "");
  GUI.drawButtonHints(renderer, labels.btn1, labels.btn2, labels.btn3, labels.btn4);
  renderer.displayBuffer();
}
