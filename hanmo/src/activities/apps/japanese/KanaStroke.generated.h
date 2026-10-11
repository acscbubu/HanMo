// SPDX-License-Identifier: MIT
// Generated lesson control code; see root MIT license.
#pragma once
#include "KanaStrokeData.generated.h"
namespace kana {
enum class Script : uint8_t { Hiragana, Katakana };
class StrokeLesson { public: StrokeLesson() = default; int cardIndex() const { return card_; } Script script() const { return script_; } int visibleStrokes() const { return visible_; } int strokeCount() const { return glyph().strokeCount; } bool nextStroke() { if (visible_ >= strokeCount()) return false; ++visible_; return true; } bool previousStroke() { if (visible_ <= 1) return false; --visible_; return true; } void restart() { visible_=1; } bool toggleScript() { script_=script_==Script::Hiragana?Script::Katakana:Script::Hiragana; visible_=1; return true; } bool nextCard() { if (card_+1 >= kStrokeCardCount) return false; ++card_; visible_=1; return true; } bool previousCard() { if (card_<=0) return false; --card_; visible_=1; return true; } private: const GlyphStrokes& glyph() const { return script_==Script::Hiragana?strokeCards[card_].hiragana:strokeCards[card_].katakana; } int card_=0; int visible_=1; Script script_=Script::Hiragana; };
}  // namespace kana
