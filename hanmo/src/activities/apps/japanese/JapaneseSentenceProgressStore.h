#pragma once

#include <HalStorage.h>
#include <array>
#include <cstddef>
#include <cstdint>
#include "JapaneseSentenceProgress.h"
#include "JapaneseReviewStore.h"

namespace japanese::sentenceprogress {
inline constexpr char kProgressPath[] = "/.crosspoint/japanese-sentences-v4.bin";
inline constexpr char kProgressPart[] = "/.crosspoint/japanese-sentences-v4.bin.part";
inline constexpr char kProgressBackup[] = "/.crosspoint/japanese-sentences-v4.bin.bak";
inline constexpr uint32_t kTableId = 0x4A534403u;  // Immutable topic table edition 3.
inline constexpr size_t kProgressBytes = 648;
inline constexpr char kLegacyV2Path[] = "/.crosspoint/japanese-sentences-v2.bin";
inline constexpr char kLegacyV2Backup[] = "/.crosspoint/japanese-sentences-v2.bin.bak";
// Exact half-open byte offsets; all multibyte fields LE, never native structs:
// [0,4) JSP4; 4 version=4; 5 categories=9; 6 max category size=30; 7 reserved=0;
// [8,10) cards=270 u16; [10,12) read bytes=34 u16; [12,14) edition=3 u16;
// [14,16) length=648 u16; [16,20) table=0x4A534403 u32; [20,24) revision u32;
// 24 lastCategory; [25,34) local positions; [34,68) physical read bitmap;
// [68,77) category IDs 0..8; [77,86) category counts (all 30);
// [86,104) category firsts (0,30,...,240) u16; [104,644) stable scene IDs u16;
// [644,648) CRC32 over [0,644). Bits 270/271 are reserved zero; local <30.
// Stable ID: local<6 ? category*6+local : 54+category*24+(local-6).
// Thus legacy IDs 0..53 keep their meanings, including categories after Basic.
inline constexpr std::array<uint16_t, kCardCount> kSceneIds = [] {
  std::array<uint16_t, kCardCount> ids{};
  for (int category = 0; category < kCategoryCount; ++category)
    for (int local = 0; local < categorySize(category); ++local)
      ids[categoryFirst(category) + local] = static_cast<uint16_t>(
          local < 6 ? category * 6 + local : 54 + category * 24 + local - 6);
  return ids;
}();
enum class LoadStatus { Empty, Imported, Loaded, StorageError, Corrupt };
namespace detail {
inline uint32_t checksum(const uint8_t* data, size_t size) { return review::detail::checksum(data, size); }
inline void put(uint8_t* out, uint32_t value, int count) { review::detail::put(out, value, count); }
inline uint32_t get(const uint8_t* in, int count) { return review::detail::get(in, count); }
}  // namespace detail
inline std::array<uint8_t, kProgressBytes> encodeProgress(const Progress& p) {
  std::array<uint8_t, kProgressBytes> bytes{'J', 'S', 'P', '4', 4, kCategoryCount, kMaxCardsPerCategory, 0};
  detail::put(bytes.data() + 8, kCardCount, 2);
  detail::put(bytes.data() + 10, kReadBytes, 2);
  detail::put(bytes.data() + 12, 3, 2);
  detail::put(bytes.data() + 14, kProgressBytes, 2);
  detail::put(bytes.data() + 16, kTableId, 4);
  detail::put(bytes.data() + 20, p.revision, 4);
  bytes[24] = p.lastCategory;
  for (int i = 0; i < kCategoryCount; ++i) {
    bytes[25 + i] = p.positions[i];
    bytes[68 + i] = static_cast<uint8_t>(i);
    bytes[77 + i] = kCategoryCounts[i];
    detail::put(bytes.data() + 86 + 2 * i, kCategoryFirsts[i], 2);
  }
  for (int i = 0; i < kReadBytes; ++i) bytes[34 + i] = p.readBits[i];
  for (int i = 0; i < kCardCount; ++i) detail::put(bytes.data() + 104 + 2 * i, kSceneIds[i], 2);
  detail::put(bytes.data() + 644, detail::checksum(bytes.data(), 644), 4);
  return bytes;
}
inline bool decodeProgress(const std::array<uint8_t, kProgressBytes>& bytes, Progress& out) {
  if (bytes[0] != 'J' || bytes[1] != 'S' || bytes[2] != 'P' || bytes[3] != '4' || bytes[4] != 4 ||
      bytes[5] != kCategoryCount || bytes[6] != kMaxCardsPerCategory || bytes[7] != 0 ||
      detail::get(bytes.data() + 8, 2) != kCardCount || detail::get(bytes.data() + 10, 2) != kReadBytes ||
      detail::get(bytes.data() + 12, 2) != 3 || detail::get(bytes.data() + 14, 2) != kProgressBytes ||
      detail::get(bytes.data() + 16, 4) != kTableId ||
      detail::get(bytes.data() + 644, 4) != detail::checksum(bytes.data(), 644)) return false;
  for (int i = 0; i < kCategoryCount; ++i)
    if (bytes[68 + i] != i || bytes[77 + i] != kCategoryCounts[i] ||
        detail::get(bytes.data() + 86 + 2 * i, 2) != kCategoryFirsts[i]) return false;
  for (int i = 0; i < kCardCount; ++i)
    if (detail::get(bytes.data() + 104 + 2 * i, 2) != kSceneIds[i]) return false;
  Progress p;
  p.revision = detail::get(bytes.data() + 20, 4);
  p.lastCategory = bytes[24];
  for (int i = 0; i < kCategoryCount; ++i) p.positions[i] = bytes[25 + i];
  for (int i = 0; i < kReadBytes; ++i) p.readBits[i] = bytes[34 + i];
  if (!validProgress(p)) return false;
  out = p;
  return true;
}
namespace detail {
// Read-only legacy codec: exact JSP2/version2/edition1/schema0x4A534401.
// [16,20) revision; 20 last category; [21,30) positions (<6);
// [30,37) bits54 (54/55 reserved zero); [37,46) category IDs;
// [46,100) IDs0..53; [100,104) CRC32 over [0,100).
inline constexpr size_t kLegacyV2Bytes = 104;
inline bool decodeLegacyV2(const std::array<uint8_t, kLegacyV2Bytes>& bytes, Progress& out) {
  if (bytes[0] != 'J' || bytes[1] != 'S' || bytes[2] != 'P' || bytes[3] != '2' || bytes[4] != 2 ||
      bytes[5] != 9 || bytes[6] != 6 || bytes[7] != 54 || bytes[8] != 7 || bytes[9] != 1 ||
      get(bytes.data() + 10, 2) != kLegacyV2Bytes || get(bytes.data() + 12, 4) != 0x4A534401u ||
      get(bytes.data() + 100, 4) != checksum(bytes.data(), 100) || bytes[20] >= 9 || (bytes[36] & 0xC0u))
    return false;
  for (int category = 0; category < 9; ++category)
    if (bytes[21 + category] >= 6 || bytes[37 + category] != category) return false;
  for (int global = 0; global < 54; ++global) if (bytes[46 + global] != global) return false;
  Progress imported;
  imported.revision = get(bytes.data() + 16, 4);
  imported.lastCategory = bytes[20];
  for (int category = 0; category < 9; ++category) imported.positions[category] = bytes[21 + category];
  for (int oldGlobal = 0; oldGlobal < 54; ++oldGlobal) {
    if (!(bytes[30 + oldGlobal / 8] & (1u << (oldGlobal % 8)))) continue;
    const int global = categoryFirst(oldGlobal / 6) + oldGlobal % 6;
    imported.readBits[global / 8] |= static_cast<uint8_t>(1u << (global % 8));
  }
  out = imported;
  return true;
}
template <typename FS>
LoadStatus readLegacyV2(FS& fs, const char* path, Progress& out,
                        std::array<uint8_t, kLegacyV2Bytes>* raw = nullptr) {
  HalFile file;
  if (!fs.openFileForRead("JP_SENTENCES", path, file)) return LoadStatus::StorageError;
  const bool sizeOk = file.size() == kLegacyV2Bytes;
  std::array<uint8_t, kLegacyV2Bytes> bytes{};
  const bool readOk = sizeOk && file.read(bytes.data(), bytes.size()) == static_cast<int>(bytes.size());
  const bool closed = file.close();
  if (!closed || !fs.ready() || !fs.exists(path)) return LoadStatus::StorageError;
  if (!sizeOk) return LoadStatus::Corrupt;
  if (!readOk) return LoadStatus::StorageError;
  Progress imported;
  if (!decodeLegacyV2(bytes, imported)) return LoadStatus::Corrupt;
  out = imported;
  if (raw) *raw = bytes;
  return LoadStatus::Imported;
}
template <typename FS>
LoadStatus readProgress(FS& fs, const char* path, Progress& out,
                        std::array<uint8_t, kProgressBytes>* raw = nullptr) {
  HalFile file;
  if (!fs.openFileForRead("JP_SENTENCES", path, file)) return LoadStatus::StorageError;
  const bool sizeOk = file.size() == kProgressBytes;
  std::array<uint8_t, kProgressBytes> bytes{};
  const bool readOk = sizeOk && file.read(bytes.data(), bytes.size()) == static_cast<int>(bytes.size());
  // HalFile (not raw FsFile): explicit close checks transaction durability/errors.
  const bool closed = file.close();
  if (!closed || !fs.ready() || !fs.exists(path)) return LoadStatus::StorageError;
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
  if (fs.exists(kProgressPath)) return detail::readProgress(fs, kProgressPath, out);
  if (fs.exists(kProgressBackup)) {
    Progress recovered;
    std::array<uint8_t, kProgressBytes> bytes{};
    const auto status = detail::readProgress(fs, kProgressBackup, recovered, &bytes);
    if (status != LoadStatus::Loaded) return status;
    if (!fs.rename(kProgressBackup, kProgressPath) || !detail::exactRead(fs, kProgressPath, bytes)) return LoadStatus::StorageError;
    out = recovered;
    return LoadStatus::Loaded;
  }
  // Never call legacy loaders that repair/rename old commits. The live v2
  // (including corrupt/future formats) is authoritative over its backup/v1.
  const char* v2Path = fs.exists(kLegacyV2Path) ? kLegacyV2Path :
                       fs.exists(kLegacyV2Backup) ? kLegacyV2Backup : nullptr;
  if (v2Path) return detail::readLegacyV2(fs, v2Path, out);
  // Never call review::loadProgress: its backup recovery renames v1 files.
  // Import only a validated live v1, or its committed backup if live is absent.
  const char* legacyPath = fs.exists(review::kProgressPath) ? review::kProgressPath :
                           fs.exists(review::kProgressBackup) ? review::kProgressBackup : nullptr;
  if (!legacyPath) { out = Progress{}; return LoadStatus::Empty; }
  review::Progress legacy;
  const auto status = review::detail::readProgress(fs, legacyPath, legacy);
  if (status != review::LoadStatus::Loaded)
    return status == review::LoadStatus::Corrupt ? LoadStatus::Corrupt : LoadStatus::StorageError;
  if (!fs.ready() || !fs.exists(legacyPath)) return LoadStatus::StorageError;
  Progress imported;
  imported.positions[0] = legacy.sentencePosition;
  imported.readBits[0] = legacy.sentenceReadMask;
  out = imported;
  return LoadStatus::Imported;
}
namespace detail {
inline bool validTransition(const Progress& base, const Progress& next) {
  if (!validProgress(base) || !validProgress(next) || base.revision == UINT32_MAX ||
      next.revision != base.revision + 1) return false;
  for (int i = 0; i < kReadBytes; ++i) if ((next.readBits[i] & base.readBits[i]) != base.readBits[i]) return false;
  return next.lastCategory != base.lastCategory || next.positions != base.positions || next.readBits != base.readBits;
}
// Bounded stack snapshot, not heap: v1 words are intentionally absent from the
// imported Progress, so its mapped bitmap alone cannot detect a word-only edit.
// Preserve raw bytes (including record order) and the exact authoritative path.
struct LegacySnapshot {
  const char* path = nullptr;
  std::array<uint8_t, review::kProgressBytes> bytes{};
};
template <typename FS>
bool captureLegacySource(FS& fs, const Progress& expected, LegacySnapshot& snapshot) {
  if (!fs.ready()) return false;
  snapshot = LegacySnapshot{};
  const char* v2Path = fs.exists(kLegacyV2Path) ? kLegacyV2Path :
                       fs.exists(kLegacyV2Backup) ? kLegacyV2Backup : nullptr;
  Progress imported;
  if (v2Path) {
    std::array<uint8_t, kLegacyV2Bytes> raw{};
    if (readLegacyV2(fs, v2Path, imported, &raw) != LoadStatus::Imported) return false;
    snapshot.path = v2Path;
    for (size_t i = 0; i < raw.size(); ++i) snapshot.bytes[i] = raw[i];
  } else {
    const char* path = fs.exists(review::kProgressPath) ? review::kProgressPath :
                       fs.exists(review::kProgressBackup) ? review::kProgressBackup : nullptr;
    if (!path) return false;
    review::Progress legacy;
    if (review::detail::readProgress(fs, path, legacy, &snapshot.bytes) != review::LoadStatus::Loaded ||
        !fs.ready() || !fs.exists(path)) return false;
    snapshot.path = path;
    imported.positions[0] = legacy.sentencePosition;
    imported.readBits[0] = legacy.sentenceReadMask;
  }
  return encodeProgress(imported) == encodeProgress(expected);
}
}  // namespace detail

template <typename FS>
bool saveProgress(FS& fs, const Progress& desired, const Progress* expected = nullptr) {
#if defined(ARDUINO_ARCH_ESP32)
  HalStorage::StorageLock transaction;
#endif
  Progress base;
  const auto status = loadProgress(fs, base);
  if ((status != LoadStatus::Empty && status != LoadStatus::Imported && status != LoadStatus::Loaded) ||
      (expected && (!validProgress(*expected) || encodeProgress(*expected) != encodeProgress(base))) ||
      !detail::validTransition(base, desired) || !fs.ensureDirectoryExists("/.crosspoint")) return false;
  detail::LegacySnapshot importedSource;
  if (status == LoadStatus::Imported && !detail::captureLegacySource(fs, base, importedSource)) return false;
  const auto bytes = encodeProgress(desired);
  if (fs.exists(kProgressPart) && !fs.remove(kProgressPart)) return false;
  HalFile file;
  if (!fs.openFileForWrite("JP_SENTENCES", kProgressPart, file)) return false;
  const bool written = file.write(bytes.data(), bytes.size()) == bytes.size();
  if (written) file.flush();
  const bool closed = file.close();
  if (!written || !closed || !detail::exactRead(fs, kProgressPart, bytes)) {
    fs.remove(kProgressPart);
    return false;
  }
  // Recheck the exact expected source after staging, under the HAL transaction
  // lock. Empty/Imported must stay that status: never recover a concurrently
  // appearing v4 backup or silently initialize over a changed legacy import.
  bool unchanged = fs.ready();
  if (unchanged && status == LoadStatus::Loaded) {
    unchanged = fs.exists(kProgressPath) && detail::exactRead(fs, kProgressPath, encodeProgress(base));
  } else if (unchanged) {
    unchanged = !fs.exists(kProgressPath) && !fs.exists(kProgressBackup);
    if (unchanged && status == LoadStatus::Imported) {
      detail::LegacySnapshot currentSource;
      unchanged = detail::captureLegacySource(fs, base, currentSource) &&
                  currentSource.path == importedSource.path && currentSource.bytes == importedSource.bytes;
    } else if (unchanged) {
      Progress current;
      unchanged = loadProgress(fs, current) == status && encodeProgress(current) == encodeProgress(base);
    }
  }
  if (!unchanged) { fs.remove(kProgressPart); return false; }
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
  if (status == LoadStatus::Loaded) fs.remove(kProgressBackup);  // Old backup cleanup is nonessential.
  return true;
}
}  // namespace japanese::sentenceprogress
