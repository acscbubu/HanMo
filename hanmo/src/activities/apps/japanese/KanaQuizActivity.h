#pragma once
#include <array>

#include "KanaData.generated.h"
#include "KanaQuiz.h"
#include "activities/Activity.h"
#include "components/UiAppHost.h"

class KanaQuizActivity final : public Activity, protected UiAppHost {
 public:
  KanaQuizActivity(GfxRenderer& r, MappedInputManager& m)
      : Activity("KanaQuiz", r, m), UiAppHost(r), quiz_(1) {}
  void onEnter() override;
  void onExit() override;
  void loop() override;
  void render(RenderLock&&) override;

 private:
  kana::Quiz quiz_;
  GfxRenderer::Orientation orientation_ = GfxRenderer::Orientation::Portrait;
  std::array<char, 96> reading_{};
  std::array<char, 80> progress_{};
  std::array<char, 80> score_{};

  void action(int value);
  void build(UiScreen& screen);
  void drawGlyphs(const kana::Card& card, const freeink::ui::Rect& area);
  void drawPrompt(const kana::Card& card, const freeink::ui::Rect& area);
  void drawAnswer(const kana::Card& card, const freeink::ui::Rect& area);
  static void screen(UiScreen& screen, void* context);
  static void event(const freeink::ui::ActionEvent& event, void* context);
};
