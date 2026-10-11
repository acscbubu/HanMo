#pragma once
#include <array>
#include <cstdint>
#include <utility>
namespace kana {
struct State {
  std::array<uint8_t, 46> order{};
  int start = 0, count = 46, index = 0;
  bool roman = true, shuffled = false;
  uint32_t seed = 1;
  explicit State(int first = 0, int size = 46) {
    if (first >= 0 && size > 0 && first + size <= 46) {
      start = first;
      count = size;
    }
    resetOrder();
  }
  void resetOrder() {
    for (int i = 0; i < count; ++i) order[i] = start + i;
    index = 0;
  }
  int current() const { return order[index]; }
  void step(int direction) { index = (index + (direction < 0 ? count - 1 : 1)) % count; }
  void shuffle() {
    shuffled = !shuffled;
    resetOrder();
    if (!shuffled) return;
    if (!seed) seed = 1;
    for (int i = count - 1; i > 0; --i) {
      seed ^= seed << 13;
      seed ^= seed >> 17;
      seed ^= seed << 5;
      std::swap(order[i], order[seed % (i + 1)]);
    }
  }
};
}  // namespace kana
