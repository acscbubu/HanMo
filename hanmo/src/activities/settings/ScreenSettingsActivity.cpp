#include "ScreenSettingsActivity.h"

#include <cstring>

#include "CrossPointSettings.h"
#include "ScreenSettingsPolicy.h"
#include "activities/boot_sleep/BootActivity.h"
#include "activities/boot_sleep/SleepActivity.h"
#include "activities/home/FileBrowserActivity.h"
#include "components/SubpageLayout.h"
#include "components/UITheme.h"
#include "util/ScreenImage.h"
namespace fui = freeink::ui;
namespace {
constexpr StrId TITLES[] = {StrId::STR_SCREEN_BOOT, StrId::STR_SCREEN_SHUTDOWN, StrId::STR_SLEEP_SCREEN};
constexpr StrId BOOT[] = {StrId::STR_SCREEN_DEFAULT, StrId::STR_CUSTOM_IMAGE, StrId::STR_SCREEN_HIDDEN};
constexpr StrId SHUTDOWN[] = {StrId::STR_SCREEN_FOLLOW_SLEEP, StrId::STR_SCREEN_DEFAULT, StrId::STR_CUSTOM_IMAGE,
                              StrId::STR_SCREEN_BLANK};
constexpr StrId SLEEP[] = {StrId::STR_DARK,         StrId::STR_LIGHT,      StrId::STR_CUSTOM,
                           StrId::STR_COVER,        StrId::STR_NONE_OPT,   StrId::STR_COVER_CUSTOM,
                           StrId::STR_QUICK_RESUME, StrId::STR_TRANSPARENT};
constexpr StrId FIT[] = {StrId::STR_FIT, StrId::STR_CROP};
constexpr StrId FILTER[] = {StrId::STR_NONE_OPT, StrId::STR_FILTER_CONTRAST, StrId::STR_INVERTED};
constexpr StrId TOGGLE[] = {StrId::STR_STATE_OFF, StrId::STR_STATE_ON};
constexpr StrId CONFIRM_OPTIONS[] = {StrId::STR_OK_BUTTON};
uint8_t& mode(int screen) {
  return screen == 0 ? SETTINGS.bootScreen : screen == 1 ? SETTINGS.shutdownScreen : SETTINGS.sleepScreen;
}
char* imagePath(int screen) {
  return screen == 0   ? SETTINGS.bootScreenImage
         : screen == 1 ? SETTINGS.shutdownScreenImage
                       : SETTINGS.sleepScreenImage;
}
const StrId* options(int screen) { return screen == 0 ? BOOT : screen == 1 ? SHUTDOWN : SLEEP; }
int optionCount(int screen) { return screen == 0 ? 3 : screen == 1 ? 4 : 8; }
const char* modeLabel(int screen) {
  const auto index = mode(screen);
  return I18N.get(options(screen)[index < optionCount(screen) ? index : 0]);
}
}  // namespace
ScreenSettingsActivity::ScreenSettingsActivity(GfxRenderer& renderer, MappedInputManager& input, int screen)
    : UiListActivity("ScreenSettings", renderer, input), screen_(screen >= 0 && screen <= 2 ? screen : -1) {}
const char* ScreenSettingsActivity::headerTitle() const {
  return screen_ < 0 ? tr(STR_SCREEN_SETTINGS) : I18N.get(TITLES[screen_]);
}
void ScreenSettingsActivity::onEnter() {
  refreshRows();
  UiListActivity::onEnter();
}
void ScreenSettingsActivity::refreshRows() {
  for (int i = 0; i < listCount(); ++i) {
    rows_[i] = {};
    rows_[i].actionValue = static_cast<int16_t>(i);
    if (screen_ < 0) {
      rows_[i].label = I18N.get(TITLES[i]);
      rows_[i].subtitle = modeLabel(i);
    }
  }
  if (screen_ < 0) return;
  rows_[0].label = tr(STR_SCREEN_MODE);
  rows_[0].subtitle = modeLabel(screen_);
  rows_[1].label = tr(STR_SCREEN_SELECT_IMAGE);
  rows_[1].subtitle = *imagePath(screen_) ? imagePath(screen_) : tr(STR_SCREEN_IMAGE_HINT);
  rows_[2].label = tr(STR_SCREEN_PREVIEW);
  rows_[2].subtitle = tr(STR_SCREEN_PREVIEW_HINT);
  if (screen_ == 2) {
    rows_[3].label = tr(STR_SLEEP_COVER_MODE);
    rows_[3].subtitle = I18N.get(FIT[SETTINGS.sleepScreenCoverMode < 2 ? SETTINGS.sleepScreenCoverMode : 0]);
    rows_[4].label = tr(STR_SLEEP_COVER_FILTER);
    rows_[4].subtitle = I18N.get(FILTER[SETTINGS.sleepScreenCoverFilter < 3 ? SETTINGS.sleepScreenCoverFilter : 0]);
    rows_[5].label = tr(STR_QUICK_RESUME_TIMEOUT);
    rows_[5].subtitle = I18N.get(TOGGLE[SETTINGS.quickResumeSleepScreen ? 1 : 0]);
  }
}
void ScreenSettingsActivity::notice(StrId message) {
  popup_.show(message, CONFIRM_OPTIONS, 1, 0, [](int) {});
  requestUpdate();
}
void ScreenSettingsActivity::setValue(uint8_t& value, uint8_t next, bool sleepMode) {
  const uint8_t previous = value, previousQuick = SETTINGS.quickResumeSleepScreen;
  value = next;
  // Explicitly selecting a picture/cover must take precedence over quick-resume timeout.
  if (sleepMode) SETTINGS.quickResumeSleepScreen = next == CrossPointSettings::QUICK_RESUME ? 1 : 0;
  if (!SETTINGS.saveToFile()) {
    value = previous;
    SETTINGS.quickResumeSleepScreen = previousQuick;
    notice(StrId::STR_SETTINGS_SAVE_FAILED);
  }
  refreshRows();
  requestUpdate();
}
void ScreenSettingsActivity::chooseImage() {
  app.clearTapFlash();
  if (!startActivityForResultWith<FileBrowserActivity>(
          [this](const ActivityResult& result) {
            if (result.isCancelled) {
              requestUpdate();
              return;
            }
            const auto* file = std::get_if<FilePathResult>(&result.data);
            if (!file || !ScreenImage::valid(file->path.c_str())) {
              notice(StrId::STR_INVALID_IMAGE_FILE);
              return;
            }
            char previousPath[ScreenSettingsPolicy::PATH_BYTES];
            char* target = imagePath(screen_);
            memcpy(previousPath, target, sizeof(previousPath));
            const uint8_t previousMode = mode(screen_), previousQuick = SETTINGS.quickResumeSleepScreen;
            memcpy(target, file->path.c_str(), file->path.size() + 1);
            mode(screen_) = screen_ == 0   ? ScreenSettingsPolicy::BootCustom
                            : screen_ == 1 ? static_cast<uint8_t>(ScreenSettingsPolicy::ShutdownCustom)
                                           : static_cast<uint8_t>(CrossPointSettings::CUSTOM);
            if (screen_ == 2) SETTINGS.quickResumeSleepScreen = 0;
            if (!SETTINGS.saveToFile()) {
              memcpy(target, previousPath, sizeof(previousPath));
              mode(screen_) = previousMode;
              SETTINGS.quickResumeSleepScreen = previousQuick;
              notice(StrId::STR_SETTINGS_SAVE_FAILED);
            }
            refreshRows();
            requestUpdate();
          },
          "/", FileBrowserActivity::Mode::PickBmp))
    notice(StrId::STR_MEMORY_ERROR);
}
void ScreenSettingsActivity::preview() {
  // Preview only draws. It does not call enterDeepSleep, change OTA slots or reboot.
  app.clearTapFlash();
  auto resumed = [this](const ActivityResult&) {
    refreshRows();
    requestUpdate();
  };
  const bool started = screen_ == 0 ? startActivityForResultWith<BootActivity>(resumed, BootActivity::Mode::Preview)
                                    : startActivityForResultWith<SleepActivity>(resumed, screen_ == 2, true);
  if (!started) notice(StrId::STR_MEMORY_ERROR);
}
void ScreenSettingsActivity::activateIndex(int index) {
  if (index < 0 || index >= listCount()) return;
  if (screen_ < 0) {
    app.clearTapFlash();
    if (!startActivityForResultWith<ScreenSettingsActivity>(
            [this](const ActivityResult&) {
              refreshRows();
              requestUpdate();
            },
            index))
      notice(StrId::STR_MEMORY_ERROR);
    return;
  }
  if (index == 1) {
    chooseImage();
    return;
  }
  if (index == 2) {
    preview();
    return;
  }
  if (index == 0) {
    popup_.show(TITLES[screen_], options(screen_), optionCount(screen_), mode(screen_), [this](int selected) {
      if ((screen_ == 0 && selected == ScreenSettingsPolicy::BootCustom) ||
          (screen_ == 1 && selected == ScreenSettingsPolicy::ShutdownCustom)) {
        if (!ScreenImage::valid(imagePath(screen_))) {
          chooseImage();
          return;
        }
      }
      setValue(mode(screen_), selected, screen_ == 2);
    });
  } else if (index == 3) {
    popup_.show(StrId::STR_SLEEP_COVER_MODE, FIT, 2, SETTINGS.sleepScreenCoverMode,
                [this](int i) { setValue(SETTINGS.sleepScreenCoverMode, i); });
  } else if (index == 4) {
    popup_.show(StrId::STR_SLEEP_COVER_FILTER, FILTER, 3, SETTINGS.sleepScreenCoverFilter,
                [this](int i) { setValue(SETTINGS.sleepScreenCoverFilter, i); });
  } else {
    popup_.show(StrId::STR_QUICK_RESUME_TIMEOUT, TOGGLE, 2, SETTINGS.quickResumeSleepScreen,
                [this](int i) { setValue(SETTINGS.quickResumeSleepScreen, i); });
  }
  requestUpdate();
}
bool ScreenSettingsActivity::handleCustomInput() {
  return popup_.handleInput(mappedInput, [this] { requestUpdate(); });
}
void ScreenSettingsActivity::render(RenderLock&& lock) {
  if (popup_.processRender(renderer, mappedInput)) return;
  UiListActivity::render(std::move(lock));
}
void ScreenSettingsActivity::buildScreen(UiScreen& screen) {
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
