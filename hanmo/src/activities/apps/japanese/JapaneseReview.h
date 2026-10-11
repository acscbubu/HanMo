#pragma once

#include <array>
#include <cstdint>
#include "JapaneseWords.h"

namespace japanese::review {
// Days since 1970-01-01, matching TimeUtils::getLocalDayOrdinal.
inline constexpr uint32_t kMinDay = 19723;  // 2024-01-01
inline constexpr uint32_t kMaxDay = 47481;  // 2099-12-31

enum class Rating : uint8_t { Again = 1, Familiar = 2, Known = 3 };
struct WordProgress {
  uint32_t dueDay = 0;
  uint32_t lastRatedDay = 0;
  uint16_t reviews = 0;
  uint8_t intervalDays = 0;
  uint8_t rating = 0;
};
struct Progress {
  std::array<WordProgress, japanese::Words::kCount> words{};
  uint32_t revision = 0;
  uint32_t latestDay = 0;
  uint8_t sentencePosition = 0;
  uint8_t sentenceReadMask = 0;
};
inline bool validDay(uint32_t today, const Progress& p) {
  return today >= kMinDay && today <= kMaxDay && today >= p.latestDay;
}
struct Stats { int due = 0; int fresh = 0; int completed = 0; };
inline Stats stats(const Progress& p, uint32_t today) {
  Stats result;
  for (const auto& word : p.words) {
    if (word.reviews == 0) ++result.fresh;
    else if (word.lastRatedDay == today) ++result.completed;
    else if (word.dueDay <= today) ++result.due;
  }
  return result;
}
inline int wordIndex(int cardId) {
  for (int i = 0; i < japanese::Words::kCount; ++i)
    if (japanese::Words::cardIdAt(i) == cardId) return i;
  return -1;
}
inline bool applyRating(Progress& p, int cardId, Rating rating, uint32_t today) {
  const int index = wordIndex(cardId);
  const auto raw = static_cast<uint8_t>(rating);
  if (index < 0 || raw < 1 || raw > 3 || !validDay(today, p) || p.revision == UINT32_MAX) return false;
  auto word = p.words[index];
  if (word.reviews && (word.lastRatedDay == today || word.dueDay > today)) return false;
  const uint8_t known = word.reviews == 0 ? 7 : word.intervalDays < 3 ? 3 :
                        word.intervalDays < 7 ? 7 : word.intervalDays < 14 ? 14 : 30;
  const uint8_t interval = rating == Rating::Again ? 1 : rating == Rating::Familiar ? 3 : known;
  if (today > kMaxDay - interval) return false;
  word.dueDay = today + interval;
  word.lastRatedDay = today;
  word.intervalDays = interval;
  word.rating = raw;
  if (word.reviews < UINT16_MAX) ++word.reviews;
  p.words[index] = word;
  p.latestDay = today;
  ++p.revision;
  return true;
}
// True means a new snapshot is available; an unchanged read is not a write.
inline bool recordSentence(Progress& p, int position, bool revealed) {
  if (position < 0 || position >= 6 || p.revision == UINT32_MAX) return false;
  const uint8_t mask = p.sentenceReadMask | (revealed ? static_cast<uint8_t>(1u << position) : 0u);
  if (p.sentencePosition == position && p.sentenceReadMask == mask) return false;
  p.sentencePosition = static_cast<uint8_t>(position);
  p.sentenceReadMask = mask;
  ++p.revision;
  return true;
}
class Session {
 public:
  bool start(const Progress& p, uint32_t today) {
    if (!validDay(today, p)) return false;
    Session next;
    // Stable insertion sort keeps equal due dates in authored shared-ID order.
    for (int i = 0; i < japanese::Words::kCount; ++i) {
      const auto& word = p.words[i];
      if (!word.reviews || word.lastRatedDay == today || word.dueDay > today) continue;
      int at = next.size_;
      while (at > 0 && p.words[wordIndex(next.queue_[at - 1])].dueDay > word.dueDay) {
        next.queue_[at] = next.queue_[at - 1];
        --at;
      }
      next.queue_[at] = static_cast<uint8_t>(japanese::Words::cardIdAt(i));
      ++next.size_;
    }
    for (int i = 0; i < japanese::Words::kCount; ++i)
      if (p.words[i].reviews == 0) next.queue_[next.size_++] = static_cast<uint8_t>(japanese::Words::cardIdAt(i));
    *this = next;
    return true;
  }
  int current() const { return done() ? -1 : queue_[position_]; }
  int size() const { return size_; }
  int position() const { return position_; }
  bool done() const { return position_ >= size_; }
  bool revealed() const { return revealed_; }
  bool reveal() {
    if (done() || revealed_) return false;
    revealed_ = true;
    return true;
  }
  // The caller must commit a valid rating before advancing; no SD writes here.
  bool advance() {
    if (done() || !revealed_) return false;
    ++position_;
    revealed_ = false;
    return true;
  }
 private:
  std::array<uint8_t, japanese::Words::kCount> queue_{};
  int size_ = 0;
  int position_ = 0;
  bool revealed_ = false;
};
}  // namespace japanese::review
