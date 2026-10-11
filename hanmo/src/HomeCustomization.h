#pragma once
#include <I18n.h>
#include "CrossPointSettings.h"
#include "HomeShortcutPolicy.h"
#include "FirmwareIdentity.h"
namespace HomeCustomization {
using Field = uint8_t CrossPointSettings::*;
inline constexpr Field slots[] = {&CrossPointSettings::homeShortcut1, &CrossPointSettings::homeShortcut2,
    &CrossPointSettings::homeShortcut3, &CrossPointSettings::homeShortcut4,
    &CrossPointSettings::homeShortcut5, &CrossPointSettings::homeShortcut6};
inline constexpr StrId labels[] = {StrId::STR_HOME_SHORTCUT_1, StrId::STR_HOME_SHORTCUT_2,
    StrId::STR_HOME_SHORTCUT_3, StrId::STR_HOME_SHORTCUT_4, StrId::STR_HOME_SHORTCUT_5, StrId::STR_HOME_SHORTCUT_6};
inline constexpr StrId options[] = {StrId::STR_HOME_THEME_DEFAULT, StrId::STR_BROWSE_FILES,
    StrId::STR_MENU_RECENT_BOOKS, StrId::STR_OPDS_BROWSER, StrId::STR_APPS_TITLE, StrId::STR_FILE_TRANSFER,
    StrId::STR_SETTINGS_TITLE, StrId::STR_AIRNOTE_TITLE, StrId::STR_AIRPAGE_TITLE, StrId::STR_HIDE,
    StrId::STR_NOT_AVAILABLE, StrId::STR_NOT_AVAILABLE, StrId::STR_READING_STATS, StrId::STR_CALCULATOR_TITLE,
    StrId::STR_STANDBY_TITLE, StrId::STR_SHELF_GAMES, StrId::STR_WEREAD_TITLE, StrId::STR_INFO_BOARD};
inline constexpr std::array<StrId, HomeShortcutPolicy::SELECTABLE_COUNT> selectableOptions = [] {
  std::array<StrId, HomeShortcutPolicy::SELECTABLE_COUNT> result{};
  for (int action = 0, index = 0; action < HomeShortcutPolicy::Count; ++action) {
    if (!HomeShortcutPolicy::isRetired(action)) result[index++] = options[action];
  }
  return result;
}();
inline constexpr Field positions[] = {&CrossPointSettings::homeLabelPos, &CrossPointSettings::homeBatteryPos,
                                     &CrossPointSettings::homeClockPos};
inline constexpr StrId positionLabels[] = {StrId::STR_HOME_LABEL_POS, StrId::STR_HOME_BATTERY_POS, StrId::STR_HOME_CLOCK_POS};
inline constexpr StrId positionOptions[] = {StrId::STR_DIR_RIGHT, StrId::STR_DIR_LEFT, StrId::STR_CENTER, StrId::STR_HIDE};
inline bool owns(Field f) {
  for (auto field : slots) if (field == f) return true;
  for (auto field : positions) if (field == f) return true;
  return false;
}
inline HomeShortcutPolicy::Menu menu(bool hasOpds, bool carousel) {
  std::array<uint8_t, HomeShortcutPolicy::SLOTS> values{};
  for (int i = 0; i < HomeShortcutPolicy::SLOTS; ++i) values[i] = SETTINGS.*slots[i];
  return HomeShortcutPolicy::resolve(values, hasOpds, carousel, SETTINGS.readsChinese());
}
// Bounded UTF-8 text, preserving the existing saved field and empty-label behavior.
inline bool validLabel(std::string_view text) {
  return text.size() < sizeof(SETTINGS.homeLabel) && FirmwareIdentity::isValid(text);
}
inline bool assignLabel(std::string_view text) {
  if (!validLabel(text)) return false;
  if (!text.empty()) memcpy(SETTINGS.homeLabel, text.data(), text.size());
  SETTINGS.homeLabel[text.size()] = '\0';
  return true;
}
static_assert(sizeof(options) / sizeof(options[0]) == HomeShortcutPolicy::Count);
}  // namespace HomeCustomization
