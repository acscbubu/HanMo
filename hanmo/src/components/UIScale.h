#pragma once
#include "fontIds.h"
#include "CrossPointSettings.h"

// Keep primary interface text at one size. The existing global large option
// selects 12pt for titles and body together; normal selects 10pt together.
// Compact status text and dedicated reader/lesson fonts remain independent.
struct UIScaleSpec {
  int smallFontId;
  int bodyFontId;
  int titleFontId;
};
inline UIScaleSpec uiScaleSpec() {
  const int fontId = SETTINGS.uiTextSize == 1 ? UI_12_FONT_ID : UI_10_FONT_ID;
  return {fontId, fontId, fontId};
}
