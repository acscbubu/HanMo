#include "AirPageImageNames.h"

#include <Arduino.h>
#include <HalStorage.h>
#include <Logging.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace airpage {

namespace {
// Trim both ends. A name that is only spaces is not a name, and storing one
// would draw a blank row with no way to tell it from a rendering fault.
const char* trimmed(const char* name, size_t& length) {
  if (name == nullptr) {
    length = 0;
    return "";
  }
  while (*name == ' ' || *name == '\t') ++name;
  size_t end = strlen(name);
  while (end > 0 && (name[end - 1] == ' ' || name[end - 1] == '\t')) --end;
  length = end;
  return name;
}
}  // namespace

void ImageNames::ensureLoaded() {
  if (loaded_) return;
  loaded_ = true;
  count_ = 0;

  // The whole file at once: twenty names of thirty-two bytes is under a
  // kilobyte, and the card is a worse place to be clever than the heap.
  char buffer[kMaxNames * (kNameCapacity + 24) + 1];
  if (Storage.readFileToBuffer(kFilePath, buffer, sizeof(buffer)) == 0) return;

  // One line per name: "<archiveId> <name>". The name runs to the end of the
  // line, so a name with a space in it survives a round trip -- which
  // splitting on whitespace would not.
  char* cursor = buffer;
  while (cursor != nullptr && *cursor != '\0' && count_ < kMaxNames) {
    char* newline = strchr(cursor, '\n');
    if (newline != nullptr) *newline = '\0';
    char* space = strchr(cursor, ' ');
    if (space != nullptr) {
      *space = '\0';
      char* end = nullptr;
      const uint64_t id = strtoull(cursor, &end, 10);
      size_t length = 0;
      const char* name = trimmed(space + 1, length);
      if (end != cursor && id != 0 && length > 0 && length < kNameCapacity) {
        entries_[count_].archiveId = id;
        memcpy(entries_[count_].name, name, length);
        entries_[count_].name[length] = '\0';
        ++count_;
      }
    }
    cursor = newline == nullptr ? nullptr : newline + 1;
  }
}

const char* ImageNames::nameFor(const uint64_t archiveId) {
  ensureLoaded();
  if (archiveId == 0) return nullptr;
  for (size_t i = 0; i < count_; ++i) {
    if (entries_[i].archiveId == archiveId) return entries_[i].name;
  }
  return nullptr;
}

bool ImageNames::setName(const uint64_t archiveId, const char* name) {
  ensureLoaded();
  // The live image has no archive id yet -- it gets one when it is archived --
  // so there is nothing stable to hang a name on.
  if (archiveId == 0) return false;

  size_t length = 0;
  const char* value = trimmed(name, length);
  if (length >= kNameCapacity) length = kNameCapacity - 1;

  size_t found = count_;
  for (size_t i = 0; i < count_; ++i) {
    if (entries_[i].archiveId == archiveId) found = i;
  }

  if (length == 0) {
    if (found == count_) return false;
    entries_[found] = entries_[--count_];
    return save();
  }

  if (found != count_) {
    if (strncmp(entries_[found].name, value, length) == 0 && entries_[found].name[length] == '\0') return false;
  } else {
    if (count_ >= kMaxNames) {
      LOG_ERR("AIRPAGE", "Name table full");
      return false;
    }
    found = count_++;
    entries_[found].archiveId = archiveId;
  }
  memcpy(entries_[found].name, value, length);
  entries_[found].name[length] = '\0';
  return save();
}

void ImageNames::prune(const uint64_t* liveIds, const size_t count) {
  ensureLoaded();
  bool changed = false;
  for (size_t i = 0; i < count_;) {
    bool live = false;
    for (size_t j = 0; j < count; ++j) live = live || liveIds[j] == entries_[i].archiveId;
    if (live) {
      ++i;
      continue;
    }
    entries_[i] = entries_[--count_];
    changed = true;
  }
  if (changed) save();
}

bool ImageNames::save() const {
  String out;
  out.reserve(count_ * (kNameCapacity + 24));
  char line[kNameCapacity + 24];
  for (size_t i = 0; i < count_; ++i) {
    snprintf(line, sizeof(line), "%llu %s\n", static_cast<unsigned long long>(entries_[i].archiveId),
             entries_[i].name);
    out += line;
  }
  if (!Storage.writeFile(kFilePath, out)) {
    LOG_ERR("AIRPAGE", "Cannot write %s", kFilePath);
    return false;
  }
  return true;
}

}  // namespace airpage
