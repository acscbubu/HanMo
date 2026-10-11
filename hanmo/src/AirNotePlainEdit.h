#pragma once
#include <HalStorage.h>
#include <string>
#include <string_view>
#include <utility>
#include "AirNotePolicy.h"
#include "AirNoteStore.h"
#include "AirNoteTodo.h"

// The existing AirNote TXT format is "title\n\nbody\n". Keep ordinary
// notes distinct from checklists, and never replace an externally edited SD
// file with a stale keyboard draft. Storage failures leave the old file or
// its recoverable .bak in place.
namespace AirNotePlainEdit {
enum class SaveResult { Saved, Unchanged, Conflict, Invalid, StorageError };

inline bool notePath(const std::string_view path) {
  constexpr std::string_view prefix = "/AirNote/";
  return path.substr(0, prefix.size()) == prefix &&
         AirNotePolicy::validFileName(path.substr(prefix.size()));
}
inline std::string sibling(const std::string& path, const char* suffix) {
  return std::string(AirNotePolicy::kDirectory) + "/." + path.substr(path.find_last_of('/') + 1) + suffix;
}

template <typename FS>
bool readPlain(FS& fs, const std::string& path, std::string& original, std::string& title, std::string& body) {
  original.clear(); title.clear(); body.clear();
  if (!notePath(path) || !AirNoteStore::recover(fs, path, sibling(path, ".bak"))) return false;
  std::string loaded;
  {
    HalFile file;
    if (!fs.openFileForRead("AirNote", path.c_str(), file)) return false;
    const auto size = file.size();
    if (size == 0 || size > AirNotePolicy::kMaxTitleBytes + AirNotePolicy::kMaxBodyBytes + 3) {
      file.close();
      return false;
    }
    loaded.resize(size);
    const bool complete = file.read(loaded.data(), size) == static_cast<int>(size);
    const bool closed = file.close();
    if (!complete || !closed) return false;
  }
  std::string_view foundTitle, foundBody;
  if (!AirNotePolicy::splitNote(loaded, foundTitle, foundBody) || AirNoteTodo::isTodo(foundBody)) return false;
  title.assign(foundTitle.data(), foundTitle.size());
  body.assign(foundBody.data(), foundBody.size());
  original = std::move(loaded);
  return true;
}

template <typename FS, typename ClearCache>
SaveResult savePlain(FS& fs, const std::string& path, const std::string_view original,
                     const std::string_view updatedBody, ClearCache clearCache) {
  std::string_view title, previous;
  if (!notePath(path) || !AirNotePolicy::splitNote(original, title, previous) ||
      AirNoteTodo::isTodo(previous) || !AirNotePolicy::validText(updatedBody) ||
      AirNoteTodo::isTodo(updatedBody)) return SaveResult::Invalid;
  std::string current, currentTitle, currentBody;
  if (!readPlain(fs, path, current, currentTitle, currentBody) || current != original)
    return SaveResult::Conflict;
  if (previous == updatedBody) return SaveResult::Unchanged;
  const std::string next = AirNotePolicy::noteContent(title, updatedBody);
  std::string_view checkTitle, checkBody;
  if (!AirNotePolicy::splitNote(next, checkTitle, checkBody) || AirNoteTodo::isTodo(checkBody))
    return SaveResult::Invalid;
  const std::string staging = sibling(path, ".part");
  const std::string backup = sibling(path, ".bak");
  if (fs.exists(staging.c_str()) && !fs.remove(staging.c_str())) return SaveResult::StorageError;
  HalFile file;
  if (!fs.openFileForWrite("AirNote", staging.c_str(), file)) return SaveResult::StorageError;
  const bool written = file.write(next.data(), next.size()) == next.size();
  if (written) file.flush();
  const bool closed = file.close();
  if (!written || !closed) {
    fs.remove(staging.c_str());
    return SaveResult::StorageError;
  }
  // The device web editor can modify the same note while this keyboard is up.
  // Recheck after staging, before the recoverable replace transaction.
  if (!readPlain(fs, path, current, currentTitle, currentBody) || current != original) {
    fs.remove(staging.c_str());
    return SaveResult::Conflict;
  }
  if (!AirNoteStore::replace(fs, path, staging, backup, clearCache)) {
    fs.remove(staging.c_str());
    return SaveResult::StorageError;
  }
  return SaveResult::Saved;
}
}  // namespace AirNotePlainEdit
