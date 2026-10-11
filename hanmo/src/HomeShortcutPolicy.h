#pragma once
#include <array>
#include <cstdint>
namespace HomeShortcutPolicy {
enum Action : uint8_t { Default, Files, Recent, Opds, Apps, Transfer, Settings, AirNote, AirPage, Hidden, Retired, RetiredPrivate, ReadingStats, Calculator, Standby, Games, WeRead, InfoBoard, Count };
constexpr int SLOTS = 6;
constexpr bool isRetired(uint8_t action) { return action == Retired || action == RetiredPrivate; }
constexpr int SELECTABLE_COUNT = Count - 2;
// Persisted IDs never move. Old private entries resolve to Hidden.
constexpr int selectionIndex(uint8_t action) {
  if (action >= Count) return Default;
  if (isRetired(action)) return Hidden;
  int index = 0;
  for (int i = 0; i < action; ++i) if (!isRetired(i)) ++index;
  return index;
}
constexpr uint8_t storedAction(int index) {
  if (index < 0 || index >= SELECTABLE_COUNT) return Default;
  for (int action = 0; action < Count; ++action) {
    if (isRetired(action)) continue;
    if (index-- == 0) return action;
  }
  return Default;
}
struct Menu { std::array<uint8_t, SLOTS> items{}; int count = 0; };
constexpr Menu resolve(const std::array<uint8_t, SLOTS>& choices, bool hasOpds, bool carousel, bool readsChinese = true) {
  constexpr uint8_t normal[] = {Files, Recent, Opds, Transfer, Settings, Apps};
  constexpr uint8_t cover[] = {Files, Recent, Opds, Apps, Transfer, Settings};
  Menu menu;
  for (int i = 0; i < SLOTS; ++i) {
    uint8_t action = choices[i];
    if (action == Default || action >= Count) action = carousel ? cover[i] : normal[i];
    if (action == Hidden || isRetired(action) || (action == WeRead && !readsChinese) || (action == Opds && !hasOpds)) continue;
    menu.items[menu.count++] = action;
  }
  // Keep a reachable settings entry and nonzero hit-test divisor if all are hidden.
  if (!menu.count) menu.items[menu.count++] = Settings;
  return menu;
}
}  // namespace HomeShortcutPolicy
