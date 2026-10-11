#include "JapaneseWordsActivity.h"

#include <EpdFontFamily.h>
#include <I18n.h>
#include <builtinFonts/hanmo_words_44.h>
#include <cstdio>

#include "KanaData.generated.h"
#include "components/UITheme.h"
#include "fontIds.h"

namespace fui = freeink::ui;
namespace {
constexpr int kWordFontId = 0x4A52002C;
const EpdFont kWordFont(&hanmo_words_44);
const EpdFontFamily kWordFamily(&kWordFont);
constexpr int kGap = 8;
constexpr int kButtonHeight = 52;
const char* text(StrId id) { return I18N.get(id); }
}  // namespace

void JapaneseWordsActivity::onEnter() {
  Activity::onEnter();
  orientation_ = renderer.getOrientation();
  renderer.setOrientation(GfxRenderer::Orientation::Portrait);
  addedWordFont_ = !renderer.getFontMap().count(kWordFontId);
  if (addedWordFont_) renderer.insertFont(kWordFontId, kWordFamily);
  lesson_.restart();
  waitForConfirmRelease_ = mappedInput.isPressed(MappedInputManager::Button::Confirm);
  resetUi();
  app.on(1, &JapaneseWordsActivity::event, this);
  app.setScreen(&JapaneseWordsActivity::screen, this);
  requestUpdate();
}
void JapaneseWordsActivity::onExit() {
  closeRouting();
  app.clearTapFlash();
  if (addedWordFont_) renderer.removeFont(kWordFontId);
  addedWordFont_ = false;
  renderer.setOrientation(orientation_);
  Activity::onExit();
}
void JapaneseWordsActivity::loop() {
  if (mappedInput.wasReleased(MappedInputManager::Button::Back)) { action(0); return; }
  const auto routed = routeTouch(mappedInput);
  if (routed.routed && app.invalidated()) requestUpdate();
  if (routed) return;
  if (waitForConfirmRelease_) {
    if (!mappedInput.isPressed(MappedInputManager::Button::Confirm)) waitForConfirmRelease_ = false;
    return;  // Consume the inherited gesture's release as well as its hold.
  }
  if (mappedInput.wasReleased(MappedInputManager::Button::Confirm)) {
    action(lesson_.done() ? 4 : lesson_.revealed() ? 2 : 1);
    return;
  }
  if (lesson_.revealed() && mappedInput.wasReleased(MappedInputManager::Button::Left)) { action(3); return; }
  if (lesson_.revealed() && mappedInput.wasReleased(MappedInputManager::Button::Right)) action(2);
}
void JapaneseWordsActivity::render(RenderLock&&) {
  renderer.clearScreen();
  const auto& metrics = UITheme::getInstance().getMetrics();
  if (lesson_.done()) progress_[0] = '\0';
  else if (lesson_.round() == 1)
    std::snprintf(progress_.data(), progress_.size(), "%d / %d", lesson_.position() + 1, lesson_.size());
  else
    std::snprintf(progress_.data(), progress_.size(), "%s %d   %d / %d", text(StrId::STR_KANA_QUIZ_REVIEW),
                  lesson_.round() - 1, lesson_.position() + 1, lesson_.size());
  GUI.drawHeader(renderer, Rect{0, metrics.topPadding, renderer.getScreenWidth(), metrics.headerHeight},
                 text(StrId::STR_JP_WORDS), progress_.data());
  renderUi();
  renderer.displayBuffer();
}
void JapaneseWordsActivity::screen(UiScreen& s, void* p) { static_cast<JapaneseWordsActivity*>(p)->build(s); }
void JapaneseWordsActivity::event(const freeink::ui::ActionEvent& e, void* p) { static_cast<JapaneseWordsActivity*>(p)->action(e.value); }
void JapaneseWordsActivity::action(int value) {
  if (value == 0) {
    closeRouting();
    app.clearTapFlash();
    finish();
    return;
  }
  bool changed = false;
  {
    RenderLock lock(*this);
    if (value == 1) changed = lesson_.reveal();
    if (value == 2) changed = lesson_.mark(true);
    if (value == 3) changed = lesson_.mark(false);
    if (value == 4 && lesson_.done()) {
      lesson_.restart();
      changed = true;
    }
  }
  if (changed) {
    app.clearTapFlash();
    requestUpdate();
  }
}

void JapaneseWordsActivity::build(UiScreen& s) {
  const auto& metrics = UITheme::getInstance().getMetrics();
  s.setContentMarginFromScreen(fui::Insets{int16_t(metrics.topPadding + metrics.headerHeight + 8), 12, 12, 12});
  const auto a = s.body();
  const int bottom = a.bottom() - kButtonHeight;
  const int smallHeight = renderer.getLineHeight(SMALL_FONT_ID);
  const int sessionHeight = 2 * smallHeight + 12;
  const int sessionY = bottom - kGap - sessionHeight;
  auto label = [&](const char* value, int y, int height) {
    auto style = s.theme().smallText;
    style.align = fui::TextAlign::Center;
    style.maxLines = 2;
    s.target().text(fui::Rect{a.x, int16_t(y), a.width, int16_t(height)}, value, style);
  };
  label(text(StrId::STR_JP_WORDS_SESSION), sessionY, sessionHeight);
  auto button = [&](StrId label, int value, int x, int width) {
    fui::ButtonProps p;
    p.label = text(label);
    p.action = 1;
    p.value = value;
    p.inputMask = fui::InputTouch;
    p.text = s.theme().smallText;
    p.text.maxLines = 2;
    p.minTouchSize = 44;
    p.enabled = true;
    s.button(p, fui::Rect{int16_t(x), int16_t(bottom), int16_t(width), kButtonHeight});
  };
  if (lesson_.done()) {
    const int groupHeight = 4 * smallHeight + 24;
    const int y = a.y + (sessionY - 12 - a.y - groupHeight) / 2;
    label(text(StrId::STR_JP_WORDS_DONE), y, 2 * smallHeight);
    std::snprintf(score_.data(), score_.size(), "%s %d / %d", text(StrId::STR_KANA_QUIZ_FIRST),
                  lesson_.firstKnown(), japanese::Words::kCount);
    label(score_.data(), y + 2 * smallHeight + 24, 2 * smallHeight);
    const int backWidth = (a.width - kGap) / 3;
    button(StrId::STR_BACK, 0, a.x, backWidth);
    button(StrId::STR_KANA_QUIZ_RESTART, 4, a.x + backWidth + kGap, a.width - backWidth - kGap);
    return;
  }
  if (lesson_.revealed()) {
    const int third = (a.width - 2 * kGap) / 3;
    button(StrId::STR_BACK, 0, a.x, third);
    button(StrId::STR_KANA_QUIZ_AGAIN, 3, a.x + third + kGap, third);
    button(StrId::STR_KANA_QUIZ_KNOWN, 2, a.x + 2 * (third + kGap), a.width - 2 * (third + kGap));
  } else {
    const int backWidth = (a.width - kGap) / 3;
    button(StrId::STR_BACK, 0, a.x, backWidth);
    button(StrId::STR_KANA_QUIZ_REVEAL, 1, a.x + backWidth + kGap, a.width - backWidth - kGap);
  }
  const auto& card = kana::cards[lesson_.current()];
  const int wordHeight = renderer.getLineHeight(kWordFontId);
  const int groupHeight = wordHeight + 24 + (lesson_.revealed() ? 2 * smallHeight + 16 : 2 * smallHeight);
  const int wordY = a.y + (sessionY - 12 - a.y - groupHeight) / 2;
  renderer.drawText(kWordFontId, a.x + (a.width - renderer.getTextWidth(kWordFontId, card.example)) / 2,
                    wordY, card.example);
  const int answerY = wordY + wordHeight + 24;
  if (lesson_.revealed()) {
    renderer.drawText(SMALL_FONT_ID,
                      a.x + (a.width - renderer.getTextWidth(SMALL_FONT_ID, card.exampleRomaji)) / 2,
                      answerY, card.exampleRomaji);
    renderer.drawText(SMALL_FONT_ID,
                      a.x + (a.width - renderer.getTextWidth(SMALL_FONT_ID, card.meaning)) / 2,
                      answerY + smallHeight + 16, card.meaning);
  } else {
    auto style = s.theme().smallText;
    style.align = fui::TextAlign::Center;
    style.maxLines = 2;
    s.target().text(fui::Rect{a.x, int16_t(answerY), a.width, int16_t(2 * smallHeight)},
                    text(StrId::STR_JP_WORDS_PROMPT), style);
  }
}
