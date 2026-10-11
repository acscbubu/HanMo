#pragma once

#include <cstddef>
#include <cstdint>

namespace freeink {
enum class Cst816sRegion : uint8_t { None, Screen, Home, Previous, Next, Invalid };
struct Cst816sFrame {
  Cst816sRegion region = Cst816sRegion::None;
  uint16_t x = 0;
  uint16_t y = 0;
};

// Five bytes starting at FingerNum (0x02). Decode bytes, never packed bitfields.
inline Cst816sFrame decodeCst816s(const uint8_t* data, size_t length) {
  if (!data || length != 5) return {Cst816sRegion::Invalid};
  if (data[0] == 0) return {};
  if (data[0] != 1) return {Cst816sRegion::Invalid};
  const uint16_t x = ((data[1] & 0x0F) << 8) | data[2];
  const uint16_t y = ((data[3] & 0x0F) << 8) | data[4];
  if (y == 900) {
    switch (x) {
      case 80:
        return {Cst816sRegion::Home};
      case 400:
        return {Cst816sRegion::Previous};
      case 240:
        return {Cst816sRegion::Next};
      default:
        return {Cst816sRegion::Invalid};
    }
  }
  if (x >= 480 || y >= 800) return {Cst816sRegion::Invalid};
  return {Cst816sRegion::Screen, y, static_cast<uint16_t>(479 - x)};
}

// One contact owns one region until release. Crossing into a bezel key cancels,
// so a drag cannot both operate the screen and turn a page/go Home.
struct Cst816sContact {
  Cst816sRegion region = Cst816sRegion::None;
  uint32_t started = 0;
  bool longFired = false;
  bool homeTap = false;
  bool homeLong = false;

  void update(Cst816sRegion next, uint32_t now, uint32_t homeHoldMs) {
    homeTap = homeLong = false;
    if (next == Cst816sRegion::None) {
      homeTap = region == Cst816sRegion::Home && !longFired;
      region = next;
      longFired = false;
      return;
    }
    if (region == Cst816sRegion::None) {
      region = next;
      started = now;
    } else if (region != next) {
      region = Cst816sRegion::Invalid;
    }
    if (region == Cst816sRegion::Home && !longFired && now - started >= homeHoldMs) {
      longFired = homeLong = true;
    }
  }
};
}  // namespace freeink
