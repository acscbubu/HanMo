#include "ScreenImage.h"

#include <Bitmap.h>
#include <GfxRenderer.h>
#include <HalDisplay.h>
#include <HalStorage.h>
#include <I18n.h>

#include "ScreenSettingsPolicy.h"
#include "components/UITheme.h"
#include "fontIds.h"
#include "images/Logo120.h"
namespace ScreenImage {
bool valid(const char* path) {
  if (!ScreenSettingsPolicy::validPath(path)) return false;
  HalFile file;
  if (!Storage.openFileForRead("ScreenImage", path, file)) return false;
  Bitmap bitmap(file, true);
  return bitmap.parseHeaders() == BmpReaderError::Ok && bitmap.getWidth() > 0 && bitmap.getHeight() > 0 &&
         ScreenSettingsPolicy::bitmapFits(file.position(), bitmap.getRowBytes(), bitmap.getHeight(), file.fileSize64());
}
bool draw(GfxRenderer& renderer, const char* path) {
  if (!ScreenSettingsPolicy::validPath(path)) return false;
  HalFile file;
  if (!Storage.openFileForRead("ScreenImage", path, file)) return false;
  Bitmap bitmap(file, true);
  if (bitmap.parseHeaders() != BmpReaderError::Ok || bitmap.getWidth() <= 0 || bitmap.getHeight() <= 0) return false;
  if (!ScreenSettingsPolicy::bitmapFits(file.position(), bitmap.getRowBytes(), bitmap.getHeight(), file.fileSize64()))
    return false;
  renderer.setRenderMode(GfxRenderer::BW);
  renderer.clearScreen();
  // Existing bounded row-buffer renderer; no full decoded image allocation.
  if (!renderer.drawBitmapCropToFill(bitmap, 0, 0, renderer.getScreenWidth(), renderer.getScreenHeight())) return false;
  renderer.displayBuffer(HalDisplay::HALF_REFRESH);
  return true;
}
void shutdownDefault(GfxRenderer& renderer) {
  renderer.clearScreen();
  renderer.drawImage(Logo120, (renderer.getScreenWidth() - 120) / 2, (renderer.getScreenHeight() - 120) / 2, 120, 120);
  renderer.drawCenteredText(UI_10_FONT_ID, renderer.getScreenHeight() / 2 + 80, tr(STR_SCREEN_POWERED_OFF));
  renderer.displayBuffer(HalDisplay::HALF_REFRESH);
}
}  // namespace ScreenImage
