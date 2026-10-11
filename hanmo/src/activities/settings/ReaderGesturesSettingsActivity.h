#pragma once
#include <array>
#include "activities/UiListActivity.h"
#include "components/OptionPopup.h"
class ReaderGesturesSettingsActivity final : public UiListActivity {
 public:
  ReaderGesturesSettingsActivity(GfxRenderer& r,MappedInputManager& i):UiListActivity("ReaderGestures",r,i){}
  void onEnter() override;
  void render(RenderLock&& lock) override;
 private:
  std::array<freeink::ui::ListItem,9> rows_{};
  OptionPopup popup_;
  bool failed_=false;
  int listCount() const override{return 9;}
  const char* headerTitle() const override{return tr(STR_READER_GESTURES);}
  void buildScreen(UiScreen& screen) override;
  void activateIndex(int index) override;
  bool handleCustomInput() override;
  void refreshRows();
};
