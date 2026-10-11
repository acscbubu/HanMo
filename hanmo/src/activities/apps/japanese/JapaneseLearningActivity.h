#pragma once

#include <array>
#include "activities/UiListActivity.h"

// A category folder, not a claim that lesson content has shipped.
class JapaneseLearningActivity final : public UiListActivity {
 public:
  JapaneseLearningActivity(GfxRenderer& renderer, MappedInputManager& input, int category = -1);
  void onEnter() override;

 private:
  static constexpr int CATEGORY_COUNT = 7;
  int category_;
  // Fixed rows: one touch Back entry plus seven categories; no per-row heap.
  std::array<freeink::ui::ListItem, CATEGORY_COUNT + 1> rows_{};
  // ListItem::label is a const char*, so the composed back text needs
  // storage that outlives onEnter(). "« 返回" is 9 bytes and the longest
  // destination 日文學習 is 12.
  std::array<char, 48> backLabel_{};
  int listCount() const override { return category_ < 0 ? CATEGORY_COUNT + 1 : 3; }
  const char* headerTitle() const override;
  void buildScreen(UiScreen& screen) override;
  void activateIndex(int index) override;
  void onBackButton() override;
};
