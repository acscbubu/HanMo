#include "WebBranding.h"

#include <Arduino.h>
#include <HalStorage.h>
#include <Logging.h>

#include <cstdio>
#include <cstring>

namespace web {

namespace {

constexpr char kTitleKey[] = "title";
constexpr char kVersionKey[] = "version";

// Trim both ends. A value that is only spaces is not a value, and storing one
// would leave the header blank with nothing to tell it from a failed fetch.
const char* trimmed(const char* value, size_t& length) {
  if (value == nullptr) {
    length = 0;
    return "";
  }
  while (*value == ' ' || *value == '\t') ++value;
  size_t end = strlen(value);
  while (end > 0 && (value[end - 1] == ' ' || value[end - 1] == '\t')) --end;
  length = end;
  return value;
}

void assign(char* field, const size_t capacity, const char* value, size_t length) {
  if (length >= capacity) length = capacity - 1;
  memcpy(field, value, length);
  field[length] = '\0';
}

bool differs(const char* field, const char* value, const size_t length) {
  return strlen(field) != length || strncmp(field, value, length) != 0;
}

}  // namespace

void Branding::ensureLoaded() {
  if (loaded_) return;
  loaded_ = true;
  title_[0] = '\0';
  version_[0] = '\0';

  char buffer[2 * (kCapacity + 16) + 1];
  if (Storage.readFileToBuffer(kFilePath, buffer, sizeof(buffer)) == 0) return;

  // One "key=value" per line. The value runs to the end of the line, so a name
  // with spaces in it survives a round trip.
  char* cursor = buffer;
  while (cursor != nullptr && *cursor != '\0') {
    char* newline = strchr(cursor, '\n');
    if (newline != nullptr) *newline = '\0';
    char* equals = strchr(cursor, '=');
    if (equals != nullptr) {
      *equals = '\0';
      size_t length = 0;
      const char* value = trimmed(equals + 1, length);
      if (strcmp(cursor, kTitleKey) == 0) {
        assign(title_, kCapacity, value, length);
      } else if (strcmp(cursor, kVersionKey) == 0) {
        assign(version_, kCapacity, value, length);
      }
    }
    cursor = newline == nullptr ? nullptr : newline + 1;
  }
}

const char* Branding::title() {
  ensureLoaded();
  return title_;
}

const char* Branding::version() {
  ensureLoaded();
  return version_;
}

bool Branding::set(const char* title, const char* version) {
  ensureLoaded();

  bool changed = false;
  if (title != nullptr) {
    size_t length = 0;
    const char* value = trimmed(title, length);
    if (length >= kCapacity) length = kCapacity - 1;
    if (differs(title_, value, length)) {
      assign(title_, kCapacity, value, length);
      changed = true;
    }
  }
  if (version != nullptr) {
    size_t length = 0;
    const char* value = trimmed(version, length);
    if (length >= kCapacity) length = kCapacity - 1;
    if (differs(version_, value, length)) {
      assign(version_, kCapacity, value, length);
      changed = true;
    }
  }

  return changed && save();
}

bool Branding::save() const {
  char out[2 * (kCapacity + 16)];
  snprintf(out, sizeof(out), "%s=%s\n%s=%s\n", kTitleKey, title_, kVersionKey, version_);
  if (!Storage.writeFile(kFilePath, String(out))) {
    LOG_ERR("WEB", "Cannot write %s", kFilePath);
    return false;
  }
  return true;
}

}  // namespace web
