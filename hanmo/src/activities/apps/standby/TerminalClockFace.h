#pragma once

#include <cstdint>

#include "StandbyFace.h"

// Instrument-panel face: a framed readout with a reversed-out title bar, the
// time in seven-segment numerals, and a short block of labelled rows beneath a
// rule. Where the analog face is sparse this one is deliberately busy, so the
// rotation offers a real choice rather than two versions of the same idea.
//
// Every string it draws is ASCII on purpose: the face should render the same
// on a build without the CJK glyph set compiled in.
class TerminalClockFace final : public StandbyFace {
 public:
  void onEnter() override;
  TickResult tick() override;
  void render(GfxRenderer& renderer, const Rect& viewport) override;
  StrId titleId() const override { return StrId::STR_FACE_TERMINAL; }
  uint32_t secondsUntilNextWake() const override;

 private:
  uint32_t startMs_ = 0;
  int32_t lastMin_ = -1;
  int16_t lastTenMinuteBucket_ = -1;
};
