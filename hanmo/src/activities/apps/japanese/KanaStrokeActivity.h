#pragma once

#include <array>
#include "KanaStroke.h"
#include "activities/Activity.h"
#include "components/UiAppHost.h"

class KanaStrokeActivity final : public Activity, protected UiAppHost {
 public:
  KanaStrokeActivity(GfxRenderer& r, MappedInputManager& m)
      : Activity("KanaStroke", r, m), UiAppHost(r) {}
  void onEnter() override;
  void onExit() override;
  void loop() override;
  void render(RenderLock&&) override;

 private:
  kana::StrokeLesson lesson_;
  GfxRenderer::Orientation orientation_ = GfxRenderer::Orientation::Portrait;
  std::array<char, 64> position_{};
  std::array<char, 80> progress_{};
  std::array<char, 64> soundReading_{};

  void action(int value);
  void build(UiScreen& screen);
  void drawGlyph(const kana::GlyphStrokes& glyph, int x, int y, int side);
  static void screen(UiScreen& screen, void* context);
  static void event(const freeink::ui::ActionEvent& event, void* context);
};
