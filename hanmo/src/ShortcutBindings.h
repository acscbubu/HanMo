#pragma once
#include <I18n.h>
#include "CrossPointSettings.h"

namespace ShortcutBindings {
using Field = uint8_t CrossPointSettings::*;
inline constexpr Field panel[] = {&CrossPointSettings::quickPanel1, &CrossPointSettings::quickPanel2,
    &CrossPointSettings::quickPanel3, &CrossPointSettings::quickPanel4,
    &CrossPointSettings::quickPanel5, &CrossPointSettings::quickPanel6,
    &CrossPointSettings::quickPanel7, &CrossPointSettings::quickPanel8,
    &CrossPointSettings::quickPanel9, &CrossPointSettings::quickPanel10,
    &CrossPointSettings::quickPanel11, &CrossPointSettings::quickPanel12};
inline constexpr Field taps[] = {&CrossPointSettings::cornerTapTopLeft, &CrossPointSettings::cornerTapMiddleLeft,
    &CrossPointSettings::cornerTapBottomLeft, &CrossPointSettings::cornerTapTopRight,
    &CrossPointSettings::cornerTapMiddleRight, &CrossPointSettings::cornerTapBottomRight};
inline constexpr StrId panelLabels[] = {StrId::STR_QUICK_SLOT_1, StrId::STR_QUICK_SLOT_2,
    StrId::STR_QUICK_SLOT_3, StrId::STR_QUICK_SLOT_4, StrId::STR_QUICK_SLOT_5, StrId::STR_QUICK_SLOT_6,
    StrId::STR_QUICK_SLOT_7, StrId::STR_QUICK_SLOT_8, StrId::STR_QUICK_SLOT_9,
    StrId::STR_QUICK_SLOT_10, StrId::STR_QUICK_SLOT_11, StrId::STR_QUICK_SLOT_12};
inline constexpr StrId tapLabels[] = {StrId::STR_CORNER_TAP_TL, StrId::STR_CORNER_TAP_ML,
    StrId::STR_CORNER_TAP_BL, StrId::STR_CORNER_TAP_TR, StrId::STR_CORNER_TAP_MR, StrId::STR_CORNER_TAP_BR};
// Indexed by the saved action id, so these stay in PanelAction order. Every
// label is one the device already ships, which is why no new wording (and no
// new CJK glyph coverage) is needed for the apps added here.
inline constexpr StrId panelOptions[] = {StrId::STR_NIGHT_MODE, StrId::STR_FORCE_REFRESH, StrId::STR_ORIENTATION,
    StrId::STR_TOUCH_TOGGLE, StrId::STR_FRONTLIGHT, StrId::STR_AIRNOTE_TITLE, StrId::STR_SETTINGS_TITLE,
    StrId::STR_DISABLED, StrId::STR_JP_LEARNING, StrId::STR_APPS_TITLE, StrId::STR_AIRPHOTO_TITLE,
    StrId::STR_CALCULATOR_TITLE, StrId::STR_FILE_TRANSFER, StrId::STR_OPDS_BROWSER, StrId::STR_SHELF_GAMES,
    StrId::STR_STANDBY_TITLE};
inline constexpr StrId tapOptions[] = {StrId::STR_DISABLED, StrId::STR_BOOKMARK_OPTION,
    StrId::STR_READER_MENU, StrId::STR_DICTIONARY};
// Tiles the pull-down panel shows, in display order: the six original slots
// always (a Disabled one keeps its place, as it always has), then each optional
// slot the user has actually bound. Returns the count and fills outSlots with
// slot indices, so a tile can still dispatch through its own slot.
inline int visibleTiles(const CrossPointSettings& settings, uint8_t* outSlots) {
  int count = 0;
  for (int i = 0; i < ScreenShortcutPolicy::SLOT_COUNT; ++i) outSlots[count++] = static_cast<uint8_t>(i);
  for (int i = ScreenShortcutPolicy::SLOT_COUNT; i < ScreenShortcutPolicy::PANEL_SLOT_COUNT; ++i) {
    if (ScreenShortcutPolicy::validAction(settings.*panel[i]) != ScreenShortcutPolicy::Disabled) {
      outSlots[count++] = static_cast<uint8_t>(i);
    }
  }
  return count;
}
inline bool owns(Field field) {
  for (auto f : panel) if (field == f) return true;
  for (auto f : taps) if (field == f) return true;
  return false;
}
static_assert(sizeof(panelOptions) / sizeof(panelOptions[0]) == ScreenShortcutPolicy::ActionCount);
}  // namespace ShortcutBindings
