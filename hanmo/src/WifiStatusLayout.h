#pragma once
#include <algorithm>
namespace WifiStatusLayout {
constexpr int width = 20, height = 18, gap = 8;
struct Box {
  int x, y, width, height;
};
// Fit within the existing status band. Never change content/viewport height.
constexpr Box place(int left, int right, int top, int bandHeight, int pos, int occupiedLeft, int occupiedRight) {
  if (pos >= 3 || right - left < width) return {0, 0, 0, 0};
  int x = pos == 1 ? left : pos == 2 ? (left + right - width) / 2 : right - width;
  if (occupiedRight > occupiedLeft && x < occupiedRight + gap && x + width > occupiedLeft - gap) {
    if (pos == 1)
      x = occupiedRight + gap;
    else
      x = occupiedLeft - gap - width;
  }
  if (x < left || x + width > right) return {0, 0, 0, 0};
  return {x, top + std::max(0, (bandHeight - height) / 2), width, height};
}
}  // namespace WifiStatusLayout
