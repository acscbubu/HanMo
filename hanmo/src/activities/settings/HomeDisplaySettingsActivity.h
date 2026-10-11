#pragma once
#include <array>
#include "activities/UiListActivity.h"
#include "components/OptionPopup.h"
class HomeDisplaySettingsActivity final : public UiListActivity {
 public:
  HomeDisplaySettingsActivity(GfxRenderer& renderer, MappedInputManager& input, bool textPage = false);
  void onEnter() override;
  void render(RenderLock&& lock) override;
 private:
  bool textPage_;
  std::array<freeink::ui::ListItem, 6> rows_{};
  OptionPopup popup_;
  bool saveFailed_ = false;
  int listCount() const override { return textPage_ ? 4 : 6; }
  const char* headerTitle() const override;
  void buildScreen(UiScreen& screen) override;
  void activateIndex(int index) override;
  bool handleCustomInput() override;
  void refreshRows();
  void notice(StrId message);
};
