#include "ChangeHistoryActivity.h"

#include <I18n.h>

#include <algorithm>

#include "components/SubpageLayout.h"
#include "components/UITheme.h"

namespace fui = freeink::ui;

ChangeHistoryActivity::ChangeHistoryActivity(GfxRenderer& renderer, MappedInputManager& input, int entry)
    : UiListActivity("ChangeHistory", renderer, input),
      entry_(entry >= 0 && entry < static_cast<int>(ChangeHistory::COUNT) ? entry : -1) {}

int ChangeHistoryActivity::listCount() const { return entry_ < 0 ? static_cast<int>(ChangeHistory::COUNT) : 4; }

const char* ChangeHistoryActivity::headerTitle() const {
  return entry_ < 0 ? tr(STR_CHANGE_HISTORY) : I18N.get(ChangeHistory::entries[entry_].title);
}

void ChangeHistoryActivity::onEnter() {
  for (int i = 0; i < listCount(); ++i) {
    auto& row = rows_[i];
    row.actionValue = static_cast<int16_t>(i);
    if (entry_ < 0) {
      row.label = I18N.get(ChangeHistory::entries[i].title);
      row.subtitle = ChangeHistory::entries[i].date;
    } else {
      const auto& entry = ChangeHistory::entries[entry_];
      row.label = i == 0 ? entry.date : I18N.get(entry.paragraphs[i - 1]);
    }
  }
  // Publish the screen only after all row pointers are ready for rendering.
  UiListActivity::onEnter();
}

void ChangeHistoryActivity::activateIndex(int index) {
  if (entry_ >= 0 || index < 0 || index >= listCount()) return;
  app.clearTapFlash();
  // Checked allocation via the normal Activity helper; no unbounded row heap.
  if (!startActivityForResultWith<ChangeHistoryActivity>([this](const ActivityResult&) { requestUpdate(); }, index)) {
    GUI.drawPopup(renderer, tr(STR_MEMORY_ERROR));
    requestUpdate();
  }
}

void ChangeHistoryActivity::buildScreen(UiScreen& screen) {
  const auto& metrics = UITheme::getInstance().getMetrics();
  const Rect safe = UITheme::getInstance().getScreenSafeArea(renderer, true, false);
  const Rect content = SubpageLayout::contentRect(safe, metrics);
  screen.setContentMarginFromScreen(fui::Insets{
      static_cast<int16_t>(content.y), static_cast<int16_t>(renderer.getScreenWidth() - content.x - content.width),
      static_cast<int16_t>(renderer.getScreenHeight() - content.y - content.height), static_cast<int16_t>(content.x)});
  fui::ListProps props;
  props.items = rows_.data();
  props.count = static_cast<uint16_t>(listCount());
  props.action = ACTION_ROW;
  props.inputMask = fui::InputTouch;
  props.labelText = screen.theme().smallText;
  props.labelText.maxLines = entry_ < 0 ? 2 : 6;
  syncListViewport(screen, props, entry_ < 0);
  screen.list(props);
}

void ChangeHistoryActivity::drawFooter() {
  const auto labels =
      mappedInput.mapLabels(tr(STR_BACK), entry_ < 0 ? tr(STR_SELECT) : "", tr(STR_DIR_UP), tr(STR_DIR_DOWN));
  GUI.drawButtonHints(renderer, labels.btn1, labels.btn2, labels.btn3, labels.btn4);
}
