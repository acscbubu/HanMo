#pragma once

#include <memory>

#include "../../activities/Activity.h"
#include "../ui/ToyboxScreen.h"
#include "SlidePuzzleCore.h"
#include "SlidePuzzleFlow.h"
#include "SlidePuzzleScreens.h"

class SlidePuzzleActivity final : public Activity {
 public:
  SlidePuzzleActivity(GfxRenderer& renderer, MappedInputManager& mappedInput)
      : Activity("Slide Puzzle", renderer, mappedInput) {}

  static std::unique_ptr<Activity> create(GfxRenderer& renderer, MappedInputManager& mappedInput);
  void onEnter() override;
  void loop() override;
  void render(RenderLock&&) override;

 private:
  void startGame(int width);
  void goTo(slidepuzzle::Screen next);
  void routeAction(const freeink::ui::ActionEvent& event);
  void routeCellTap(int x, int y);
  uint32_t surfaceMeaning() const override;

  slidepuzzle::Screen screen = slidepuzzle::Screen::Menu;
  slidepuzzle::Game game{};
  int selectedWidth = slidepuzzle::kMinWidth;
  toybox::Interactions interactions;
  bool interactionsReady = false;
};
