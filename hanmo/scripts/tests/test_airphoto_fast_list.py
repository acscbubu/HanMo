"""Compile the real AirPhoto Activity against host SD/display/input shims."""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'src/activities/apps/airphoto/AirPhotoActivity.cpp'
SHIMS = (
    'MappedInputManager.h', 'activities/Activity.h', 'components/OptionPopup.h',
    'Bitmap.h', 'FsHelpers.h', 'GfxRenderer.h', 'HalStorage.h', 'I18n.h',
    'JpegToBmpConverter.h', 'PngToBmpConverter.h',
    'activities/apps/airpage/AirPageImageStore.h',
    'activities/apps/airpage/AirPageWallpaper.h',
    'components/UITheme.h', 'components/themes/BaseTheme.h', 'fontIds.h', 'Icon.h',
)

PLATFORM = r'''
#pragma once
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <functional>
#include <string>
#include <utility>
#include <vector>
struct Rect { int x, y, width, height; };
// freeink-sdk Icon.h verbatim: the generated listIcons.h glyphs declare
// against this layout, and the header blits them a row-run at a time.
namespace freeink {
struct Icon { uint16_t w; uint16_t h; int16_t opticalCenterY; const uint8_t* bits; };
}
namespace HalDisplay { enum RefreshMode { HALF_REFRESH }; }
inline std::vector<std::string> files;
inline int bitmapReads = 0, conversions = 0, inspectCalls = 0, displayCalls = 0, appExits = 0;
inline std::string lastDrawnName, lastOpenedPath, missingBitmapPath, watchedGridLabel;
inline bool missingBitmapRead = false;
inline int watchedVisibleRight = -1, watchedClipLeft = -1;
inline std::string physicalLeftHint, physicalRightHint;
// Chrome recorder: the toggle is judged by what actually reaches the panel,
// so every outline, ink run and string is kept with its coordinates.
struct DrawnRect { int x, y, w, h; };
struct DrawnText { int font, x; std::string text; };
inline std::vector<DrawnRect> outlineRects, inkRects;
inline std::vector<DrawnText> drawnTexts;
struct HalFile {
  bool valid = false, directory = false;
  size_t next = 0;
  std::string filename;
  explicit operator bool() const { return valid; }
  bool isDirectory() const { return directory; }
  HalFile openNextFile() {
    if (next >= files.size()) return {};
    HalFile f; f.valid = true; f.filename = files[next++]; return f;
  }
  void getName(char* out, size_t cap) const { snprintf(out, cap, "%s", filename.c_str()); }
  int read(uint8_t*, size_t) { return 0; }
  void flush() {}
  bool close() { return true; }
};
struct FakeStorage {
  HalFile open(const char*) { HalFile f; f.valid = true; f.directory = true; return f; }
  bool ensureDirectoryExists(const char*) { return true; }
  bool exists(const char*) { return false; }
  bool remove(const char* path) {
    const std::string p(path);
    if (p.rfind("/AirPhoto/", 0) == 0 && p.find("/.", 10) == std::string::npos) {
      const auto it = std::find(files.begin(), files.end(), p.substr(10));
      if (it != files.end()) files.erase(it);
    }
    return true;
  }
  bool rename(const char*, const char*) { return true; }
  bool openFileForRead(const char*, const char* path, HalFile& out) {
    ++bitmapReads;
    if (path == missingBitmapPath) { missingBitmapRead = true; return false; }
    out.valid = true; out.filename = path; lastOpenedPath = path; return true;
  }
  bool openFileForWrite(const char*, const char*, HalFile& out) { out.valid = true; return true; }
};
inline FakeStorage fakeStorage;
#define Storage fakeStorage
struct FsHelpers {
  static bool ends(const std::string& s, const char* suffix) {
    const size_t n = strlen(suffix); return s.size() >= n && s.compare(s.size() - n, n, suffix) == 0;
  }
  static bool hasJpgExtension(const std::string& s) { return ends(s, ".jpg"); }
  static bool hasPngExtension(const std::string& s) { return ends(s, ".png"); }
  static bool hasBmpExtension(const std::string& s) { return ends(s, ".bmp"); }
};
namespace airpage {
  enum class ImageFormat { Bmp };
  struct ImageInfo { ImageFormat format = ImageFormat::Bmp; int width = 20, height = 40; };
  struct AirPageImageStore {
    static bool inspectImage(const char* path, ImageInfo& info) {
      ++inspectCalls;
      if (strcmp(path, "/AirPhoto/wide.jpg") == 0) {
        info.width = 800; info.height = 480; return true;
      }
      return false;
    }
  };
  struct SelectedImage { char path[300]{}; ImageInfo image; };
  struct AirPageWallpaper {
    static bool install(const SelectedImage&, bool) { return true; }
  };
}
struct GfxRenderer {
  enum class Orientation { Portrait, LandscapeCounterClockwise };
  struct FrameBufferLoan { explicit FrameBufferLoan(GfxRenderer&) {} };
  mutable bool clipActive = false;
  mutable int clipLeft = 0, clipRight = 0;
  struct ClipScope {
    const GfxRenderer& renderer;
    bool priorActive;
    int priorLeft, priorRight;
    ClipScope(const GfxRenderer& r, int x, int, int width, int)
        : renderer(r), priorActive(r.clipActive), priorLeft(r.clipLeft), priorRight(r.clipRight) {
      renderer.clipActive = true;
      renderer.clipLeft = priorActive ? std::max(priorLeft, x) : x;
      renderer.clipRight = priorActive ? std::min(priorRight, x + width) : x + width;
    }
    ~ClipScope() {
      renderer.clipActive = priorActive;
      renderer.clipLeft = priorLeft; renderer.clipRight = priorRight;
    }
  };
  Orientation orientation = Orientation::Portrait;
  int getScreenWidth() const { return orientation == Orientation::Portrait ? 480 : 800; }
  int getScreenHeight() const { return orientation == Orientation::Portrait ? 800 : 480; }
  void setOrientation(Orientation o) { orientation = o; }
  void clearScreen() {}
  void drawCenteredText(int, int, const char*) {}
  void drawText(int font, int x, int, const char* text) {
    lastDrawnName = text;
    drawnTexts.push_back({font, x, text});
    if (text == watchedGridLabel) {
      watchedClipLeft = clipActive ? clipLeft : -1;
      watchedVisibleRight = clipActive ? std::min(x + getTextWidth(font, text), clipRight)
                                       : x + getTextWidth(font, text);
    }
  }
  void drawRect(int x, int y, int w, int h, int = 1, bool = true) { outlineRects.push_back({x, y, w, h}); }
  void fillRect(int x, int y, int w, int h, bool = true) const { inkRects.push_back({x, y, w, h}); }
  void drawLine(int, int, int, int) {}
  int getTextHeight(int) const { return 14; }
  int getTextWidth(int, const char* s) const { return static_cast<int>(strlen(s) * 8); }
  void drawBitmap(...) { ++bitmapReads; }
  void displayBuffer(HalDisplay::RefreshMode) { ++displayCalls; }
};
struct Bitmap {
  Bitmap(HalFile&, bool) { ++bitmapReads; }
  int parseHeaders() { return 0; }
  int getWidth() const { return 20; }
  int getHeight() const { return 40; }
};
namespace BmpReaderError { constexpr int Ok = 0; }
struct MappedInputManager {
  enum class Button { Back, Confirm, Left, Right, Up, Down, NavNext, NavPrevious };
  enum class SwipeDir { None, Left, Right };
  struct Labels { const char* btn1; const char* btn2; const char* btn3; const char* btn4; };
  Button released = Button::Back;
  bool release = false, longConfirm = false, touch = false, frontButtonFollowOrientation = false;
  const GfxRenderer* screen = nullptr;
  mutable bool suppressedConfirm = false;
  int tapX = -1, tapY = -1, popupChoice = -1;
  SwipeDir swipe = SwipeDir::None;
  bool isNavDirectionSwapped() const {
    // MappedInputManager.cpp:28-34: live orientation plus touch/follow policy.
    return screen && (touch || frontButtonFollowOrientation) &&
           screen->orientation == GfxRenderer::Orientation::LandscapeCounterClockwise;
  }
  bool wasReleased(Button b) const {
    if (!release) return false;
    if (b == Button::NavNext)
      return released == (isNavDirectionSwapped() ? Button::Left : Button::Right) ||
             released == (isNavDirectionSwapped() ? Button::Up : Button::Down);
    if (b == Button::NavPrevious)
      return released == (isNavDirectionSwapped() ? Button::Right : Button::Left) ||
             released == (isNavDirectionSwapped() ? Button::Down : Button::Up);
    return b == released;
  }
  bool wasLongPressed(Button b, unsigned long) const {
    if (b != Button::Confirm || !longConfirm) return false;
    suppressedConfirm = true;
    return true;
  }
  bool consumeSuppressedRelease() {
    if (!suppressedConfirm || !release || released != Button::Confirm) return false;
    suppressedConfirm = false;
    return true;
  }
  bool hasTouch() const { return touch; }
  bool wasTapInRect(int x, int y, int w, int h) const {
    return touch && tapX >= x && tapX < x + w && tapY >= y && tapY < y + h;
  }
  bool wasScreenLongPress(int&, int&) const { return false; }
  SwipeDir wasSwipe() const { return swipe; }
  Labels mapLabels(const char* a, const char* b, const char* c, const char* d) const {
    // MappedInputManager.cpp:557-564: labels follow the same swapped axis.
    return isNavDirectionSwapped() ? Labels{a, b, d, c} : Labels{a, b, c, d};
  }
  void reset() { release = false; longConfirm = false; tapX = tapY = popupChoice = -1; swipe = SwipeDir::None; }
};
struct ActivityManagerFake { void goToApps() { ++appExits; } };
inline ActivityManagerFake activityManager;
struct RenderLock {};
struct Activity {
  GfxRenderer& renderer;
  MappedInputManager& mappedInput;
  Activity(const char*, GfxRenderer& r, MappedInputManager& i) : renderer(r), mappedInput(i) {}
  virtual ~Activity() = default;
  virtual void onEnter() {}
  virtual void onExit() {}
  virtual void loop() {}
  virtual void render(RenderLock&&) {}
  void requestUpdate() {}
};
struct OptionPopup {
  bool active = false;
  std::function<void(int)> onSelect;
  template<class Title, class Label, size_t N, class Callback>
  void show(Title, const Label (&)[N], int, int, Callback callback) {
    active = true; onSelect = callback;
  }
  template<class Callback>
  bool handleInput(MappedInputManager& input, Callback requestUpdate) {
    if (!active) return false;
    if (input.popupChoice >= 0) {
      const int choice = input.popupChoice;
      input.popupChoice = -1;
      active = false;
      onSelect(choice);
      requestUpdate();
    }
    return true;
  }
  void processRender(GfxRenderer&, MappedInputManager&) {}
  bool isActive() const { return active; }
};
struct FakeGUI {
  void drawPopup(GfxRenderer&, const char*) {}
  void drawButtonHints(GfxRenderer&, const char*, const char*, const char* left, const char* right) {
    physicalLeftHint = left; physicalRightHint = right;
  }
  void drawSideScrollBar(GfxRenderer&, Rect, int, int, int) {}
};
inline FakeGUI fakeGUI;
#define GUI fakeGUI
#define UI_10_FONT_ID 10
#define UI_12_FONT_ID 12
#define SMALL_FONT_ID 8
enum StrId {
  STR_AIRPHOTO_TITLE, STR_AIRPHOTO_EMPTY, STR_AIRPHOTO_ROTATE,
  STR_AIRPHOTO_LIST_VIEW, STR_AIRPHOTO_GRID_VIEW,
  STR_LOADING_POPUP, STR_BACK, STR_PREV_PAGE, STR_NEXT_PAGE,
  STR_SET_SLEEP_COVER, STR_SCREEN_BOOT, STR_SLEEP_SCREEN, STR_SCREEN_SHUTDOWN, STR_DELETE, STR_CANCEL, STR_CONFIRM,
  STR_FAILED_LOWER, STR_INVALID_IMAGE_FILE, STR_DONE, STR_SELECT
};
inline const char* tr(StrId id) {
  if (id == STR_AIRPHOTO_LIST_VIEW) return "List";
  if (id == STR_AIRPHOTO_GRID_VIEW) return "Grid";
  if (id == STR_PREV_PAGE) return "Previous";
  if (id == STR_NEXT_PAGE) return "Next";
  return "Label";
}
struct JpegToBmpConverter {
  static bool jpegFileToBmpStreamWithSize(HalFile&, HalFile&, int, int, bool) { ++conversions; return true; }
};
struct PngToBmpConverter {
  static bool pngFileToBmpStreamWithSize(HalFile&, HalFile&, int, int, bool) { ++conversions; return true; }
  static bool pngFileToBmpFile(const char*, const char*, bool) { ++conversions; return true; }
};
inline void delay(int) {}
'''

HARNESS = r'''
#include "FakePlatform.h"
#include "AirPhotoActivity.h"
int main() {
  files = {"00.jpg", "01.png", "02.bmp"};
  GfxRenderer screen;
  MappedInputManager keys;
  AirPhotoActivity activity(screen, keys);
  activity.onEnter();
  // Entry must not inspect a thumbnail, BMP cache, or original image.
  if (inspectCalls || bitmapReads || conversions) return 1;
  if (displayCalls != 1) return 2;
  if (lastDrawnName != "02.bmp") return 3;
  return 0;
}
'''


PAGING_HARNESS = r'''
#include "FakePlatform.h"
#include "AirPhotoActivity.h"
int main() {
  for (int i = 0; i < 13; ++i) {
    char name[16]; snprintf(name, sizeof(name), "%02d.jpg", i); files.emplace_back(name);
  }
  GfxRenderer screen;
  MappedInputManager keys;
  AirPhotoActivity activity(screen, keys);
  activity.onEnter();
  keys.release = true;
  keys.released = MappedInputManager::Button::Right;
  activity.loop();
  if (inspectCalls || bitmapReads || conversions) return 1;
  if (displayCalls != 2) return 2;
  if (lastDrawnName != "12.jpg") return 3;
  return 0;
}
'''


PHYSICAL_HARNESS = r'''
#include "FakePlatform.h"
#include "AirPhotoActivity.h"
int main() {
  for (int i = 0; i < 13; ++i) {
    char name[16]; snprintf(name, sizeof(name), "%02d.jpg", i); files.emplace_back(name);
  }
  GfxRenderer screen;
  MappedInputManager keys;
  AirPhotoActivity activity(screen, keys);
  activity.onEnter();
  keys.release = true; keys.released = MappedInputManager::Button::Right; activity.loop();
  keys.reset(); keys.release = true; keys.released = MappedInputManager::Button::Confirm; activity.loop();
  if (lastOpenedPath != "/AirPhoto/.view/12.jpg.bmp") return 1;
  if (inspectCalls == 0) return 2; // Full-screen opens lazily; browsing did not.
  const int reads = bitmapReads, inspections = inspectCalls;
  keys.reset(); keys.release = true; keys.released = MappedInputManager::Button::Back; activity.loop();
  if (bitmapReads != reads || inspectCalls != inspections) return 3;
  if (lastDrawnName != "12.jpg" || screen.orientation != GfxRenderer::Orientation::Portrait) return 4;
  keys.reset(); keys.release = true; keys.released = MappedInputManager::Button::Left; activity.loop();
  keys.reset(); keys.release = true; keys.released = MappedInputManager::Button::Down; activity.loop();
  keys.reset(); keys.release = true; keys.released = MappedInputManager::Button::Confirm; activity.loop();
  if (lastOpenedPath != "/AirPhoto/.view/01.jpg.bmp") return 5;
  return 0;
}
'''


TOUCH_HARNESS = r'''
#include "FakePlatform.h"
#include "AirPhotoActivity.h"
int main() {
  for (int i = 0; i < 13; ++i) {
    char name[16]; snprintf(name, sizeof(name), "%02d.jpg", i); files.emplace_back(name);
  }
  GfxRenderer screen;
  MappedInputManager keys;
  keys.touch = true;
  AirPhotoActivity activity(screen, keys);
  activity.onEnter();
  keys.tapX = 40; keys.tapY = 40 + 5 * 60 + 20; activity.loop();
  if (lastOpenedPath != "/AirPhoto/.view/05.jpg.bmp") return 1;
  keys.reset(); keys.release = true; keys.released = MappedInputManager::Button::Back; activity.loop();
  keys.reset(); keys.release = true; keys.released = MappedInputManager::Button::Right; activity.loop();
  const int reads = bitmapReads, inspections = inspectCalls;
  keys.reset(); keys.tapX = 40; keys.tapY = 40 + 2 * 60 + 20; activity.loop();
  if (bitmapReads != reads || inspectCalls != inspections) return 2; // Empty row, last page.
  if (lastDrawnName != "12.jpg") return 3;
  return 0;
}
'''


GRID_MARGIN_HARNESS = r'''
#include "FakePlatform.h"
#include "AirPhotoActivity.h"
int main() {
  files = {"00.bmp", "01.bmp"};
  GfxRenderer screen;
  MappedInputManager keys;
  keys.touch = true;
  AirPhotoActivity activity(screen, keys);
  activity.onEnter();
  keys.tapX = 410; keys.tapY = 18; activity.loop(); // Grid, 160x180 cells at y=40.
  const int draws = displayCalls, reads = bitmapReads;
  // Cell 0 draws inside (6,46)-(154,214); cell 1 begins at x=160.
  for (const auto& point : {std::pair<int, int>{1, 80}, {159, 80}, {20, 42},
                             {20, 219}, {160, 80}}) {
    keys.reset(); keys.tapX = point.first; keys.tapY = point.second;
    activity.loop();
    if (displayCalls != draws || bitmapReads != reads) return 1;
  }
  keys.reset(); keys.tapX = 20; keys.tapY = 80; activity.loop();
  if (lastOpenedPath != "/AirPhoto/00.bmp" || displayCalls != draws + 1) return 2;
  return 0;
}
'''


GRID_LABEL_HARNESS = r'''
#include "FakePlatform.h"
#include "AirPhotoActivity.h"
int main() {
  const std::string longName(80, 0x41);
  watchedGridLabel = longName + ".jpg";
  files = {watchedGridLabel, "neighbor.bmp"};
  missingBitmapPath = "/AirPhoto/.thumb/" + watchedGridLabel + ".bmp";
  GfxRenderer screen;
  MappedInputManager keys;
  keys.touch = true;
  AirPhotoActivity activity(screen, keys);
  activity.onEnter();
  keys.tapX = 410; keys.tapY = 18; activity.loop();
  if (!missingBitmapRead || lastDrawnName != watchedGridLabel) return 1;
  // The fallback label belongs inside the first thumbnail (x=6..154).
  if (watchedClipLeft < 12 || watchedVisibleRight <= watchedClipLeft ||
      watchedVisibleRight > 154) return 2;
  return 0;
}
'''


TOGGLE_HARNESS = r'''
#include "FakePlatform.h"
#include "AirPhotoActivity.h"
int main() {
  files = {"00.jpg", "01.png"};
  GfxRenderer screen;
  MappedInputManager keys;
  keys.touch = true;
  AirPhotoActivity activity(screen, keys);
  activity.onEnter();
  keys.tapX = 410; keys.tapY = 18; activity.loop(); // Grid: thumbnails are lazy.
  if (inspectCalls == 0 || bitmapReads == 0 || conversions == 0) return 1;
  const int reads = bitmapReads, inspections = inspectCalls, decoded = conversions;
  keys.reset(); keys.tapX = 410; keys.tapY = 18; activity.loop(); // List: no bitmap I/O.
  if (bitmapReads != reads || inspectCalls != inspections || conversions != decoded) return 2;
  keys.reset(); keys.longConfirm = true; activity.loop(); // Hold select for grid.
  if (bitmapReads == reads) return 3;
  const int gridReads = bitmapReads;
  keys.reset(); keys.release = true; keys.released = MappedInputManager::Button::Confirm;
  if (!keys.consumeSuppressedRelease()) activity.loop(); // ActivityManager consumes this release.
  if (bitmapReads != gridReads) return 4;
  keys.reset(); keys.release = true; keys.released = MappedInputManager::Button::Confirm;
  activity.loop(); // Fresh short confirm in grid returns to list.
  if (bitmapReads != gridReads) return 5;
  return 0;
}
'''


DELETE_HARNESS = r'''
#include "FakePlatform.h"
#include "AirPhotoActivity.h"
int main() {
  files = {"00.jpg", "01.jpg"};
  GfxRenderer screen;
  MappedInputManager keys;
  AirPhotoActivity activity(screen, keys);
  activity.onEnter();
  keys.release = true; keys.released = MappedInputManager::Button::Confirm; activity.loop(); // Open 00.
  keys.reset(); keys.release = true; keys.released = MappedInputManager::Button::Confirm; activity.loop(); // Menu.
  keys.reset(); keys.popupChoice = 2; activity.loop(); // Delete confirmation.
  const int reads = bitmapReads, inspections = inspectCalls;
  keys.reset(); keys.popupChoice = 1; activity.loop(); // Confirm delete.
  if (files.size() != 1 || files.front() != "01.jpg") return 1;
  if (bitmapReads != reads || inspectCalls != inspections) return 2;
  if (lastDrawnName != "01.jpg" || screen.orientation != GfxRenderer::Orientation::Portrait) return 3;
  return 0;
}
'''


GRID_PAGE_HARNESS = r'''
#include "FakePlatform.h"
#include "AirPhotoActivity.h"
int main() {
  for (int i = 0; i < 13; ++i) {
    char name[16]; snprintf(name, sizeof(name), "%02d.jpg", i); files.emplace_back(name);
  }
  GfxRenderer screen;
  MappedInputManager keys;
  keys.touch = true;
  AirPhotoActivity activity(screen, keys);
  activity.onEnter();
  keys.tapX = 410; keys.tapY = 18; activity.loop(); // Grid page 1.
  keys.reset(); keys.release = true; keys.released = MappedInputManager::Button::Right; activity.loop();
  keys.reset(); keys.release = true; keys.released = MappedInputManager::Button::Confirm; activity.loop();
  const int reads = bitmapReads, inspections = inspectCalls;
  keys.reset(); keys.release = true; keys.released = MappedInputManager::Button::Confirm; activity.loop();
  if (lastOpenedPath != "/AirPhoto/.view/12.jpg.bmp") return 1;
  if (bitmapReads <= reads || inspectCalls <= inspections) return 2;
  return 0;
}
'''


ORIENTATION_HARNESS = r'''
#include "FakePlatform.h"
#include "AirPhotoActivity.h"
int main() {
  files = {"wide.jpg"};
  GfxRenderer screen;
  MappedInputManager keys;
  AirPhotoActivity activity(screen, keys);
  activity.onEnter();
  if (bitmapReads || inspectCalls || screen.orientation != GfxRenderer::Orientation::Portrait) return 1;
  keys.release = true; keys.released = MappedInputManager::Button::Confirm; activity.loop();
  if (screen.orientation != GfxRenderer::Orientation::LandscapeCounterClockwise) return 2;
  const int reads = bitmapReads, inspections = inspectCalls;
  keys.reset(); keys.release = true; keys.released = MappedInputManager::Button::Back; activity.loop();
  if (screen.orientation != GfxRenderer::Orientation::Portrait) return 3;
  if (bitmapReads != reads || inspectCalls != inspections) return 4;
  keys.reset(); keys.release = true; keys.released = MappedInputManager::Button::Confirm; activity.loop();
  if (screen.orientation != GfxRenderer::Orientation::LandscapeCounterClockwise) return 5;
  activity.onExit(); // Home from the viewer restores the global orientation too.
  if (screen.orientation != GfxRenderer::Orientation::Portrait) return 6;
  return 0;
}
'''


LANDSCAPE_HINT_HARNESS = r'''
#include "FakePlatform.h"
#include "AirPhotoActivity.h"
int main() {
  files = {"00.bmp", "wide.jpg", "zz.bmp"};
  GfxRenderer screen;
  MappedInputManager keys;
  keys.screen = &screen;
  keys.frontButtonFollowOrientation = true;
  AirPhotoActivity activity(screen, keys);
  activity.onEnter();
  if (physicalLeftHint != "Previous" || physicalRightHint != "Next") return 1;
  keys.release = true; keys.released = MappedInputManager::Button::Down; activity.loop();
  keys.reset(); keys.release = true; keys.released = MappedInputManager::Button::Confirm;
  activity.loop(); // wide.jpg switches the live renderer to landscape.
  if (screen.orientation != GfxRenderer::Orientation::LandscapeCounterClockwise) return 2;
  if (physicalLeftHint != "Next" || physicalRightHint != "Previous") return 3;
  // The label under each physical key must describe the action it actually takes.
  keys.reset(); keys.release = true; keys.released = MappedInputManager::Button::Left;
  activity.loop();
  if (lastOpenedPath != "/AirPhoto/zz.bmp") return 4;
  keys.reset(); keys.release = true; keys.released = MappedInputManager::Button::Left;
  activity.loop(); // Portrait Left returns to wide.jpg.
  if (screen.orientation != GfxRenderer::Orientation::LandscapeCounterClockwise) return 5;
  keys.reset(); keys.release = true; keys.released = MappedInputManager::Button::Right;
  activity.loop();
  if (lastOpenedPath != "/AirPhoto/00.bmp") return 6;
  return 0;
}
'''


VIEW_TOGGLE_CHROME_HARNESS = r'''
#include "FakePlatform.h"
#include "AirPhotoActivity.h"
#include "components/icons/listIcons.h"

namespace {

constexpr int kBand = 40;  // Header band; everything below belongs to the list/grid.
using Pixels = std::vector<std::pair<int, int>>;

// Shape only: the icon is compared by artwork, not by where it landed.
Pixels normalised(Pixels pixels) {
  if (pixels.empty()) return pixels;
  int left = pixels.front().first, top = pixels.front().second;
  for (const auto& p : pixels) { left = std::min(left, p.first); top = std::min(top, p.second); }
  for (auto& p : pixels) { p.first -= left; p.second -= top; }
  std::sort(pixels.begin(), pixels.end());
  return pixels;
}

// The generated asset itself: rows top-to-bottom, MSB first, 0 = ink.
Pixels glyphPixels(const freeink::Icon& icon) {
  Pixels pixels;
  const int rowBytes = (icon.w + 7) / 8;
  for (int row = 0; row < icon.h; ++row)
    for (int column = 0; column < icon.w; ++column)
      if (((icon.bits[row * rowBytes + column / 8] >> (7 - column % 8)) & 1U) == 0)
        pixels.emplace_back(column, row);
  return pixels;
}

struct Band { Pixels pixels; int left = 1 << 20, right = -1, top = 1 << 20, bottom = -1; };

Band headerInk() {
  Band band;
  for (const auto& r : inkRects) {
    if (r.y >= kBand) continue;
    for (int dy = 0; dy < r.h; ++dy)
      for (int dx = 0; dx < r.w; ++dx) band.pixels.emplace_back(r.x + dx, r.y + dy);
    band.left = std::min(band.left, r.x);
    band.right = std::max(band.right, r.x + r.w);
    band.top = std::min(band.top, r.y);
    band.bottom = std::max(band.bottom, r.y + r.h);
  }
  return band;
}

bool headerLabel(DrawnText& out) {
  for (const auto& t : drawnTexts)
    if (t.font == SMALL_FONT_ID) { out = t; return true; }
  return false;
}

void forget() { outlineRects.clear(); inkRects.clear(); drawnTexts.clear(); }

}  // namespace

int main() {
  files = {"00.jpg", "01.png"};
  GfxRenderer screen;
  MappedInputManager keys;
  keys.touch = true;
  AirPhotoActivity activity(screen, keys);

  forget();
  activity.onEnter();  // Filename list: the control offers the grid.

  // No frame around the control any more.
  for (const auto& r : outlineRects)
    if (r.y < kBand) return 1;

  DrawnText label;
  if (!headerLabel(label) || label.text != "Grid") return 2;
  // Smaller than the browser title beside it, and drawn only once.
  for (const auto& t : drawnTexts)
    if (t.font != SMALL_FONT_ID && t.text == label.text) return 18;
  const int labelWidth = screen.getTextWidth(SMALL_FONT_ID, label.text.c_str());
  const int controlRight = label.x + labelWidth;
  if (controlRight > screen.getScreenWidth() - 4 ||
      controlRight < screen.getScreenWidth() - 20) return 3;

  Band ink = headerInk();
  if (ink.pixels.size() < 30) return 4;              // An icon, not a stray pixel.
  if (ink.right > label.x) return 5;                 // Entirely before the words.
  if (ink.left < label.x - 30) return 6;             // ...and adjacent to them.
  if (ink.top < 4 || ink.bottom > 34) return 7;      // Inside the 30px header band.
  if (normalised(ink.pixels) != normalised(glyphPixels(icon_layout_grid_24))) return 8;

  // Tapping the icon itself switches the view.
  forget();
  keys.reset(); keys.tapX = ink.left; keys.tapY = 18; activity.loop();
  for (const auto& r : outlineRects)
    if (r.y < kBand) return 9;
  DrawnText gridLabel;
  if (!headerLabel(gridLabel) || gridLabel.text != "List") return 10;
  Band gridIcon = headerInk();
  if (gridIcon.right > gridLabel.x) return 11;
  if (normalised(gridIcon.pixels) != normalised(glyphPixels(icon_list_24))) return 12;
  if (normalised(gridIcon.pixels) == normalised(ink.pixels)) return 13;

  // The hit area stops where the drawing stops, on both sides.
  const int quiet = displayCalls;
  keys.reset(); keys.tapX = gridIcon.left - 6; keys.tapY = 18; activity.loop();
  if (displayCalls != quiet) return 14;
  const int gridLabelWidth = screen.getTextWidth(SMALL_FONT_ID, gridLabel.text.c_str());
  keys.reset(); keys.tapX = gridLabel.x + gridLabelWidth + 6; keys.tapY = 18; activity.loop();
  if (displayCalls != quiet) return 15;

  // A tap on the words still toggles back.
  forget();
  keys.reset(); keys.tapX = gridLabel.x + 2; keys.tapY = 18; activity.loop();
  if (displayCalls != quiet + 1) return 16;
  DrawnText back;
  if (!headerLabel(back) || back.text != "Grid") return 17;
  return 0;
}
'''


class FastListTest(unittest.TestCase):
    def run_host(self, scenario):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / 'FakePlatform.h').write_text(PLATFORM)
            for name in SHIMS:
                shim = root / name
                shim.parent.mkdir(parents=True, exist_ok=True)
                shim.write_text('#include "FakePlatform.h"\n')
            main = root / 'main.cpp'
            main.write_text(scenario)
            cover_stub = root / 'AirPhotoActionsStub.cpp'
            cover_stub.write_text('#include "FakePlatform.h"\n#include "AirPhotoActions.h"\n'
                                  'namespace airphoto { bool setCover(const char*, Cover) { return true; } }\n')
            binary = root / 'airphoto_host'
            build = subprocess.run(
                ['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-I', str(root),
                 '-I', str(SOURCE.parent), '-I', str(ROOT / 'src'),
                 str(main), str(SOURCE), str(cover_stub), '-o', str(binary)],
                text=True, capture_output=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(binary)], text=True, capture_output=True)
            self.assertEqual(run.returncode, 0, f'host activity returned {run.returncode}: {run.stderr}')

    def test_entry_renders_names_without_bitmap_io_or_decode(self):
        self.run_host(HARNESS)

    def test_page_turn_is_filename_only_even_when_thumbnails_missing(self):
        self.run_host(PAGING_HARNESS)

    def test_button_selection_opens_correct_page_and_returns_to_fast_list(self):
        self.run_host(PHYSICAL_HARNESS)

    def test_row_tap_opens_photo_and_ignores_blank_row_on_last_page(self):
        self.run_host(TOUCH_HARNESS)

    def test_grid_blank_cell_margins_do_not_open_photos(self):
        self.run_host(GRID_MARGIN_HARNESS)

    def test_missing_grid_thumbnail_clips_long_filename_to_own_cell(self):
        self.run_host(GRID_LABEL_HARNESS)

    def test_explicit_touch_and_button_toggle_lazily_generates_only_grid(self):
        self.run_host(TOGGLE_HARNESS)

    def test_delete_restores_list_without_generating_survivor_thumbnails(self):
        self.run_host(DELETE_HARNESS)

    def test_grid_page_change_then_list_confirm_opens_visible_photo(self):
        self.run_host(GRID_PAGE_HARNESS)

    def test_landscape_hint_labels_match_physical_navigation_with_follow_orientation(self):
        self.run_host(LANDSCAPE_HINT_HARNESS)

    def test_landscape_view_back_and_home_restore_portrait_list(self):
        self.run_host(ORIENTATION_HARNESS)

    def test_view_toggle_draws_borderless_icon_plus_label_matching_its_hit_area(self):
        self.run_host(VIEW_TOGGLE_CHROME_HARNESS)

if __name__ == '__main__':
    unittest.main()
