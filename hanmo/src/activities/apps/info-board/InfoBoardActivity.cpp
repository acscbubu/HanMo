#include "InfoBoardActivity.h"

#include <HalClock.h>
#include <I18n.h>
#include <WiFi.h>

#include "CrossPointSettings.h"
#include "InfoBoardPolicy.h"
#include "NetworkStartup.h"
#include "WifiCredentialStore.h"
#include "activities/apps/standby/SegmentDigits.h"
#include "activities/network/WifiSelectionActivity.h"
#include "components/UITheme.h"
#include "fontIds.h"
#include "util/TimeUtils.h"
namespace fui = freeink::ui;
namespace {
uint32_t nextGeneration = 0;
constexpr StrId titles[] = {StrId::STR_CLOCK, StrId::STR_INFO_WEATHER, StrId::STR_INFO_PC};
constexpr StrId cities[] = {StrId::STR_INFO_MELBOURNE, StrId::STR_INFO_SYDNEY, StrId::STR_INFO_BRISBANE};
constexpr StrId intervals[] = {StrId::STR_INFO_15S, StrId::STR_INFO_30S, StrId::STR_INFO_60S, StrId::STR_INFO_120S};
}  // namespace
void InfoBoardActivity::onEnter() {
  generation_ = ++nextGeneration;
  Activity::onEnter();
  resetUi();
  app.on(1, &InfoBoardActivity::event, this);
  app.setScreen(&InfoBoardActivity::screen, this);
  rotated_ = millis();
  // Nonblocking reconnect only to the user's last saved network. Never disable
  // an existing AP/connection, and keep Wi-Fi alive when leaving this app.
  if (WiFi.getMode() == WIFI_OFF) {
    std::string ssid, pass;
    {
      RenderLock lock(*this);
      if (!WIFI_STORE.getCredentialCount()) WIFI_STORE.loadFromFile();
      auto c = WIFI_STORE.findCredential(WIFI_STORE.getLastConnectedSsid());
      if (c) {
        ssid = c->ssid;
        pass = c->password;
      }
    }
    if (!ssid.empty()) {
      WiFi.persistent(false);
      NetworkStartup::setMode(renderer, WIFI_STA);
      WiFi.begin(ssid.c_str(), pass.c_str());
    }
  }
  requestUpdate();
}
void InfoBoardActivity::screen(UiScreen& s, void* p) { static_cast<InfoBoardActivity*>(p)->build(s); }
void InfoBoardActivity::event(const fui::ActionEvent& e, void* p) {
  static_cast<InfoBoardActivity*>(p)->action(e.value);
}
void InfoBoardActivity::action(int v) {
  if (v == 20) {
    app.clearTapFlash();
    onGoHome();
    return;
  }
  if (v == 21) {
    app.clearTapFlash();
    startActivityForResultWith<WifiSelectionActivity>([this](const ActivityResult&) {
      tried_.fill(false);
      requestUpdate();
    });
    return;
  }
  {
    RenderLock lock(*this);
    rotated_ = millis();
    if (v >= 0 && v < 3) {
      scene_ = v;
      SETTINGS.infoBoardRotate = 0;
    }
    if (v == 10) SETTINGS.infoBoardRotate = !SETTINGS.infoBoardRotate;
    if (v == 11) config_ = !config_;
    if (v == 12) SETTINGS.infoBoardInterval = (SETTINGS.infoBoardInterval + 1) % 4;
    if (v == 13) {
      SETTINGS.infoBoardDemo = !SETTINGS.infoBoardDemo;
      tried_.fill(false);
    }
    if (v == 14) {
      generation_ = ++nextGeneration;
      SETTINGS.infoBoardCity = (SETTINGS.infoBoardCity + 1) % 3;
      data_[1] = {};
      tried_[1] = false;
    }
    if (v == 22) tried_[scene_] = false;
    if (v != 11 && v != 22) SETTINGS.saveToFile();
  }
  requestUpdate();
}
void InfoBoardActivity::loop() {
  if (mappedInput.wasReleased(MappedInputManager::Button::Back)) {
    if (config_)
      action(11);
    else
      onGoHome();
    return;
  }
  if (routeTouch(mappedInput)) return;
  if (mappedInput.wasReleased(MappedInputManager::Button::Confirm)) {
    action(10);
    return;
  }
  if (mappedInput.wasReleased(MappedInputManager::Button::Right)) {
    action((scene_ + 1) % 3);
    return;
  }
  if (mappedInput.wasReleased(MappedInputManager::Button::Left)) {
    action((scene_ + 2) % 3);
    return;
  }
  const auto swipe = mappedInput.wasSwipe();
  if (swipe == MappedInputManager::SwipeDir::Left) {
    action((scene_ + 1) % 3);
    return;
  }
  if (swipe == MappedInputManager::SwipeDir::Right) {
    action((scene_ + 2) % 3);
    return;
  }
  const uint32_t now = millis();
  if (WiFi.status() == WL_CONNECTED && !clockSyncRequested_) {
    clockSyncRequested_ = true;
    halClock.requestSync();
  }
  uint8_t scene;
  info_board::Data incoming;
  if (info_board::take(scene, incoming) && scene < 3 && incoming.generation == generation_) {
    {
      RenderLock lock(*this);
      if (incoming.valid) {
        data_[scene] = std::move(incoming);
        received_[scene] = now;
      } else
        data_[scene].error = incoming.error;
    }
    requestUpdate();
  }
  if (!config_ && SETTINGS.infoBoardRotate &&
      info_board::due(now, rotated_, info_board::rotationMs(SETTINGS.infoBoardInterval))) {
    {
      RenderLock lock(*this);
      scene_ = (scene_ + 1) % 3;
      rotated_ = now;
    }
    requestUpdate();
  }
  const auto stamp = TimeUtils::getCurrentValidTimestamp();
  const auto minute = stamp ? stamp / 60 : now / 60000;
  if (minute != paintedMinute_) {
    paintedMinute_ = minute;
    requestUpdate();
  }
  if (!config_ && scene_ && !SETTINGS.infoBoardDemo && WiFi.status() == WL_CONNECTED && !info_board::busy() &&
      (!tried_[scene_] || info_board::due(now, attempted_[scene_], info_board::refreshMs(scene_)))) {
    info_board::Request r;
    r.generation = generation_;
    r.scene = scene_;
    r.city = SETTINGS.infoBoardCity;
    if (scene_ == 2) r.url = SETTINGS.infoBoardPcUrl;
    tried_[scene_] = true;
    attempted_[scene_] = now;
    if (info_board::start(std::move(r))) requestUpdate();
  }
}
void InfoBoardActivity::build(UiScreen& s) {
  const auto& m = UITheme::getInstance().getMetrics();
  s.setContentMarginFromScreen(fui::Insets{int16_t(m.topPadding + m.headerHeight + 8), 12, 12, 12});
  const auto a = s.body();
  const int gap = 6;
  const int h = 48;
  auto text = [&](const std::string& str, int y, int height, bool title = false) {
    auto style = title ? s.theme().titleText : s.theme().bodyText;
    style.align = fui::TextAlign::Center;
    s.target().text(fui::Rect{a.x, int16_t(y), a.width, int16_t(height)}, str.c_str(), style);
  };
  auto button = [&](const char* label, int v, int x, int y, int w, int bh) {
    fui::ButtonProps p;
    p.label = label;
    p.action = 1;
    p.value = v;
    p.inputMask = fui::InputTouch;
    p.text = s.theme().smallText;
    p.minTouchSize = 1;
    s.button(p, fui::Rect{int16_t(x), int16_t(y), int16_t(w), int16_t(bh)});
  };
  const int available = a.width - 2 * gap;
  const int widths[] = {available / 3, available / 3, available - 2 * (available / 3)};
  int tabX = a.x;
  for (int i = 0; i < 3; i++) {
    button(i == 2 ? tr(STR_INFO_PC_TAB) : I18N.get(titles[i]), i, tabX, a.y, widths[i], h);
    tabX += widths[i] + gap;
  }
  const int bottom = a.bottom() - h;
  const int third = (a.width - 2 * gap) / 3;
  button(tr(STR_HOME), 20, a.x, bottom, third, h);
  button("Wi-Fi", 21, a.x + third + gap, bottom, third, h);
  button(config_ ? tr(STR_BACK) : tr(STR_SETTINGS_TITLE), 11, a.x + 2 * (third + gap), bottom, third, h);
  if (config_) {
    const int start = a.y + h + 18, row = 64;
    const std::string mode =
        std::string(tr(STR_INFO_ROTATE)) + ": " + I18N.get(SETTINGS.infoBoardRotate ? StrId::STR_YES : StrId::STR_NO);
    button(mode.c_str(), 10, a.x, start, a.width, h);
    const std::string interval =
        std::string(tr(STR_INFO_INTERVAL)) + ": " + I18N.get(intervals[SETTINGS.infoBoardInterval % 4]);
    button(interval.c_str(), 12, a.x, start + row, a.width, h);
    button(I18N.get(cities[SETTINGS.infoBoardCity % 3]), 14, a.x, start + 2 * row, a.width, h);
    const std::string demo = std::string(tr(STR_INFO_DEMO_SETTING)) + ": " +
                             I18N.get(SETTINGS.infoBoardDemo ? StrId::STR_YES : StrId::STR_NO);
    button(demo.c_str(), 13, a.x, start + 3 * row, a.width, h);
    text(tr(STR_INFO_LINK_ONLY), start + 4 * row, 70);
    return;
  }
  const int top = a.y + h + 16, controls = bottom - h - gap;
  const int half = (a.width - gap) / 2;
  button(I18N.get(SETTINGS.infoBoardRotate ? StrId::STR_INFO_AUTO : StrId::STR_INFO_MANUAL), 10, a.x, controls, half,
         h);
  button(tr(STR_INFO_REFRESH), 22, a.x + half + gap, controls, half, h);
  text(I18N.get(titles[scene_]), top, 44, true);
  if (scene_ == 0) {
    const auto stamp = TimeUtils::getCurrentValidTimestamp();
    std::tm local{};
    if (stamp && TimeUtils::getLocalDateTime(stamp, local)) {
      const auto digits = segment_digits::metricsFor(segment_digits::cellHeightForWidth(a.width - 36));
      unsigned hour = local.tm_hour;
      if (SETTINGS.clockFormat) hour = hour % 12 ? hour % 12 : 12;
      segment_digits::drawHHMM(renderer, a.x + (a.width - segment_digits::hhmmWidth(digits)) / 2, top + 85, digits,
                               hour, local.tm_min, true);
      text(TimeUtils::formatDate(stamp) + (SETTINGS.clockFormat ? (local.tm_hour >= 12 ? " PM" : " AM") : ""),
           top + 85 + digits.cellHeight + 32, 56);
    } else {
      text("--:--", top + 70, 80, true);
      text(tr(STR_AUTO_TIME), top + 160, 56);
    }
    return;
  }
  const bool demo = SETTINGS.infoBoardDemo;
  const auto& data = data_[scene_];
  std::string status;
  if (demo)
    status = tr(STR_INFO_DEMO);
  else if (data.valid && (data.error || WiFi.status() != WL_CONNECTED ||
                          info_board::due(millis(), received_[scene_], info_board::refreshMs(scene_) * 2)))
    status = tr(STR_INFO_CACHED);
  else if (!data.valid)
    status = info_board::busy() ? tr(STR_LOADING) : tr(STR_INFO_FAILED);
  if (!demo && (scene_ == 2 && !SETTINGS.infoBoardPcUrl[0]))
    status = tr(STR_INFO_NOT_SET);
  if (scene_ == 1) text(I18N.get(cities[SETTINGS.infoBoardCity % 3]), top + 44, 40);
  const int rowTop = top + (scene_ == 1 ? 88 : 52), rowHeight = 64;
  const char* labelsWeather[] = {tr(STR_INFO_TEMPERATURE), tr(STR_INFO_HUMIDITY), tr(STR_INFO_WIND)};
  const char* labelsPc[] = {"CPU", "RAM", tr(STR_INFO_DISK)};
  const char* samplesWeather[] = {"18.5 C", "63 %", "12.0 km/h"};
  const char* samplesPc[] = {"24 %", "58 %", "42 %"};
  for (int i = 0; i < 3; i++) {
    std::string label, value;
    if (demo) {
      label = scene_ == 1 ? labelsWeather[i] : labelsPc[i];
      value = scene_ == 1 ? samplesWeather[i] : samplesPc[i];
    } else {
      label = data.valid && scene_ == 1   ? labelsWeather[i]
              : data.valid && scene_ == 2 ? labelsPc[i]
                                          : data.rows[i].label;
      value = data.rows[i].value;
    }
    if (label.empty()) continue;
    text(label + "  " + value, rowTop + i * rowHeight, rowHeight, true);
  }
  const int statusY = rowTop + 3 * rowHeight + 8;
  text(status, statusY, 52);
  if (!demo && data.valid) text(std::string(tr(STR_INFO_UPDATED)) + ": " + data.updated, statusY + 52, 40);
  if (scene_ == 1) text("Open-Meteo.com", controls - 30, 26);
}
void InfoBoardActivity::render(RenderLock&&) {
  renderer.clearScreen();
  const auto& m = UITheme::getInstance().getMetrics();
  GUI.drawHeader(renderer, Rect{0, m.topPadding, renderer.getScreenWidth(), m.headerHeight}, tr(STR_INFO_BOARD));
  renderUi();
  renderer.displayBuffer();
}
