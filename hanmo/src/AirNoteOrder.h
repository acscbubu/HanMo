#pragma once
#include "AirNotePolicy.h"
#include "AirNoteStore.h"
#include <array>
#include <cstring>
#include <cstdint>
#include <string>
#include <vector>

// A streamed filename catalog: no note contents, renames, or directory-sized
// allocation. Unlisted/new notes follow saved notes in SD directory order.
namespace AirNoteOrder {
inline constexpr char path[] = "/AirNote/.order";
inline constexpr char staging[] = "/AirNote/.order.part";
inline constexpr char backup[] = "/AirNote/.order.bak";
using Name = std::array<char, 128>;

// Return 1 for a line, 0 at EOF, -1 on truncation, bad filename or I/O failure.
template<class File>
int line(File& file, size_t& remaining, Name& name) {
  name.fill(0); size_t length=0;
  if (!remaining) return 0;
  while (remaining) {
    char ch=0;
    if (file.read(&ch,1)!=1) return -1;
    --remaining;
    if (ch=='\n') return AirNotePolicy::validFileName({name.data(),length}) ? 1 : -1;
    if (!ch || length+1>=name.size()) return -1;
    name[length++]=ch;
  }
  return -1; // A committed catalog always has complete newline-terminated rows.
}
template<class FS>
bool contains(FS& fs, const char* name, size_t prefix, bool& found) {
  found=false;
  if (!fs.exists(path)) return true;
  auto file=fs.open(path); if(!file || file.isDirectory())return false;
  size_t remaining=file.size(); const size_t total=remaining;
  Name value;
  while(remaining && total-remaining<prefix) {
    if(line(file,remaining,value)!=1)return false;
    if(std::strcmp(value.data(),name)==0){found=true;return true;}
  }
  return true;
}
// Callback receives each existing AirNote exactly once. pulse keeps the ESP
// watchdog fed during SD scans; tests use a no-op. Memory stays constant.
template <class FS, class Visitor, class Pulse>
bool visit(FS& fs, Visitor visitor, Pulse pulse, bool strictDuplicates = false) {
  if (!AirNoteStore::recover(fs, path, backup)) return false;
  if (fs.exists(path)) {
    auto file = fs.open(path);
    if (!file || file.isDirectory()) return false;
    size_t remaining = file.size();
    const size_t total = remaining;
    Name name;
    while (remaining) {
      const size_t prefix = total - remaining;
      if (line(file, remaining, name) != 1) return false;
      bool duplicate = false;
      if (!contains(fs, name.data(), prefix, duplicate) || (strictDuplicates && duplicate)) return false;
      if (!duplicate) {
        const std::string note = std::string(AirNotePolicy::kDirectory) + "/" + name.data();
        auto entry = fs.open(note.c_str());
        if (!entry) {
          // A removed note is stale; an existing one that failed to open must abort the writer.
          if (fs.exists(note.c_str())) return false;
        } else if (!entry.isDirectory() && !visitor(name.data())) return false;
      }
      pulse();
    }
  }
  auto directory = fs.open(AirNotePolicy::kDirectory);
  if (!directory || !directory.isDirectory()) return false;
  for (auto file = directory.openNextFile(); file; file = directory.openNextFile()) {
    Name name{};
    file.getName(name.data(), name.size());
    const bool regular=!file.isDirectory();file.close();pulse();
    if(!regular || !AirNotePolicy::validFileName(name.data()))continue;
    bool listed=false;
    if(!contains(fs,name.data(),static_cast<size_t>(-1),listed))return false;
    if(!listed && !visitor(name.data()))return false;
  }
  return true;
}
// Swap two adjacent filenames. All other entries (including new notes) are
// retained. Caller checks the directory revision before invoking this writer.
template<class FS,class Pulse>
bool swap(FS& fs,const char* first,const char* second,Pulse pulse) {
  if(!AirNotePolicy::validFileName(first)||!AirNotePolicy::validFileName(second)||!std::strcmp(first,second))return false;
  if(fs.exists(staging) && !fs.remove(staging))return false;
  decltype(fs.open(path)) file;
  if(!fs.openFileForWrite("AIRN",staging,file))return false;
  unsigned seenFirst=0,seenSecond=0;
  bool written=visit(fs,[&](const char* name){
    const char* output=name;
    if(!std::strcmp(name,first)){output=second;++seenFirst;}
    else if(!std::strcmp(name,second)){output=first;++seenSecond;}
    const size_t n=std::strlen(output);
    return file.write(output,n)==n && file.write("\n",1)==1;
  },pulse) && seenFirst==1 && seenSecond==1;
  if(written)file.flush();
  const bool closed=file.close();
  const bool saved=written && closed && (fs.exists(path)
    ? AirNoteStore::replace(fs,path,staging,backup,[](const std::string&){return true;})
    : fs.rename(staging,path));
  if(!saved)fs.remove(staging);
  return saved;
}

// Move to a final zero-based position with one streamed, recoverable write.
// Unlike a swap, every intervening note keeps its relative order.
template<class FS,class Pulse>
bool moveTo(FS& fs,const char* source,size_t target,Pulse pulse) {
  if(!AirNotePolicy::validFileName(source))return false;
  if(fs.exists(staging)&&!fs.remove(staging))return false;
  decltype(fs.open(path)) file;if(!fs.openFileForWrite("AIRN",staging,file))return false;
  size_t position=0,seen=0;bool inserted=false;
  auto emit=[&](const char* name){const size_t n=std::strlen(name);return file.write(name,n)==n&&file.write("\n",1)==1;};
  bool written=visit(fs,[&](const char* name){
    if(!std::strcmp(name,source)){++seen;return true;}
    if(position==target){if(!emit(source))return false;inserted=true;++position;}
    if(!emit(name))return false;++position;return true;
  },pulse);
  if(written&&!inserted&&position==target){written=emit(source);inserted=written;}
  written=written&&inserted&&seen==1;if(written)file.flush();const bool closed=file.close();
  const bool saved=written&&closed&&(fs.exists(path)?AirNoteStore::replace(fs,path,staging,backup,[](const std::string&){return true;}):fs.rename(staging,path));
  if(!saved)fs.remove(staging);return saved;
}
// The caller supplies catalog-ordered indices, not request order. The entire
// move is streamed into one staging catalog; no note contents are touched.
template <class FS, class Pulse>
bool moveManyBefore(FS& fs, const std::vector<std::string>& names, const uint8_t* ordered, const char* before,
                    Pulse pulse) {
  if (fs.exists(staging) && !fs.remove(staging)) return false;
  decltype(fs.open(path)) file;
  if (!fs.openFileForWrite("AIRN", staging, file)) return false;
  bool seen[32] = {};
  size_t found = 0;
  bool anchorFound = before == nullptr, inserted = false;
  auto emit = [&](const char* name) {
    const size_t n = std::strlen(name);
    return file.write(name, n) == n && file.write("\n", 1) == 1;
  };
  auto emitSelected = [&]() {
    for (size_t i = 0; i < names.size(); ++i)
      if (!emit(names[ordered[i]].c_str())) return false;
    inserted = true;
    return true;
  };
  bool written = visit(
      fs,
      [&](const char* name) {
        for (size_t i = 0; i < names.size(); ++i)
          if (!std::strcmp(name, names[i].c_str())) {
            if (seen[i]) return false;
            seen[i] = true;
            ++found;
            return true;
          }
        if (before && !std::strcmp(name, before)) {
          anchorFound = true;
          if (!emitSelected()) return false;
        }
        return emit(name);
      },
      pulse, true);
  if (written && before == nullptr) written = emitSelected();
  written = written && inserted && anchorFound && found == names.size();
  if (written) file.flush();
  const bool closed = file.close();
  const bool saved =
      written && closed &&
      (fs.exists(path) ? AirNoteStore::replace(fs, path, staging, backup, [](const std::string&) { return true; })
                       : fs.rename(staging, path));
  if (!saved) fs.remove(staging);
  return saved;
}
} // namespace AirNoteOrder
