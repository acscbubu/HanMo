#include "HomeDisplaySettingsActivity.h"
#include "HomeCustomization.h"
#include "activities/util/KeyboardEntryActivity.h"
#include "components/SubpageLayout.h"
#include "components/UITheme.h"
namespace fui = freeink::ui;
namespace { constexpr StrId NOTICE_OPTIONS[] = {StrId::STR_OK_BUTTON}; }
HomeDisplaySettingsActivity::HomeDisplaySettingsActivity(GfxRenderer& renderer, MappedInputManager& input, bool textPage)
    : UiListActivity("HomeDisplaySettings", renderer, input), textPage_(textPage) {}
const char* HomeDisplaySettingsActivity::headerTitle() const {
  return textPage_ ? tr(STR_HOME_TEXT_MENU) : tr(STR_HOME_SHORTCUT_MENU);
}
void HomeDisplaySettingsActivity::onEnter() { refreshRows(); UiListActivity::onEnter(); }
void HomeDisplaySettingsActivity::refreshRows() {
  for (int i = 0; i < listCount(); ++i) {
    rows_[i] = {};
    rows_[i].actionValue = static_cast<int16_t>(i);
    if (textPage_ && i == 0) {
      rows_[i].label = tr(STR_HOME_LABEL);
      rows_[i].subtitle = *SETTINGS.homeLabel ? SETTINGS.homeLabel : tr(STR_HOME_LABEL_EDIT_HINT);
    } else {
      const int index = textPage_ ? i - 1 : i;
      const auto* fields = textPage_ ? HomeCustomization::positions : HomeCustomization::slots;
      const auto* labels = textPage_ ? HomeCustomization::positionLabels : HomeCustomization::labels;
      const auto* choices = textPage_ ? HomeCustomization::positionOptions : HomeCustomization::selectableOptions.data();
      const int count = textPage_ ? 4 : HomeShortcutPolicy::SELECTABLE_COUNT;
      const uint8_t value = SETTINGS.*fields[index];
      rows_[i].label = I18N.get(labels[index]);
      const int selection = textPage_ ? value : HomeShortcutPolicy::selectionIndex(value);
      rows_[i].subtitle = I18N.get(choices[selection < count ? selection : 0]);
    }
  }
}
void HomeDisplaySettingsActivity::notice(StrId message) {
  popup_.show(message, NOTICE_OPTIONS, 1, 0, [](int) {});
  requestUpdate();
}
void HomeDisplaySettingsActivity::activateIndex(int index) {
  if (index < 0 || index >= listCount()) return;
  if (textPage_ && index == 0) {
    app.clearTapFlash();
    if (!startActivityForResultWith<KeyboardEntryActivity>([this](const ActivityResult& result) {
      if (result.isCancelled || !std::holds_alternative<KeyboardResult>(result.data)) return;
      const auto& text = std::get<KeyboardResult>(result.data).text;
      char previous[sizeof(SETTINGS.homeLabel)];
      memcpy(previous, SETTINGS.homeLabel, sizeof(previous));
      if (!HomeCustomization::assignLabel(text)) {
        notice(StrId::STR_HOME_LABEL_INVALID);
      } else if (!SETTINGS.saveToFile()) {
        memcpy(SETTINGS.homeLabel, previous, sizeof(previous));
        notice(StrId::STR_SETTINGS_SAVE_FAILED);
      }
      refreshRows(); requestUpdate();
    }, tr(STR_HOME_LABEL), SETTINGS.homeLabel, sizeof(SETTINGS.homeLabel) - 1, InputType::Text)) notice(StrId::STR_MEMORY_ERROR);
    return;
  }
  const int row = textPage_ ? index - 1 : index;
  const auto field = (textPage_ ? HomeCustomization::positions : HomeCustomization::slots)[row];
  const auto* labels = textPage_ ? HomeCustomization::positionLabels : HomeCustomization::labels;
  const auto* choices = textPage_ ? HomeCustomization::positionOptions : HomeCustomization::selectableOptions.data();
  const int count = textPage_ ? 4 : HomeShortcutPolicy::SELECTABLE_COUNT;
  const int selectedIndex = textPage_ ? SETTINGS.*field : HomeShortcutPolicy::selectionIndex(SETTINGS.*field);
  popup_.show(labels[row], choices, count, selectedIndex, [this, field, count](int selected) {
    if (selected < 0 || selected >= count) return;
    const uint8_t previous = SETTINGS.*field;
    SETTINGS.*field = textPage_ ? static_cast<uint8_t>(selected) : HomeShortcutPolicy::storedAction(selected);
    if (!SETTINGS.saveToFile()) { SETTINGS.*field = previous; saveFailed_ = true; }
    refreshRows(); requestUpdate();
  });
  requestUpdate();
}
bool HomeDisplaySettingsActivity::handleCustomInput() {
  const bool handled = popup_.handleInput(mappedInput, [this] { requestUpdate(); });
  if (saveFailed_) {
    saveFailed_ = false;
    notice(StrId::STR_SETTINGS_SAVE_FAILED);
  }
  return handled;
}
void HomeDisplaySettingsActivity::render(RenderLock&& lock) {
  if (popup_.processRender(renderer, mappedInput)) return;
  UiListActivity::render(std::move(lock));
}
void HomeDisplaySettingsActivity::buildScreen(UiScreen& screen) {
  const auto& metrics = UITheme::getInstance().getMetrics();
  const Rect safe = UITheme::getInstance().getScreenSafeArea(renderer, true, false);
  const Rect body = SubpageLayout::contentRect(safe, metrics);
  screen.setContentMarginFromScreen(fui::Insets{
      static_cast<int16_t>(body.y), static_cast<int16_t>(renderer.getScreenWidth() - body.x - body.width),
      static_cast<int16_t>(renderer.getScreenHeight() - body.y - body.height), static_cast<int16_t>(body.x)});
  fui::ListProps props;
  props.items = rows_.data();
  props.count = static_cast<uint16_t>(listCount());
  props.action = ACTION_ROW;
  props.inputMask = fui::InputTouch;
  props.labelText = screen.theme().smallText;
  props.labelText.maxLines = 2;
  syncListViewport(screen, props, true);
  screen.list(props);
}
