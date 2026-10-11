#pragma once
#include <array>
#include <cstdint>

namespace kana {
constexpr int kCardCount = 46;
constexpr int kPracticeRounds = 5;
constexpr uint8_t kPracticeBits = 0x7c;  // bits 2..6

// Markers belong to the absolute kana ID, never to the shuffled list position.
// Star and check have no enforced meaning; five circles record manual rounds.
struct Practice {
  std::array<uint8_t, kCardCount> marks{};

  bool active(int card, int marker) const {
    return card >= 0 && card < kCardCount && marker >= 0 && marker < 2 + kPracticeRounds &&
           (marks[card] & (uint8_t{1} << marker)) != 0;
  }

  bool toggle(int card, int marker) {
    if (card < 0 || card >= kCardCount || marker < 0 || marker >= 2 + kPracticeRounds) return false;
    marks[card] ^= static_cast<uint8_t>(1u << marker);
    return true;
  }

  int doneCount(int start, int count) const {
    if (start < 0 || count < 0 || start > kCardCount || count > kCardCount - start) return 0;
    int total = 0;
    for (int i = start; i < start + count; ++i) total += (marks[i] & kPracticeBits) != 0;
    return total;
  }
};
}  // namespace kana
