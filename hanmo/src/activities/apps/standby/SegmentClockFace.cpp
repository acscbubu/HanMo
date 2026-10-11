#include "SegmentClockFace.h"

#include <Arduino.h>
#include <GfxRenderer.h>
#include <HalPowerManager.h>
#include <time.h>

#include <cstdio>

#include "SegmentDigits.h"
#include "StandbyTime.h"
#include "fontIds.h"

void SegmentClockFace::onEnter() {
  startMs_ = millis();
  lastMin_ = -1;
  lastTenMinuteBucket_ = -1;
}

void SegmentClockFace::flip() {
  inverse_ = !inverse_;
  lastMin_ = -1;  // force the next tick to redraw rather than wait for the minute
}

void SegmentClockFace::onShake(uint32_t) { flip(); }

void SegmentClockFace::onPagePrev() { flip(); }

void SegmentClockFace::onPageNext() { flip(); }

StandbyFace::TickResult SegmentClockFace::tick() {
  const uint32_t nowMin = standby_time::getMinuteTick(startMs_);
  if (static_cast<int32_t>(nowMin) == lastMin_) return TickResult::None;
  lastMin_ = static_cast<int32_t>(nowMin);

  const uint8_t currentBucket = standby_time::getTenMinuteBucket(startMs_);
  const bool cleanGhosting = standby_time::didTenMinuteBucketChange(lastTenMinuteBucket_, currentBucket);
  lastTenMinuteBucket_ = currentBucket;
  // A full-bleed black field leaves more behind than line art does, so the
  // inverted variant always asks for the cleanup waveform.
  return (cleanGhosting || inverse_) ? TickResult::RedrawWithGhostCleanup : TickResult::Redraw;
}

void SegmentClockFace::render(GfxRenderer& renderer, const Rect& viewport) {
  unsigned hh = 0;
  unsigned mm = 0;
  standby_time::getNowHHMM(startMs_, hh, mm);

  const bool ink = !inverse_;
  if (inverse_) renderer.fillRect(viewport.x, viewport.y, viewport.width, viewport.height, true);

  const int margin = viewport.width / 12;
  int cell = segment_digits::cellHeightForWidth(viewport.width - 2 * margin);
  if (cell > viewport.height / 3) cell = viewport.height / 3;
  const auto metrics = segment_digits::metricsFor(cell);

  const int runWidth = segment_digits::hhmmWidth(metrics);
  const int x = viewport.x + (viewport.width - runWidth) / 2;
  const int y = viewport.y + (viewport.height - metrics.cellHeight) / 2 - metrics.cellHeight / 4;
  segment_digits::drawHHMM(renderer, x, y, metrics, hh, mm, ink);

  char label[40];
  const time_t now = time(nullptr);
  struct tm local = {};
  if (standby_time::isSynced() && localtime_r(&now, &local) != nullptr) {
    strftime(label, sizeof(label), "%A  %d %B", &local);
  } else {
    snprintf(label, sizeof(label), "%s", "--");
  }
  const int labelY = y + metrics.cellHeight + metrics.cellHeight / 3;
  renderer.drawCenteredText(NOTOSANS_16_FONT_ID, labelY, label, ink);

  // Charge belongs on a standby screen: it is the one number you want from a
  // device you are about to leave alone for a while.
  char status[24];
  snprintf(status, sizeof(status), "BATT  %u%%", static_cast<unsigned>(powerManager.getBatteryPercentage()));
  renderer.drawCenteredText(UI_12_FONT_ID, labelY + renderer.getLineHeight(NOTOSANS_16_FONT_ID) + 12, status, ink);
}

uint32_t SegmentClockFace::secondsUntilNextWake() const {
  uint32_t sec;
  if (standby_time::isSynced()) {
    const time_t now = time(nullptr);
    sec = static_cast<uint32_t>(now % 60);
  } else {
    sec = static_cast<uint32_t>(((millis() - startMs_) / 1000u) % 60u);
  }
  const uint32_t remaining = (sec == 0) ? 60u : (60u - sec);
  return remaining < 1u ? 1u : remaining;
}
