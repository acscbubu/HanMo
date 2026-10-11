#pragma once
#include <HalStorage.h>
#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include "AirNoteStore.h"
#include "KanaPractice.h"

namespace kana {
inline constexpr char kPracticePath[] = "/.crosspoint/kana-practice-v1.bin";
inline constexpr char kPracticePart[] = "/.crosspoint/kana-practice-v1.bin.part";
inline constexpr char kPracticeBackup[] = "/.crosspoint/kana-practice-v1.bin.bak";
inline constexpr size_t kPracticeBytes = 6 + kCardCount + 4;
enum class LoadStatus { Empty, Loaded, Corrupt, StorageError };

inline uint32_t checksum(const uint8_t* bytes, size_t size) {
  uint32_t crc = 0xFFFFFFFFu;
  for (size_t i = 0; i < size; ++i) {
    crc ^= bytes[i];
    for (int j = 0; j < 8; ++j) crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
  }
  return ~crc;
}
inline std::array<uint8_t, kPracticeBytes> encodePractice(const Practice& value) {
  std::array<uint8_t, kPracticeBytes> bytes{'K', 'N', 'P', '1', 1, kCardCount};
  for (int i = 0; i < kCardCount; ++i) bytes[6 + i] = value.marks[i];
  const uint32_t crc = checksum(bytes.data(), kPracticeBytes - 4);
  for (int i = 0; i < 4; ++i) bytes[kPracticeBytes - 4 + i] = static_cast<uint8_t>(crc >> (i * 8));
  return bytes;
}
inline bool decodePractice(const std::array<uint8_t, kPracticeBytes>& bytes, Practice& result) {
  if (bytes[0] != 'K' || bytes[1] != 'N' || bytes[2] != 'P' || bytes[3] != '1' ||
      bytes[4] != 1 || bytes[5] != kCardCount) return false;
  for (int i = 0; i < kCardCount; ++i) if (bytes[6 + i] & 0x80u) return false;
  const uint32_t stored = static_cast<uint32_t>(bytes[kPracticeBytes - 4]) |
                          (static_cast<uint32_t>(bytes[kPracticeBytes - 3]) << 8) |
                          (static_cast<uint32_t>(bytes[kPracticeBytes - 2]) << 16) |
                          (static_cast<uint32_t>(bytes[kPracticeBytes - 1]) << 24);
  if (stored != checksum(bytes.data(), kPracticeBytes - 4)) return false;
  for (int i = 0; i < kCardCount; ++i) result.marks[i] = bytes[6 + i];
  return true;
}

template <typename FS>
LoadStatus loadPractice(FS& fs, Practice& result) {
  if (!AirNoteStore::recover(fs, kPracticePath, kPracticeBackup)) return LoadStatus::StorageError;
  if (!fs.exists(kPracticePath)) { result = Practice{}; return LoadStatus::Empty; }
  HalFile file;
  if (!fs.openFileForRead("KANA", kPracticePath, file)) return LoadStatus::StorageError;
  if (file.size() != kPracticeBytes) { file.close(); return LoadStatus::Corrupt; }
  std::array<uint8_t, kPracticeBytes> data{};
  const bool read = file.read(data.data(), data.size()) == static_cast<int>(data.size());
  const bool closed = file.close();
  if (!read || !closed) return LoadStatus::StorageError;
  Practice candidate;
  if (!decodePractice(data, candidate)) return LoadStatus::Corrupt;
  result = candidate;
  return LoadStatus::Loaded;
}

template <typename FS>
bool savePractice(FS& fs, const Practice& value, const Practice* expected = nullptr) {
  Practice checked;
  const LoadStatus status = loadPractice(fs, checked);
  if (status == LoadStatus::Corrupt || status == LoadStatus::StorageError ||
      (expected && checked.marks != expected->marks) ||
      !fs.ensureDirectoryExists("/.crosspoint")) return false;
  if (fs.exists(kPracticePart) && !fs.remove(kPracticePart)) return false;
  HalFile file;
  if (!fs.openFileForWrite("KANA", kPracticePart, file)) return false;
  const auto bytes = encodePractice(value);
  const bool written = file.write(bytes.data(), bytes.size()) == bytes.size();
  if (written) file.flush();
  const bool closed = file.close();
  if (!written || !closed) { fs.remove(kPracticePart); return false; }
  HalFile verify;
  if (!fs.openFileForRead("KANA", kPracticePart, verify) || verify.size() != kPracticeBytes) {
    if (verify) verify.close();
    fs.remove(kPracticePart);
    return false;
  }
  std::array<uint8_t, kPracticeBytes> readback{};
  const bool readbackOk = verify.read(readback.data(), readback.size()) == static_cast<int>(readback.size());
  verify.close();
  Practice decoded;
  if (!readbackOk || !decodePractice(readback, decoded) || decoded.marks != value.marks) {
    fs.remove(kPracticePart);
    return false;
  }
  if (status == LoadStatus::Empty) {
    if (!fs.rename(kPracticePart, kPracticePath)) { fs.remove(kPracticePart); return false; }
    return true;
  }
  if (!AirNoteStore::replace(fs, kPracticePath, kPracticePart, kPracticeBackup,
                             [](const std::string&) { return true; })) {
    fs.remove(kPracticePart);
    return false;
  }
  return true;
}
}  // namespace kana
