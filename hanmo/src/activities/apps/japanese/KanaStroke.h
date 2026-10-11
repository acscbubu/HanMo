#pragma once

#include "KanaStroke.generated.h"

namespace kana {
// The generated paths are sourced from the pinned SVG stroke order, while this
// small state machine owns only the transient lesson position.
static_assert(kStrokeCardCount == 46, "kana stroke data must cover the 46 basic cards");
}  // namespace kana
