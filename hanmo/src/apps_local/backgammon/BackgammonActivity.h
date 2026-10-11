#pragma once

#include <memory>
#include "../../activities/Activity.h"
#include "BackgammonScreens.h"

class BackgammonActivity final : public Activity {
 public:
  BackgammonActivity(GfxRenderer& renderer, MappedInputManager& mappedInput)
      : Activity("Backgammon", renderer, mappedInput) {}
  static std::unique_ptr<Activity> create(GfxRenderer& renderer, MappedInputManager& mappedInput);
  void onEnter() override;
  void loop() override;
  void render(RenderLock&&) override;
 private:
  void routeAction(const freeink::ui::ActionEvent& event);
  uint32_t surfaceMeaning() const override;
  backgammonui::Flow flow;
  toybox::Interactions interactions;
  bool interactionsReady = false;
};
