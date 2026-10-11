#include "AppVisibilitySettingsActivity.h"

#include <GfxRenderer.h>
#include <I18n.h>

#include "CrossPointSettings.h"
#include "MappedInputManager.h"
#include "activities/apps/AppsMenuActivity.h"
#include "components/UITheme.h"

namespace fui = freeink::ui;

namespace {
// Long enough not to fire on a normal toggle, short enough that a finger
// resting on a row discovers it. Matches the reader's own hold.
constexpr unsigned long PICK_UP_HOLD_MS = 500;
}  // namespace

AppVisibilitySettingsActivity::AppVisibilitySettingsActivity(GfxRenderer& renderer, MappedInputManager& mappedInput)
    : UiListActivity("AppVisibilitySettings", renderer, mappedInput, /*wantsTouchLongPress=*/true) {}

void AppVisibilitySettingsActivity::onEnter() {
  UiListActivity::onEnter();
  dirty = false;
  carrying = -1;
  waitForConfirmRelease = mappedInput.isPressed(MappedInputManager::Button::Confirm);

  rowItems.assign(static_cast<size_t>(listCount()), fui::ListItem{});
  labels.assign(static_cast<size_t>(listCount()), "");
  rebuildLabels();
}

void AppVisibilitySettingsActivity::onExit() {
  if (dirty) SETTINGS.saveToFile();
  Activity::onExit();
}

int AppVisibilitySettingsActivity::listCount() const { return AppsMenuActivity::getAppCount(); }

void AppVisibilitySettingsActivity::rebuildLabels() {
  for (int i = 0; i < listCount(); ++i) {
    const int appIndex = AppsMenuActivity::getAppIndexAt(i);
    labels[static_cast<size_t>(i)] = I18N.get(AppsMenuActivity::getAppTitleId(appIndex));
    rowItems[static_cast<size_t>(i)].label = labels[static_cast<size_t>(i)];
    rowItems[static_cast<size_t>(i)].actionValue = static_cast<int16_t>(i);
  }
}

void AppVisibilitySettingsActivity::pickUp(const int index) {
  if (index < 0 || index >= listCount()) return;
  carrying = index;
  moveSelectionTo(index);
  requestUpdate();
}

void AppVisibilitySettingsActivity::dropAt(const int index) {
  const int from = carrying;
  carrying = -1;
  if (from >= 0 && index >= 0 && index < listCount() && AppsMenuActivity::moveAppTo(from, index)) {
    dirty = true;
    rebuildLabels();
    moveSelectionTo(index);
  }
  requestUpdate();
}

// Touch: hold a row to pick it up.
//
// A hold while already carrying drops at the held row, exactly as a tap does.
// Dropping it back at its old position instead would mean the same gesture on
// the same pixel did two different things depending on how long the finger
// stayed, which is the kind of distinction nobody makes on purpose. Holding
// the carried row itself still puts it down where it is, because that is what
// dropping it at its own position means.
void AppVisibilitySettingsActivity::onRowLongPress(const int index) {
  app.clearTapFlash();
  if (carrying >= 0) {
    dropAt(index);
    return;
  }
  pickUp(index);
}

bool AppVisibilitySettingsActivity::handleCustomInput() {
  // Entered with Confirm already down (the tap that opened this screen). Its
  // release is not a command.
  if (waitForConfirmRelease) {
    if (!mappedInput.isPressed(MappedInputManager::Button::Confirm)) waitForConfirmRelease = false;
    return true;
  }

  if (carrying < 0) {
    // Button path, for hardware with four of them. Consumed here so the
    // release that follows cannot also toggle the row.
    if (mappedInput.wasLongPressed(MappedInputManager::Button::Confirm, PICK_UP_HOLD_MS)) {
      waitForConfirmRelease = true;
      pickUp(nav.selected);
      return true;
    }
    return false;
  }

  // Carrying: the nav keys step the row rather than the selection.
  if (mappedInput.wasReleased(MappedInputManager::Button::NavPrevious)) {
    if (carrying > 0 && AppsMenuActivity::moveAppTo(carrying, carrying - 1)) {
      dirty = true;
      rebuildLabels();
      --carrying;
      moveSelectionTo(carrying);
    }
    requestUpdate();
    return true;
  }
  if (mappedInput.wasReleased(MappedInputManager::Button::NavNext)) {
    if (carrying + 1 < listCount() && AppsMenuActivity::moveAppTo(carrying, carrying + 1)) {
      dirty = true;
      rebuildLabels();
      ++carrying;
      moveSelectionTo(carrying);
    }
    requestUpdate();
    return true;
  }
  if (mappedInput.wasReleased(MappedInputManager::Button::Confirm)) {
    dropAt(carrying);
    return true;
  }
  return false;
}

void AppVisibilitySettingsActivity::onBackButton() {
  // Back puts the row down rather than leaving. Every move is already applied,
  // so there is nothing to cancel -- but leaving the screen mid-carry would
  // strand the mode, and Back is where a hand goes to get out of one.
  if (carrying >= 0) {
    dropAt(carrying);
    return;
  }
  finish();
}

void AppVisibilitySettingsActivity::activateIndex(const int index) {
  if (index < 0 || index >= listCount()) return;
  app.clearTapFlash();
  // A tap while carrying says where it goes. Including a tap on the carried
  // row itself, which means "here is fine".
  if (carrying >= 0) {
    dropAt(index);
    return;
  }
  nav.selected = index;
  const int appIndex = AppsMenuActivity::getAppIndexAt(index);
  const bool visible = AppsMenuActivity::isAppVisible(appIndex);
  if (AppsMenuActivity::setAppVisible(appIndex, !visible)) {
    dirty = true;
    requestUpdate();
  }
}

// The header carries the mode, because the footer cannot: button hints are not
// drawn on a device with a touch panel (BaseTheme::buttonHintsVisible).
const char* AppVisibilitySettingsActivity::headerTitle() const {
  return carrying >= 0 ? tr(STR_APPS_MENU_PLACE) : tr(STR_APPS_MENU_EDIT);
}

void AppVisibilitySettingsActivity::buildScreen(UiScreen& screen) {
  const auto& metrics = UITheme::getInstance().getMetrics();
  screen.setContentMargin(fui::Insets{static_cast<int16_t>(metrics.topPadding + metrics.headerHeight), 0,
                                      static_cast<int16_t>(metrics.buttonHintsHeight), 0});
  screen.spacer(static_cast<int16_t>(metrics.verticalSpacing));

  for (int i = 0; i < listCount(); ++i) {
    const int appIndex = AppsMenuActivity::getAppIndexAt(i);
    // The carried row says so where its on/off state would be: the one row
    // whose taps mean something different is the one that has to look
    // different.
    rowItems[static_cast<size_t>(i)].value =
        (i == carrying) ? tr(STR_APPS_MENU_MOVING)
                        : (AppsMenuActivity::isAppVisible(appIndex) ? tr(STR_STATE_ON) : tr(STR_STATE_OFF));
  }

  fui::ListProps props;
  props.items = rowItems.data();
  props.count = static_cast<uint16_t>(rowItems.size());
  props.action = ACTION_ROW;
  props.inputMask = static_cast<uint16_t>(fui::InputTouch | fui::InputLongPress);
  props.valueInset = 8;
  syncListViewport(screen, props);
  screen.list(props);
}

void AppVisibilitySettingsActivity::drawFooter() {
  const auto labelSet =
      carrying >= 0 ? mappedInput.mapLabels(tr(STR_BACK), tr(STR_APPS_MENU_DROP), tr(STR_DIR_UP), tr(STR_DIR_DOWN))
                    : mappedInput.mapLabels(tr(STR_BACK), tr(STR_TOGGLE), tr(STR_DIR_UP), tr(STR_DIR_DOWN));
  GUI.drawButtonHints(renderer, labelSet.btn1, labelSet.btn2, labelSet.btn3, labelSet.btn4);
}
