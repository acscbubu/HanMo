#pragma once
#include <array>

#include "ChangeHistoryData.h"
#include "activities/UiListActivity.h"

// Fixed row storage; text stays in translated Flash strings. A detail page
// reuses the same list host for touch swipes, button navigation and wrapping.
class ChangeHistoryActivity final : public UiListActivity {
 public:
  ChangeHistoryActivity(GfxRenderer& renderer, MappedInputManager& input, int entry = -1);
  void onEnter() override;

 private:
  int listCount() const override;
  const char* headerTitle() const override;
  void buildScreen(UiScreen& screen) override;
  void activateIndex(int index) override;
  void drawFooter() override;
  const int entry_;
  std::array<freeink::ui::ListItem, ChangeHistory::COUNT> rows_{};
};
