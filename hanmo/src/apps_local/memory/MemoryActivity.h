#pragma once

#include <memory>

#include "../../activities/Activity.h"
#include "../ui/ToyboxScreen.h"
#include "MemoryCore.h"
#include "MemoryFlow.h"
#include "MemoryScreens.h"

class MemoryActivity final : public Activity {
 public:
  MemoryActivity(GfxRenderer& renderer, MappedInputManager& mappedInput)
      : Activity("Memory Match", renderer, mappedInput) {}
  ~MemoryActivity() override = default;

  static std::unique_ptr<Activity> create(GfxRenderer& renderer, MappedInputManager& mappedInput);

  void onEnter() override;
  void loop() override;
  void render(RenderLock&&) override;

 private:
  void startLevel(int level);
  void goTo(memorymatch::Screen next);
  void routeAction(const freeink::ui::ActionEvent& event);
  void routeCardTap(int x, int y);

  uint32_t surfaceMeaning() const override;

  memorymatch::Screen screen = memorymatch::Screen::Menu;
  memorymatch::Game game{};
  int selectedLevel = 0;
  int cursor = memorymatch::kNoCell;

  toybox::Interactions interactions;
  bool interactionsReady = false;
};
