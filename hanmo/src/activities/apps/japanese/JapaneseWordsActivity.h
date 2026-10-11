#pragma once
#include <array>

#include "JapaneseWords.h"
#include "activities/Activity.h"
#include "components/UiAppHost.h"

class JapaneseWordsActivity final : public Activity, protected UiAppHost {
 public:
  JapaneseWordsActivity(GfxRenderer& r, MappedInputManager& m)
      : Activity("JapaneseWords", r, m), UiAppHost(r) {}
  void onEnter() override;
  void onExit() override;
  void loop() override;
  void render(RenderLock&&) override;

 private:
  japanese::Words lesson_;
  GfxRenderer::Orientation orientation_ = GfxRenderer::Orientation::Portrait;
  bool addedWordFont_ = false;
  bool waitForConfirmRelease_ = false;
  std::array<char, 80> progress_{};
  std::array<char, 80> score_{};

  void action(int value);
  void build(UiScreen& screen);
  static void screen(UiScreen& screen, void* context);
  static void event(const freeink::ui::ActionEvent& event, void* context);
};
