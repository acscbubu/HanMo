#include "JapaneseReviewActivity.h"

#include <EpdFontFamily.h>
#include <HalStorage.h>
#include <I18n.h>
#include <builtinFonts/hanmo_words_44.h>
#include <cstdio>

#include "JapaneseReviewStore.h"
#include "KanaData.generated.h"
#include "components/UITheme.h"
#include "components/UiAppHelpers.h"
#include "fontIds.h"
#include "util/TimeUtils.h"

namespace fui = freeink::ui;
namespace jr = japanese::review;
namespace {
constexpr int kWordFontId = 0x4A52002C;
const EpdFont kWordFont(&hanmo_words_44);
const EpdFontFamily kWordFamily(&kWordFont);
constexpr int kGap = 8;
constexpr int kButtonHeight = 52;
}

void JapaneseReviewActivity::onEnter() {
  Activity::onEnter();
  orientation_ = renderer.getOrientation();
  renderer.setOrientation(GfxRenderer::Orientation::Portrait);
  addedWordFont_ = !renderer.getFontMap().count(kWordFontId);
  if (addedWordFont_) renderer.insertFont(kWordFontId, kWordFamily);
  pending_ = false;
  waitForRelease_.fill(false);
  waitForTouchRelease_ = false;
  loadDashboard();
  armReleaseBarriers();
  resetUi();
  app.on(1, &JapaneseReviewActivity::event, this);
  app.setScreen(&JapaneseReviewActivity::screen, this);
  requestUpdate();
}
void JapaneseReviewActivity::loadDashboard() {
  const bool discarded = pending_;
  pending_ = false;
  page_ = Page::Dashboard;
  dayBlocked_ = false;
  const auto load = jr::loadProgress(Storage, progress_);
  day_ = TimeUtils::getLocalDayOrdinal(TimeUtils::getCurrentValidTimestamp());
  status_ = load == jr::LoadStatus::StorageError ? Status::StorageError :
            load == jr::LoadStatus::Corrupt ? Status::Corrupt :
            !jr::validDay(day_, progress_) ? Status::Clock : Status::None;
  if (status_ == Status::None && discarded) status_ = Status::SaveError;
  date_[0] = '\0';
  if (jr::validDay(day_, progress_)) {
    int year; unsigned month, day;
    TimeUtils::getDateFromDayOrdinal(day_, year, month, day);
    std::snprintf(date_.data(), date_.size(), "%04d-%02u-%02u", year, month, day);
  }
}
void JapaneseReviewActivity::onExit() {
  closeRouting();
  app.clearTapFlash();
  if (addedWordFont_) renderer.removeFont(kWordFontId);
  addedWordFont_ = false;
  renderer.setOrientation(orientation_);
  Activity::onExit();
}
void JapaneseReviewActivity::loop() {
  if (mappedInput.wasReleased(MappedInputManager::Button::Back)) { action(0); return; }
  if (page_ != Page::Dashboard && !dayBlocked_) {
    RenderLock lock(*this);
    if (!checkSessionDay()) { closeRouting(); app.clearTapFlash(); requestUpdate(); }
  }
  using B = MappedInputManager::Button;
  const std::array<B, 3> buttons{B::Left, B::Confirm, B::Right};
  const auto consume = waitForRelease_;
  for (int i = 0; i < 3; ++i)
    if (waitForRelease_[i] && !mappedInput.isPressed(buttons[i])) waitForRelease_[i] = false;
  // Even while the old interaction table is closed, touch snapshots consume
  // this frame. They must never fall through into a physical self-rating.
  const auto snap = touchSnapshotFrom(mappedInput);
  if (waitForTouchRelease_) {
    if (!snap.touchHeld && !snap.touchPressed) waitForTouchRelease_ = false;
    return;
  }
  if (snap.touchPressed || snap.touchReleased || snap.touchHeld) {
    if (routingReady() && (snap.touchPressed || snap.touchReleased)) {
      const bool wasTouchActive = app.touchActive();
      route(snap);
      if (app.invalidated() || wasTouchActive != app.touchActive()) requestUpdate();
    }
    return;
  }
  if (!consume[1] && mappedInput.wasReleased(B::Confirm)) { action(page_ == Page::Dashboard ? 1 : pending_ ? 6 : session_.revealed() ? 4 : 2); return; }
  if (!consume[0] && mappedInput.wasReleased(B::Left)) { action(3); return; }
  if (!consume[2] && mappedInput.wasReleased(B::Right)) action(5);
}
void JapaneseReviewActivity::armReleaseBarriers() {
  using B = MappedInputManager::Button;
  const std::array<B, 3> buttons{B::Left, B::Confirm, B::Right};
  for (int i = 0; i < 3; ++i) waitForRelease_[i] = waitForRelease_[i] || mappedInput.isPressed(buttons[i]);
  const auto snap = touchSnapshotFrom(mappedInput);
  waitForTouchRelease_ = waitForTouchRelease_ || snap.touchPressed || snap.touchHeld;
}
void JapaneseReviewActivity::render(RenderLock&&) {
  renderer.clearScreen();
  const auto& metrics = UITheme::getInstance().getMetrics();
  if (page_ == Page::Session) std::snprintf(position_.data(), position_.size(), pending_ ? "%d / %d   %s" : "%d / %d%s", session_.position() + 1, session_.size(), pending_ ? ratingText() : "");
  else position_[0] = '\0';
  GUI.drawHeader(renderer, Rect{0, metrics.topPadding, renderer.getScreenWidth(), metrics.headerHeight},
                 tr(STR_JP_REVIEW), date_.data());
  renderUi();
  renderer.displayBuffer();
}
void JapaneseReviewActivity::screen(UiScreen& s, void* p) { static_cast<JapaneseReviewActivity*>(p)->build(s); }
void JapaneseReviewActivity::event(const fui::ActionEvent& e, void* p) { static_cast<JapaneseReviewActivity*>(p)->action(e.value); }
void JapaneseReviewActivity::action(int value) {
  if (value == 0 && page_ == Page::Dashboard) { closeRouting(); app.clearTapFlash(); finish(); return; }
  bool changed = false;
  {
    RenderLock lock(*this);
    if (value == 0) { loadDashboard(); changed = true; }
    else if (value == 1 && page_ == Page::Dashboard) {
      loadDashboard();
      if (healthy() && session_.start(progress_, day_))
        page_ = session_.done() ? Page::Complete : Page::Session;
      changed = true;
    } else if (page_ == Page::Session) {
      if (!checkSessionDay()) changed = true;
      else if (value == 6 && pending_) { retryPending(); changed = true; }
      else if (value == 2 && !pending_) changed = session_.reveal();
      else if (value >= 3 && value <= 5 && session_.revealed() && !pending_) {
        proposed_ = progress_;
        proposedRating_ = static_cast<jr::Rating>(value - 2);
        if (jr::applyRating(proposed_, session_.current(), proposedRating_, day_)) {
          pending_ = true;
          attemptPending();
          changed = true;
        } else { status_ = Status::SaveError; changed = true; }
      }
    }
  }
  if (changed) { armReleaseBarriers(); closeRouting(); app.clearTapFlash(); requestUpdate(); }
}
void JapaneseReviewActivity::attemptPending() {
  if (!jr::saveProgress(Storage, proposed_, &progress_)) { status_ = Status::SaveError; return; }
  acceptPending();
}
void JapaneseReviewActivity::retryPending() {
  jr::Progress current;
  const auto load = jr::loadProgress(Storage, current);
  if (load == jr::LoadStatus::Corrupt) { status_ = Status::Corrupt; return; }
  if (load == jr::LoadStatus::StorageError) { status_ = Status::StorageError; return; }
  // A previous final readback may have failed AFTER the transaction committed.
  // Only the exact desired encoded state proves that rating was committed.
  if (jr::encodeProgress(current) == jr::encodeProgress(proposed_)) { acceptPending(); return; }
  // Do not merge a rating into changed progress or clobber a concurrent lesson.
  if (jr::encodeProgress(current) != jr::encodeProgress(progress_)) { status_ = Status::SaveError; return; }
  attemptPending();
}
void JapaneseReviewActivity::acceptPending() {
  progress_ = proposed_;
  pending_ = false;
  session_.advance();
  if (session_.done()) page_ = Page::Complete;
  status_ = Status::Saved;
}
bool JapaneseReviewActivity::checkSessionDay() {
  if (dayBlocked_) return false;
  const uint32_t today = TimeUtils::getLocalDayOrdinal(TimeUtils::getCurrentValidTimestamp());
  if (today == day_ && jr::validDay(today, progress_)) return true;
  // Once stale, this deterministic queue may only be replaced from Dashboard.
  // Never silently carry a pending rating onto a different local day.
  dayBlocked_ = true;
  status_ = Status::Clock;
  return false;
}
bool JapaneseReviewActivity::healthy() const {
  return status_ == Status::None || status_ == Status::Saved || status_ == Status::SaveError;
}
const char* JapaneseReviewActivity::ratingText() const {
  switch (proposedRating_) {
    case jr::Rating::Again: return tr(STR_JP_REVIEW_AGAIN);
    case jr::Rating::Familiar: return tr(STR_JP_REVIEW_FAMILIAR);
    case jr::Rating::Known: return tr(STR_JP_REVIEW_KNOWN);
  }
  return "";
}
const char* JapaneseReviewActivity::statusText() const {
  switch (status_) {
    case Status::None: return "";
    case Status::Saved: return tr(STR_JP_REVIEW_SAVED);
    case Status::SaveError: return tr(STR_JP_REVIEW_SAVE_ERROR);
    case Status::StorageError: return tr(STR_JP_REVIEW_STORAGE_ERROR);
    case Status::Corrupt: return tr(STR_JP_REVIEW_CORRUPT);
    case Status::Clock: return tr(STR_JP_REVIEW_CLOCK);
  }
  return "";
}
void JapaneseReviewActivity::build(UiScreen& s) {
  const auto& metrics = UITheme::getInstance().getMetrics();
  s.setContentMarginFromScreen(fui::Insets{int16_t(metrics.topPadding + metrics.headerHeight + 8), 12, 12, 12});
  const auto a = s.body();
  const auto stats = jr::stats(progress_, day_);
  std::snprintf(counts_[0].data(), counts_[0].size(), "%s %d", tr(STR_JP_REVIEW_NEW), stats.fresh);
  std::snprintf(counts_[1].data(), counts_[1].size(), "%s %d", tr(STR_JP_REVIEW_DUE), stats.due);
  std::snprintf(counts_[2].data(), counts_[2].size(), "%s %d", tr(STR_JP_REVIEW_DONE), stats.completed);
  auto style = s.theme().smallText; style.align = fui::TextAlign::Center; style.maxLines = 2;
  const int line = renderer.getLineHeight(SMALL_FONT_ID);
  if (page_ == Page::Dashboard && healthy()) {
    for (int i = 0; i < 3; ++i)
      s.target().text(fui::Rect{a.x, int16_t(a.y + 80 + i * (2 * line + 12)), a.width, int16_t(2 * line)}, counts_[i].data(), style);
  } else if (page_ == Page::Dashboard) {
    s.target().text(fui::Rect{a.x, int16_t(a.y + 80), a.width, int16_t(2 * line)}, statusText(), style);
  }
  if (page_ != Page::Session) {
    s.target().text(fui::Rect{a.x, int16_t(a.bottom() - kButtonHeight - kGap - 2 * line), a.width, int16_t(2 * line)}, tr(STR_JP_REVIEW_RULES), style);
    if (healthy()) s.target().text(fui::Rect{a.x, int16_t(a.bottom() - kButtonHeight - kGap - 3 * line), a.width, int16_t(line)}, statusText(), style);
  }
  auto button = [&](const char* label, int value, int x, int width, int y, bool enabled = true) {
    fui::ButtonProps p; p.label = label; p.action = 1; p.value = value; p.inputMask = fui::InputTouch;
    p.text = style; p.minTouchSize = 44; p.enabled = enabled;
    s.button(p, fui::Rect{int16_t(x), int16_t(y), int16_t(width), kButtonHeight});
  };
  const int half = (a.width - kGap) / 2;
  const int bottom = a.bottom() - kButtonHeight;
  button(tr(STR_BACK), 0, a.x, half, bottom);
  if (page_ == Page::Dashboard) {
    button(tr(STR_JP_REVIEW_START), 1, a.x + half + kGap, a.width - half - kGap, bottom, healthy());
    return;
  }
  if (page_ == Page::Complete) {
    if (dayBlocked_) {
      s.target().text(fui::Rect{a.x, int16_t(a.y + 80), a.width, int16_t(2 * line)}, statusText(), style);
      return;
    }
    s.target().text(fui::Rect{a.x, int16_t(a.y + 80), a.width, int16_t(2 * line)}, tr(STR_JP_REVIEW_COMPLETE), style);
    s.target().text(fui::Rect{a.x, int16_t(a.y + 80 + 2 * line + 12), a.width, int16_t(2 * line)}, counts_[2].data(), style);
    return;
  }
  const int ratingY = bottom - kButtonHeight - kGap;
  const int rulesY = ratingY - 2 * line - 12;
  s.target().text(fui::Rect{a.x, a.y, a.width, int16_t(2 * line)}, position_.data(), style);
  if (session_.revealed()) {
    const int third = (a.width - 2 * kGap) / 3;
    button(tr(STR_JP_REVIEW_AGAIN), 3, a.x, third, ratingY, !pending_ && !dayBlocked_);
    button(tr(STR_JP_REVIEW_FAMILIAR), 4, a.x + third + kGap, third, ratingY, !pending_ && !dayBlocked_);
    button(tr(STR_JP_REVIEW_KNOWN), 5, a.x + 2 * (third + kGap), a.width - 2 * (third + kGap), ratingY, !pending_ && !dayBlocked_);
    if (pending_) button(tr(STR_JP_REVIEW_RETRY), 6, a.x + half + kGap, a.width - half - kGap, bottom, !dayBlocked_);
  } else {
    button(tr(STR_KANA_QUIZ_REVEAL), 2, a.x + half + kGap, a.width - half - kGap, bottom, !dayBlocked_);
  }
  auto footerStyle = style; footerStyle.maxLines = 1;
  s.target().text(fui::Rect{a.x, int16_t(rulesY), a.width, int16_t(line)}, statusText(), footerStyle);
  s.target().text(fui::Rect{a.x, int16_t(rulesY + line), a.width, int16_t(line)}, tr(STR_JP_REVIEW_RULES), footerStyle);
  const auto& card = kana::cards[session_.current()];
  const int wordHeight = renderer.getLineHeight(kWordFontId);
  const int groupHeight = wordHeight + 24 + 2 * line + 16;
  const int wordY = a.y + 2 * line + std::max(0, (rulesY - 12 - a.y - 2 * line - groupHeight) / 2);
  renderer.drawText(kWordFontId, a.x + (a.width - renderer.getTextWidth(kWordFontId, card.example)) / 2, wordY, card.example);
  const int answerY = wordY + wordHeight + 24;
  if (session_.revealed()) {
    renderer.drawText(SMALL_FONT_ID, a.x + (a.width - renderer.getTextWidth(SMALL_FONT_ID, card.exampleRomaji)) / 2, answerY, card.exampleRomaji);
    renderer.drawText(SMALL_FONT_ID, a.x + (a.width - renderer.getTextWidth(SMALL_FONT_ID, card.meaning)) / 2, answerY + line + 16, card.meaning);
  } else {
    s.target().text(fui::Rect{a.x, int16_t(answerY), a.width, int16_t(2 * line)}, tr(STR_JP_WORDS_PROMPT), style);
  }
}
