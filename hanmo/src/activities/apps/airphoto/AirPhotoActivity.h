#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "AirPhotoActions.h"
#include "MappedInputManager.h"
#include "activities/Activity.h"
#include "components/OptionPopup.h"

// Photos uploaded from a computer or phone over the device hotspot.
//
// The browser does the expensive work: it uploads the untouched original to
// /AirPhoto, a screen-sized bitmap to /AirPhoto/.view and a small one to
// /AirPhoto/.thumb, all in the 2bpp grayscale BMP the panel reads directly.
// Browsing the default filename list never opens or decodes an image. The
// optional grid can generate missing thumbnails for files copied to the card;
// full-screen viewing lazily builds its own display-sized bitmap.
class AirPhotoActivity final : public Activity {
 public:
  AirPhotoActivity(GfxRenderer& renderer, MappedInputManager& mappedInput);

  void onEnter() override;
  void onExit() override;
  void loop() override;
  void render(RenderLock&& lock) override;

 private:
  static constexpr int kColumns = 3;
  static constexpr int kGridRows = 4;
  static constexpr int kPerPage = kColumns * kGridRows;
  static constexpr int kThumbMaxWidth = 120;
  static constexpr int kThumbMaxHeight = 160;
  enum class ViewMode : uint8_t { List, Grid };

  void loadPhotos();
  // The browser pre-builds these when it uploads, but a card copied straight
  // from a computer has none, so the device fills the cache itself.
  bool ensureDerived(int index, const char* subDir, int maxWidth, int maxHeight);
  bool ensureDerivedAt(int index, const std::string& target, int maxWidth, int maxHeight);
  void ensurePageDerived();
  bool needsDerived(int index) const;
  void drawBrowserHeader();
  // The control has no frame, so its width is measured from what it draws;
  // both the drawing and the hit area read the label through here.
  const char* viewToggleLabel() const;
  Rect viewToggleRect() const;
  void drawList(bool present = true);
  bool listRect(int slot, Rect& out) const;
  int tappedListSlot() const;
  void drawGrid(bool present = true);
  void drawOpenPhoto(bool present = true);
  bool cellRect(int slot, Rect& out) const;
  int tappedSlot() const;
  void showPhotoMenu();
  void showCoverPrompt();
  void confirmDeletePhoto();
  void deletePhoto();
  void toggleRotation();
  // The cached view bitmap is built for whichever orientation it will be shown
  // in, so turning the screen means rebuilding it.
  bool viewIsLandscape() const;
  void applyOrientation();
  void applyCover();
  bool openPhoto(int index);
  int pageCount() const;

  std::string photoPath(int index) const;
  std::string derivedPath(int index, const char* subDir) const;
  std::string viewPath(int index) const;

  std::vector<std::string> photos_;
  int page_ = 0;
  int selectedIndex_ = -1;
  ViewMode view_ = ViewMode::List;
  // -1 means the filename list or grid is showing; otherwise full-screen.
  int openIndex_ = -1;
  OptionPopup photoMenuPopup_;
  OptionPopup confirmationPopup_;
  // Popup callbacks run on the loop task; only render() presents their final
  // base/popup frame. No second framebuffer or per-transition allocation.
  bool panelDeferred_ = false;
  bool popupCallback_ = false;
  bool baseDirty_ = false;
  bool rotatePending_ = false;
  bool coverPending_ = false;
  airphoto::Cover coverToSet_ = airphoto::Cover::Sleep;
  bool operationFailed_ = false;
  // Landscape photos waste more than half of a 480x800 panel when fitted
  // upright, so the screen turns instead of the photo shrinking. Remembered
  // per photo index for the session; -1 means decide from the photo itself.
  std::vector<int8_t> rotateOverride_;
  bool landscape_ = false;
};
