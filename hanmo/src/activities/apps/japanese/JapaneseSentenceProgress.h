#pragma once

#include <array>
#include <cstdint>

namespace japanese::sentenceprogress {
// Independent of generated teaching content; immutable category/card edition.
inline constexpr int kCategoryCount = 9;
inline constexpr int kMaxCardsPerCategory = 30;
inline constexpr int kCardCount = 270;
inline constexpr int kReadBytes = 34;
inline constexpr std::array<uint8_t, kCategoryCount> kCategoryCounts{30, 30, 30, 30, 30, 30, 30, 30, 30};
inline constexpr std::array<uint16_t, kCategoryCount> kCategoryFirsts{0, 30, 60, 90, 120, 150, 180, 210, 240};
inline constexpr int categorySize(int category) {
  return category >= 0 && category < kCategoryCount ? kCategoryCounts[category] : 0;
}
inline constexpr int categoryFirst(int category) {
  return category >= 0 && category < kCategoryCount ? kCategoryFirsts[category] : -1;
}
struct Progress {
  uint32_t revision = 0;
  uint8_t lastCategory = 0;
  std::array<uint8_t, kCategoryCount> positions{};
  std::array<uint8_t, kReadBytes> readBits{};
};
inline bool validProgress(const Progress& p) {
  if (p.lastCategory >= kCategoryCount || (p.readBits.back() & 0xC0u)) return false;
  for (int category = 0; category < kCategoryCount; ++category)
    if (p.positions[category] >= categorySize(category)) return false;
  return true;
}
inline bool isRead(const Progress& p, int global) {
  return global >= 0 && global < kCardCount && (p.readBits[global / 8] & (1u << (global % 8)));
}
inline int readCount(const Progress& p, int category) {
  if (category < 0 || category >= kCategoryCount) return 0;
  int count = 0;
  for (int local = 0; local < categorySize(category); ++local) if (isRead(p, categoryFirst(category) + local)) ++count;
  return count;
}
inline bool record(Progress& p, int category, int local, bool revealed) {
  if (!validProgress(p) || category < 0 || category >= kCategoryCount || local < 0 ||
      local >= categorySize(category) || p.revision == UINT32_MAX) return false;
  const int global = categoryFirst(category) + local;
  if (p.lastCategory == category && p.positions[category] == local && (!revealed || isRead(p, global))) return false;
  p.lastCategory = static_cast<uint8_t>(category);
  p.positions[category] = static_cast<uint8_t>(local);
  if (revealed) p.readBits[global / 8] |= static_cast<uint8_t>(1u << (global % 8));
  ++p.revision;
  return true;
}
// A pending snapshot's revision is not an event count for the new commit.
// Union all reads, but only explicitly dirty category positions/last category.
inline bool mergePending(Progress& latest, const Progress& pending, uint16_t dirtyCategories, bool dirtyLast) {
  if (!validProgress(latest) || !validProgress(pending) || (dirtyCategories & ~0x01FFu) ||
      latest.revision == UINT32_MAX) return false;
  Progress next = latest;
  for (int i = 0; i < kReadBytes; ++i) next.readBits[i] |= pending.readBits[i];
  for (int i = 0; i < kCategoryCount; ++i)
    if (dirtyCategories & (1u << i)) next.positions[i] = pending.positions[i];
  if (dirtyLast) next.lastCategory = pending.lastCategory;
  if (next.readBits == latest.readBits && next.positions == latest.positions && next.lastCategory == latest.lastCategory)
    return false;
  ++next.revision;
  latest = next;
  return true;
}
}  // namespace japanese::sentenceprogress
