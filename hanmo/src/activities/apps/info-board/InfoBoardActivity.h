#pragma once
#include <array>

#include "activities/Activity.h"
#include "components/UiAppHost.h"
#include "network/InfoBoardData.h"
class InfoBoardActivity final : public Activity, protected UiAppHost {
 public:
  InfoBoardActivity(GfxRenderer& r, MappedInputManager& m) : Activity("InfoBoard", r, m), UiAppHost(r) {}
  void onEnter() override;
  void loop() override;
  void render(RenderLock&&) override;
  bool preventAutoSleep() override { return true; }

 private:
  uint8_t scene_ = 0;
  uint32_t generation_ = 0;
  bool config_ = false;
  uint32_t rotated_ = 0, paintedMinute_ = 0;
  bool clockSyncRequested_ = false;
  std::array<info_board::Data, 3> data_{};
  std::array<uint32_t, 3> attempted_{}, received_{};
  std::array<bool, 3> tried_{};
  void action(int value);
  void build(UiScreen& screen);
  static void screen(UiScreen&, void*);
  static void event(const freeink::ui::ActionEvent&, void*);
};
