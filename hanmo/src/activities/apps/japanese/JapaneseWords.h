#pragma once
#include <array>
#include <cstdint>

namespace japanese {
// Session-only self-assessment. Reuses authored card IDs, never copies vocabulary
// or links to manual practice marks / storage. Both queues have fixed capacity.
class Words {
 public:
  static constexpr int kCount = 45;
  static constexpr int cardIdAt(int index) {
    return index < 0 || index >= kCount ? -1 : (index < 44 ? index : 45);
  }
  explicit Words(uint32_t seed = 0) { restart(seed); }
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
  void restart(uint32_t seed = 0) {
    for (int i = 0; i < kCount; ++i) order_[i] = static_cast<uint8_t>(cardIdAt(i));
    // Zero is the authored order; nonzero seeds shuffle reproducibly without
    // clocks, entropy or platform-dependent random generators.
    for (int i = seed ? kCount - 1 : 0; i > 0; --i) {
      seed ^= seed << 13;
      seed ^= seed >> 17;
      seed ^= seed << 5;
      const int j = static_cast<int>(seed % static_cast<uint32_t>(i + 1));
      const auto old = order_[i];
      order_[i] = order_[j];
      order_[j] = old;
    }
    position_ = firstKnown_ = missedCount_ = 0;
    roundSize_ = kCount;
    round_ = 1;
    revealed_ = false;
  }
 private:
  std::array<uint8_t, kCount> order_{};
  std::array<uint8_t, kCount> retry_{};
  int position_ = 0;
  int roundSize_ = kCount;
  int missedCount_ = 0;
  int round_ = 1;
  int firstKnown_ = 0;
  bool revealed_ = false;
};
}  // namespace japanese
