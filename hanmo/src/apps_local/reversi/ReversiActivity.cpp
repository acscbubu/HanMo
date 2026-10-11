#include "ReversiActivity.h"

#include <Memory.h>

#include "../Shelf.h"
#include "../../components/UITheme.h"
#include "../ui/ToyboxFonts.h"
#include "../ui/ToyboxTheme.h"

namespace {
namespace fui = freeink::ui;
namespace rv = reversi;
namespace ui = reversiui;
}

std::unique_ptr<Activity> ReversiActivity::create(GfxRenderer& renderer, MappedInputManager& mappedInput) {
  // ActivityManager owns the instance across frames; stack storage cannot.
  auto activity = makeUniqueNoThrow<ReversiActivity>(renderer, mappedInput);
  if (!activity) LOG_ERR("REVERSI", "OOM: ReversiActivity");
  return activity;
}

void ReversiActivity::onEnter() {
  Activity::onEnter();
  toybox::ensureFonts(renderer);
  screen = rv::Screen::Menu;
  passedSide = rv::kEmpty;
  cursor = rv::kNoCell;
  waitForConfirmRelease = mappedInput.isPressed(MappedInputManager::Button::Confirm);
  interactionsReady = false;
  requestUpdate();
}

void ReversiActivity::goTo(const rv::Screen next) {
  screen = next;
  if (next != rv::Screen::Board) cursor = rv::kNoCell;
  interactionsReady = false;
  requestUpdate();
}

void ReversiActivity::startGame() {
  rv::start(game);  // Fixed opening, no randomness or AI opponent.
  passedSide = rv::kEmpty;
  selectFirstLegal();
  goTo(rv::Screen::Board);
}

void ReversiActivity::selectFirstLegal() {
  cursor = rv::kNoCell;
  for (int index = 0; index < rv::kCells; ++index) {
    if (rv::legalAt(game, index % rv::kSize, index / rv::kSize)) {
      cursor = index;
      return;
    }
  }
}

void ReversiActivity::routeCellTap(const int x, const int y) {
  if (screen != rv::Screen::Board || !surfaceRevealed()) return;
  const auto device = toybox::makeTarget(renderer).deviceContext();
  const int index = ui::cellAt(device, x, y);
  if (index == rv::kNoCell) return;
  playCell(index);
}

void ReversiActivity::playCell(const int index) {
  if (screen != rv::Screen::Board || index < 0 || index >= rv::kCells) return;
  const uint8_t mover = game.turn;
  if (!rv::play(game, index % rv::kSize, index / rv::kSize)) return;
  // Core play() already settles: same mover means the other side had to pass.
  passedSide = !rv::over(game) && game.turn == mover ? rv::other(mover) : rv::kEmpty;
  if (rv::over(game)) goTo(rv::Screen::Done);
  else {
    selectFirstLegal();
    requestUpdate();
  }
}

void ReversiActivity::routeAction(const fui::ActionEvent& event) {
  if (event.action == ui::ActionStart && screen == rv::Screen::Menu) startGame();
  if (event.action == ui::ActionMenu && screen != rv::Screen::Menu) shelf::leave(renderer, mappedInput);
  if (event.action == ui::ActionAgain && screen == rv::Screen::Done) startGame();
}

void ReversiActivity::loop() {
  if (mappedInput.wasReleased(MappedInputManager::Button::Back)) {
    if (rv::leavesApp(screen)) shelf::leave(renderer, mappedInput);
    else goTo(rv::back(screen));
    return;
  }
  // Consume an inherited Confirm release without suppressing independent taps.
  const bool consumeConfirm = waitForConfirmRelease;
  if (waitForConfirmRelease && !mappedInput.isPressed(MappedInputManager::Button::Confirm))
    waitForConfirmRelease = false;
  if (!interactionsReady) return;
  if (!consumeConfirm && mappedInput.wasReleased(MappedInputManager::Button::Confirm)) {
    if (screen == rv::Screen::Menu && interactions.routable()) startGame();
    else if (screen == rv::Screen::Done && interactions.routable()) startGame();
    else if (screen == rv::Screen::Board && surfaceRevealed()) playCell(cursor);
    return;
  }
  if (screen == rv::Screen::Board && surfaceRevealed()) {
    int dc = 0, dr = 0;
    if (mappedInput.wasReleased(MappedInputManager::Button::Left)) dc = -1;
    else if (mappedInput.wasReleased(MappedInputManager::Button::Right)) dc = 1;
    else if (mappedInput.wasReleased(MappedInputManager::Button::Up)) dr = -1;
    else if (mappedInput.wasReleased(MappedInputManager::Button::Down)) dr = 1;
    if (dc || dr) {
      if (cursor == rv::kNoCell) selectFirstLegal();
      if (cursor != rv::kNoCell) {
        const int column = (cursor % rv::kSize + dc + rv::kSize) % rv::kSize;
        const int row = (cursor / rv::kSize + dr + rv::kSize) % rv::kSize;
        cursor = row * rv::kSize + column;
        requestUpdate();
      }
      return;
    }
  }
  int x = 0, y = 0;
  if (!mappedInput.wasScreenTapped(x, y) || !interactionsReady) return;
  if (screen == rv::Screen::Board) {
    const auto device = toybox::makeTarget(renderer).deviceContext();
    if (ui::cellAt(device, x, y) != rv::kNoCell) {
      routeCellTap(x, y);
      return;
    }
  }
  fui::InputSnapshot input{};
  input.touchReleased = true;
  input.touchX = static_cast<int16_t>(x);
  input.touchY = static_cast<int16_t>(y);
  routeAction(interactions.route(input));
}

uint32_t ReversiActivity::surfaceMeaning() const {
  uint32_t meaning = paintclock::mixMeaning(paintclock::kMeaningSeed, static_cast<uint32_t>(screen));
  meaning = paintclock::mixMeaning(meaning, screen == rv::Screen::Board && !rv::over(game) ? 1u : 0u);
  // Which local player's disc a tap places changes uniformly for every cell.
  meaning = paintclock::mixMeaning(meaning, game.turn);
  const auto device = toybox::makeTarget(renderer).deviceContext();
  const auto safe = device.safeRect();
  for (const int value : {device.width, device.height, safe.x, safe.y, safe.width, safe.height})
    meaning = paintclock::mixMeaning(meaning, static_cast<uint32_t>(value));
  return meaning;
}

void ReversiActivity::render(RenderLock&&) {
  renderer.clearScreen();
  auto target = toybox::makeTarget(renderer);
  const auto device = target.deviceContext();
  const fui::InputSnapshot noInput{};
  interactionsReady = false;
  toybox::Frame frame(target, device, noInput, interactions);
  toybox::Screen surface(frame);
  if (screen == rv::Screen::Menu) ui::buildMenu(surface);
  else ui::buildBoard(surface, ui::BoardModel{&game, passedSide, cursor});
  interactionsReady = true;
  toybox::reportOverflow(interactions, "Reversi");
  const auto labels = mappedInput.mapLabels("Back", screen == rv::Screen::Menu ? "Start" :
      screen == rv::Screen::Done ? "Again" : "Place", screen == rv::Screen::Board ? "<" : "",
      screen == rv::Screen::Board ? ">" : "");
  GUI.drawButtonHints(renderer, labels.btn1, labels.btn2, labels.btn3, labels.btn4);
  renderer.displayBuffer();
}
