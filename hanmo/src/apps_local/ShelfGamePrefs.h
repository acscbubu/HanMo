#pragma once

// Games-only preferences. Registry indices exist only in RAM: the card stores
// titles so a removed/inserted game cannot transfer its favorite or position.
// No heap allocation for the live ordering (64 indices + 64 flags).
#include <cstddef>
#include <cstdint>
#include <string>

namespace shelf {

class GamePrefs {
 public:
  static constexpr int kMaxGames = 64;
  static constexpr size_t kMaxFileBytes = 4096;

  GamePrefs(const char* const* titles, int count);
  bool isFavorite(int item) const;
  bool setFavorite(int item, bool on);
  // Moves within the favorite/nonfavorite group; cannot put nonfavorites ahead
  // of favorites. Return false for no-op/invalid index.
  bool moveUp(int item);
  bool moveDown(int item);
  bool moveToTop(int item);
  // Place a held game relative to its visible neighbor. Hidden games remain
  // installed in order_, but must not consume a touch "MOVE UP/DOWN" step.
  bool moveAheadOf(int item, int neighbor);
  bool moveBehind(int item, int neighbor);

  template <typename IsHidden>
  int count(bool favoritesOnly, IsHidden hidden) const {
    int result = 0;
    for (int group = 0; group < (favoritesOnly ? 1 : 2); ++group)
      for (int pos = 0; pos < count_; ++pos) {
        const int item = order_[pos];
        if (favorites_[item] == (group == 0) && !hidden(item)) ++result;
      }
    return result;
  }

  template <typename IsHidden>
  int itemAt(int row, bool favoritesOnly, IsHidden hidden) const {
    if (row < 0) return -1;
    for (int group = 0; group < (favoritesOnly ? 1 : 2); ++group)
      for (int pos = 0; pos < count_; ++pos) {
        const int item = order_[pos];
        if (favorites_[item] != (group == 0) || hidden(item)) continue;
        if (row-- == 0) return item;
      }
    return -1;
  }

  // For an excluded item returns the count of rows before it in visual order,
  // possibly the end. Caller clamps to last row for a shrinking/empty list.
  template <typename IsHidden>
  int rowFor(int item, bool favoritesOnly, IsHidden hidden) const {
    if (item < 0 || item >= count_) return 0;
    int row = 0;
    for (int group = 0; group < (favoritesOnly ? 1 : 2); ++group)
      for (int pos = 0; pos < count_; ++pos) {
        const int current = order_[pos];
        if (favorites_[current] != (group == 0)) continue;
        if (current == item) return row;
        if (!hidden(current)) ++row;
      }
    return row;
  }

  // Version, title rows and FNV checksum/terminator. No partial mutation on a
  // bad/truncated file. Unknown titles are ignored; new games append in registry
  // order. Writes omit unknown titles (retired sources and saves are untouched).
  bool parse(const char* text, size_t size);
  std::string format() const;

 private:
  int position(int item) const;
  bool valid(int item) const { return item >= 0 && item < count_; }
  const char* const* titles_;
  int count_;
  uint8_t order_[kMaxGames] = {};
  bool favorites_[kMaxGames] = {};
};

}  // namespace shelf
