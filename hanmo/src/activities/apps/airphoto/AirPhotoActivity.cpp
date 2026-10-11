#include "AirPhotoActivity.h"
#include "AirPhotoOrientation.h"
#include "AirPhotoDeletion.h"

#include <Bitmap.h>
#include <FsHelpers.h>
#include <GfxRenderer.h>
#include <HalStorage.h>
#include <I18n.h>
#include <JpegToBmpConverter.h>
#include <PngToBmpConverter.h>

#include <algorithm>
#include <cstdio>

#include "../../../components/icons/listIcons.h"
#include "activities/apps/airpage/AirPageImageStore.h"
#include "activities/apps/airpage/AirPageWallpaper.h"
#include "components/UITheme.h"
#include "components/themes/BaseTheme.h"
#include "fontIds.h"

namespace {

constexpr char kPhotoDir[] = "/AirPhoto";
constexpr char kViewDir[] = "/AirPhoto/.view";
constexpr char kThumbDir[] = "/AirPhoto/.thumb";
constexpr int kHeaderHeight = 40;
constexpr int kFooterHeight = 40;
constexpr int kCellPadding = 6;
constexpr int kToggleIconSize = 24;
constexpr int kToggleGap = 6;
constexpr int kToggleMargin = 12;
// Chrome, not content: the label rides one step below the browser title so
// the pair reads as a control. Measure the hit area with the SAME font.
constexpr int kToggleFont = SMALL_FONT_ID;

// The generated SDK assets are stored unrotated, which the legacy
// GfxRenderer::drawIcon() cannot consume, so blit them here. One fill per
// run of ink in a row rather than one per pixel.
void blitIcon(const GfxRenderer& renderer, const freeink::Icon& icon, const int x, const int y) {
  const int rowBytes = (icon.w + 7) / 8;
  for (int row = 0; row < icon.h; ++row) {
    const uint8_t* bits = icon.bits + row * rowBytes;
    int run = 0;
    for (int column = 0; column <= icon.w; ++column) {
      if (column < icon.w && ((bits[column / 8] >> (7 - column % 8)) & 1U) == 0) {
        ++run;
        continue;
      }
      if (run > 0) renderer.fillRect(x + column - run, y + row, run, 1);
      run = 0;
    }
  }
}

bool isPhotoName(const std::string& name) {
  return FsHelpers::hasJpgExtension(name) || FsHelpers::hasPngExtension(name) || FsHelpers::hasBmpExtension(name);
}

// Keep the complete original name in the cache key: holiday.jpg and
// holiday.png must not overwrite or display each other's derived bitmap.
std::string bitmapNameFor(const std::string& name) { return name + ".bmp"; }

// A few older host Activity shims omit these real renderer/lock helpers. On
// device both overloads below select the real request and busy check.
template <typename Display>
auto requestPopupHalfRefresh(Display& display, int)
    -> decltype(display.requestNextRefresh(HalDisplay::HALF_REFRESH), void()) {
  display.requestNextRefresh(HalDisplay::HALF_REFRESH);
}
template <typename Display>
void requestPopupHalfRefresh(Display&, long) {}

template <typename Lock>
auto renderIsBusy(int) -> decltype(Lock::peek()) { return Lock::peek(); }
template <typename Lock>
bool renderIsBusy(long) { return false; }

}  // namespace

AirPhotoActivity::AirPhotoActivity(GfxRenderer& renderer, MappedInputManager& mappedInput)
    : Activity("AirPhoto", renderer, mappedInput) {}

std::string AirPhotoActivity::photoPath(const int index) const {
  return std::string(kPhotoDir) + "/" + photos_[index];
}

std::string AirPhotoActivity::derivedPath(const int index, const char* subDir) const {
  return std::string(subDir) + "/" + bitmapNameFor(photos_[index]);
}

// A view fitted to 480x800 is the wrong shape for a turned screen, so the two
// orientations get separate cache files. The upright name is left exactly as
// the browser uploads it.
std::string AirPhotoActivity::viewPath(const int index) const {
  const std::string upright = derivedPath(index, kViewDir);
  if (!landscape_) return upright;
  const size_t dot = upright.rfind('.');
  return dot == std::string::npos ? upright + ".land.bmp"
                                  : upright.substr(0, dot) + ".land" + upright.substr(dot);
}

int AirPhotoActivity::pageCount() const {
  if (photos_.empty()) return 1;
  return (static_cast<int>(photos_.size()) + kPerPage - 1) / kPerPage;
}

void AirPhotoActivity::loadPhotos() {
  photos_.clear();

  auto dir = Storage.open(kPhotoDir);
  if (!dir || !dir.isDirectory()) return;

  char name[500];
  for (auto file = dir.openNextFile(); file; file = dir.openNextFile()) {
    if (file.isDirectory()) continue;
    file.getName(name, sizeof(name));
    // Skip the generated .view/.thumb bitmaps and any other dot entry.
    if (name[0] == '.') continue;
    std::string fname(name);
    if (isPhotoName(fname)) photos_.push_back(std::move(fname));
  }
  std::sort(photos_.begin(), photos_.end());
  rotateOverride_.assign(photos_.size(), -1);

  if (page_ >= pageCount()) page_ = pageCount() - 1;
  if (page_ < 0) page_ = 0;
  if (photos_.empty()) {
    selectedIndex_ = -1;
  } else if (selectedIndex_ < page_ * kPerPage ||
             selectedIndex_ >= std::min((page_ + 1) * kPerPage, static_cast<int>(photos_.size()))) {
    selectedIndex_ = page_ * kPerPage;
  }
}

bool AirPhotoActivity::cellRect(const int slot, Rect& out) const {
  if (slot < 0 || slot >= kPerPage) return false;
  const int screenWidth = renderer.getScreenWidth();
  const int screenHeight = renderer.getScreenHeight();
  const int gridHeight = screenHeight - kHeaderHeight - kFooterHeight;
  const int cellWidth = screenWidth / kColumns;
  const int cellHeight = gridHeight / kGridRows;

  // One rectangle for the drawn thumbnail and its tap target. Leave blank
  // margins between cells instead of activating the invisible grid band.
  out.x = (slot % kColumns) * cellWidth + kCellPadding;
  out.y = kHeaderHeight + (slot / kColumns) * cellHeight + kCellPadding;
  out.width = cellWidth - kCellPadding * 2;
  out.height = cellHeight - kCellPadding * 2;
  return true;
}

int AirPhotoActivity::tappedSlot() const {
  for (int slot = 0; slot < kPerPage; slot++) {
    Rect cell;
    if (!cellRect(slot, cell)) continue;
    if (mappedInput.wasTapInRect(cell.x, cell.y, cell.width, cell.height)) return slot;
  }
  return -1;
}

bool AirPhotoActivity::needsDerived(const int index) const {
  // A BMP original is already in a format the panel reads, and drawBitmap
  // scales it into the cell, so it needs no cached copy.
  return !FsHelpers::hasBmpExtension(photos_[index]);
}

bool AirPhotoActivity::ensureDerived(const int index, const char* subDir, const int maxWidth,
                                     const int maxHeight) {
  if (!Storage.ensureDirectoryExists(subDir)) return false;
  return ensureDerivedAt(index, derivedPath(index, subDir), maxWidth, maxHeight);
}

bool AirPhotoActivity::ensureDerivedAt(const int index, const std::string& target, const int maxWidth,
                                       const int maxHeight) {
  if (!needsDerived(index)) return false;
  airpage::ImageInfo cached;
  const bool existing = Storage.exists(target.c_str());
  if (existing && airpage::AirPageImageStore::inspectImage(target.c_str(), cached) &&
      cached.format == airpage::ImageFormat::Bmp) return false;

  // The caller may pass a name inside .view or .thumb, so make sure the parent
  // folder is there rather than assuming ensureDerived created it.
  const size_t slash = target.rfind('/');
  if (slash != std::string::npos && slash > 0) {
    if (!Storage.ensureDirectoryExists(target.substr(0, slash).c_str())) return false;
  }

  // Write through a .part file: an interrupted conversion would otherwise
  // leave a truncated bitmap that never parses again.
  const std::string part = target + ".part";
  Storage.remove(part.c_str());

  const std::string source = photoPath(index);
  bool ok = false;
  {
    GfxRenderer::FrameBufferLoan loan(renderer);
    HalFile in;
    HalFile out;
    if (Storage.openFileForRead("APHO", source.c_str(), in) &&
        Storage.openFileForWrite("APHO", part.c_str(), out)) {
      ok = FsHelpers::hasPngExtension(photos_[index])
               ? PngToBmpConverter::pngFileToBmpStreamWithSize(in, out, maxWidth, maxHeight, /*crop=*/false)
               : JpegToBmpConverter::jpegFileToBmpStreamWithSize(in, out, maxWidth, maxHeight, /*crop=*/false);
      out.flush();
      ok = out.close() && ok;
    }
  }

  // Check the new file before touching an existing cache. A power loss or a
  // failed decode must not replace even a damaged final file with another
  // truncated one; an interrupted upload will be retried on the next entry.
  airpage::ImageInfo generated;
  if (!ok || !airpage::AirPageImageStore::inspectImage(part.c_str(), generated) ||
      generated.format != airpage::ImageFormat::Bmp) {
    Storage.remove(part.c_str());
    return false;
  }
  const std::string backup = target + ".bak";
  if (existing) {
    Storage.remove(backup.c_str());
    if (!Storage.rename(target.c_str(), backup.c_str())) {
      Storage.remove(part.c_str());
      return false;
    }
  }
  if (!Storage.rename(part.c_str(), target.c_str())) {
    if (existing) Storage.rename(backup.c_str(), target.c_str());
    Storage.remove(part.c_str());
    return false;
  }
  if (existing) Storage.remove(backup.c_str());
  return true;
}

void AirPhotoActivity::ensurePageDerived() {
  const int first = page_ * kPerPage;
  const int last = std::min(first + kPerPage, static_cast<int>(photos_.size()));

  int pending = 0;
  for (int index = first; index < last; index++) {
    if (needsDerived(index)) {
      airpage::ImageInfo cached;
      const bool valid = airpage::AirPageImageStore::inspectImage(derivedPath(index, kThumbDir).c_str(), cached) &&
                         cached.format == airpage::ImageFormat::Bmp;
      if (!valid) pending++;
    }
  }
  if (pending == 0) return;

  // Decoding a full-size photo is slow enough to look like a hang, so say so.
  int done = 0;
  char message[48];
  for (int index = first; index < last; index++) {
    if (!needsDerived(index)) continue;
    airpage::ImageInfo cached;
    const bool valid = airpage::AirPageImageStore::inspectImage(derivedPath(index, kThumbDir).c_str(), cached) &&
                       cached.format == airpage::ImageFormat::Bmp;
    if (valid) continue;
    snprintf(message, sizeof(message), "%s %d/%d", tr(STR_LOADING_POPUP), done + 1, pending);
    GUI.drawPopup(renderer, message);
    ensureDerived(index, kThumbDir, kThumbMaxWidth, kThumbMaxHeight);
    done++;
  }
}

const char* AirPhotoActivity::viewToggleLabel() const {
  return view_ == ViewMode::List ? tr(STR_AIRPHOTO_GRID_VIEW) : tr(STR_AIRPHOTO_LIST_VIEW);
}

// Sized from the glyph plus the translated label, so a Chinese and an English
// build each get a hit area that covers exactly the ink the user can see.
Rect AirPhotoActivity::viewToggleRect() const {
  const int width = kToggleIconSize + kToggleGap + renderer.getTextWidth(kToggleFont, viewToggleLabel());
  return Rect{renderer.getScreenWidth() - kToggleMargin - width, 4, width, 30};
}

void AirPhotoActivity::drawBrowserHeader() {
  const Rect toggle = viewToggleRect();
  char header[64];
  snprintf(header, sizeof(header), "%s  %d/%d", tr(STR_AIRPHOTO_TITLE), page_ + 1, pageCount());
  {
    // A long title must never reach the control, which now floats left as the
    // label grows.
    GfxRenderer::ClipScope clip(renderer, 10, 4, std::max(0, toggle.x - 22), 32);
    renderer.drawText(UI_12_FONT_ID, 10, 10, header);
  }
  // The glyph names the view being switched to, exactly like the label beside it.
  blitIcon(renderer, view_ == ViewMode::List ? icon_layout_grid_24 : icon_list_24, toggle.x,
           toggle.y + (toggle.height - kToggleIconSize) / 2);
  renderer.drawText(kToggleFont, toggle.x + kToggleIconSize + kToggleGap,
                    toggle.y + (toggle.height - renderer.getTextHeight(kToggleFont)) / 2,
                    viewToggleLabel());
}

bool AirPhotoActivity::listRect(const int slot, Rect& out) const {
  if (slot < 0 || slot >= kPerPage) return false;
  const int width = renderer.getScreenWidth();
  const int step = (renderer.getScreenHeight() - kHeaderHeight - kFooterHeight) / kPerPage;
  if (step <= 6 || width <= 16) return false;
  // Six pixels of visible space between rows; the hit area matches the drawing.
  out = Rect{8, kHeaderHeight + slot * step + 3, width - 16, step - 6};
  return true;
}

int AirPhotoActivity::tappedListSlot() const {
  const int first = page_ * kPerPage;
  for (int slot = 0; slot < kPerPage && first + slot < static_cast<int>(photos_.size()); ++slot) {
    Rect row;
    if (listRect(slot, row) && mappedInput.wasTapInRect(row.x, row.y, row.width, row.height)) return slot;
  }
  return -1;
}

void AirPhotoActivity::drawList(const bool present) {
  if (panelDeferred_) {
    baseDirty_ = true;
    return;
  }
  renderer.clearScreen();
  drawBrowserHeader();
  if (photos_.empty()) {
    renderer.drawCenteredText(UI_10_FONT_ID, renderer.getScreenHeight() / 2, tr(STR_AIRPHOTO_EMPTY));
  } else {
    const int first = page_ * kPerPage;
    for (int slot = 0; slot < kPerPage && first + slot < static_cast<int>(photos_.size()); ++slot) {
      Rect row;
      if (!listRect(slot, row)) break;
      const int index = first + slot;
      if (index == selectedIndex_) renderer.fillRect(row.x, row.y + 4, 4, row.height - 8);
      GfxRenderer::ClipScope clip(renderer, row.x + 14, row.y, row.width - 24, row.height);
      renderer.drawText(UI_10_FONT_ID, row.x + 14,
                        row.y + (row.height - renderer.getTextHeight(UI_10_FONT_ID)) / 2,
                        photos_[index].c_str());
    }
    GUI.drawSideScrollBar(renderer,
                          Rect{0, kHeaderHeight, renderer.getScreenWidth(),
                               renderer.getScreenHeight() - kHeaderHeight - kFooterHeight},
                          static_cast<int>(photos_.size()), first, kPerPage);
  }
  const auto labels = mappedInput.mapLabels(tr(STR_BACK), tr(STR_SELECT), tr(STR_PREV_PAGE), tr(STR_NEXT_PAGE));
  GUI.drawButtonHints(renderer, labels.btn1, labels.btn2, labels.btn3, labels.btn4);
  if (present) renderer.displayBuffer(HalDisplay::HALF_REFRESH);
}

void AirPhotoActivity::drawGrid(const bool present) {
  if (panelDeferred_) {
    baseDirty_ = true;
    return;
  }
  renderer.clearScreen();
  drawBrowserHeader();

  if (photos_.empty()) {
    renderer.drawCenteredText(UI_10_FONT_ID, renderer.getScreenHeight() / 2, tr(STR_AIRPHOTO_EMPTY));
  } else {
    const int first = page_ * kPerPage;
    for (int slot = 0; slot < kPerPage; slot++) {
      const int index = first + slot;
      if (index >= static_cast<int>(photos_.size())) break;

      Rect cell;
      if (!cellRect(slot, cell)) continue;

      // A BMP original has no cached thumbnail; drawBitmap scales it to fit.
      const std::string thumb =
          needsDerived(index) ? derivedPath(index, kThumbDir) : photoPath(index);
      HalFile file;
      bool drew = false;
      if (Storage.openFileForRead("APHO", thumb.c_str(), file)) {
        Bitmap bitmap(file, true);
        if (bitmap.parseHeaders() == BmpReaderError::Ok) {
          renderer.drawBitmap(bitmap, cell.x, cell.y, cell.width, cell.height);
          drew = true;
        }
      }
      // A photo uploaded by other means has no generated thumbnail; show the
      // name so it is still reachable rather than silently missing.
      if (!drew) {
        renderer.drawRect(cell.x, cell.y, cell.width, cell.height);
        GfxRenderer::ClipScope labelClip(renderer, cell.x + kCellPadding, cell.y + kCellPadding,
                                         cell.width - kCellPadding * 2, cell.height - kCellPadding * 2);
        renderer.drawText(UI_10_FONT_ID, cell.x + kCellPadding, cell.y + cell.height / 2,
                          photos_[index].c_str());
      }
    }
  }

  const auto labels = mappedInput.mapLabels(tr(STR_BACK), tr(STR_AIRPHOTO_LIST_VIEW),
                                            tr(STR_PREV_PAGE), tr(STR_NEXT_PAGE));
  GUI.drawButtonHints(renderer, labels.btn1, labels.btn2, labels.btn3, labels.btn4);
  if (present) renderer.displayBuffer(HalDisplay::HALF_REFRESH);
}

void AirPhotoActivity::drawOpenPhoto(const bool present) {
  if (panelDeferred_) {
    baseDirty_ = true;
    return;
  }
  renderer.clearScreen();

  const int screenWidth = renderer.getScreenWidth();
  const int screenHeight = renderer.getScreenHeight();

  // The view bitmap is already panel-sized and panel-formatted, so this is a
  // straight blit with no decoding.
  const std::string view = needsDerived(openIndex_) ? viewPath(openIndex_) : photoPath(openIndex_);
  HalFile file;
  bool drew = false;
  if (Storage.openFileForRead("APHO", view.c_str(), file)) {
    Bitmap bitmap(file, true);
    if (bitmap.parseHeaders() == BmpReaderError::Ok) {
      const int x = std::max(0, (screenWidth - bitmap.getWidth()) / 2);
      const int y = std::max(0, (screenHeight - bitmap.getHeight()) / 2);
      renderer.drawBitmap(bitmap, x, y, screenWidth, screenHeight);
      drew = true;
    }
  }
  if (!drew) {
    renderer.drawCenteredText(UI_10_FONT_ID, screenHeight / 2, tr(STR_INVALID_IMAGE_FILE));
  }

  const auto labels =
      mappedInput.mapLabels(tr(STR_BACK), tr(STR_SET_SLEEP_COVER), tr(STR_PREV_PAGE), tr(STR_NEXT_PAGE));
  GUI.drawButtonHints(renderer, labels.btn1, labels.btn2, labels.btn3, labels.btn4);
  if (present) renderer.displayBuffer(HalDisplay::HALF_REFRESH);
}

bool AirPhotoActivity::openPhoto(const int index) {
  if (index < 0 || index >= static_cast<int>(photos_.size())) return false;
  openIndex_ = index;
  selectedIndex_ = index;
  page_ = index / kPerPage;
  landscape_ = viewIsLandscape();
  applyOrientation();
  if (needsDerived(index)) {
    airpage::ImageInfo cached;
    const bool valid = airpage::AirPageImageStore::inspectImage(viewPath(index).c_str(), cached) &&
                       cached.format == airpage::ImageFormat::Bmp;
    if (!valid) {
      GUI.drawPopup(renderer, tr(STR_LOADING_POPUP));
      ensureDerivedAt(index, viewPath(index), renderer.getScreenWidth(), renderer.getScreenHeight());
    }
  }
  drawOpenPhoto();
  return true;
}

void AirPhotoActivity::showPhotoMenu() {
  static constexpr StrId options[] = {StrId::STR_AIRPHOTO_ROTATE, StrId::STR_SET_SLEEP_COVER,
                                      StrId::STR_DELETE, StrId::STR_CANCEL};
  photoMenuPopup_.show(StrId::STR_AIRPHOTO_TITLE, options, 4, 0, [this](const int index) {
    if (index == 0) toggleRotation();
    if (index == 1) showCoverPrompt();
    if (index == 2) confirmDeletePhoto();
  });
  requestUpdate();
}

void AirPhotoActivity::showCoverPrompt() {
  // A separate popup avoids replacing the callback currently dispatched by
  // photoMenuPopup_. Choosing a target is the affirmative cover action;
  // Cancel is the default and leaves all settings and originals untouched.
  static constexpr StrId options[] = {StrId::STR_SCREEN_BOOT, StrId::STR_SLEEP_SCREEN,
                                      StrId::STR_SCREEN_SHUTDOWN, StrId::STR_CANCEL};
  drawOpenPhoto();
  confirmationPopup_.show(StrId::STR_SET_SLEEP_COVER, options, 4, 3, [this](const int index) {
    if (index < 0 || index > 2) return;
    coverToSet_ = index == 0 ? airphoto::Cover::Startup
                : index == 1 ? airphoto::Cover::Sleep : airphoto::Cover::Shutdown;
    if (popupCallback_) {
      coverPending_ = true;
      baseDirty_ = true;
    } else {
      applyCover();
    }
  });
  requestUpdate();
}

void AirPhotoActivity::confirmDeletePhoto() {
  if (openIndex_ < 0 || openIndex_ >= static_cast<int>(photos_.size())) return;
  const char* confirmOptions[] = {tr(STR_CANCEL), tr(STR_DELETE)};
  const std::string title = std::string(tr(STR_DELETE)) + " " + photos_[openIndex_] + "?";
  drawOpenPhoto();
  confirmationPopup_.show(title.c_str(), confirmOptions, 2, 0, [this](const int index) {
    if (index == 1) deletePhoto();
  });
  requestUpdate();
}

void AirPhotoActivity::deletePhoto() {
  // The original is removed while the loop owns RenderLock; panelDeferred_
  // keeps the list/grid redraw for the render task's single final commit.
  const auto plan = airphoto::deletionPlan(photos_, openIndex_);
  if (!plan.valid) return;

  // The original is the user's data. A failed removal must leave both it and
  // every derived copy intact. Cache cleanup follows only a successful delete.
  if (!Storage.remove(plan.original.c_str())) {
    operationFailed_ = true;
    drawOpenPhoto();  // Deferred until render(); never paint stale dialog chrome.
    return;
  }
  if (plan.removeCaches) {
    if (Storage.exists(plan.view.c_str())) Storage.remove(plan.view.c_str());
    if (Storage.exists(plan.landscapeView.c_str())) Storage.remove(plan.landscapeView.c_str());
    if (Storage.exists(plan.thumb.c_str())) Storage.remove(plan.thumb.c_str());
  }
  openIndex_ = -1;
  landscape_ = false;
  applyOrientation();
  loadPhotos();
  if (view_ == ViewMode::Grid) {
    ensurePageDerived();
    drawGrid();
  } else {
    drawList();
  }
}

bool AirPhotoActivity::viewIsLandscape() const {
  if (openIndex_ < 0 || openIndex_ >= static_cast<int>(rotateOverride_.size())) return false;
  const int8_t override = rotateOverride_[openIndex_];
  if (override >= 0) return override != 0;

  // No choice made yet: turn the screen when the photo is wider than it is
  // tall. This reads the ORIGINAL's dimensions, which works for JPEG too --
  // probing the cached bitmap instead would never rotate a photo on its first
  // viewing, because the cache does not exist yet.
  if (FsHelpers::hasPngExtension(photos_[openIndex_])) {
    HalFile file;
    const std::string source = photoPath(openIndex_);
    uint8_t header[24];
    return Storage.openFileForRead("APHO", source.c_str(), file) &&
           file.read(header, sizeof(header)) == static_cast<int>(sizeof(header)) &&
           airphoto::isLandscapePng(header, sizeof(header));
  }
  airpage::ImageInfo info;
  if (!airpage::AirPageImageStore::inspectImage(photoPath(openIndex_).c_str(), info)) return false;
  return info.width > info.height;
}

void AirPhotoActivity::applyOrientation() {
  // The orientation is global, so it is set on the way into a photo and put
  // back on the way out, the same way SolitaireActivity does it.
  renderer.setOrientation(landscape_ ? GfxRenderer::Orientation::LandscapeCounterClockwise
                                     : GfxRenderer::Orientation::Portrait);
}

void AirPhotoActivity::toggleRotation() {
  if (openIndex_ < 0 || openIndex_ >= static_cast<int>(rotateOverride_.size())) return;
  landscape_ = !landscape_;
  rotateOverride_[openIndex_] = landscape_ ? 1 : 0;
  applyOrientation();

  // Each orientation keeps its own cache file, so turning the screen builds the
  // other one instead of throwing the first away.
  if (needsDerived(openIndex_)) {
    airpage::ImageInfo cached;
    const bool valid = airpage::AirPageImageStore::inspectImage(viewPath(openIndex_).c_str(), cached) &&
                       cached.format == airpage::ImageFormat::Bmp;
    if (!valid) {
      if (popupCallback_) {
        rotatePending_ = true;
      } else {
        ensureDerivedAt(openIndex_, viewPath(openIndex_), renderer.getScreenWidth(),
                        renderer.getScreenHeight());
      }
    }
  }
  drawOpenPhoto();
}

void AirPhotoActivity::applyCover() {
  if (openIndex_ < 0 || openIndex_ >= static_cast<int>(photos_.size())) return;
  if (popupCallback_) {
    coverPending_ = true;
    baseDirty_ = true;
    return;
  }

  // The original is never moved or deleted. r4's independent boot/shutdown
  // transaction and AirPage's recoverable sleep transaction run under the
  // render lock: conversion may temporarily borrow/clear the framebuffer.
  const std::string original = photoPath(openIndex_);
  bool ok = false;
  {
    GfxRenderer::FrameBufferLoan loan(renderer);
    ok = airphoto::setCover(original.c_str(), coverToSet_);
  }
  operationFailed_ = !ok;
  baseDirty_ = true;
}

void AirPhotoActivity::onExit() {
  // ActivityManager calls onExit() before Home replaces this activity. The
  // renderer orientation is global, so restore portrait even when the user
  // leaves with the Home gesture instead of AirPhoto's Back button.
  landscape_ = false;
  renderer.setOrientation(GfxRenderer::Orientation::Portrait);
  Activity::onExit();
}

void AirPhotoActivity::onEnter() {
  Activity::onEnter();
  if (openIndex_ >= 0) {
    // Coming back from the wallpaper popup: restore the turn we were using.
    applyOrientation();
    drawOpenPhoto();
    return;
  }
  landscape_ = false;
  applyOrientation();
  view_ = ViewMode::List;
  loadPhotos();
  drawList();
}

void AirPhotoActivity::render(RenderLock&&) {
  // Conversions can borrow/clear the framebuffer. Finish them under the render
  // lock, then paint one complete base before the active popup commits it.
  if (rotatePending_) {
    rotatePending_ = false;
    if (openIndex_ >= 0) {
      ensureDerivedAt(openIndex_, viewPath(openIndex_), renderer.getScreenWidth(),
                      renderer.getScreenHeight());
    }
    baseDirty_ = true;
  }
  if (coverPending_) {
    coverPending_ = false;
    applyCover();
  }
  if (baseDirty_) {
    baseDirty_ = false;
    if (openIndex_ >= 0) drawOpenPhoto(false);
    else if (view_ == ViewMode::List) drawList(false);
    else drawGrid(false);
    if (operationFailed_) {
      operationFailed_ = false;
      // A loan may have cleared the buffer, or a dismissed dialog may still
      // be on it. Show failure only over the rebuilt photo, then clear it.
      GUI.drawPopup(renderer, tr(STR_FAILED_LOWER));
      delay(1000);
      if (openIndex_ >= 0) drawOpenPhoto(false);
      else if (view_ == ViewMode::List) drawList(false);
      else drawGrid(false);
    }
    if (confirmationPopup_.isActive() || photoMenuPopup_.isActive()) {
      // OptionPopup::processRender performs the sole panel commit; let that
      // commit use HALF_REFRESH for this rebuilt base + popup frame.
      requestPopupHalfRefresh(renderer, 0);
    } else {
      renderer.displayBuffer(HalDisplay::HALF_REFRESH);
      return;
    }
  }
  if (confirmationPopup_.isActive()) confirmationPopup_.processRender(renderer, mappedInput);
  else photoMenuPopup_.processRender(renderer, mappedInput);
}

void AirPhotoActivity::loop() {
  Activity::loop();
  // Wait for the previous popup frame, not only its published hit table, before
  // changing its state or sharing the framebuffer with the render task.
  if (renderIsBusy<RenderLock>(0)) return;
  [[maybe_unused]] RenderLock lock;

  if (confirmationPopup_.isActive()) {
    panelDeferred_ = popupCallback_ = true;
    if (confirmationPopup_.handleInput(mappedInput, [this] { requestUpdate(); })) {
      if (!confirmationPopup_.isActive()) {
        if (openIndex_ >= 0) {
          drawOpenPhoto();
        } else if (view_ == ViewMode::List) {
          drawList();
        } else {
          drawGrid();
        }
        requestUpdate();
      }
      panelDeferred_ = popupCallback_ = false;
      return;
    }
    panelDeferred_ = popupCallback_ = false;
  }

  if (photoMenuPopup_.isActive()) {
    panelDeferred_ = popupCallback_ = true;
    if (photoMenuPopup_.handleInput(mappedInput, [this] { requestUpdate(); })) {
      if (!photoMenuPopup_.isActive()) {
        if (openIndex_ >= 0) {
          drawOpenPhoto();
        } else if (view_ == ViewMode::List) {
          drawList();
        } else {
          drawGrid();
        }
        requestUpdate();
      }
      panelDeferred_ = popupCallback_ = false;
      return;
    }
    panelDeferred_ = popupCallback_ = false;
  }

  if (openIndex_ >= 0) {
    int longPressX = 0;
    int longPressY = 0;
    if (mappedInput.wasScreenLongPress(longPressX, longPressY)) {
      showPhotoMenu();
      return;
    }

    if (mappedInput.wasReleased(MappedInputManager::Button::Back)) {
      openIndex_ = -1;
      // Browser views are always upright; return to the mode that opened it.
      landscape_ = false;
      applyOrientation();
      if (view_ == ViewMode::List) {
        drawList();
      } else {
        drawGrid();
      }
      return;
    }

    const auto swipe = mappedInput.wasSwipe();
    if (swipe == MappedInputManager::SwipeDir::Left ||
        mappedInput.wasReleased(MappedInputManager::Button::NavNext)) {
      openPhoto(openIndex_ + 1);
      return;
    }
    if (swipe == MappedInputManager::SwipeDir::Right ||
        mappedInput.wasReleased(MappedInputManager::Button::NavPrevious)) {
      openPhoto(openIndex_ - 1);
      return;
    }
    if (mappedInput.wasReleased(MappedInputManager::Button::Confirm)) {
      showPhotoMenu();
      return;
    }
    return;
  }

  if (mappedInput.wasReleased(MappedInputManager::Button::Back)) {
    // Leaving with the screen still turned would rotate the Apps menu.
    landscape_ = false;
    applyOrientation();
    activityManager.goToApps();
    return;
  }

  if (mappedInput.hasTouch()) {
    const Rect toggle = viewToggleRect();
    if (mappedInput.wasTapInRect(toggle.x, toggle.y, toggle.width, toggle.height)) {
      view_ = view_ == ViewMode::List ? ViewMode::Grid : ViewMode::List;
      if (view_ == ViewMode::Grid) {
        ensurePageDerived();
        drawGrid();
      } else {
        drawList();
      }
      return;
    }
  }

  if (view_ == ViewMode::List) {
    // ActivityManager consumes the release suppressed by wasLongPressed(), so
    // this Confirm gesture cannot also toggle the new grid back to the list.
    if (mappedInput.wasLongPressed(MappedInputManager::Button::Confirm, 650)) {
      view_ = ViewMode::Grid;
      ensurePageDerived();
      drawGrid();
      return;
    }
    if (mappedInput.hasTouch()) {
      const int slot = tappedListSlot();
      if (slot >= 0) {
        openPhoto(page_ * kPerPage + slot);
        return;
      }
    }
    if (mappedInput.wasReleased(MappedInputManager::Button::Confirm)) {
      openPhoto(selectedIndex_);
      return;
    }
    if (mappedInput.wasReleased(MappedInputManager::Button::Down) ||
        mappedInput.wasReleased(MappedInputManager::Button::Up)) {
      const int step = mappedInput.wasReleased(MappedInputManager::Button::Down) ? 1 : -1;
      const int next = selectedIndex_ + step;
      if (selectedIndex_ >= 0 && next >= 0 && next < static_cast<int>(photos_.size())) {
        selectedIndex_ = next;
        page_ = next / kPerPage;
        drawList();
      }
      return;
    }
    const auto swipe = mappedInput.wasSwipe();
    if (swipe == MappedInputManager::SwipeDir::Left ||
        mappedInput.wasReleased(MappedInputManager::Button::Right)) {
      if (page_ + 1 < pageCount()) {
        ++page_;
        selectedIndex_ = page_ * kPerPage;
        drawList();
      }
      return;
    }
    if (swipe == MappedInputManager::SwipeDir::Right ||
        mappedInput.wasReleased(MappedInputManager::Button::Left)) {
      if (page_ > 0) {
        --page_;
        selectedIndex_ = page_ * kPerPage;
        drawList();
      }
      return;
    }
    return;
  }

  if (mappedInput.wasReleased(MappedInputManager::Button::Confirm)) {
    view_ = ViewMode::List;
    drawList();
    return;
  }

  if (mappedInput.hasTouch()) {
    const int slot = tappedSlot();
    if (slot >= 0) {
      openPhoto(page_ * kPerPage + slot);
      return;
    }
  }

  const auto swipe = mappedInput.wasSwipe();
  if (swipe == MappedInputManager::SwipeDir::Left ||
      mappedInput.wasReleased(MappedInputManager::Button::Right) ||
      mappedInput.wasReleased(MappedInputManager::Button::Down)) {
    if (page_ + 1 < pageCount()) {
      page_++;
      selectedIndex_ = page_ * kPerPage;
      ensurePageDerived();
      drawGrid();
    }
    return;
  }
  if (swipe == MappedInputManager::SwipeDir::Right ||
      mappedInput.wasReleased(MappedInputManager::Button::Left) ||
      mappedInput.wasReleased(MappedInputManager::Button::Up)) {
    if (page_ > 0) {
      page_--;
      selectedIndex_ = page_ * kPerPage;
      ensurePageDerived();
      drawGrid();
    }
    return;
  }
}
