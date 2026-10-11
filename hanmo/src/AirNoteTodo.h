#pragma once
#include "AirNotePolicy.h"
#include <array>

// Versioned TXT body. Existing plain TXT notes retain their original format.
// No dynamic parse storage: offsets point into the caller's bounded buffer.
namespace AirNoteTodo {
inline constexpr std::string_view marker = "#!AirNote-Todo:1\n";
inline constexpr size_t maxItems = 64;
inline constexpr size_t maxItemBytes = 240;
struct Item { size_t offset = 0; size_t length = 0; bool done = false; };
using Items = std::array<Item, maxItems>;
inline bool isTodo(std::string_view body) { return body.substr(0, marker.size()) == marker; }
inline bool validLabel(std::string_view label) {
  if (label.empty() || label.size() > maxItemBytes || !AirNotePolicy::validText(label)) return false;
  for (unsigned char c : label) if (c < 0x20 || c == 0x7f) return false;
  return true;
}
inline bool parse(std::string_view body, Items& items, size_t& count) {
  count = 0;
  if (!isTodo(body) || body.size() > AirNotePolicy::kMaxBodyBytes) return false;
  size_t pos = marker.size();
  while (pos < body.size()) {
    auto end = body.find('\n', pos);
    if (end == std::string_view::npos) end = body.size();
    auto line = body.substr(pos, end - pos);
    if (count == maxItems || line.size() < 5 || line[0] != '[' || line[2] != ']' || line[3] != ' ' ||
        (line[1] != ' ' && line[1] != 'x') || !validLabel(line.substr(4))) return false;
    items[count++] = {pos, line.size() - 4, line[1] == 'x'};
    pos = end + 1;
  }
  return count > 0 && body.back() != '\n';
}
// Browser/API accept one item per line; optional [x] / [ ] preserve state.
inline bool encode(std::string_view text, std::string& body) {
  body.clear();
  if (text.size() > AirNotePolicy::kMaxBodyBytes) return false;
  body.reserve(AirNotePolicy::kMaxBodyBytes);
  body.assign(marker);
  size_t pos = 0, count = 0;
  while (pos < text.size()) {
    auto end = text.find('\n', pos);
    if (end == std::string_view::npos) end = text.size();
    auto line = text.substr(pos, end - pos);
    if (!line.empty() && line.back() == '\r') line.remove_suffix(1);
    pos = end + 1;
    if (line.empty()) continue;
    bool done = false;
    if (line.size() >= 4 && (line.substr(0, 4) == "[x] " || line.substr(0, 4) == "[ ] ")) {
      done = line[1] == 'x'; line.remove_prefix(4);
    }
    if (++count > maxItems || !validLabel(line)) return false;
    if (count > 1) body += '\n';
    body += done ? "[x] " : "[ ] ";
    body.append(line.data(), line.size());
    if (body.size() > AirNotePolicy::kMaxBodyBytes) return false;
  }
  return count > 0;
}
}  // namespace AirNoteTodo
