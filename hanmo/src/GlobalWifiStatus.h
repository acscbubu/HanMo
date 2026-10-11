#pragma once
#include <GfxRenderer.h>
#include <WiFi.h>

#include "CrossPointSettings.h"
#include "WifiStatusLayout.h"
namespace GlobalWifiStatus {

inline bool connected() { return WiFi.status() == WL_CONNECTED; }
inline bool visible() {
#if FREEINK_DEVICE_X4PRO || defined(SIMULATOR)
  return SETTINGS.wifiStatusPosition < 3;
#else
  return false;
#endif
}
inline void place(const GfxRenderer& r, int left, int right, int top, int bandHeight, int occupiedLeft,
                  int occupiedRight) {
  const auto box = WifiStatusLayout::place(left, right, top, bandHeight, visible() ? SETTINGS.wifiStatusPosition : 3,
                                           occupiedLeft, occupiedRight);
  r.setSystemStatusRect(box.x, box.y, box.width, box.height);
}
inline void draw(const GfxRenderer& r) {
  const auto box = r.getSystemStatusRect();
  if (!visible() || box.width == 0) return;
  const int x = box.x, y = box.y;
  const GfxRenderer::ClipScope iconClip(r,x,y,box.width,box.height);
  r.fillRect(x, y, box.width, box.height, false);
  // Raster Wi-Fi arcs, deliberately independent of font/glyph availability.
  const int cx = x + 9, cy = y + 16;
  for (int dy = -13; dy <= 0; dy++)
    for (int dx = -13; dx <= 13; dx++) {
      const int d = dx * dx + dy * dy;
      if (dy <= -abs(dx) && ((d >= 132 && d <= 169) || (d >= 56 && d <= 81) || (d >= 12 && d <= 25)))
        r.drawPixel(cx + dx, cy + dy);
    }
  r.fillRect(cx - 1, cy - 1, 3, 3, true);
  if (!connected()) {
    r.drawLine(x, y + 1, x + 17, y + 17, 4, false);
    r.drawLine(x, y + 1, x + 17, y + 17, 2, true);
  }
}
}  // namespace GlobalWifiStatus
