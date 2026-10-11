#pragma once

#include <vector>

#include "activities/UiListActivity.h"

// The Apps menu editor: which apps appear, and in what order.
//
// Rows are POSITIONS in the user's order, not rows of the catalog table, so
// what this screen shows top to bottom is what the Apps menu shows top to
// bottom. One screen for both because they are one question -- what the menu
// looks like -- and because this device cannot afford two.
//
// Reordering is touch-first, because the X4 Pro is: it has two physical nav
// keys and nothing else, with Back and Confirm coming off the GT911, and
// BaseTheme::buttonHintsVisible() is false whenever there is a touch panel --
// so a footer explaining a button sequence would not even be drawn. Long-press
// a row to pick it up, then tap where it should go. Tapping it again puts it
// back down.
//
// The button path is kept for hardware that has four of them: hold Confirm to
// pick up, nav keys to step, Confirm or Back to drop.
class AppVisibilitySettingsActivity final : public UiListActivity {
 public:
  explicit AppVisibilitySettingsActivity(GfxRenderer& renderer, MappedInputManager& mappedInput);

  void onEnter() override;
  void onExit() override;

 private:
  int listCount() const override;
  void buildScreen(UiScreen& screen) override;
  void activateIndex(int index) override;
  void onRowLongPress(int index) override;
  bool handleCustomInput() override;
  void onBackButton() override;
  const char* headerTitle() const override;
  void drawFooter() override;

  void rebuildLabels();
  void pickUp(int index);
  void dropAt(int index);

  std::vector<freeink::ui::ListItem> rowItems;
  // Titles are looked up per position and the list re-sorts under them, so the
  // ListItem labels cannot point at the catalog: they point here.
  std::vector<const char*> labels;
  bool waitForConfirmRelease = false;
  // -1 when nothing is being carried. A position, not a catalog index: the
  // list renumbers under a move and the carried row has to follow it.
  int carrying = -1;
  bool dirty = false;
};
