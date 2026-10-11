#pragma once

#include <array>
#include <cstddef>

#include "components/themes/BaseTheme.h"

// Leading glyphs for the four Settings categories.
//
// Only the accordion layout (themes with main tabs) draws them: there a
// category is a row in the same list as the settings nested under it, so the
// icon is what tells the two apart. The tabbed layout the other themes use
// puts the categories in the tab bar, which has no icon slot.
//
// Kept out of SettingsActivity so the mapping stays host-testable on its own:
// the activity itself needs the whole firmware (storage, renderer, i18n) to
// construct.
namespace SettingsCategoryIcons {
// Mirrors SettingsActivity::categoryCount, which static_asserts this.
inline constexpr int count = 4;

// Indexed by category: Display, Reader, Controls, System. An out-of-range ask
// draws nothing rather than reading past the table.
constexpr UIIcon at(const int category) {
  constexpr std::array<UIIcon, count> icons = {UIIcon::Monitor, UIIcon::Book, UIIcon::Sliders, UIIcon::Cpu};
  return category < 0 || category >= count ? UIIcon::None : icons[static_cast<std::size_t>(category)];
}
}  // namespace SettingsCategoryIcons
