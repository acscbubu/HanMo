#pragma once

#include <cstdio>

#include "network/HotspotName.h"

// Display-only settings. Never use these values for OTA comparisons or logs.
namespace FirmwareIdentity {
constexpr size_t MAX_BYTES = HotspotName::MAX_BYTES;
constexpr size_t BUFFER_SIZE = MAX_BYTES + 1;
// English fallback if an i18n string is unavailable; the CJK UI uses 翰墨.
inline constexpr char DEFAULT_NAME[] = "HanMo";

// Reuse the tested UTF-8/control-character validator; an empty name is allowed.
inline bool isValid(std::string_view text) { return text.empty() || HotspotName::isValid(text); }
inline bool assign(char (&destination)[BUFFER_SIZE], std::string_view text) {
  if (!isValid(text)) return false;
  if (!text.empty()) memcpy(destination, text.data(), text.size());
  destination[text.size()] = '\0';
  return true;
}
inline bool load(char (&destination)[BUFFER_SIZE], JsonVariantConst value) {
  if (value.isUnbound()) return false;
  if (value.is<const char*>()) {
    const JsonString text = value.as<JsonString>();
    if (assign(destination, std::string_view(text.c_str(), text.size()))) return false;
  }
  destination[0] = '\0';
  return true;
}
inline bool validVisibility(JsonVariantConst value) {
  return value.is<bool>() || (value.is<int>() && (value.as<int>() == 0 || value.as<int>() == 1));
}
inline bool loadVisibility(uint8_t& destination, JsonVariantConst value) {
  if (value.isUnbound()) return false;
  if (validVisibility(value)) {
    destination = value.as<bool>() ? 1 : 0;
    return false;
  }
  destination = 1;
  return true;
}
inline const char* name(const char* customName, const char* originalName) {
  return customName[0] ? customName : (originalName && originalName[0] ? originalName : DEFAULT_NAME);
}
// Caller supplies a small stack buffer; no new persistent or transient heap.
inline void format(char* output, size_t capacity, const char* customName, const char* originalName, bool showVersion,
                   const char* version) {
  snprintf(output, capacity, "%s%s%s", name(customName, originalName), showVersion ? " " : "",
           showVersion ? version : "");
}
}  // namespace FirmwareIdentity
