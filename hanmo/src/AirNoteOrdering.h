#pragma once
#include "AirNoteOrder.h"
#include <HalStorage.h>
#include <MD5Builder.h>
#include <util/TaskWatchdog.h>
#include <cstdio>
#include <cstdint>
#include <vector>
namespace AirNoteOrdering {
inline void pulse() { yield(); resetTaskWatchdogIfSubscribed(); }
template <class Visitor>
bool scan(Visitor visitor, std::string& revision, bool strictDuplicates = false) {
  MD5Builder hash;
  hash.begin();
  const bool ok = AirNoteOrder::visit(
      Storage,
      [&](const char* name) {
        hash.add(reinterpret_cast<const uint8_t*>(name), std::strlen(name) + 1);
        visitor(name);
        return true;
      },
      pulse, strictDuplicates);
  if (!ok) {
    revision.clear();
    return false;
  }
  hash.calculate();
  revision = hash.toString().c_str();
  return true;
}
enum class Result { Saved, Conflict, Missing, StorageError, Invalid };
inline Result move(const char* name,int direction,const std::string& expected) {
  AirNoteOrder::Name previous{},adjacent{};
  bool found=false,wantNext=false;std::string revision;
  if(!scan([&](const char* current){
    if(wantNext){std::snprintf(adjacent.data(),adjacent.size(),"%s",current);wantNext=false;}
    if(!std::strcmp(current,name)) {
      found=true;
      if(direction<0)adjacent=previous;else wantNext=true;
    }
    std::snprintf(previous.data(),previous.size(),"%s",current);
  },revision))return Result::StorageError;
  if(expected.empty() || revision!=expected)return Result::Conflict;
  if(!found)return Result::Missing;
  if(!adjacent[0])return Result::Saved;
  return AirNoteOrder::swap(Storage,name,adjacent.data(),pulse)?Result::Saved:Result::StorageError;
}

inline Result moveTo(const char* name,size_t target,const std::string& expected) {
 size_t count=0,from=static_cast<size_t>(-1);std::string revision;
 if(!scan([&](const char* current){if(!std::strcmp(current,name))from=count;++count;},revision))return Result::StorageError;
 if(expected.empty()||revision!=expected)return Result::Conflict;
 if(from==static_cast<size_t>(-1)||target>=count)return Result::Missing;
 if(from==target)return Result::Saved;
 return AirNoteOrder::moveTo(Storage,name,target,pulse)?Result::Saved:Result::StorageError;
}

// Validate identities and the revision token before touching the SD card.
inline bool validBulkRequest(const std::vector<std::string>& names, const char* before, const std::string& expected) {
  if (names.empty() || names.size() > 32 || expected.size() != 32) return false;
  for (char c : expected)
    if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F'))) return false;
  if (before && !AirNotePolicy::validFileName(before)) return false;
  for (size_t i = 0; i < names.size(); ++i) {
    if (!AirNotePolicy::validFileName(names[i]) || (before && names[i] == before)) return false;
    for (size_t j = 0; j < i; ++j)
      if (names[i] == names[j]) return false;
  }
  return true;
}

// Move a bounded selection in current catalog order before an unselected anchor.
// A null anchor appends the group; stale revisions never write.
inline Result moveManyBefore(const std::vector<std::string>& names, const char* before, const std::string& expected) {
  if (!validBulkRequest(names, before, expected)) return Result::Invalid;
  uint8_t ordered[32] = {};
  bool seen[32] = {};
  size_t found = 0;
  bool anchorFound = before == nullptr;
  std::string revision;
  if (!scan(
          [&](const char* current) {
            if (before && !std::strcmp(current, before)) anchorFound = true;
            for (size_t i = 0; i < names.size(); ++i)
              if (!seen[i] && names[i] == current) {
                seen[i] = true;
                ordered[found++] = static_cast<uint8_t>(i);
                break;
              }
          },
          revision, true))
    return Result::StorageError;
  if (revision != expected) return Result::Conflict;
  if (found != names.size() || !anchorFound) return Result::Missing;
  return AirNoteOrder::moveManyBefore(Storage, names, ordered, before, pulse) ? Result::Saved : Result::StorageError;
}
} // namespace AirNoteOrdering
