#include "InfoBoardSettingsActivity.h"

#include <cstring>
#include <utility>

#include "CrossPointSettings.h"
#include "InfoBoardPolicy.h"
#include "activities/util/KeyboardEntryActivity.h"
#include "components/SubpageLayout.h"
#include "components/UITheme.h"

namespace fui = freeink::ui;
namespace {
constexpr StrId ROW_LABELS[] = {StrId::STR_INFO_ROTATE, StrId::STR_INFO_INTERVAL, StrId::STR_INFO_CITY,
                                StrId::STR_INFO_DEMO_SETTING, StrId::STR_INFO_PC_URL};
constexpr StrId INTERVALS[] = {StrId::STR_INFO_15S, StrId::STR_INFO_30S, StrId::STR_INFO_60S,
                               StrId::STR_INFO_120S};
constexpr StrId CITIES[] = {StrId::STR_INFO_MELBOURNE, StrId::STR_INFO_SYDNEY, StrId::STR_INFO_BRISBANE};
constexpr StrId OK_OPTIONS[] = {StrId::STR_OK_BUTTON};
}  // namespace

void InfoBoardSettingsActivity::onEnter() {
  refreshRows();
  UiListActivity::onEnter();
}

const char* InfoBoardSettingsActivity::headerTitle() const { return tr(STR_INFO_BOARD); }

void InfoBoardSettingsActivity::refreshRows() {
  for (int i = 0; i < ROW_COUNT; ++i) {
    rows_[i] = {};
    rows_[i].label = I18N.get(ROW_LABELS[i]);
    rows_[i].actionValue = static_cast<int16_t>(i);
  }
  rows_[0].subtitle = SETTINGS.infoBoardRotate ? tr(STR_STATE_ON) : tr(STR_STATE_OFF);
  rows_[1].subtitle = I18N.get(INTERVALS[SETTINGS.infoBoardInterval < 4 ? SETTINGS.infoBoardInterval : 1]);
  rows_[2].subtitle = I18N.get(CITIES[SETTINGS.infoBoardCity < 3 ? SETTINGS.infoBoardCity : 0]);
  rows_[3].subtitle = SETTINGS.infoBoardDemo ? tr(STR_STATE_ON) : tr(STR_STATE_OFF);
  rows_[4].subtitle = *SETTINGS.infoBoardPcUrl ? SETTINGS.infoBoardPcUrl : tr(STR_NONE_OPT);
}

void InfoBoardSettingsActivity::notice(StrId message) {
  popup_.show(message, OK_OPTIONS, 1, 0, [](int) {});
  requestUpdate();
}

void InfoBoardSettingsActivity::activateIndex(int index) {
  if (index < 0 || index >= ROW_COUNT || popup_.isActive()) return;
  app.clearTapFlash();
  if (index == 4) {
    if (!startActivityForResultWith<KeyboardEntryActivity>(
            [this](const ActivityResult& result) {
              if (result.isCancelled || !std::holds_alternative<KeyboardResult>(result.data)) return;
              const auto& text = std::get<KeyboardResult>(result.data).text;
              if (text.size() >= sizeof(SETTINGS.infoBoardPcUrl) ||
                  (!text.empty() && !info_board::localPcUrl(text))) {
                notice(StrId::STR_INFO_PC_URL_INVALID);
                return;
              }
              char previous[sizeof(SETTINGS.infoBoardPcUrl)];
              memcpy(previous, SETTINGS.infoBoardPcUrl, sizeof(previous));
              memcpy(SETTINGS.infoBoardPcUrl, text.c_str(), text.size() + 1);
              if (!SETTINGS.saveToFile()) {
                memcpy(SETTINGS.infoBoardPcUrl, previous, sizeof(previous));
                notice(StrId::STR_SETTINGS_SAVE_FAILED);
              }
              refreshRows();
              requestUpdate();
            },
            tr(STR_INFO_PC_URL), SETTINGS.infoBoardPcUrl, sizeof(SETTINGS.infoBoardPcUrl) - 1, InputType::Url)) {
      notice(StrId::STR_MEMORY_ERROR);
    }
    return;
  }
  if (index == 1 || index == 2) {
    const bool interval = index == 1;
    const auto field = interval ? &CrossPointSettings::infoBoardInterval : &CrossPointSettings::infoBoardCity;
    const uint8_t old = SETTINGS.*field;
    popup_.show(ROW_LABELS[index], interval ? INTERVALS : CITIES, interval ? 4 : 3,
                old < (interval ? 4 : 3) ? old : 0, [this, field, interval](int next) {
                  if (next < 0 || next >= (interval ? 4 : 3)) return;
                  const uint8_t previous = SETTINGS.*field;
                  SETTINGS.*field = static_cast<uint8_t>(next);
                  if (!SETTINGS.saveToFile()) {
                    SETTINGS.*field = previous;
                    saveFailed_ = true;
                  }
                  refreshRows();
                  requestUpdate();
                });
    requestUpdate();
    return;
  }
  uint8_t& value = index == 0 ? SETTINGS.infoBoardRotate : SETTINGS.infoBoardDemo;
  const uint8_t previous = value;
  value = !value;
  if (!SETTINGS.saveToFile()) {
    value = previous;
    notice(StrId::STR_SETTINGS_SAVE_FAILED);
  }
  refreshRows();
  requestUpdate();
}

bool InfoBoardSettingsActivity::handleCustomInput() {
  const bool handled = popup_.handleInput(mappedInput, [this] { requestUpdate(); });
  if (saveFailed_) {
    saveFailed_ = false;
    notice(StrId::STR_SETTINGS_SAVE_FAILED);
  }
  return handled;
}

void InfoBoardSettingsActivity::render(RenderLock&& lock) {
  if (popup_.processRender(renderer, mappedInput)) return;
  UiListActivity::render(std::move(lock));
}

void InfoBoardSettingsActivity::buildScreen(UiScreen& screen) {
  const auto& metrics = UITheme::getInstance().getMetrics();
  const Rect safe = UITheme::getInstance().getScreenSafeArea(renderer, true, false);
  const Rect body = SubpageLayout::contentRect(safe, metrics);
  screen.setContentMarginFromScreen(fui::Insets{
      static_cast<int16_t>(body.y), static_cast<int16_t>(renderer.getScreenWidth() - body.x - body.width),
      static_cast<int16_t>(renderer.getScreenHeight() - body.y - body.height), static_cast<int16_t>(body.x)});
  fui::ListProps props;
  props.items = rows_.data();
  props.count = static_cast<uint16_t>(ROW_COUNT);
  props.action = ACTION_ROW;
  props.inputMask = fui::InputTouch;
  props.labelText = screen.theme().smallText;
  props.labelText.maxLines = 2;
  syncListViewport(screen, props, true);
  screen.list(props);
}
