#pragma once
#include <array>
#include <cstdint>
#include <utility>

namespace kana {
// A transient self-assessment; it deliberately has no SD practice linkage.
class Quiz {
 public:
  explicit Quiz(uint32_t seed) { restart(seed); }
  void restart(uint32_t seed) {
    for (int i = 0; i < 46; ++i) order_[i] = static_cast<uint8_t>(i);
    uint32_t state = seed ? seed : 1;
    for (int i = 45; i > 0; --i) {
      state ^= state << 13;
      state ^= state >> 17;
      state ^= state << 5;
      std::swap(order_[i], order_[state % (i + 1)]);
    }
    position_ = 0;
    roundSize_ = 46;
    missedCount_ = 0;
    round_ = 1;
    firstKnown_ = 0;
    revealed_ = false;
  }
  int size() const { return roundSize_; }
  int round() const { return round_; }
  int position() const { return position_; }
  int current() const { return done() ? -1 : order_[position_]; }
  int firstKnown() const { return firstKnown_; }
  bool done() const { return position_ >= size(); }
  bool revealed() const { return revealed_; }
  bool reveal() {
    if (done() || revealed_) return false;
    revealed_ = true;
    return true;
  }
  bool mark(bool known) {
    if (done() || !revealed_) return false;
    if (round_ == 1 && known) ++firstKnown_;
    if (!known) retry_[missedCount_++] = order_[position_];
    revealed_ = false;
    ++position_;
    if (position_ == roundSize_ && missedCount_ > 0) {
      order_.swap(retry_);
      roundSize_ = missedCount_;
      missedCount_ = 0;
      position_ = 0;
      ++round_;
    }
    return true;
  }
 private:
  std::array<uint8_t, 46> order_{};
  std::array<uint8_t, 46> retry_{};
  int position_ = 0;
  int roundSize_ = 46;
  int missedCount_ = 0;
  int round_ = 1;
  int firstKnown_ = 0;
  bool revealed_ = false;
};
}  // namespace kana
