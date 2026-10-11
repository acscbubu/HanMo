#pragma once
#include <cstdint>

// Stable saved action IDs; do not reorder when changing the picker labels.
namespace ScreenShortcutPolicy {
enum PanelAction : uint8_t { Night, Refresh, Orientation, Touch, Light, AirNote, Settings, Disabled,
                             // Appended AFTER Disabled on purpose: the saved setting IS this index,
                             // so the eight values above must never move. The picker shows
                             // PICKER_ORDER rather than this declaration order, which keeps
                             // "disabled" at the bottom of the list where it has always been.
                             JapaneseLearning, Apps, AirPhoto, Calculator, FileTransfer, Opds,
                             Games, Standby, ActionCount };
// The two rows that have always been there, each still freely configurable.
constexpr int SLOT_COUNT = 6;
// Six more tiles the user can switch on one at a time. They stay Disabled
// until something is picked, and a Disabled optional slot is skipped instead of
// leaving a dead tile, so an untouched device shows exactly the same two rows.
constexpr int EXTRA_SLOT_COUNT = 6;
constexpr int PANEL_SLOT_COUNT = SLOT_COUNT + EXTRA_SLOT_COUNT;
constexpr int COLUMNS = 3;
constexpr uint8_t DEFAULTS[SLOT_COUNT] = {Night, Refresh, Orientation, Touch, Light, AirNote};
constexpr uint8_t PICKER_ORDER[ActionCount] = {Night, Refresh, Orientation, Touch, Light, AirNote,
    Settings, JapaneseLearning, Apps, AirPhoto, Calculator, FileTransfer, Opds, Games, Standby,
    Disabled};
constexpr uint8_t validAction(uint8_t action) { return action < ActionCount ? action : Disabled; }

// Keep the original corner footprints. Middle targets have the same size,
// separated by unused edge space that remains available for page turning.
// Result order: left top/middle/bottom, right top/middle/bottom.
constexpr int tapSlot(int width, int height, int x, int y) {
  if (width < 6 || height < 6 || x < 0 || y < 0 || x >= width || y >= height) return -1;
  const int w = width / 6, h = height / 6;
  const int side = x < w ? 0 : x >= width - w ? 3 : -1;
  if (side < 0) return -1;
  if (y < h) return side;
  if (y >= height - h) return side + 2;
  const int middle = (height - h) / 2;
  return y >= middle && y < middle + h ? side + 1 : -1;
}
}  // namespace ScreenShortcutPolicy
