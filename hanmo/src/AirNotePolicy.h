#pragma once

#include <cstddef>
#include <string>
#include <string_view>

// The AirNote web endpoint writes short UTF-8 notes as ordinary books on SD.
// Keep this policy independent of Arduino so the same validation is host-tested.
namespace AirNotePolicy {
inline constexpr char kDirectory[] = "/AirNote";
inline constexpr std::size_t kMaxTitleBytes = 80;
inline constexpr std::size_t kMaxBodyBytes = 16 * 1024;

inline bool validUtf8(const std::string_view value) {
  for (std::size_t i = 0; i < value.size();) {
    const unsigned char first = static_cast<unsigned char>(value[i]);
    if (first < 0x80) {
      ++i;
      continue;
    }
    const std::size_t count = first >= 0xC2 && first <= 0xDF ? 2 : first >= 0xE0 && first <= 0xEF ? 3
                                                             : first >= 0xF0 && first <= 0xF4 ? 4 : 0;
    if (count == 0 || count > value.size() - i) return false;
    const unsigned char second = static_cast<unsigned char>(value[i + 1]);
    if (second < 0x80 || second > 0xBF || (first == 0xE0 && second < 0xA0) ||
        (first == 0xED && second >= 0xA0) || (first == 0xF0 && second < 0x90) ||
        (first == 0xF4 && second > 0x8F))
      return false;
    for (std::size_t j = 2; j < count; ++j) {
      const unsigned char byte = static_cast<unsigned char>(value[i + j]);
      if (byte < 0x80 || byte > 0xBF) return false;
    }
    i += count;
  }
  return true;
}

inline bool validTitle(const std::string_view title) {
  if (title.empty() || title.size() > kMaxTitleBytes || !validUtf8(title)) return false;
  if (title.front() == '.' || title.front() == ' ' || title.back() == '.' || title.back() == ' ') return false;
  bool visible = false;
  for (const unsigned char c : title) {
    if (c < 0x20 || c == 0x7F || c == '/' || c == '\\' || c == ':' || c == '*' || c == '?' || c == '"' ||
        c == '<' || c == '>' || c == '|')
      return false;
    if (c != ' ') visible = true;
  }
  return visible;
}

inline bool validText(const std::string_view body) {
  if (body.empty() || body.size() > kMaxBodyBytes || !validUtf8(body)) return false;
  bool visible = false;
  for (const unsigned char c : body) {
    if ((c < 0x20 && c != '\n' && c != '\r' && c != '\t') || c == 0x7F) return false;
    if (c != ' ' && c != '\n' && c != '\r' && c != '\t') visible = true;
  }
  return visible;
}

// A stored name may include the generated -99 suffix. Never accept paths or
// hidden transaction files; this validation is also used during recovery.
inline bool validFileName(const std::string_view name) {
  if (name.size() < 5 || name.size() > kMaxTitleBytes + 7 || name.substr(name.size() - 4) != ".txt") return false;
  const auto stem = name.substr(0, name.size() - 4);
  if (stem.size() <= kMaxTitleBytes) return validTitle(stem);
  const auto dash = stem.rfind('-');
  if (dash == std::string_view::npos || !validTitle(stem.substr(0, dash))) return false;
  const auto suffix = stem.substr(dash + 1);
  return suffix.size() <= 2 && !suffix.empty() && suffix.front() >= '1' && suffix.front() <= '9' &&
         (suffix.size() == 1 || (suffix[1] >= '0' && suffix[1] <= '9'));
}

inline bool splitNote(const std::string_view content, std::string_view& title, std::string_view& body) {
  const auto separator = content.find("\n\n");
  if (separator == std::string_view::npos || content.empty() || content.back() != '\n') return false;
  title = content.substr(0, separator);
  body = content.substr(separator + 2, content.size() - separator - 3);
  return validTitle(title) && validText(body);
}

inline std::string fileName(const std::string_view title, const unsigned suffix) {
  std::string name(title);
  if (suffix > 1) name += "-" + std::to_string(suffix);
  return name + ".txt";
}

inline std::string noteContent(const std::string_view title, const std::string_view body) {
  std::string content;
  content.reserve(title.size() + body.size() + 4);
  content.append(title.data(), title.size());
  content += "\n\n";
  content.append(body.data(), body.size());
  content += '\n';
  return content;
}
}  // namespace AirNotePolicy
