#pragma once
#include <array>
#include "activities/UiListActivity.h"
#include "ScreenShortcutPolicy.h"
#include "components/OptionPopup.h"
class ShortcutSettingsActivity final : public UiListActivity {
 public:
  ShortcutSettingsActivity(GfxRenderer& renderer, MappedInputManager& input, int page = -1);
  void onEnter() override;
  void render(RenderLock&& lock) override;
 private:
  int page_;
  std::array<freeink::ui::ListItem, ScreenShortcutPolicy::PANEL_SLOT_COUNT> rows_{};
  OptionPopup popup_;
  bool saveFailed_ = false;
  // The pull-down page lists every slot (the optional ones read "disabled"
  // until used); the tap page still has its four corners plus two middles.
  int listCount() const override {
    return page_ < 0 ? 2 : (page_ == 0 ? ScreenShortcutPolicy::PANEL_SLOT_COUNT : 6);
  }
  const char* headerTitle() const override;
  void buildScreen(UiScreen& screen) override;
  void activateIndex(int index) override;
  bool handleCustomInput() override;
  void refreshRows();
  void notice(StrId message);
};
