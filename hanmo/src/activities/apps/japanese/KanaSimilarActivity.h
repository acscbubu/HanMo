#pragma once

#include "KanaSimilar.h"
#include "activities/Activity.h"
#include "components/UiAppHost.h"

class KanaSimilarActivity final : public Activity, protected UiAppHost {
 public:
  KanaSimilarActivity(GfxRenderer& renderer, MappedInputManager& input)
      : Activity("KanaSimilar", renderer, input), UiAppHost(renderer) {}

  void onEnter() override;
  void onExit() override;
  void loop() override;
  void render(RenderLock&&) override;

 private:
  kana::Similar lesson_;
  GfxRenderer::Orientation orientation_ = GfxRenderer::Orientation::Portrait;
  int focusedChoice_ = 0;

  void action(int value);
  void build(UiScreen& screen);
  void drawCompare(UiScreen& screen, const freeink::ui::Rect& area);
  void drawTestPrompt(UiScreen& screen, const freeink::ui::Rect& area);
  void drawTestAnswer(UiScreen& screen, const freeink::ui::Rect& area);
  void drawChoiceGlyph(int cardId, const freeink::ui::Rect& area);
  void drawPairCard(int cardId, int x, int width, int glyphY, int readingY);
  void addButton(UiScreen& screen, const char* label, int value, const freeink::ui::Rect& rect,
                 bool enabled = true, freeink::ui::State state = freeink::ui::StateNormal);
  const char* hintLine(int line) const;

  static void screen(UiScreen& screen, void* context);
  static void event(const freeink::ui::ActionEvent& event, void* context);
};
