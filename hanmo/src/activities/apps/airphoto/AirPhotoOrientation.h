#pragma once

#include <cstddef>
#include <cstdint>

namespace airphoto {

// Read only the PNG signature and IHDR dimensions; invalid or incomplete data
// is treated as portrait so a corrupt photo never rotates the whole UI.
inline bool isLandscapePng(const uint8_t* header, size_t size) {
  static constexpr uint8_t kSignature[] = {137, 80, 78, 71, 13, 10, 26, 10};
  if (!header || size < 24) return false;
  for (size_t i = 0; i < sizeof(kSignature); ++i) {
    if (header[i] != kSignature[i]) return false;
  }
  if (header[8] != 0 || header[9] != 0 || header[10] != 0 || header[11] != 13 ||
      header[12] != 'I' || header[13] != 'H' || header[14] != 'D' || header[15] != 'R') {
    return false;
  }
  const uint32_t width = (uint32_t(header[16]) << 24) | (uint32_t(header[17]) << 16) |
                         (uint32_t(header[18]) << 8) | uint32_t(header[19]);
  const uint32_t height = (uint32_t(header[20]) << 24) | (uint32_t(header[21]) << 16) |
                          (uint32_t(header[22]) << 8) | uint32_t(header[23]);
  return width > 0 && height > 0 && width > height;
}

}  // namespace airphoto
