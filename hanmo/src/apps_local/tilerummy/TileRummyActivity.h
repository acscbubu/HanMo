#pragma once
#include <memory>

#include "../../activities/Activity.h"
#include "TileRummyFlow.h"
#include "TileRummyScreens.h"

class TileRummyActivity final : public Activity {
 public:
  TileRummyActivity(GfxRenderer& renderer, MappedInputManager& mappedInput)
      : Activity("TILE RUMMY", renderer, mappedInput) {}
  static std::unique_ptr<Activity> create(GfxRenderer& renderer, MappedInputManager& mappedInput);
  void onEnter() override;
  void loop() override;
  void render(RenderLock&&) override;

 private:
  void startGame();
  void routeAction(const freeink::ui::ActionEvent& event);
  int visibleTiles() const;
  uint32_t surfaceMeaning() const override;
  tilerummyui::Flow flow{};
  toybox::Interactions interactions;
  bool interactionsReady = false;
  int focus = -1;
};
