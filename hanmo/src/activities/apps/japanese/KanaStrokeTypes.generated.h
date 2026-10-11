// SPDX-License-Identifier: MIT
// Generated interface declarations; see root MIT license.
#pragma once
#include <cstdint>
namespace kana {
struct StrokePoint { uint16_t x; uint16_t y; };
struct StrokePart { uint8_t pointCount; const StrokePoint* points; };
struct Stroke { uint8_t partCount; const StrokePart* parts; };
struct GlyphStrokes { const char* glyph; uint8_t strokeCount; const Stroke* strokes; };
struct StrokeCard { GlyphStrokes hiragana; GlyphStrokes katakana; };
}
