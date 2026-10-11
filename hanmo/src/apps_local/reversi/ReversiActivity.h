#pragma once

#include <memory>

#include "../../activities/Activity.h"
#include "../ui/ToyboxScreen.h"
#include "ReversiCore.h"
#include "ReversiFlow.h"
#include "ReversiScreens.h"

class ReversiActivity final : public Activity {
 public:
  ReversiActivity(GfxRenderer& renderer, MappedInputManager& mappedInput)
      : Activity("Reversi", renderer, mappedInput) {}
  ~ReversiActivity() override = default;

  static std::unique_ptr<Activity> create(GfxRenderer& renderer, MappedInputManager& mappedInput);
  void onEnter() override;
  void loop() override;
  void render(RenderLock&&) override;

 private:
  void startGame();
  void goTo(reversi::Screen next);
  void routeAction(const freeink::ui::ActionEvent& event);
  void routeCellTap(int x, int y);
  void playCell(int index);
  void selectFirstLegal();
  uint32_t surfaceMeaning() const override;

  reversi::Screen screen = reversi::Screen::Menu;
  reversi::Game game{};
  uint8_t passedSide = reversi::kEmpty;
  int cursor = reversi::kNoCell;
  bool waitForConfirmRelease = false;
  toybox::Interactions interactions;
  bool interactionsReady = false;
};
