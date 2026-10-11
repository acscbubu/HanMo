#pragma once

#include <cstddef>

namespace web {

// The name and the version line the web pages carry.
//
// This is a fork, so the product name at the top of the page is the user's to
// choose, and the version line is a label rather than the build string: a
// custom build wants to be able to say what it is. Either one left empty means
// "show what was compiled in", which is also what an untouched device does.
class Branding {
 public:
  static constexpr size_t kCapacity = 40;
  static constexpr char kFilePath[] = "/.crosspoint/web-branding.cfg";

  void ensureLoaded();

  // Empty when the user has not chosen one; the page falls back on its own.
  const char* title();
  const char* version();

  // Either may be nullptr to leave it alone. Returns false when nothing
  // actually changed, so retyping the same text costs the card nothing.
  bool set(const char* title, const char* version);

 private:
  bool save() const;

  char title_[kCapacity]{};
  char version_[kCapacity]{};
  bool loaded_ = false;
};

}  // namespace web
