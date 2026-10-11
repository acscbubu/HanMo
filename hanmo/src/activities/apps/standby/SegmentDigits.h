#pragma once

#include <GfxRenderer.h>

#include <cstdint>

// Seven-segment numerals built from filled rectangles.
//
// The built-in faces stop at 18pt, which is nowhere near large enough for a
// clock meant to be read from across the room, and e-ink has no antialiasing
// worth the name, so straight rectangles lose nothing. They also invert
// cleanly, which is what the dark variant of the segment face needs.
namespace segment_digits {

struct Metrics {
  int cellWidth;
  int cellHeight;
  int thickness;
  int gap;
};

inline Metrics metricsFor(const int cellHeight) {
  Metrics m{};
  m.cellHeight = cellHeight;
  m.thickness = cellHeight / 8;
  if (m.thickness < 2) m.thickness = 2;
  m.cellWidth = (cellHeight * 7) / 12;
  m.gap = m.thickness;
  return m;
}

inline int colonWidth(const Metrics& m) { return m.thickness * 2; }

// Width of "HH:MM" at these metrics.
inline int hhmmWidth(const Metrics& m) {
  return 4 * m.cellWidth + 3 * m.gap + colonWidth(m) + 2 * m.gap;
}

// Largest cell height whose HH:MM still fits the given width. Sizing from the
// width rather than the height is what keeps the run from running off a
// portrait panel.
inline int cellHeightForWidth(const int availableWidth) {
  // hhmmWidth is very close to 3.21 * cellHeight once the ratios above are
  // substituted; solving for the height avoids a search loop.
  int cell = (availableWidth * 100) / 321;
  if (cell < 24) cell = 24;
  return cell;
}

// bit0..bit6 are segments a,b,c,d,e,f,g in the conventional order.
inline uint8_t maskFor(const int digit) {
  static const uint8_t kMasks[10] = {0x3F, 0x06, 0x5B, 0x4F, 0x66, 0x6D, 0x7D, 0x07, 0x7F, 0x6F};
  return (digit >= 0 && digit <= 9) ? kMasks[digit] : 0;
}

inline void drawDigit(const GfxRenderer& renderer, const int x, const int y, const Metrics& m, const int digit,
                      const bool ink) {
  if (digit < 0 || digit > 9) return;
  const uint8_t mask = maskFor(digit);
  const int t = m.thickness;
  const int w = m.cellWidth;
  const int h = m.cellHeight;
  const int mid = y + (h - t) / 2;
  const int barLen = w - 2 * t;
  const int stemLen = mid - (y + t);
  if (barLen <= 0 || stemLen <= 0) return;

  if (mask & 0x01) renderer.fillRect(x + t, y, barLen, t, ink);
  if (mask & 0x02) renderer.fillRect(x + w - t, y + t, t, stemLen, ink);
  if (mask & 0x04) renderer.fillRect(x + w - t, mid + t, t, stemLen, ink);
  if (mask & 0x08) renderer.fillRect(x + t, y + h - t, barLen, t, ink);
  if (mask & 0x10) renderer.fillRect(x, mid + t, t, stemLen, ink);
  if (mask & 0x20) renderer.fillRect(x, y + t, t, stemLen, ink);
  if (mask & 0x40) renderer.fillRect(x + t, mid, barLen, t, ink);
}

inline void drawColon(const GfxRenderer& renderer, const int x, const int y, const Metrics& m, const bool ink) {
  const int t = m.thickness;
  const int h = m.cellHeight;
  renderer.fillRect(x, y + h / 3 - t, t * 2, t * 2, ink);
  renderer.fillRect(x, y + (2 * h) / 3 - t, t * 2, t * 2, ink);
}

// Draws HH:MM with its left edge at x. Returns the width consumed.
inline int drawHHMM(const GfxRenderer& renderer, const int x, const int y, const Metrics& m, const unsigned hh,
                    const unsigned mm, const bool ink) {
  int cursor = x;
  drawDigit(renderer, cursor, y, m, static_cast<int>(hh / 10u), ink);
  cursor += m.cellWidth + m.gap;
  drawDigit(renderer, cursor, y, m, static_cast<int>(hh % 10u), ink);
  cursor += m.cellWidth + m.gap * 2;
  drawColon(renderer, cursor, y, m, ink);
  cursor += colonWidth(m) + m.gap * 2;
  drawDigit(renderer, cursor, y, m, static_cast<int>(mm / 10u), ink);
  cursor += m.cellWidth + m.gap;
  drawDigit(renderer, cursor, y, m, static_cast<int>(mm % 10u), ink);
  cursor += m.cellWidth;
  return cursor - x;
}

}  // namespace segment_digits
