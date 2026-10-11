#include "AirPhotoActions.h"

#include <Bitmap.h>
#include <HalStorage.h>
#include <JpegToBmpConverter.h>
#include <PngToBmpConverter.h>

#include <algorithm>
#include <cstdint>
#include <cstring>

#include "CrossPointSettings.h"
#include "ScreenSettingsPolicy.h"
#include "activities/apps/airpage/AirPageImageStore.h"
#include "activities/apps/airpage/AirPageWallpaper.h"

namespace airphoto {
namespace {
constexpr char kBoot[] = "/AirPhoto/.boot-cover.bmp";
constexpr char kShutdown[] = "/AirPhoto/.shutdown-cover.bmp";
constexpr char kSleepPart[] = "/AirPhoto/.sleep-cover.bmp.part";

bool endsWith(const char* path, const char* suffix) {
  const size_t len = strlen(path), end = strlen(suffix);
  if (len < end) return false;
  for (size_t i = 0; i < end; ++i) {
    const unsigned char c = static_cast<unsigned char>(path[len - end + i]);
    if ((c >= 'A' && c <= 'Z' ? c + ('a' - 'A') : c) != static_cast<unsigned char>(suffix[i])) return false;
  }
  return true;
}

bool validBmp(const char* path) {
  HalFile file;
  if (!Storage.openFileForRead("APHO", path, file)) return false;
  Bitmap bitmap(file, true);
  return bitmap.parseHeaders() == BmpReaderError::Ok && bitmap.getWidth() > 0 && bitmap.getHeight() > 0 &&
         ScreenSettingsPolicy::bitmapFits(file.position(), bitmap.getRowBytes(), bitmap.getHeight(), file.fileSize64());
}

bool writeBmp(const char* source, const char* part) {
  // Close both HAL handles before the caller validates/renames the result.
  HalFile in, out;
  if (!Storage.openFileForRead("APHO", source, in) || !Storage.openFileForWrite("APHO", part, out)) return false;
  const bool png = endsWith(source, ".png");
  const bool jpeg = endsWith(source, ".jpg") || endsWith(source, ".jpeg");
  if (png || jpeg) {
    const bool converted = png ? PngToBmpConverter::pngFileToBmpStream(in, out, true)
                               : JpegToBmpConverter::jpegFileToBmpStream(in, out, true);
    out.flush();
    return out.close() && converted;
  }
  const uint64_t expected = in.fileSize64();
  uint64_t copied = 0;
  uint8_t buffer[128];
  while (copied < expected) {
    const size_t want = std::min<uint64_t>(sizeof(buffer), expected - copied);
    const int read = in.read(buffer, want);
    if (read <= 0 || out.write(buffer, static_cast<size_t>(read)) != static_cast<size_t>(read)) return false;
    copied += static_cast<uint64_t>(read);
  }
  out.flush();
  return out.close() && copied == expected;
}

bool clearPart(const char* path) { return !Storage.exists(path) || Storage.remove(path); }

// A stale backup is authoritative if settings never switched to this path.
bool recover(const char* target, const char* backup, uint8_t mode, uint8_t custom, const char* imagePath) {
  if (!Storage.exists(backup)) return true;
  if (mode == custom && strcmp(imagePath, target) == 0 && Storage.exists(target)) return Storage.remove(backup);
  if (Storage.exists(target) && !Storage.remove(target)) return false;
  return Storage.rename(backup, target);
}

bool installScreen(const char* original, Cover cover) {
  const bool startup = cover == Cover::Startup;
  const char* target = startup ? kBoot : kShutdown;
  const char* backup = startup ? "/AirPhoto/.boot-cover.bmp.bak" : "/AirPhoto/.shutdown-cover.bmp.bak";
  const char* part = startup ? "/AirPhoto/.boot-cover.bmp.part" : "/AirPhoto/.shutdown-cover.bmp.part";
  uint8_t& mode = startup ? SETTINGS.bootScreen : SETTINGS.shutdownScreen;
  char* imagePath = startup ? SETTINGS.bootScreenImage : SETTINGS.shutdownScreenImage;
  const uint8_t custom = startup ? static_cast<uint8_t>(ScreenSettingsPolicy::BootCustom)
                                 : static_cast<uint8_t>(ScreenSettingsPolicy::ShutdownCustom);
  if (!recover(target, backup, mode, custom, imagePath) || !clearPart(part)) return false;
  if (!writeBmp(original, part) || !validBmp(part)) {
    clearPart(part);
    return false;
  }
  const bool hadPrevious = Storage.exists(target);
  if (hadPrevious && !Storage.rename(target, backup)) {
    clearPart(part);
    return false;
  }
  if (!Storage.rename(part, target)) {
    if (hadPrevious) Storage.rename(backup, target);
    clearPart(part);
    return false;
  }
  const uint8_t previousMode = mode;
  char previousPath[ScreenSettingsPolicy::PATH_BYTES];
  memcpy(previousPath, imagePath, sizeof(previousPath));
  // The managed path is bounded, independent of the original filename.
  memcpy(imagePath, target, strlen(target) + 1);
  mode = custom;
  if (!SETTINGS.saveToFile()) {
    mode = previousMode;
    memcpy(imagePath, previousPath, sizeof(previousPath));
    (void)SETTINGS.saveToFile();
    Storage.remove(target);
    if (hadPrevious) Storage.rename(backup, target);
    return false;
  }
  if (hadPrevious) Storage.remove(backup);
  return true;
}
}  // namespace

bool setCover(const char* original, Cover cover) {
  if (!original || strncmp(original, "/AirPhoto/", 10) != 0 || !original[10] || original[10] == '.' ||
      strchr(original + 10, '/') ||
      !(endsWith(original, ".bmp") || endsWith(original, ".png") || endsWith(original, ".jpg") ||
        endsWith(original, ".jpeg")))
    return false;
  if (cover != Cover::Sleep) return installScreen(original, cover);

  airpage::SelectedImage selected;
  // AirPage's fixed source-path field is 96 bytes; stage a bounded BMP for
  // PNG and long filenames, then reuse its /sleep.bmp transaction unchanged.
  const bool stage = endsWith(original, ".png") || strlen(original) >= sizeof(selected.path);
  if (stage) {
    if (!clearPart(kSleepPart) || !writeBmp(original, kSleepPart)) {
      clearPart(kSleepPart);
      return false;
    }
    memcpy(selected.path, kSleepPart, sizeof(kSleepPart));
  } else {
    memcpy(selected.path, original, strlen(original) + 1);
  }
  const bool ok = airpage::AirPageImageStore::inspectImage(selected.path, selected.image) &&
                  airpage::AirPageWallpaper::install(selected, /*cropToFill=*/true);
  if (stage) clearPart(kSleepPart);
  return ok;
}

bool deletePhoto(const char* original, const char* view, const char* thumb, bool sharedDerived) {
  if (!original || !Storage.remove(original)) return false;
  if (!sharedDerived) {
    Storage.remove(view);
    Storage.remove(thumb);
  }
  return true;
}
}  // namespace airphoto
