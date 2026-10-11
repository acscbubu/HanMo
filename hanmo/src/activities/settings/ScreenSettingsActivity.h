#pragma once
#include <array>

#include "activities/UiListActivity.h"
#include "components/OptionPopup.h"
class ScreenSettingsActivity final : public UiListActivity {
 public:
  ScreenSettingsActivity(GfxRenderer& renderer, MappedInputManager& input, int screen = -1);
  void onEnter() override;
  void render(RenderLock&& lock) override;

 private:
  int screen_;
  std::array<freeink::ui::ListItem, 6> rows_{};
  OptionPopup popup_;
  int listCount() const override { return screen_ < 0 ? 3 : screen_ == 2 ? 6 : 3; }
  const char* headerTitle() const override;
  void buildScreen(UiScreen& screen) override;
  void activateIndex(int index) override;
  bool handleCustomInput() override;
  void refreshRows();
  void chooseImage();
  void preview();
  void notice(StrId message);
  void setValue(uint8_t& value, uint8_t next, bool sleepMode = false);
};
