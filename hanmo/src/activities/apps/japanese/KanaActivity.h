#pragma once
#include "KanaCardState.h"
#include "KanaPractice.h"
#include "activities/UiListActivity.h"
class KanaGroupsActivity final : public UiListActivity {
 public:
  KanaGroupsActivity(GfxRenderer& r, MappedInputManager& m) : UiListActivity("KanaGroups", r, m) {}
  void onEnter() override;

 private:
  std::array<freeink::ui::ListItem, 13> rows_{};
  std::array<std::array<char, 16>, 13> progressLabels_{};
  void refreshProgress();
  int listCount() const override { return 13; }
  const char* headerTitle() const override;
  void buildScreen(UiScreen&) override;
  void activateIndex(int) override;
};
class KanaCardActivity final : public Activity, protected UiAppHost {
 public:
  KanaCardActivity(GfxRenderer& r, MappedInputManager& m, int start, int count)
      : Activity("KanaCards", r, m), UiAppHost(r), state_(start, count) {}
  void onEnter() override;
  void onExit() override;
  void loop() override;
  void render(RenderLock&&) override;

 private:
  kana::State state_;
  kana::Practice practice_;
  bool recordReady_ = false;
  bool saveFailed_ = false;
  GfxRenderer::Orientation orientation_ = GfxRenderer::Orientation::Portrait;
  void action(int);
  void build(UiScreen&);
  static void screen(UiScreen&, void*);
  static void event(const freeink::ui::ActionEvent&, void*);
};
