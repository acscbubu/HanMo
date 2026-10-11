#include "ShortcutSettingsActivity.h"
#include "ShortcutBindings.h"
#include "components/SubpageLayout.h"
#include "components/UITheme.h"
namespace fui = freeink::ui;
namespace {
constexpr StrId TITLES[] = {StrId::STR_QUICK_PANEL, StrId::STR_TAP_SHORTCUTS};
constexpr StrId HINTS[] = {StrId::STR_QUICK_PANEL_HINT, StrId::STR_TAP_SHORTCUTS_HINT};
constexpr StrId NOTICE_OPTIONS[] = {StrId::STR_OK_BUTTON};
}
ShortcutSettingsActivity::ShortcutSettingsActivity(GfxRenderer& renderer, MappedInputManager& input, int page)
    : UiListActivity("ShortcutSettings", renderer, input), page_(page >= 0 && page <= 1 ? page : -1) {}
const char* ShortcutSettingsActivity::headerTitle() const {
  return page_ < 0 ? tr(STR_SCREEN_SHORTCUTS) : I18N.get(TITLES[page_]);
}
void ShortcutSettingsActivity::onEnter() {
  refreshRows();
  UiListActivity::onEnter();
}
void ShortcutSettingsActivity::refreshRows() {
  for (int i = 0; i < listCount(); ++i) {
    rows_[i] = {};
    rows_[i].actionValue = static_cast<int16_t>(i);
    if (page_ < 0) {
      rows_[i].label = I18N.get(TITLES[i]);
      rows_[i].subtitle = I18N.get(HINTS[i]);
    } else {
      const auto* fields = page_ == 0 ? ShortcutBindings::panel : ShortcutBindings::taps;
      const auto* labels = page_ == 0 ? ShortcutBindings::panelLabels : ShortcutBindings::tapLabels;
      const auto* choices = page_ == 0 ? ShortcutBindings::panelOptions : ShortcutBindings::tapOptions;
      const int count = page_ == 0 ? static_cast<int>(ScreenShortcutPolicy::ActionCount) : static_cast<int>(CrossPointSettings::CORNER_TAP_ACTION_COUNT);
      const auto selected = SETTINGS.*fields[i];
      rows_[i].label = I18N.get(labels[i]);
      rows_[i].subtitle = I18N.get(choices[selected < count ? selected : 0]);
    }
  }
}
void ShortcutSettingsActivity::notice(StrId message) {
  popup_.show(message, NOTICE_OPTIONS, 1, 0, [](int) {});
  requestUpdate();
}
void ShortcutSettingsActivity::activateIndex(int index) {
  if (index < 0 || index >= listCount()) return;
  if (page_ < 0) {
    app.clearTapFlash();
    // The child outlives this frame; the base helper allocates with checked nothrow.
    if (!startActivityForResultWith<ShortcutSettingsActivity>(
            [this](const ActivityResult&) { refreshRows(); requestUpdate(); }, index)) notice(StrId::STR_MEMORY_ERROR);
    return;
  }
  const auto field = (page_ == 0 ? ShortcutBindings::panel : ShortcutBindings::taps)[index];
  const auto* choices = page_ == 0 ? ShortcutBindings::panelOptions : ShortcutBindings::tapOptions;
  const auto* labels = page_ == 0 ? ShortcutBindings::panelLabels : ShortcutBindings::tapLabels;
  const int count = page_ == 0 ? static_cast<int>(ScreenShortcutPolicy::ActionCount) : static_cast<int>(CrossPointSettings::CORNER_TAP_ACTION_COUNT);
  // The pull-down picker lists actions in reader order (PICKER_ORDER) so
  // "disabled" stays at the bottom, while the SAVED value remains the action
  // id. Map the rows both ways around the popup; the tap page is unaffected.
  const bool panelPage = page_ == 0;
  StrId ordered[ScreenShortcutPolicy::ActionCount];
  int current = SETTINGS.*field;
  if (panelPage) {
    for (int i = 0; i < count; ++i) ordered[i] = choices[ScreenShortcutPolicy::PICKER_ORDER[i]];
    choices = ordered;
    const uint8_t saved = ScreenShortcutPolicy::validAction(SETTINGS.*field);
    current = 0;
    for (int i = 0; i < count; ++i) {
      if (ScreenShortcutPolicy::PICKER_ORDER[i] == saved) current = i;
    }
  }
  popup_.show(labels[index], choices, count, current, [this, field, count, panelPage](int selected) {
    if (selected < 0 || selected >= count) return;
    const uint8_t previous = SETTINGS.*field;
    SETTINGS.*field = panelPage ? ScreenShortcutPolicy::PICKER_ORDER[selected]
                                : static_cast<uint8_t>(selected);
    if (!SETTINGS.saveToFile()) {
      SETTINGS.*field = previous;
      saveFailed_ = true;  // Show after the current callback has returned.
    }
    refreshRows();
    requestUpdate();
  });
  requestUpdate();
}
bool ShortcutSettingsActivity::handleCustomInput() {
  const bool handled = popup_.handleInput(mappedInput, [this] { requestUpdate(); });
  if (saveFailed_) {
    saveFailed_ = false;
    notice(StrId::STR_SETTINGS_SAVE_FAILED);
  }
  return handled;
}
void ShortcutSettingsActivity::render(RenderLock&& lock) {
  if (popup_.processRender(renderer, mappedInput)) return;
  UiListActivity::render(std::move(lock));
}
void ShortcutSettingsActivity::buildScreen(UiScreen& screen) {
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
