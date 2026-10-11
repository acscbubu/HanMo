#pragma once
#include <cstdint>
#include <string>
namespace info_board {
constexpr uint32_t rotationMs(uint8_t option) {
  return option == 0 ? 15000u : option == 2 ? 60000u : option == 3 ? 120000u : 30000u;
}
constexpr uint32_t refreshMs(uint8_t scene) { return scene == 1 ? 900000u : scene == 2 ? 30000u : 120000u; }
constexpr bool due(uint32_t now, uint32_t last, uint32_t interval) { return uint32_t(now - last) >= interval; }
// A PC helper is intentionally LAN-only; never send OPDS credentials to it.
inline bool localPcUrl(const std::string& url) {
  if (url.compare(0, 7, "http://") != 0 || url.size() > 127) return false;
  const auto slash = url.find('/', 7);
  if (slash == std::string::npos || url.substr(slash) != "/metrics.json") return false;
  auto host = url.substr(7, slash - 7);
  const auto colon = host.find(':');
  if (colon != std::string::npos) {
    auto port = host.substr(colon + 1);
    if (port.empty() || port.size() > 5) return false;
    unsigned p = 0;
    for (char c : port) {
      if (c < '0' || c > '9') return false;
      p = p * 10 + c - '0';
    }
    if (!p || p > 65535) return false;
    host.resize(colon);
  }
  unsigned octets[4]{};
  unsigned part = 0, digits = 0;
  for (char c : host) {
    if (c == '.') {
      if (!digits || part == 3) return false;
      ++part;
      digits = 0;
      continue;
    }
    if (c < '0' || c > '9' || ++digits > 3) return false;
    octets[part] = octets[part] * 10 + c - '0';
    if (octets[part] > 255) return false;
  }
  return part == 3 && digits && octets[3] != 0 && octets[3] != 255 &&
         (octets[0] == 10 || (octets[0] == 192 && octets[1] == 168) ||
          (octets[0] == 172 && octets[1] >= 16 && octets[1] <= 31));
}
}  // namespace info_board
