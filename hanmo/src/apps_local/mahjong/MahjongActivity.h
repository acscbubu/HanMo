#pragma once

#include <memory>

#include "../../activities/Activity.h"
#include "MahjongScreens.h"

class MahjongActivity final : public Activity {
 public:
  MahjongActivity(GfxRenderer& renderer, MappedInputManager& mappedInput)
      : Activity("Mahjong Solitaire", renderer, mappedInput) {}
  static std::unique_ptr<Activity> create(GfxRenderer& renderer, MappedInputManager& mappedInput);
  void onEnter() override;
  void loop() override;
  void render(RenderLock&&) override;
  uint32_t surfaceMeaning() const override;

 private:
  void startDeal();
  void routeAction(const freeink::ui::ActionEvent& event);

  mahjongui::Flow flow;
  toybox::Interactions interactions;
  bool interactionsReady = false;
};
