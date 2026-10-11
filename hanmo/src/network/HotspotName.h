#pragma once

#include <ArduinoJson.h>

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <string>
#include <string_view>

namespace HotspotName {
constexpr size_t MAX_BYTES = 32;
constexpr size_t BUFFER_SIZE = MAX_BYTES + 1;
constexpr char DEFAULT_NAME[] = "XTEINK-X4-PRO";

// Wi-Fi SSIDs are byte-limited. Reject malformed UTF-8 and control characters
// instead of truncating a code point or silently changing the requested name.
inline bool isValid(const std::string_view text) {
  if (text.empty() || text.size() > MAX_BYTES) return false;
  bool visible = false;
  for (size_t i = 0; i < text.size();) {
    const auto first = static_cast<uint8_t>(text[i++]);
    if (first < 0x20 || first == 0x7f) return false;
    if (first < 0x80) {
      visible |= first != ' ';
      continue;
    }
    size_t remaining;
    uint32_t codepoint;
    uint32_t minimum;
    if (first >= 0xc2 && first <= 0xdf) {
      remaining = 1;
      codepoint = first & 0x1f;
      minimum = 0x80;
    } else if (first >= 0xe0 && first <= 0xef) {
      remaining = 2;
      codepoint = first & 0x0f;
      minimum = 0x800;
    } else if (first >= 0xf0 && first <= 0xf4) {
      remaining = 3;
      codepoint = first & 0x07;
      minimum = 0x10000;
    } else {
      return false;
    }
    if (i + remaining > text.size()) return false;
    while (remaining--) {
      const auto next = static_cast<uint8_t>(text[i++]);
      if ((next & 0xc0) != 0x80) return false;
      codepoint = (codepoint << 6) | (next & 0x3f);
    }
    if (codepoint < minimum || codepoint > 0x10ffff || (codepoint >= 0xd800 && codepoint <= 0xdfff)) return false;
    if (codepoint >= 0x80 && codepoint <= 0x9f) return false;
    visible = true;
  }
  return visible;
}

inline bool assign(char (&destination)[BUFFER_SIZE], std::string_view text) {
  if (text.empty()) text = DEFAULT_NAME;
  if (!isValid(text)) return false;
  memcpy(destination, text.data(), text.size());
  destination[text.size()] = '\0';
  return true;
}

// Returns whether a malformed/empty saved value should be rewritten. An older
// settings file without this field keeps the struct-initializer default.
inline bool load(char (&destination)[BUFFER_SIZE], const JsonVariantConst value) {
  if (value.isUnbound()) return false;
  if (value.is<const char*>()) {
    const JsonString text = value.as<JsonString>();
    if (assign(destination, std::string_view(text.c_str(), text.size()))) return text.size() == 0;
  }
  assign(destination, {});
  return true;
}
// This replaces the existing transient QR string. Reserve once for the
// worst case (every SSID byte escaped), at most 82 bytes for a valid name.
inline std::string wifiQrPayload(const std::string_view name) {
  std::string payload;
  payload.reserve(18 + name.size() * 2);
  payload = "WIFI:T:nopass;S:";
  for (const char c : name) {
    if (c == '\\' || c == ';' || c == ',' || c == ':' || c == '"') payload += '\\';
    payload += c;
  }
  payload += ";;";
  return payload;
}

}  // namespace HotspotName
