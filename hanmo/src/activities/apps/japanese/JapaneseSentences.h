#pragma once

#include "JapaneseSentences.generated.h"  // Retain the original six-card include contract.
#include <array>
#include <cstdint>

namespace japanese {
// Pure category-local navigation. Read progress belongs to the separate store.
class Sentences {
 public:
  static constexpr int categoryCount() { return 9; }
  static constexpr int categorySize(int category) {
    return category >= 0 && category < categoryCount() ? kCategoryCounts[category] : 0;
  }
  static constexpr int categoryFirst(int category) {
    return category >= 0 && category < categoryCount() ? kCategoryFirsts[category] : -1;
  }
  int count() const { return categorySize(category_); }
  int category() const { return category_; }
  int position() const { return position_; }
  int globalPosition() const { return categoryFirst(category_) + position(); }
  bool revealed() const { return revealed_; }
  bool canPrevious() const { return position_ > 0; }
  bool canNext() const { return position_ + 1 < count(); }
  bool selectCategory(int category, int localPosition = 0) {
    if (category < 0 || category >= categoryCount() || localPosition < 0 || localPosition >= categorySize(category)) return false;
    category_ = category;
    position_ = localPosition;
    revealed_ = false;
    return true;
  }
  bool restore(int position) {
    if (position < 0 || position >= count()) return false;
    position_ = position;
    revealed_ = false;
    return true;
  }
  bool previous() {
    if (!canPrevious()) return false;
    --position_;
    revealed_ = false;
    return true;
  }
  bool next() {
    if (!canNext()) return false;
    ++position_;
    revealed_ = false;
    return true;
  }
  void toggleReveal() { revealed_ = !revealed_; }
  void restart() {
    position_ = 0;
    revealed_ = false;
  }

 private:
  inline static constexpr std::array<uint8_t, 9> kCategoryCounts{30, 30, 30, 30, 30, 30, 30, 30, 30};
  inline static constexpr std::array<uint16_t, 9> kCategoryFirsts{0, 30, 60, 90, 120, 150, 180, 210, 240};
  int category_ = 0;
  int position_ = 0;
  bool revealed_ = false;
};
}  // namespace japanese
