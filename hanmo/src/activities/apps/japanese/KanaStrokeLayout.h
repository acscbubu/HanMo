#pragma once
#include <algorithm>
#include "KanaStroke.h"

namespace kana_ui {
struct Box { int x, y, w, h; };

// One geometry source for FreeInkUI's drawn and tappable control bounds.
struct StrokeLayout {
  static constexpr int kButtonHeight = 48;
  static constexpr int kGap = 9;
  Box hiragana{}, katakana{};
  Box previousStroke{}, restart{}, nextStroke{};
  Box previousCard{}, back{}, nextCard{};
  Box romaji{}, progress{}, hint{}, source{};
  int artX = 0, artY = 0, artSide = 0, glyphY = 0;

  static StrokeLayout forBody(int x, int y, int width, int height) {
    StrokeLayout l;
    const int half = (width - kGap) / 2;
    const int third = (width - 2 * kGap) / 3;
    const int last = width - 2 * (third + kGap);
    const int cardY = y + height - kButtonHeight;
    const int strokeY = cardY - kGap - kButtonHeight;
    l.hiragana = {x, y, half, kButtonHeight};
    l.katakana = {x + half + kGap, y, width - half - kGap, kButtonHeight};
    l.previousStroke = {x, strokeY, third, kButtonHeight};
    l.restart = {x + third + kGap, strokeY, third, kButtonHeight};
    l.nextStroke = {x + 2 * (third + kGap), strokeY, last, kButtonHeight};
    l.previousCard = {x, cardY, third, kButtonHeight};
    l.back = {x + third + kGap, cardY, third, kButtonHeight};
    l.nextCard = {x + 2 * (third + kGap), cardY, last, kButtonHeight};
    // Put the two explanation blocks together immediately above the controls.
    l.source = {x, strokeY - 32, width, 24};
    l.hint = {x, l.source.y - kGap - 56, width, 56};
    l.progress = {x, l.hint.y - 4 - 30, width, 30};
    l.artY = y + kButtonHeight + 30;
    // The longest authored 50-sound card reading is yu（優）: keep its 20pt
    // glyphs in the left column without letting them touch the diagram.
    l.artSide = std::min({280, std::max(150, width - 172),
                          std::max(150, l.progress.y - l.artY - 40)});
    l.artX = x + width - l.artSide - 6;
    l.glyphY = l.artY - 30;
    // Keep the card's romaji + Chinese sound hint under the kana.
    l.romaji = {x + 12, l.artY + 102, std::max(0, l.artX - x - 18), 48};
    return l;
  }
};

// Align the baseline of the Latin reading with the actual kana glyph's center.
inline int centerUnderGlyph(int glyphX, int glyphWidth, int readingWidth) {
  return glyphX + (glyphWidth - readingWidth) / 2;
}

// Preserve glyph centering when possible, but keep longer Chinese sound hints
// inside the left column and clear of the adjacent stroke diagram.
inline int centerReadingInColumn(const Box& column, int glyphWidth, int readingWidth) {
  return std::clamp(centerUnderGlyph(column.x, glyphWidth, readingWidth),
                    column.x, column.x + column.w - readingWidth);
}

inline bool selectScript(kana::StrokeLesson& lesson, kana::Script wanted) {
  if (lesson.script() == wanted) return false;
  return lesson.toggleScript();
}
}  // namespace kana_ui
