#pragma once

#include <cstdint>

#include "StandbyFace.h"

// Big seven-segment HH:MM with the date under it, and an inverted variant on
// the same face rather than as a second entry in the table: the picture is
// identical, only the ink is swapped, and a face rotation that offers the same
// clock twice is a worse menu than one that offers a switch.
//
// Up or Down flips it. The choice is not persisted; Standby is transient and a
// setting for it would outlive the moment it was made for.
class SegmentClockFace final : public StandbyFace {
 public:
  void onEnter() override;
  void onShake(uint32_t seed) override;
  void onPagePrev() override;
  void onPageNext() override;
  TickResult tick() override;
  void render(GfxRenderer& renderer, const Rect& viewport) override;
  StrId titleId() const override { return StrId::STR_FACE_SEGMENT_CLOCK; }
  uint32_t secondsUntilNextWake() const override;

 private:
  uint32_t startMs_ = 0;
  int32_t lastMin_ = -1;
  int16_t lastTenMinuteBucket_ = -1;
  bool inverse_ = false;

  void flip();
};
