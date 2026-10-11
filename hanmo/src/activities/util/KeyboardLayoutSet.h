#pragma once

#include <FreeInkUI.h>
#include <I18n.h>

#include <cstdint>

namespace keyboard_layouts {

struct LayoutInfo {
  freeink::ui::KeyboardLayoutId id;
  // The layout's own name, not a UI language name.
  const char* label;
};

// This build ships QWERTY and nothing else. Upstream carried eight more --
// AZERTY, QWERTZ, Spanish, four Cyrillic and Hebrew -- and none of them is
// reachable from a device whose UI is English or Chinese: the shipped
// languages all type Latin, and the layout key only appears when more than
// one layout is enabled, so the others were a settings screen and ~40
// kilobytes of key tables nobody could get to.
//
// Table position is still the persisted bit assignment. Appending a layout
// later is safe; inserting one ahead of QWERTY would reinterpret every saved
// mask.
inline constexpr LayoutInfo ALL[] = {
    {freeink::ui::KeyboardLayoutId::QwertyEn, "QWERTY"},
};
inline constexpr uint8_t COUNT = sizeof(ALL) / sizeof(ALL[0]);
static_assert(COUNT <= 16, "keyboard layout mask is uint16_t");

inline constexpr uint16_t bitAt(const uint8_t i) { return static_cast<uint16_t>(1u << i); }
// Symbol layers have no Latin letters, so credentials and URLs require at
// least one Latin layout to remain enabled. With one layout that is bit 0,
// and enabled() can never return a mask without it.
inline constexpr uint16_t LATIN_BITS = bitAt(0);

uint16_t enabled();
freeink::ui::KeyboardLayoutId startingLayout();
freeink::ui::KeyboardLayoutId next(freeink::ui::KeyboardLayoutId current);

}  // namespace keyboard_layouts
