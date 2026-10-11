#pragma once

#include <I18n.h>

#include <vector>

#include "activities/UiListActivity.h"

// Apps menu — the single entry-point on the home screen for all non-reader sub-apps
// (Sudoku, Gomoku, Ugly Avatar, ...). The full list is the constexpr `kAppEntries` table
// in AppsMenuActivity.cpp; add a new app by assigning a stable AppId, appending one row,
// and adding goTo<App>() in ActivityManager. See src/activities/apps/README.md.
class AppsMenuActivity final : public UiListActivity {
 public:
  AppsMenuActivity(GfxRenderer& renderer, MappedInputManager& mappedInput)
      : UiListActivity("AppsMenu", renderer, mappedInput) {}
  ~AppsMenuActivity() override = default;

  void onEnter() override;
  MainTab mainTab() const override { return MainTab::Apps; }
  void selectMainTabContentEdge(MainTabContentEdge edge) override;

  static int getAppCount();
  static StrId getAppTitleId(int appIndex);
  static bool isAppVisible(int appIndex);
  static bool setAppVisible(int appIndex, bool visible);
  // The catalog index shown at `position` of the user's order, or -1. The
  // editor screen lists positions; everything else here takes catalog indices.
  static int getAppIndexAt(int position);
  // Move the app at `from` to `to`, sliding the rows between them along. True
  // when the order moved, which is also when the caller owes a save.
  static bool moveAppTo(int from, int to);

 private:
  static int getVisibleAppCount();
  static int getAppIndexForVisibleIndex(int visibleIndex);
  int listCount() const override { return getVisibleAppCount(); }
  void buildScreen(UiScreen& screen) override;
  void activateIndex(int index) override;
  bool handleCustomInput() override;
  void onBackButton() override;
  void drawChrome() override;
  void drawFooter() override;
  bool usesIconLayout() const;
  int iconIndexFromPoint(int x, int y) const;
  void rebuildRowItems();
  void openSelected();
  void drawIconGrid(const Rect& rect, int visibleCount, bool showSelection) const;

  // Allocated once on entry and reused for every repaint. The app catalog is
  // bounded to 32 entries; dynamic storage avoids pinning the maximum in every
  // live Apps activity while keeping render allocation-free.
  std::vector<freeink::ui::ListItem> rowItems;
};
