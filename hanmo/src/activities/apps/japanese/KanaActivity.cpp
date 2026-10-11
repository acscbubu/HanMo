#include "KanaActivity.h"

#include <EpdFontFamily.h>
#include <I18n.h>
#include <HalStorage.h>
#include <cstdio>
#include <cstring>
#include <builtinFonts/hanmo_kana_12.h>
#include <builtinFonts/hanmo_kana_20.h>
#include <builtinFonts/hanmo_kana_52.h>

#include "KanaData.generated.h"
#include "KanaPracticeIcons.h"
#include "KanaPracticeStore.h"
#include "components/SubpageLayout.h"
#include "components/UITheme.h"
#include "fontIds.h"
namespace fui = freeink::ui;
namespace {
constexpr int groupId = 0x4A50000C;
const EpdFont groupFont(&hanmo_kana_12);
const EpdFontFamily groupFamily(&groupFont);
constexpr int bigId = 0x4A500034, exampleId = 0x4A500014;
const EpdFont bigFont(&hanmo_kana_52), exampleFont(&hanmo_kana_20);
const EpdFontFamily bigFamily(&bigFont), exampleFamily(&exampleFont);
const char* text(StrId id) { return I18N.get(id); }
}  // namespace
void KanaGroupsActivity::refreshProgress() {
  kana::Practice view;
  kana::LoadStatus status = kana::LoadStatus::StorageError;
  if (Storage.ready()) {
#if defined(ARDUINO_ARCH_ESP32)
    HalStorage::StorageLock lock;
#endif
    status = kana::loadPractice(Storage, view);
  }
  const bool available = status == kana::LoadStatus::Loaded || status == kana::LoadStatus::Empty;
  rows_[1].subtitle = text(available ? StrId::STR_KANA_PRACTICED : StrId::STR_KANA_LOAD_FAILED);
  for (int i = 1; i < 13; ++i) {
    if (!available) { rows_[i].value = nullptr; continue; }
    const int start = i == 1 ? 0 : kana::groups[i - 2].start;
    const int count = i == 1 ? kana::kCardCount : kana::groups[i - 2].count;
    std::snprintf(progressLabels_[i].data(), progressLabels_[i].size(), "%d/%d", view.doneCount(start, count), count);
    rows_[i].value = progressLabels_[i].data();
  }
}
void KanaGroupsActivity::onEnter() {
  if (!renderer.getFontMap().count(groupId)) renderer.insertFont(groupId, groupFamily);
  uiTarget.setFont(fui::GfxRendererTarget::FONT_BODY, groupId);
  rows_[0].label = text(StrId::STR_BACK);
  rows_[1].label = text(StrId::STR_KANA_ALL);
  for (int i = 0; i < 11; ++i) rows_[i + 2].label = kana::groups[i].label;
  for (int i = 0; i < 13; ++i) rows_[i].actionValue = i;
  refreshProgress();
  UiListActivity::onEnter();
}
const char* KanaGroupsActivity::headerTitle() const { return text(StrId::STR_JP_KANA); }
void KanaGroupsActivity::buildScreen(UiScreen& s) {
  const auto& m = UITheme::getInstance().getMetrics();
  const auto safe = UITheme::getInstance().getScreenSafeArea(renderer, true, true);
  const auto c = SubpageLayout::contentRect(safe, m);
  s.setContentMarginFromScreen(fui::Insets{int16_t(c.y), int16_t(renderer.getScreenWidth() - c.x - c.width),
                                           int16_t(renderer.getScreenHeight() - c.y - c.height), int16_t(c.x)});
  fui::ListProps p;
  p.items = rows_.data();
  p.count = 13;
  p.action = ACTION_ROW;
  p.inputMask = fui::InputTouch;
  syncListViewport(s, p);
  s.list(p);
}
void KanaGroupsActivity::activateIndex(int i) {
  if (i < 0 || i >= 13) return;
  app.clearTapFlash();
  if (!i) {
    finish();
    return;
  }
  const int start = i == 1 ? 0 : kana::groups[i - 2].start, count = i == 1 ? 46 : kana::groups[i - 2].count;
  if (!startActivityForResultWith<KanaCardActivity>([this](const ActivityResult&) { refreshProgress(); requestUpdate(); }, start, count)) {
    GUI.drawPopup(renderer, tr(STR_MEMORY_ERROR));
    requestUpdate();
  }
}
void KanaCardActivity::onEnter() {
  Activity::onEnter();
  orientation_ = renderer.getOrientation();
  renderer.setOrientation(GfxRenderer::Orientation::Portrait);
  // Two small, immutable subset families reuse renderer's existing registry.
  if (!renderer.getFontMap().count(bigId)) renderer.insertFont(bigId, bigFamily);
  if (!renderer.getFontMap().count(exampleId)) renderer.insertFont(exampleId, exampleFamily);
  state_.seed = millis() | 1;
  practice_ = kana::Practice{};
  saveFailed_ = false;
  recordReady_ = false;
  if (Storage.ready()) {
#if defined(ARDUINO_ARCH_ESP32)
    HalStorage::StorageLock lock;
#endif
    const auto status = kana::loadPractice(Storage, practice_);
    recordReady_ = status == kana::LoadStatus::Loaded || status == kana::LoadStatus::Empty;
  }
  resetUi();
  app.on(1, &KanaCardActivity::event, this);
  app.setScreen(&KanaCardActivity::screen, this);
  requestUpdate();
}
void KanaCardActivity::onExit() {
  renderer.setOrientation(orientation_);
  Activity::onExit();
}
void KanaCardActivity::screen(UiScreen& s, void* p) { static_cast<KanaCardActivity*>(p)->build(s); }
void KanaCardActivity::event(const fui::ActionEvent& e, void* p) { static_cast<KanaCardActivity*>(p)->action(e.value); }
void KanaCardActivity::action(int value) {
  if (value == 0) {
    app.clearTapFlash();
    finish();
    return;
  }
  if (value >= 10 && value < 17) {
    RenderLock lock(*this);
    if (recordReady_ && Storage.ready()) {
      auto candidate = practice_;
      if (candidate.toggle(state_.current(), value - 10)) {
#if defined(ARDUINO_ARCH_ESP32)
        HalStorage::StorageLock storageLock;
#endif
        if (kana::savePractice(Storage, candidate, &practice_)) {
          practice_ = candidate;  // Never show an unsaved tap as committed.
          saveFailed_ = false;
        } else {
          saveFailed_ = true;
        }
      }
    } else {
      saveFailed_ = true;
    }
    requestUpdate();
    return;
  }
  {
    RenderLock lock(*this);
    if (value == 1) state_.step(-1);
    if (value == 2) state_.step(1);
    if (value == 3) state_.roman = !state_.roman;
    if (value == 4) state_.shuffle();
  }
  requestUpdate();
}
void KanaCardActivity::loop() {
  if (mappedInput.wasReleased(MappedInputManager::Button::Back)) {
    action(0);
    return;
  }
  if (routeTouch(mappedInput)) return;
  if (mappedInput.wasReleased(MappedInputManager::Button::Left) ||
      mappedInput.wasReleased(MappedInputManager::Button::Up)) {
    action(1);
    return;
  }
  if (mappedInput.wasReleased(MappedInputManager::Button::Right) ||
      mappedInput.wasReleased(MappedInputManager::Button::Down)) {
    action(2);
    return;
  }
  if (mappedInput.wasReleased(MappedInputManager::Button::Confirm)) {
    action(3);
    return;
  }
  const auto swipe = mappedInput.wasSwipe();
  if (swipe == MappedInputManager::SwipeDir::Left)
    action(2);
  else if (swipe == MappedInputManager::SwipeDir::Right)
    action(1);
}
void KanaCardActivity::build(UiScreen& s) {
  const auto& m = UITheme::getInstance().getMetrics();
  s.setContentMarginFromScreen(fui::Insets{int16_t(m.topPadding + m.headerHeight + 8), 12, 12, 12});
  const auto a = s.body();
  const int gap = 8, h = 48, half = (a.width - gap) / 2;
  auto button = [&](const char* label, int v, int x, int y, int w) {
    fui::ButtonProps p;
    p.label = label;
    p.action = 1;
    p.value = v;
    p.inputMask = fui::InputTouch;
    p.text = s.theme().smallText;
    p.minTouchSize = 1;
    s.button(p, fui::Rect{int16_t(x), int16_t(y), int16_t(w), int16_t(h)});
  };
  auto label = [&](const char* str, int y, int height) {
    auto st = s.theme().bodyText;
    st.align = fui::TextAlign::Center;
    st.maxLines = 2;
    s.target().text(fui::Rect{a.x, int16_t(y), a.width, int16_t(height)}, str, st);
  };
  button(text(state_.roman ? StrId::STR_KANA_HIDE_ROMAJI : StrId::STR_KANA_SHOW_ROMAJI), 3, a.x, a.y, half);
  button(text(state_.shuffled ? StrId::STR_KANA_ORDERED : StrId::STR_KANA_SHUFFLE), 4, a.x + half + gap, a.y, half);
  const int third = (a.width - 2 * gap) / 3, bottom = a.bottom() - h;
  button(text(StrId::STR_BACK), 0, a.x, bottom, third);
  button(text(StrId::STR_KANA_PREV), 1, a.x + third + gap, bottom, third);
  button(text(StrId::STR_KANA_NEXT), 2, a.x + 2 * (third + gap), bottom, third);
  const auto& card = kana::cards[state_.current()];
  const int labelY = a.y + h + 14, glyphY = labelY + 34;
  renderer.drawText(SMALL_FONT_ID, a.x + (half - renderer.getTextWidth(SMALL_FONT_ID, text(StrId::STR_KANA_HIRA))) / 2,
                    labelY, text(StrId::STR_KANA_HIRA));
  renderer.drawText(SMALL_FONT_ID,
                    a.x + half + gap + (half - renderer.getTextWidth(SMALL_FONT_ID, text(StrId::STR_KANA_KATA))) / 2,
                    labelY, text(StrId::STR_KANA_KATA));
  renderer.drawText(bigId, a.x + (half - renderer.getTextWidth(bigId, card.hiragana)) / 2, glyphY, card.hiragana);
  renderer.drawText(bigId, a.x + half + gap + (half - renderer.getTextWidth(bigId, card.katakana)) / 2, glyphY,
                    card.katakana);
  const int romaY = glyphY + renderer.getLineHeight(bigId) + 8;
  // The reference character is a sound hint, not the example meaning or a Taiwanese romanization.
  char romajiTaiwan[64];
  const bool parenthesized = std::strncmp(card.soundHint, "（", 3) == 0;
  std::snprintf(romajiTaiwan, sizeof(romajiTaiwan), "%s%s%s", card.romaji,
                parenthesized ? "" : " ", card.soundHint);
  if (state_.roman)
    renderer.drawCenteredText(exampleId, romaY, romajiTaiwan);
  else
    label(text(StrId::STR_KANA_ROMAJI_HIDDEN), romaY, 38);
  const int exampleY = romaY + 52;
  renderer.drawCenteredText(exampleId, exampleY, card.example);
  const int exampleReadingY = exampleY + renderer.getLineHeight(exampleId) + 3;
  label(state_.roman ? card.exampleRomaji : text(StrId::STR_KANA_ROMAJI_HIDDEN), exampleReadingY, 30);
  const int meaningY = exampleReadingY + 31;
  label(card.meaning, meaningY, 36);
  const int noteY = meaningY + 44, markerY = bottom - 72, helpY = markerY - 29;
  StrId note = StrId::STR_KANA_BASIC_NOTE;
  if (state_.current() == 25) note = StrId::STR_KANA_HA_NOTE;
  if (state_.current() == 28) note = StrId::STR_KANA_HE_NOTE;
  if (state_.current() == 44) note = StrId::STR_KANA_WO_NOTE;
  if (state_.current() == 45) note = StrId::STR_KANA_N_NOTE;
  label(text(note), noteY, 50);
  label(text(StrId::STR_KANA_TAIWAN_NOTE), noteY + 51, std::max(0, helpY - noteY - 55));
  auto helpStyle = s.theme().smallText;
  helpStyle.align = fui::TextAlign::Center;
  helpStyle.maxLines = 1;
  const auto help = !recordReady_ ? StrId::STR_KANA_LOAD_FAILED :
                    saveFailed_ ? StrId::STR_KANA_SAVE_FAILED : StrId::STR_KANA_MARKS_HELP;
  s.target().text(fui::Rect{a.x, int16_t(helpY), a.width, 25}, text(help), helpStyle);
  const int markerGap = 4, markerW = (a.width - markerGap * 6) / 7;
  for (int marker = 0; marker < 7; ++marker) {
    const bool on = practice_.active(state_.current(), marker);
    const uint8_t* bitmap = marker == 0 ? (on ? kana::icons::kStarOn : kana::icons::kStarOff) :
                            marker == 1 ? (on ? kana::icons::kCheckOn : kana::icons::kCheckOff) :
                                          (on ? kana::icons::kCircleOn : kana::icons::kCircleOff);
    fui::ButtonProps p;
    p.icon = fui::BitmapRef{bitmap, 24, 24, fui::BitmapFormat::BW1, true};
    p.iconSize = 24;
    p.action = 1;
    p.value = 10 + marker;
    p.inputMask = fui::InputTouch;
    p.minTouchSize = 44;
    p.enabled = recordReady_;
    const int x = a.x + marker * (markerW + markerGap);
    s.button(p, fui::Rect{int16_t(x), int16_t(markerY),
                          int16_t(marker == 6 ? a.right() - x : markerW), 48});
  }
}
void KanaCardActivity::render(RenderLock&&) {
  renderer.clearScreen();
  const auto& m = UITheme::getInstance().getMetrics();
  char progress[24];
  snprintf(progress, sizeof(progress), "%d / %d", state_.index + 1, state_.count);
  GUI.drawHeader(renderer, Rect{0, m.topPadding, renderer.getScreenWidth(), m.headerHeight}, text(StrId::STR_JP_KANA),
                 progress);
  renderUi();
  renderer.displayBuffer();
}
