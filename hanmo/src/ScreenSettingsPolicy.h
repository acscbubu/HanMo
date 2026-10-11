#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace ScreenSettingsPolicy {
constexpr size_t PATH_BYTES = 256;
enum Boot : uint8_t { BootDefault, BootCustom, BootHidden, BootCount };
enum Shutdown : uint8_t { FollowSleep, ShutdownDefault, ShutdownCustom, ShutdownBlank, ShutdownCount };
inline bool usesSleepScreen(bool fromTimeout, uint8_t shutdown) { return fromTimeout || shutdown == FollowSleep; }
inline bool quickResume(bool fromTimeout, uint8_t shutdown, bool sleepKeepsFrame, bool timeoutKeepsFrame) {
  return usesSleepScreen(fromTimeout, shutdown) && (sleepKeepsFrame || (fromTimeout && timeoutKeepsFrame));
}
inline bool bitmapFits(uint64_t offset, uint64_t rowBytes, uint64_t height, uint64_t fileBytes) {
  return offset >= 54 && rowBytes > 0 && rowBytes <= 8192 && height > 0 && height <= 3072 && offset <= fileBytes &&
         rowBytes * height <= fileBytes - offset;
}
inline bool validPath(const char* path) {
  if (!path || path[0] != '/') return false;
  const size_t len = strlen(path);
  if (len < 5 || len >= PATH_BYTES || strchr(path, '\\')) return false;
  for (const char* s = path; *s; ++s) {
    if (static_cast<unsigned char>(*s) < 32) return false;
    if (*s == '/' &&
        (s[1] == '/' || (s[1] == '.' && (s[2] == '/' || !s[2] || (s[2] == '.' && (s[3] == '/' || !s[3]))))))
      return false;
  }
  const char* ext = path + len - 4;
  return ext[0] == '.' && (ext[1] == 'b' || ext[1] == 'B') && (ext[2] == 'm' || ext[2] == 'M') &&
         (ext[3] == 'p' || ext[3] == 'P');
}
inline bool assignPath(char (&dest)[PATH_BYTES], const char* path) {
  if (!path || (*path && !validPath(path))) return false;
  memcpy(dest, path, strlen(path) + 1);
  return true;
}
}  // namespace ScreenSettingsPolicy
