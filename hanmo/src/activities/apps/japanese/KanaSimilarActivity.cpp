#include "KanaSimilarActivity.h"

#include <EpdFontFamily.h>
#include <I18n.h>
#include <builtinFonts/hanmo_kana_52.h>
#include <cstdio>

#include "KanaData.generated.h"
#include "components/UITheme.h"
#include "fontIds.h"

namespace fui = freeink::ui;
namespace {
constexpr int kBigFontId = 0x4A510034;
const EpdFont kBigFont(&hanmo_kana_52);
const EpdFontFamily kBigFamily(&kBigFont);
constexpr int kGap = 8;
constexpr int kButtonHeight = 52;
const char* text(StrId id) { return I18N.get(id); }
}  // namespace

void KanaSimilarActivity::onEnter() {
  Activity::onEnter();
  orientation_ = renderer.getOrientation();
  renderer.setOrientation(GfxRenderer::Orientation::Portrait);
  if (!renderer.getFontMap().count(kBigFontId)) renderer.insertFont(kBigFontId, kBigFamily);
  lesson_ = kana::Similar{};
  focusedChoice_ = 0;
  resetUi();
  app.on(1, &KanaSimilarActivity::event, this);
  app.setScreen(&KanaSimilarActivity::screen, this);
  requestUpdate();
}

void KanaSimilarActivity::onExit() {
  renderer.setOrientation(orientation_);
  Activity::onExit();
}

void KanaSimilarActivity::screen(UiScreen& s, void* context) {
  static_cast<KanaSimilarActivity*>(context)->build(s);
}
void KanaSimilarActivity::event(const fui::ActionEvent& e, void* context) {
  static_cast<KanaSimilarActivity*>(context)->action(e.value);
}

void KanaSimilarActivity::action(int value) {
  if (value == 0) {
    if (!lesson_.back()) {
      app.clearTapFlash();
      finish();
      return;
    }
    app.clearTapFlash();
    focusedChoice_ = 0;
    requestUpdate();
    return;
  }
  bool changed = false;
  {
    RenderLock lock(*this);
    if (value == 1) changed = lesson_.stepCompare(-1);
    if (value == 2) changed = lesson_.stepCompare(1);
    if (value == 3) {
      changed = lesson_.startTest();
      if (changed) focusedChoice_ = 0;
    }
    if (value == 4 || value == 5) {
      focusedChoice_ = value - 4;
      changed = lesson_.choose(focusedChoice_ == 0 ? lesson_.leftChoiceCardId() : lesson_.rightChoiceCardId());
    }
    if (value == 6) {
      changed = lesson_.next();
      if (changed) focusedChoice_ = 0;
    }
    if (value == 7) {
      changed = lesson_.restart();
      if (changed) focusedChoice_ = 0;
    }
  }
  if (changed) requestUpdate();
}

void KanaSimilarActivity::loop() {
  if (mappedInput.wasReleased(MappedInputManager::Button::Back)) { action(0); return; }
  const auto routed = routeTouch(mappedInput);
  if (routed.routed && app.invalidated()) requestUpdate();
  if (routed) return;
  if (mappedInput.wasReleased(MappedInputManager::Button::Confirm)) {
    if (lesson_.screen() == kana::Similar::Screen::Compare) action(3);
    else if (lesson_.screen() == kana::Similar::Screen::Done) action(7);
    else if (lesson_.answered()) action(6);
    else action(4 + focusedChoice_);  // Confirm chooses the focused glyph.
    return;
  }
  if (mappedInput.wasReleased(MappedInputManager::Button::Left)) {
    if (lesson_.screen() == kana::Similar::Screen::Compare) action(1);
    else if (lesson_.screen() == kana::Similar::Screen::Test && !lesson_.answered()) {
      focusedChoice_ = 0;
      action(4 + focusedChoice_);
    }
    return;
  }
  if (mappedInput.wasReleased(MappedInputManager::Button::Right)) {
    if (lesson_.screen() == kana::Similar::Screen::Compare) action(2);
    else if (lesson_.screen() == kana::Similar::Screen::Test && !lesson_.answered()) {
      focusedChoice_ = 1;
      action(4 + focusedChoice_);
    }
  }
}

const char* KanaSimilarActivity::hintLine(int line) const {
  // Pair-specific hints are separate strings because this renderer truncates
  // embedded newlines instead of laying them out as two text rows.
  if (lesson_.hintPair() == 0)
    return text(line == 0 ? StrId::STR_KANA_SIMILAR_SHI_HINT : StrId::STR_KANA_SIMILAR_TSU_HINT);
  return text(line == 0 ? StrId::STR_KANA_SIMILAR_SO_HINT : StrId::STR_KANA_SIMILAR_N_HINT);
}

void KanaSimilarActivity::addButton(UiScreen& s, const char* label, int value, const fui::Rect& rect,
                                    bool enabled, fui::State state) {
  fui::ButtonProps p;
  p.label = label;
  p.action = 1;
  p.value = value;
  p.inputMask = fui::InputTouch;
  p.text = s.theme().smallText;
  p.text.maxLines = 2;
  p.minTouchSize = 44;
  p.enabled = enabled;
  p.state = state;
  s.button(p, rect);
}

void KanaSimilarActivity::drawPairCard(int cardId, int x, int width, int glyphY, int readingY) {
  const auto& card = kana::cards[cardId];
  renderer.drawText(kBigFontId, x + (width - renderer.getTextWidth(kBigFontId, card.katakana)) / 2,
                    glyphY, card.katakana);
  renderer.drawText(SMALL_FONT_ID, x + (width - renderer.getTextWidth(SMALL_FONT_ID, card.romaji)) / 2,
                    readingY, card.romaji);
}

void KanaSimilarActivity::drawCompare(UiScreen& s, const fui::Rect& a) {
  const int half = (a.width - kGap) / 2;
  const int glyphY = a.y + 110;
  const int readingY = glyphY + renderer.getLineHeight(kBigFontId) + 16;
  drawPairCard(lesson_.compareLeftCardId(), a.x, half, glyphY, readingY);
  drawPairCard(lesson_.compareRightCardId(), a.x + half + kGap, a.width - half - kGap, glyphY, readingY);
  auto style = s.theme().bodyText;
  style.align = fui::TextAlign::Center;
  style.maxLines = 1;
  s.target().text(fui::Rect{a.x, int16_t(readingY + 76), a.width, 34}, hintLine(0), style);
  s.target().text(fui::Rect{a.x, int16_t(readingY + 116), a.width, 34}, hintLine(1), style);
}

void KanaSimilarActivity::drawTestPrompt(UiScreen& s, const fui::Rect& a) {
  const auto& card = kana::cards[lesson_.targetCardId()];
  auto style = s.theme().bodyText;
  style.align = fui::TextAlign::Center;
  style.maxLines = 2;
  s.target().text(fui::Rect{a.x, int16_t(a.y + 54), a.width, 54}, text(StrId::STR_KANA_SIMILAR_CHOOSE), style);
  // Only the target's romaji appears here: not the correct katakana, hiragana,
  // example, sound hint or meaning. The two glyphs are offered below.
  renderer.drawCenteredText(SMALL_FONT_ID, a.y + 115, card.romaji);
}

void KanaSimilarActivity::drawTestAnswer(UiScreen& s, const fui::Rect& a) {
  auto style = s.theme().bodyText;
  style.align = fui::TextAlign::Center;
  style.maxLines = 2;
  const StrId result = lesson_.correct() ? StrId::STR_KANA_SIMILAR_CORRECT
                                         : StrId::STR_KANA_SIMILAR_TRY_AGAIN;
  s.target().text(fui::Rect{a.x, int16_t(a.y + 392), a.width, 48}, text(result), style);
  // The selected choice remains visible above; do not duplicate the glyph
  // below the feedback, where it would collide with the pair hint.
  style.maxLines = 1;
  s.target().text(fui::Rect{a.x, int16_t(a.y + 522), a.width, 30}, hintLine(0), style);
  s.target().text(fui::Rect{a.x, int16_t(a.y + 558), a.width, 30}, hintLine(1), style);
}

void KanaSimilarActivity::drawChoiceGlyph(int cardId, const fui::Rect& rect) {
  const char* glyph = kana::cards[cardId].katakana;
  renderer.drawText(kBigFontId, rect.x + (rect.width - renderer.getTextWidth(kBigFontId, glyph)) / 2,
                    rect.y + (rect.height - renderer.getLineHeight(kBigFontId)) / 2, glyph);
}

void KanaSimilarActivity::build(UiScreen& s) {
  const auto& m = UITheme::getInstance().getMetrics();
  s.setContentMarginFromScreen(fui::Insets{int16_t(m.topPadding + m.headerHeight + 8), 12, 12, 12});
  const auto a = s.body();
  const int half = (a.width - kGap) / 2;
  const int bottom = a.bottom() - kButtonHeight;
  if (lesson_.screen() == kana::Similar::Screen::Compare) {
    drawCompare(s, a);
    addButton(s, text(StrId::STR_BACK), 0,
              fui::Rect{a.x, int16_t(bottom), int16_t(half), kButtonHeight});
    addButton(s, text(StrId::STR_KANA_PREV), 1,
              fui::Rect{int16_t(a.x + half + kGap), int16_t(bottom - 2 * (kButtonHeight + kGap)),
                        int16_t(half), kButtonHeight});
    addButton(s, text(StrId::STR_KANA_NEXT), 2,
              fui::Rect{int16_t(a.x + half + kGap), int16_t(bottom - kButtonHeight - kGap),
                        int16_t(half), kButtonHeight});
    addButton(s, text(StrId::STR_KANA_SIMILAR_TEST), 3,
              fui::Rect{int16_t(a.x + half + kGap), int16_t(bottom), int16_t(half), kButtonHeight});
    return;
  }
  if (lesson_.screen() == kana::Similar::Screen::Done) {
    char score[32];
    std::snprintf(score, sizeof(score), "%d / %d", lesson_.score(), lesson_.questionCount());
    auto style = s.theme().bodyText;
    style.align = fui::TextAlign::Center;
    style.maxLines = 2;
    s.target().text(fui::Rect{a.x, int16_t(a.y + 175), a.width, 56}, score, style);
    addButton(s, text(StrId::STR_BACK), 0,
              fui::Rect{a.x, int16_t(bottom), int16_t(half), kButtonHeight});
    addButton(s, text(StrId::STR_KANA_SIMILAR_RESTART), 7,
              fui::Rect{int16_t(a.x + half + kGap), int16_t(bottom), int16_t(half), kButtonHeight});
    return;
  }
  drawTestPrompt(s, a);
  const int choiceY = a.y + 222;
  const fui::Rect left{a.x, int16_t(choiceY), int16_t(half), 150};
  const fui::Rect right{int16_t(a.x + half + kGap), int16_t(choiceY), int16_t(half), 150};
  const auto choiceState = [&](const int index) {
    const int cardId = index == 0 ? lesson_.leftChoiceCardId() : lesson_.rightChoiceCardId();
    if (lesson_.answered()) {
      if (cardId == lesson_.targetCardId()) return fui::StateFocused;
      return lesson_.selectedCardId() == cardId ? fui::StateSelected : fui::StateNormal;
    }
    return focusedChoice_ == index ? fui::StateFocused : fui::StateNormal;
  };
  addButton(s, nullptr, 4, left, !lesson_.answered(),
            choiceState(0));
  addButton(s, nullptr, 5, right, !lesson_.answered(),
            choiceState(1));
  drawChoiceGlyph(lesson_.leftChoiceCardId(), left);
  drawChoiceGlyph(lesson_.rightChoiceCardId(), right);
  if (lesson_.answered()) drawTestAnswer(s, a);
  addButton(s, text(StrId::STR_BACK), 0,
            fui::Rect{a.x, int16_t(bottom), int16_t(half), kButtonHeight});
  if (lesson_.answered())
    addButton(s, text(StrId::STR_KANA_SIMILAR_NEXT), 6,
              fui::Rect{int16_t(a.x + half + kGap), int16_t(bottom), int16_t(half), kButtonHeight});
}

void KanaSimilarActivity::render(RenderLock&&) {
  renderer.clearScreen();
  const auto& m = UITheme::getInstance().getMetrics();
  char progress[24] = {};
  if (lesson_.screen() == kana::Similar::Screen::Test)
    std::snprintf(progress, sizeof(progress), "%d / %d", lesson_.questionIndex() + 1, lesson_.questionCount());
  GUI.drawHeader(renderer, Rect{0, m.topPadding, renderer.getScreenWidth(), m.headerHeight},
                 text(lesson_.screen() == kana::Similar::Screen::Compare ? StrId::STR_KANA_SIMILAR_COMPARE
                                                                      : StrId::STR_JP_SIMILAR), progress);
  renderUi();
  renderer.displayBuffer();
}
