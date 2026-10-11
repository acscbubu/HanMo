#pragma once

#include "AirPageImageStore.h"

namespace airpage {

class AirPageWallpaper final {
 public:
  static void recoverInterruptedTransaction();
  // cropToFill=false keeps the AirPage behaviour (letterboxed). AirPhoto asks
  // for true so a photo fills the sleep screen instead of leaving blank bands.
  static bool install(const SelectedImage& selected, bool cropToFill = false);

 private:
  static bool writePart(const SelectedImage& selected, bool cropToFill);
  static bool copyFile(const char* sourcePath, const char* targetPath);
};

}  // namespace airpage
