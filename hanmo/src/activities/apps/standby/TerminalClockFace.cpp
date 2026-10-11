#include "TerminalClockFace.h"

#include <Arduino.h>
#include <GfxRenderer.h>
#include <HalPowerManager.h>
#include <time.h>

#include <cstdio>

#include "SegmentDigits.h"
#include "StandbyTime.h"
#include "fontIds.h"

namespace {

// One labelled row: name on the left margin, value hard against the right.
void drawRow(GfxRenderer& renderer, const int left, const int right, const int y, const char* label,
             const char* value) {
  renderer.drawText(UI_12_FONT_ID, left, y, label);
  const int valueWidth = renderer.getTextWidth(NOTOSANS_14_FONT_ID, value);
  renderer.drawText(NOTOSANS_14_FONT_ID, right - valueWidth, y, value);
}

}  // namespace

void TerminalClockFace::onEnter() {
  startMs_ = millis();
  lastMin_ = -1;
  lastTenMinuteBucket_ = -1;
}

StandbyFace::TickResult TerminalClockFace::tick() {
  const uint32_t nowMin = standby_time::getMinuteTick(startMs_);
  if (static_cast<int32_t>(nowMin) == lastMin_) return TickResult::None;
  lastMin_ = static_cast<int32_t>(nowMin);

  const uint8_t currentBucket = standby_time::getTenMinuteBucket(startMs_);
  const bool cleanGhosting = standby_time::didTenMinuteBucketChange(lastTenMinuteBucket_, currentBucket);
  lastTenMinuteBucket_ = currentBucket;
  return cleanGhosting ? TickResult::RedrawWithGhostCleanup : TickResult::Redraw;
}

void TerminalClockFace::render(GfxRenderer& renderer, const Rect& viewport) {
  unsigned hh = 0;
  unsigned mm = 0;
  standby_time::getNowHHMM(startMs_, hh, mm);

  const int inset = 10;
  const int frameX = viewport.x + inset;
  const int frameY = viewport.y + inset;
  const int frameW = viewport.width - 2 * inset;
  const int frameH = viewport.height - 2 * inset;
  renderer.drawRoundedRect(frameX, frameY, frameW, frameH, 3, 10, true);

  const int barHeight = renderer.getLineHeight(UI_12_FONT_ID) + 14;
  renderer.fillRect(frameX + 3, frameY + 3, frameW - 6, barHeight, true);
  renderer.drawCenteredText(UI_12_FONT_ID, frameY + 3 + 7, "S T A N D B Y", false);

  const int padding = 22;
  const int left = frameX + padding;
  const int right = frameX + frameW - padding;
  int cell = segment_digits::cellHeightForWidth(right - left);
  if (cell > frameH / 3) cell = frameH / 3;
  const auto metrics = segment_digits::metricsFor(cell);

  const int runWidth = segment_digits::hhmmWidth(metrics);
  const int timeX = frameX + (frameW - runWidth) / 2;
  const int timeY = frameY + barHeight + (frameH - barHeight) / 2 - metrics.cellHeight;
  segment_digits::drawHHMM(renderer, timeX, timeY, metrics, hh, mm, true);

  int y = timeY + metrics.cellHeight + metrics.cellHeight / 3;
  renderer.fillRect(left, y, right - left, 2, true);
  y += 18;

  char dateText[24] = "--";
  char dayText[24] = "--";
  const time_t now = time(nullptr);
  struct tm local = {};
  const bool synced = standby_time::isSynced() && localtime_r(&now, &local) != nullptr;
  if (synced) {
    strftime(dateText, sizeof(dateText), "%Y-%m-%d", &local);
    strftime(dayText, sizeof(dayText), "%A", &local);
  }

  const int rowStep = renderer.getLineHeight(NOTOSANS_14_FONT_ID) + 10;
  drawRow(renderer, left, right, y, "DATE", dateText);
  y += rowStep;
  drawRow(renderer, left, right, y, "DAY", dayText);
  y += rowStep;
  char battText[16];
  snprintf(battText, sizeof(battText), "%u%%", static_cast<unsigned>(powerManager.getBatteryPercentage()));
  drawRow(renderer, left, right, y, "BATTERY", battText);
  y += rowStep;
  drawRow(renderer, left, right, y, "CLOCK", synced ? "SYNCED" : "FREE RUN");
}

uint32_t TerminalClockFace::secondsUntilNextWake() const {
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
