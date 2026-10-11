#pragma once

#include <I18nKeys.h>

#include <cstddef>
#include <cstring>

namespace webui {

// A browser's explicit choice only selects a page; it never changes the device UI.
// An absent, empty, or unsupported choice falls back to the device language.
enum class PageLanguage { EN, ZH_CN, ZH_HANT };

inline PageLanguage pageLanguage(const Language deviceLanguage, const char* selection) {
  if (selection) {
    if (std::strcmp(selection, "en") == 0) return PageLanguage::EN;
    if (std::strcmp(selection, "zh-CN") == 0) return PageLanguage::ZH_CN;
    if (std::strcmp(selection, "zh-Hant") == 0) return PageLanguage::ZH_HANT;
  }
  if (deviceLanguage == Language::ZH_CN) return PageLanguage::ZH_CN;
  if (deviceLanguage == Language::ZH_TW) return PageLanguage::ZH_HANT;
  return PageLanguage::EN;
}

// A GET /api/settings?ui=... chooses only the response language. Never call
// I18N.setLanguage here: it changes the device UI for every browser.
inline Language settingsLanguage(const Language deviceLanguage, const char* selection) {
  if (!selection) return deviceLanguage;
  if (std::strcmp(selection, "en") == 0) return Language::EN;
  if (std::strcmp(selection, "zh-CN") == 0) return Language::ZH_CN;
  if (std::strcmp(selection, "zh-Hant") == 0) return Language::ZH_TW;
  return deviceLanguage;
}

// Read the same compact generated translation tables as I18n::get(), but for
// this response's language rather than mutating the singleton's device language.
inline const char* settingsText(const StrId id, const Language language) {
  const auto index = static_cast<size_t>(id);
  if (index >= static_cast<size_t>(StrId::_COUNT)) return "???";
  const LangStrings strings = getLanguageStrings(language);
  const uint16_t offset = strings.offsets[index];
  return offset & 0x8000u ? i18n_strings::STRINGS_EN_DATA + (offset & 0x7fffu) : strings.data + offset;
}

// Dynamic SD-card names stay untouched; built-in options are translated for
// this request even when a device-language label was copied into the list.
inline const char* settingsDynamicOption(const char* key, const size_t index, const char* value,
                                         const Language language) {
  if (!key) return value;
  if (std::strcmp(key, "dictionaryName") == 0 && index == 0) {
    return settingsText(StrId::STR_NONE_OPT, language);
  }
  if (std::strcmp(key, "fontFamily") == 0) {
#ifdef ENABLE_CHINESE_VERSION
    if (index == 0) return settingsText(StrId::STR_NOTO_SANS, language);
#else
    if (index == 0) return settingsText(StrId::STR_NOTO_SERIF, language);
    if (index == 1) return settingsText(StrId::STR_NOTO_SANS, language);
#endif
  }
  return value;
}

}  // namespace webui
