#pragma once

#include <HalStorage.h>
#include <array>
#include <cstddef>
#include <cstdint>
#include "JapaneseReview.h"

namespace japanese::review {
inline constexpr char kProgressPath[] = "/.crosspoint/japanese-review-v1.bin";
inline constexpr char kProgressPart[] = "/.crosspoint/japanese-review-v1.bin.part";
inline constexpr char kProgressBackup[] = "/.crosspoint/japanese-review-v1.bin.bak";
// Header: magic[4], version, word count, sentence edition/count, revision/day
// LE32, position/mask, authored sentence IDs[6] (0..5 = sentence-01..06 in
// immutable edition 1). Each word: shared ID, due/last LE32, reviews LE16,
// interval/rating. CRC32 LE covers all preceding bytes; no native structs on SD.
inline constexpr size_t kProgressBytes = 24 + 13 * japanese::Words::kCount + 4;
enum class LoadStatus { Empty, Loaded, Corrupt, StorageError };
namespace detail {
inline uint32_t checksum(const uint8_t* data, size_t size) {
  uint32_t crc = 0xFFFFFFFFu;
  for (size_t i = 0; i < size; ++i) {
    crc ^= data[i];
    for (int bit = 0; bit < 8; ++bit) crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
  }
  return ~crc;
}
inline void put(uint8_t* out, uint32_t value, int count) {
  for (int i = 0; i < count; ++i) out[i] = static_cast<uint8_t>(value >> (8 * i));
}
inline uint32_t get(const uint8_t* in, int count) {
  uint32_t value = 0;
  for (int i = 0; i < count; ++i) value |= static_cast<uint32_t>(in[i]) << (8 * i);
  return value;
}
}  // namespace detail
inline std::array<uint8_t, kProgressBytes> encodeProgress(const Progress& p) {
  std::array<uint8_t, kProgressBytes> bytes{'J', 'R', 'P', '1', 1, japanese::Words::kCount, 1, 6};
  detail::put(bytes.data() + 8, p.revision, 4);
  detail::put(bytes.data() + 12, p.latestDay, 4);
  bytes[16] = p.sentencePosition;
  bytes[17] = p.sentenceReadMask;
  for (int i = 0; i < 6; ++i) bytes[18 + i] = static_cast<uint8_t>(i);
  for (int i = 0; i < japanese::Words::kCount; ++i) {
    auto* record = bytes.data() + 24 + i * 13;
    const auto& word = p.words[i];
    record[0] = static_cast<uint8_t>(japanese::Words::cardIdAt(i));
    detail::put(record + 1, word.dueDay, 4);
    detail::put(record + 5, word.lastRatedDay, 4);
    detail::put(record + 9, word.reviews, 2);
    record[11] = word.intervalDays;
    record[12] = word.rating;
  }
  detail::put(bytes.data() + kProgressBytes - 4, detail::checksum(bytes.data(), kProgressBytes - 4), 4);
  return bytes;
}
inline bool decodeProgress(const std::array<uint8_t, kProgressBytes>& bytes, Progress& out) {
  if (bytes[0] != 'J' || bytes[1] != 'R' || bytes[2] != 'P' || bytes[3] != '1' ||
      bytes[4] != 1 || bytes[5] != japanese::Words::kCount || bytes[6] != 1 || bytes[7] != 6) return false;
  for (int i = 0; i < 6; ++i) if (bytes[18 + i] != i) return false;
  if (detail::get(bytes.data() + kProgressBytes - 4, 4) != detail::checksum(bytes.data(), kProgressBytes - 4)) return false;
  Progress p;
  p.revision = detail::get(bytes.data() + 8, 4);
  p.latestDay = detail::get(bytes.data() + 12, 4);
  p.sentencePosition = bytes[16];
  p.sentenceReadMask = bytes[17];
  if (p.sentencePosition >= 6 || (p.sentenceReadMask & 0xC0u)) return false;
  std::array<bool, japanese::Words::kCount> seen{};
  uint32_t lastDay = 0;
  uint32_t reviews = 0;
  for (int i = 0; i < japanese::Words::kCount; ++i) {
    const auto* record = bytes.data() + 24 + i * 13;
    const int index = wordIndex(record[0]);
    if (index < 0 || seen[index]) return false;
    seen[index] = true;
    auto& word = p.words[index];
    word.dueDay = detail::get(record + 1, 4);
    word.lastRatedDay = detail::get(record + 5, 4);
    word.reviews = static_cast<uint16_t>(detail::get(record + 9, 2));
    word.intervalDays = record[11];
    word.rating = record[12];
    if (!word.reviews) {
      if (word.dueDay || word.lastRatedDay || word.intervalDays || word.rating) return false;
      continue;
    }
    if (word.lastRatedDay < kMinDay || word.lastRatedDay > kMaxDay || word.rating < 1 || word.rating > 3) return false;
    const bool intervalOk = word.rating == 1 ? word.intervalDays == 1 :
                           word.rating == 2 ? word.intervalDays == 3 :
                           word.intervalDays == 3 || word.intervalDays == 7 || word.intervalDays == 14 || word.intervalDays == 30;
    if (!intervalOk || (word.reviews == 1 && word.rating == 3 && word.intervalDays != 7) ||
        word.lastRatedDay > kMaxDay - word.intervalDays || word.dueDay != word.lastRatedDay + word.intervalDays) return false;
    if (word.lastRatedDay > lastDay) lastDay = word.lastRatedDay;
    reviews += word.reviews;  // Lower bound only: saturated counters stay valid.
  }
  if (p.latestDay != lastDay || p.revision < reviews ||
      (!p.revision && (p.sentencePosition || p.sentenceReadMask))) return false;
  out = p;
  return true;
}
namespace detail {
inline bool validTransition(const Progress& base, const Progress& next) {
  if (base.revision == UINT32_MAX || next.revision != base.revision + 1) return false;
  const auto target = encodeProgress(next);
  Progress replay = base;
  const bool revealed = next.sentencePosition < 6 && (next.sentenceReadMask & (1u << next.sentencePosition));
  if (recordSentence(replay, next.sentencePosition, revealed) && encodeProgress(replay) == target) return true;
  for (int i = 0; i < japanese::Words::kCount; ++i) {
    const auto& word = next.words[i];
    if (word.lastRatedDay == base.words[i].lastRatedDay) continue;
    replay = base;
    if (applyRating(replay, japanese::Words::cardIdAt(i), static_cast<Rating>(word.rating), word.lastRatedDay) &&
        encodeProgress(replay) == target) return true;
  }
  return false;
}
template <typename FS>
LoadStatus readProgress(FS& fs, const char* path, Progress& out,
                        std::array<uint8_t, kProgressBytes>* raw = nullptr) {
  HalFile file;
  if (!fs.openFileForRead("JP_REVIEW", path, file)) return LoadStatus::StorageError;
  const bool sizeOk = file.size() == kProgressBytes;
  std::array<uint8_t, kProgressBytes> bytes{};
  const bool readOk = sizeOk && file.read(bytes.data(), bytes.size()) == static_cast<int>(bytes.size());
  const bool closed = file.close();
  if (!closed) return LoadStatus::StorageError;
  if (!sizeOk) return LoadStatus::Corrupt;
  if (!readOk) return LoadStatus::StorageError;
  Progress p;
  if (!decodeProgress(bytes, p)) return LoadStatus::Corrupt;
  out = p;
  if (raw) *raw = bytes;
  return LoadStatus::Loaded;
}
template <typename FS>
bool exactRead(FS& fs, const char* path, const std::array<uint8_t, kProgressBytes>& expected) {
  Progress ignored;
  std::array<uint8_t, kProgressBytes> bytes{};
  return readProgress(fs, path, ignored, &bytes) == LoadStatus::Loaded && bytes == expected;
}
}  // namespace detail

template <typename FS>
LoadStatus loadProgress(FS& fs, Progress& out) {
#if defined(ARDUINO_ARCH_ESP32)
  HalStorage::StorageLock transaction;
#endif
  if (!fs.ready()) return LoadStatus::StorageError;
  if (!fs.exists(kProgressPath)) {
    if (!fs.exists(kProgressBackup)) { out = Progress{}; return LoadStatus::Empty; }
    Progress recovered;
    std::array<uint8_t, kProgressBytes> bytes{};
    const auto status = detail::readProgress(fs, kProgressBackup, recovered, &bytes);
    if (status != LoadStatus::Loaded) return status;
    // Only a fully validated previous commit is eligible for recovery. Part is
    // never a source, even when it is valid and carries a later revision.
    if (!fs.rename(kProgressBackup, kProgressPath) || !detail::exactRead(fs, kProgressPath, bytes)) return LoadStatus::StorageError;
    out = recovered;
    return LoadStatus::Loaded;
  }
  return detail::readProgress(fs, kProgressPath, out);
}

template <typename FS>
bool saveProgress(FS& fs, const Progress& value, const Progress* expected = nullptr) {
#if defined(ARDUINO_ARCH_ESP32)
  HalStorage::StorageLock transaction;
#endif
  Progress base;
  const auto status = loadProgress(fs, base);
  const auto bytes = encodeProgress(value);
  Progress validated;
  if ((status != LoadStatus::Empty && status != LoadStatus::Loaded) || !decodeProgress(bytes, validated) ||
      (expected && encodeProgress(*expected) != encodeProgress(base)) ||
      !detail::validTransition(base, value) ||
      !fs.ensureDirectoryExists("/.crosspoint")) return false;
  if (fs.exists(kProgressPart) && !fs.remove(kProgressPart)) return false;
  HalFile file;
  if (!fs.openFileForWrite("JP_REVIEW", kProgressPart, file)) return false;
  const bool written = file.write(bytes.data(), bytes.size()) == bytes.size();
  if (written) file.flush();
  const bool closed = file.close();
  if (!written || !closed || !detail::exactRead(fs, kProgressPart, bytes)) {
    fs.remove(kProgressPart);
    return false;
  }
  // Recheck after staging; a stale proposal must never move a newer commit.
  if (!fs.ready() || (status == LoadStatus::Loaded ? !detail::exactRead(fs, kProgressPath, encodeProgress(base)) :
      fs.exists(kProgressPath) || fs.exists(kProgressBackup))) {
    fs.remove(kProgressPart);
    return false;
  }
  if (status == LoadStatus::Loaded) {
    if (fs.exists(kProgressBackup) && !fs.remove(kProgressBackup)) { fs.remove(kProgressPart); return false; }
    if (!fs.rename(kProgressPath, kProgressBackup)) { fs.remove(kProgressPart); return false; }
  }
  if (!fs.rename(kProgressPart, kProgressPath)) {
    if (status == LoadStatus::Loaded) fs.rename(kProgressBackup, kProgressPath);
    fs.remove(kProgressPart);
    return false;
  }
  if (!detail::exactRead(fs, kProgressPath, bytes)) return false;
  if (status == LoadStatus::Loaded) fs.remove(kProgressBackup);  // Cleanup failure leaves a safe old backup.
  return true;
}
}  // namespace japanese::review
