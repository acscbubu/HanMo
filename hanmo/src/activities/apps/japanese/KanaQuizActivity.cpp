#include "KanaQuizActivity.h"

#include <EpdFontFamily.h>
#include <I18n.h>
#include <builtinFonts/hanmo_kana_20.h>
#include <builtinFonts/hanmo_kana_52.h>
#include <cstdio>
#include <cstring>

#include "components/UITheme.h"
#include "fontIds.h"

namespace fui = freeink::ui;
namespace {
constexpr int kBigId = 0x4A500034;
constexpr int kExampleId = 0x4A500014;
const EpdFont kBigFont(&hanmo_kana_52), kExampleFont(&hanmo_kana_20);
const EpdFontFamily kBigFamily(&kBigFont), kExampleFamily(&kExampleFont);
const char* text(StrId id) { return I18N.get(id); }
}  // namespace

void KanaQuizActivity::onEnter() {
  Activity::onEnter();
  orientation_ = renderer.getOrientation();
  renderer.setOrientation(GfxRenderer::Orientation::Portrait);
  if (!renderer.getFontMap().count(kBigId)) renderer.insertFont(kBigId, kBigFamily);
  if (!renderer.getFontMap().count(kExampleId)) renderer.insertFont(kExampleId, kExampleFamily);
  quiz_.restart(millis() | 1);
  resetUi();
  app.on(1, &KanaQuizActivity::event, this);
  app.setScreen(&KanaQuizActivity::screen, this);
  requestUpdate();
}

void KanaQuizActivity::onExit() {
  renderer.setOrientation(orientation_);
  Activity::onExit();
}

void KanaQuizActivity::screen(UiScreen& s, void* p) { static_cast<KanaQuizActivity*>(p)->build(s); }
void KanaQuizActivity::event(const fui::ActionEvent& e, void* p) { static_cast<KanaQuizActivity*>(p)->action(e.value); }

void KanaQuizActivity::action(int value) {
  if (value == 0) {
    app.clearTapFlash();
    finish();
    return;
  }
  bool changed = false;
  {
    RenderLock lock(*this);
    if (value == 1) changed = quiz_.reveal();
    if (value == 2) changed = quiz_.mark(true);
    if (value == 3) changed = quiz_.mark(false);
    if (value == 4 && quiz_.done()) {
      quiz_.restart(millis() | 1);
      changed = true;
    }
  }
  if (changed) requestUpdate();
}

void KanaQuizActivity::loop() {
  if (mappedInput.wasReleased(MappedInputManager::Button::Back)) { action(0); return; }
  if (routeTouch(mappedInput)) return;
  if (mappedInput.wasReleased(MappedInputManager::Button::Confirm)) {
    action(quiz_.done() ? 4 : quiz_.revealed() ? 2 : 1);
    return;
  }
  if (quiz_.revealed() && mappedInput.wasReleased(MappedInputManager::Button::Left)) {
    action(3);
    return;
  }
  if (quiz_.revealed() && mappedInput.wasReleased(MappedInputManager::Button::Right)) action(2);
}

void KanaQuizActivity::drawGlyphs(const kana::Card& card, const fui::Rect& a) {
  const int gap = 8, half = (a.width - gap) / 2;
  const int labelY = a.y + 88, glyphY = labelY + 30;
  renderer.drawText(SMALL_FONT_ID, a.x + (half - renderer.getTextWidth(SMALL_FONT_ID, text(StrId::STR_KANA_HIRA))) / 2,
                    labelY, text(StrId::STR_KANA_HIRA));
  renderer.drawText(SMALL_FONT_ID,
                    a.x + half + gap + (half - renderer.getTextWidth(SMALL_FONT_ID, text(StrId::STR_KANA_KATA))) / 2,
                    labelY, text(StrId::STR_KANA_KATA));
  renderer.drawText(kBigId, a.x + (half - renderer.getTextWidth(kBigId, card.hiragana)) / 2,
                    glyphY, card.hiragana);
  renderer.drawText(kBigId,
                    a.x + half + gap + (half - renderer.getTextWidth(kBigId, card.katakana)) / 2,
                    glyphY, card.katakana);
}

void KanaQuizActivity::drawPrompt(const kana::Card& card, const fui::Rect& a) {
  drawGlyphs(card, a);
  renderer.drawCenteredText(SMALL_FONT_ID, a.y + 358, text(StrId::STR_KANA_QUIZ_PROMPT));
}

void KanaQuizActivity::drawAnswer(const kana::Card& card, const fui::Rect& a) {
  drawGlyphs(card, a);
  // Sound hints are a separate field, never a replacement for Japanese readings or meanings.
  const bool parenthesized = std::strncmp(card.soundHint, "（", 3) == 0;
  std::snprintf(reading_.data(), reading_.size(), "%s%s%s", card.romaji,
                parenthesized ? "" : " ", card.soundHint);
  renderer.drawCenteredText(kExampleId, a.y + 218, reading_.data());
  renderer.drawCenteredText(kExampleId, a.y + 291, card.example);
  renderer.drawCenteredText(SMALL_FONT_ID, a.y + 338, card.exampleRomaji);
  renderer.drawCenteredText(SMALL_FONT_ID, a.y + 378, card.meaning);
  renderer.drawCenteredText(SMALL_FONT_ID, a.y + 472, text(StrId::STR_KANA_TAIWAN_NOTE));
  StrId note = StrId::STR_KANA_BASIC_NOTE;
  if (quiz_.current() == 25) note = StrId::STR_KANA_HA_NOTE;
  if (quiz_.current() == 28) note = StrId::STR_KANA_HE_NOTE;
  if (quiz_.current() == 44) note = StrId::STR_KANA_WO_NOTE;
  if (quiz_.current() == 45) note = StrId::STR_KANA_N_NOTE;
  if (note != StrId::STR_KANA_BASIC_NOTE)
    renderer.drawCenteredText(SMALL_FONT_ID, a.y + 506, text(note));
}

void KanaQuizActivity::build(UiScreen& s) {
  const auto& metrics = UITheme::getInstance().getMetrics();
  s.setContentMarginFromScreen(fui::Insets{int16_t(metrics.topPadding + metrics.headerHeight + 8), 12, 12, 12});
  const auto a = s.body();
  constexpr int gap = 8, h = 50;
  const int bottom = a.bottom() - h;
  auto button = [&](const char* label, int value, int x, int width) {
    fui::ButtonProps p;
    p.label = label;
    p.action = 1;
    p.value = value;
    p.inputMask = fui::InputTouch;
    p.text = s.theme().smallText;
    p.minTouchSize = 48;
    s.button(p, fui::Rect{int16_t(x), int16_t(bottom), int16_t(width), h});
  };
  auto label = [&](const char* str, int y, int height) {
    auto style = s.theme().bodyText;
    style.align = fui::TextAlign::Center;
    style.maxLines = 2;
    s.target().text(fui::Rect{a.x, int16_t(y), a.width, int16_t(height)}, str, style);
  };
  if (quiz_.done()) {
    label(text(StrId::STR_KANA_QUIZ_DONE), a.y + 159, 54);
    std::snprintf(score_.data(), score_.size(), "%s %d / 46", text(StrId::STR_KANA_QUIZ_FIRST), quiz_.firstKnown());
    label(score_.data(), a.y + 233, 55);
    label(text(StrId::STR_KANA_QUIZ_SESSION), bottom - 85, 70);
    const int backWidth = (a.width - gap) / 3;
    button(text(StrId::STR_BACK), 0, a.x, backWidth);
    button(text(StrId::STR_KANA_QUIZ_RESTART), 4, a.x + backWidth + gap, a.width - backWidth - gap);
    return;
  }
  const auto& card = kana::cards[quiz_.current()];
  if (quiz_.revealed()) drawAnswer(card, a);
  else drawPrompt(card, a);
  label(text(StrId::STR_KANA_QUIZ_SESSION), bottom - 91, 70);
  if (quiz_.revealed()) {
    const int third = (a.width - 2 * gap) / 3;
    button(text(StrId::STR_BACK), 0, a.x, third);
    button(text(StrId::STR_KANA_QUIZ_AGAIN), 3, a.x + third + gap, third);
    button(text(StrId::STR_KANA_QUIZ_KNOWN), 2, a.x + 2 * (third + gap), a.width - 2 * (third + gap));
  } else {
    const int backWidth = (a.width - gap) / 3;
    button(text(StrId::STR_BACK), 0, a.x, backWidth);
    button(text(StrId::STR_KANA_QUIZ_REVEAL), 1, a.x + backWidth + gap, a.width - backWidth - gap);
  }
}

void KanaQuizActivity::render(RenderLock&&) {
  renderer.clearScreen();
  const auto& metrics = UITheme::getInstance().getMetrics();
  if (quiz_.done()) progress_[0] = '\0';
  else if (quiz_.round() == 1)
    std::snprintf(progress_.data(), progress_.size(), "%d / %d", quiz_.position() + 1, quiz_.size());
  else
    std::snprintf(progress_.data(), progress_.size(), "%s %d   %d / %d", text(StrId::STR_KANA_QUIZ_REVIEW),
                  quiz_.round() - 1, quiz_.position() + 1, quiz_.size());
  GUI.drawHeader(renderer, Rect{0, metrics.topPadding, renderer.getScreenWidth(), metrics.headerHeight},
                 text(StrId::STR_JP_QUIZ), progress_.data());
  renderUi();
  renderer.displayBuffer();
}
