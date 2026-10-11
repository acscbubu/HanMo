#include "MemoryActivity.h"

#include <Memory.h>

#include "../Shelf.h"
#include "../../components/UITheme.h"
#include "../ui/ToyboxFonts.h"
#include "../ui/ToyboxSeed.h"
#include "../ui/ToyboxTheme.h"

namespace {
namespace fui = freeink::ui;
namespace mm = memorymatch;
namespace ui = memoryui;
}

std::unique_ptr<Activity> MemoryActivity::create(GfxRenderer& renderer, MappedInputManager& mappedInput) {
  return makeUniqueNoThrow<MemoryActivity>(renderer, mappedInput);
}

void MemoryActivity::onEnter() {
  Activity::onEnter();
  toybox::ensureFonts(renderer);
  screen = mm::Screen::Menu;
  selectedLevel = 0;
  cursor = mm::kNoCell;
  interactionsReady = false;
  requestUpdate();
}

void MemoryActivity::goTo(const mm::Screen next) {
  screen = next;
  cursor = mm::kNoCell;
  interactionsReady = false;
  requestUpdate();
}

void MemoryActivity::startLevel(const int level) {
  selectedLevel = level < 0 || level >= mm::kLevelCount ? 0 : level;
  mm::start(game, selectedLevel, toybox::seed());
  cursor = mm::kNoCell;
  goTo(mm::Screen::Board);
}

void MemoryActivity::routeCardTap(const int x, const int y) {
  if (screen != mm::Screen::Board || !surfaceRevealed()) return;
  const fui::DeviceContext device = toybox::makeTarget(renderer).deviceContext();
  const int index = ui::cardAt(device, game, x, y);
  if (index == mm::kNoCell) return;
  if (mm::expose(game, index)) {
    cursor = game.secondPick != mm::kNoCell ? game.secondPick : game.firstPick;
    if (mm::complete(game)) {
      cursor = mm::kNoCell;
      goTo(mm::Screen::Done);
    } else {
      requestUpdate();
    }
  }
}

void MemoryActivity::routeAction(const fui::ActionEvent& event) {
  switch (event.action) {
    case ui::ActionLevel:
      if (screen == mm::Screen::Menu) startLevel(event.value);
      return;
    case ui::ActionNext:
      if (screen == mm::Screen::Board && mm::awaitingMismatch(game) && mm::resolveMismatch(game)) {
        cursor = mm::kNoCell;
        requestUpdate();
      }
      return;
    case ui::ActionMenu:
      if (screen == mm::Screen::Board || screen == mm::Screen::Done) shelf::leave(renderer, mappedInput);
      return;
    case ui::ActionAgain:
      if (screen == mm::Screen::Done) startLevel(selectedLevel);
      return;
    default:
      return;
  }
}

void MemoryActivity::loop() {
  if (mappedInput.wasReleased(MappedInputManager::Button::Back)) {
    if (mm::leavesApp(screen)) {
      shelf::leave(renderer, mappedInput);
    } else {
      goTo(mm::back(screen));
    }
    return;
  }

  fui::InputSnapshot input;
  int tapX = 0;
  int tapY = 0;
  if (mappedInput.wasScreenTapped(tapX, tapY)) {
    input.touchReleased = true;
    input.touchX = static_cast<int16_t>(tapX);
    input.touchY = static_cast<int16_t>(tapY);
  }
  if (!input.touchReleased || !interactionsReady) return;

  if (screen == mm::Screen::Board) {
    const fui::DeviceContext device = toybox::makeTarget(renderer).deviceContext();
    if (ui::cardAt(device, game, tapX, tapY) != mm::kNoCell) {
      routeCardTap(tapX, tapY);
      return;
    }
  }
  routeAction(interactions.route(input));
}

uint32_t MemoryActivity::surfaceMeaning() const {
  const uint32_t withScreen = paintclock::mixMeaning(paintclock::kMeaningSeed, static_cast<uint32_t>(screen));
  const uint32_t withLevel = paintclock::mixMeaning(withScreen, static_cast<uint32_t>(game.level));
  const bool live = screen == mm::Screen::Board && !mm::complete(game) && !mm::awaitingMismatch(game);
  return paintclock::mixMeaning(withLevel, live ? 1u : 0u);
}

void MemoryActivity::render(RenderLock&&) {
  renderer.clearScreen();
  fui::GfxRendererTarget target = toybox::makeTarget(renderer);
  const fui::DeviceContext device = target.deviceContext();
  const fui::InputSnapshot noInput{};
  interactionsReady = false;
  toybox::Frame frame(target, device, noInput, interactions);
  toybox::Screen surface(frame);

  if (screen == mm::Screen::Menu) {
    ui::MenuModel model;
    model.selected = selectedLevel;
    ui::buildMenu(surface, model);
  } else {
    ui::BoardModel model;
    model.game = &game;
    model.cursor = cursor;
    ui::buildBoard(surface, model);
  }

  interactionsReady = true;
  toybox::reportOverflow(interactions, "Memory Match");

  const auto labels = mappedInput.mapLabels("Back", "", "", "");
  GUI.drawButtonHints(renderer, labels.btn1, labels.btn2, labels.btn3, labels.btn4);
  renderer.displayBuffer();
}
