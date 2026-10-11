#pragma once
#include <array>
#include <string>
#include <string_view>
#include <vector>

#include "AirNotePolicy.h"
#include "AirNoteTodo.h"

// Creating and editing AirNote files on the device itself.
//
// AirNoteTodoActivity mutates its checklist in place inside one fixed-size
// buffer: toggling flips a single state byte and reordering std::rotates whole
// lines, so neither changes the file's length. Adding, relabelling and deleting
// items DO change it, so they are expressed here as whole-content transforms --
// take the complete file, return the complete replacement -- and the caller
// writes the result through the existing staging/replace path.
//
// Every transform re-parses its own output before returning it. A splice that
// would produce a file the reader cannot load fails here instead of landing on
// the SD card.
//
// Note the invariant AirNoteTodo::parse enforces: a checklist must hold at
// least one item and its body must not end in a newline. There is no valid
// empty checklist, so creation always takes a first item and deleting the last
// remaining one is refused.
namespace AirNoteTodoEdit {

inline bool isChecklist(const std::string_view content) {
  std::string_view title, body;
  return AirNotePolicy::splitNote(content, title, body) && AirNoteTodo::isTodo(body);
}

// Round-trips through the real reader, so a transform cannot emit a file that
// AirNoteTodoActivity::load() would later reject.
inline bool readable(const std::string_view content, size_t& count) {
  std::string_view title, body;
  AirNoteTodo::Items items;
  count = 0;
  return AirNotePolicy::splitNote(content, title, body) && AirNoteTodo::parse(body, items, count);
}

inline bool readable(const std::string_view content) {
  size_t ignored = 0;
  return readable(content, ignored);
}

// Byte offset of the checklist body, and the parsed items within it.
inline bool locate(const std::string_view content, size_t& bodyOffset, AirNoteTodo::Items& items, size_t& count) {
  std::string_view title, body;
  if (!AirNotePolicy::splitNote(content, title, body) || !AirNoteTodo::parse(body, items, count)) return false;
  bodyOffset = title.size() + 2;
  return true;
}

inline bool createChecklist(const std::string_view title, const std::string_view firstItem, std::string& out) {
  out.clear();
  if (!AirNotePolicy::validTitle(title) || !AirNoteTodo::validLabel(firstItem)) return false;
  std::string body(AirNoteTodo::marker);
  body += "[ ] ";
  body.append(firstItem.data(), firstItem.size());
  if (body.size() > AirNotePolicy::kMaxBodyBytes) return false;
  out = AirNotePolicy::noteContent(title, body);
  return readable(out);
}

inline bool createNote(const std::string_view title, const std::string_view firstLine, std::string& out) {
  out.clear();
  if (!AirNotePolicy::validTitle(title) || !AirNotePolicy::validText(firstLine)) return false;
  // A plain note that opened with the checklist marker would be read back as a
  // checklist by AirNoteTodoActivity::recognizes().
  if (AirNoteTodo::isTodo(firstLine)) return false;
  out = AirNotePolicy::noteContent(title, firstLine);
  std::string_view checkTitle, checkBody;
  return AirNotePolicy::splitNote(out, checkTitle, checkBody) && !AirNoteTodo::isTodo(checkBody);
}

inline bool appendItem(const std::string_view content, const std::string_view label, std::string& out) {
  out.clear();
  size_t bodyOffset = 0, count = 0;
  AirNoteTodo::Items items;
  if (!locate(content, bodyOffset, items, count) || !AirNoteTodo::validLabel(label)) return false;
  if (count >= AirNoteTodo::maxItems) return false;
  // The file's last byte terminates the last item; the new line takes its place
  // and re-supplies the terminator.
  out.assign(content.substr(0, content.size() - 1));
  out += "\n[ ] ";
  out.append(label.data(), label.size());
  out += '\n';
  return readable(out);
}

inline bool relabelItem(const std::string_view content, const size_t index, const std::string_view label,
                        std::string& out) {
  out.clear();
  size_t bodyOffset = 0, count = 0;
  AirNoteTodo::Items items;
  if (!locate(content, bodyOffset, items, count) || index >= count || !AirNoteTodo::validLabel(label)) return false;
  const size_t start = bodyOffset + items[index].offset + 4;  // past "[ ] "
  out.assign(content.substr(0, start));
  out.append(label.data(), label.size());
  out.append(content.substr(start + items[index].length));
  return readable(out);
}

// Bulk deletion is ONE transform, not a loop over removeItem: every splice
// shifts the offsets the remaining indices were measured against, and a
// half-applied loop would leave a note nobody asked for on the SD card. So the
// entire request is validated before a byte moves, and the survivors are copied
// forward from the original offsets.
inline bool removeItems(const std::string_view content, const std::vector<size_t>& indices, std::string& out) {
  out.clear();
  size_t bodyOffset = 0, count = 0;
  AirNoteTodo::Items items;
  if (!locate(content, bodyOffset, items, count) || indices.empty()) return false;
  // A repeated index would silently splice a second, innocent line, so a
  // duplicate is a refusal rather than something quietly ignored.
  std::array<bool, AirNoteTodo::maxItems> dropping{};
  for (const size_t index : indices) {
    if (index >= count || dropping[index]) return false;
    dropping[index] = true;
  }
  // parse() rejects an item-less checklist, exactly as removeItem's count == 1
  // guard does: there is no valid empty checklist to write.
  if (indices.size() >= count) return false;
  out.assign(content.substr(0, bodyOffset + AirNoteTodo::marker.size()));  // title, blank line, marker
  for (size_t i = 0; i < count; ++i) {
    if (dropping[i]) continue;
    // Whole line plus its newline, byte for byte: order and checked state of
    // every survivor is carried over untouched.
    out.append(content.substr(bodyOffset + items[i].offset, 4 + items[i].length + 1));
  }
  return readable(out);
}

inline bool removeItem(const std::string_view content, const size_t index, std::string& out) {
  out.clear();
  size_t bodyOffset = 0, count = 0;
  AirNoteTodo::Items items;
  if (!locate(content, bodyOffset, items, count) || index >= count) return false;
  // Dropping the last one would leave a body parse() rejects; the caller should
  // delete the whole note instead.
  if (count == 1) return false;
  const size_t start = bodyOffset + items[index].offset;
  const size_t stop = start + 4 + items[index].length + 1;  // line plus its newline
  out.assign(content.substr(0, start));
  out.append(content.substr(stop));
  return readable(out);
}

// Notes are stored under their title, so a repeated title needs the same -N
// suffix the web endpoint applies. `taken` reports whether a candidate name
// already exists.
template <typename TakenFn>
inline bool uniqueFileName(const std::string_view title, TakenFn taken, std::string& out) {
  out.clear();
  if (!AirNotePolicy::validTitle(title)) return false;
  for (unsigned suffix = 1; suffix <= 99; ++suffix) {
    std::string candidate = AirNotePolicy::fileName(title, suffix);
    if (!AirNotePolicy::validFileName(candidate)) return false;
    if (!taken(candidate)) {
      out = std::move(candidate);
      return true;
    }
  }
  return false;
}

}  // namespace AirNoteTodoEdit
