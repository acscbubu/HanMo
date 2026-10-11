#pragma once

#include <array>

#include "activities/UiListActivity.h"
#include "components/OptionPopup.h"

// Device-side grouping only: SettingsList still owns the persisted/web keys.
class InfoBoardSettingsActivity final : public UiListActivity {
 public:
  InfoBoardSettingsActivity(GfxRenderer& renderer, MappedInputManager& input)
      : UiListActivity("InfoBoardSettings", renderer, input) {}

  void onEnter() override;
  void render(RenderLock&& lock) override;

 private:
  static constexpr int ROW_COUNT = 5;
  std::array<freeink::ui::ListItem, ROW_COUNT> rows_{};
  OptionPopup popup_;
  bool saveFailed_ = false;

  int listCount() const override { return ROW_COUNT; }
  const char* headerTitle() const override;
  void buildScreen(UiScreen& screen) override;
  void activateIndex(int index) override;
  bool handleCustomInput() override;
  void refreshRows();
  void notice(StrId message);
};
