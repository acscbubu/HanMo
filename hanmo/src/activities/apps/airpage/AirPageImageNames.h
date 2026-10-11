#pragma once

#include <cstddef>
#include <cstdint>

namespace airpage {

// The names the user has given archived images.
//
// A sidecar rather than a rename on the card. The file NAME carries the
// archiveId and the format, and AirPageImageStore parses both back out of it
// on every scan -- so renaming the file renames the identity, and an image
// called "Tokyo" would no longer be findable, sortable by date, or prunable.
// The id stays the id; this maps it to what to print.
//
// Cleared entries are dropped rather than stored empty, so "no name" has one
// representation and a row falls back to its date the moment the name goes.
class ImageNames {
 public:
  static constexpr size_t kMaxNames = 20;
  static constexpr size_t kNameCapacity = 32;
  static constexpr char kFilePath[] = "/.crosspoint/airpage/names.cfg";

  // Reads the card once; later calls are free.
  void ensureLoaded();

  // The name for `archiveId`, or nullptr when it has none.
  const char* nameFor(uint64_t archiveId);

  // Set or, with an empty/blank name, clear. Writes the card only when
  // something actually changed: a card has a finite erase count and a tap that
  // changes nothing should cost nothing.
  bool setName(uint64_t archiveId, const char* name);

  // Forget names whose image is gone. Called after a history scan, because
  // otherwise a card that cycles through twenty images keeps every name it
  // ever had and the file grows without a bound.
  void prune(const uint64_t* liveIds, size_t count);

 private:
  struct Entry {
    uint64_t archiveId;
    char name[kNameCapacity];
  };

  bool save() const;

  Entry entries_[kMaxNames]{};
  size_t count_ = 0;
  bool loaded_ = false;
};

}  // namespace airpage
