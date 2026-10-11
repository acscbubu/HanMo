#pragma once
#include <string>

// The caller fully writes, flushes and closes staging first. A per-note backup
// survives reset between FAT renames. No heap buffers beyond bounded paths.
namespace AirNoteStore {
template <typename FS>
bool recover(FS& fs, const std::string& path, const std::string& backup) {
  if (!fs.exists(backup.c_str())) return true;
  if (!fs.exists(path.c_str())) return fs.rename(backup.c_str(), path.c_str());
  return fs.remove(backup.c_str());
}

template <typename FS, typename ClearCache>
bool replace(FS& fs, const std::string& path, const std::string& staging,
             const std::string& backup, ClearCache clearCache) {
  if (!recover(fs, path, backup) || !fs.exists(path.c_str()) || !clearCache(path)) return false;
  if (!fs.rename(path.c_str(), backup.c_str())) return false;
  if (!fs.rename(staging.c_str(), path.c_str())) {
    fs.rename(backup.c_str(), path.c_str()); // If this also fails, recovery keeps the original.
    return false;
  }
  fs.remove(backup.c_str()); // A cleanup failure is recoverable; the new note is committed.
  return true;
}
}  // namespace AirNoteStore
