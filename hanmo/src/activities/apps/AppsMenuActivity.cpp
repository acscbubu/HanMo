#include "components/UIScale.h"
#include "AppsMenuActivity.h"

#include <I18n.h>

#include <algorithm>
#include <cstdint>
#include <string>

#include "CrossPointSettings.h"
#include "InxItemLayout.h"
#include "OpdsServerStore.h"
#include "components/UITheme.h"
#include "components/UiAppHelpers.h"
#include "components/icons/inx_apps.h"
#include "fontIds.h"

namespace fui = freeink::ui;

namespace {

// The games all live in the shelf's Games folder now; what is left here is
// the apps. The AppId values they used are retired in place rather than
// renumbered, because each is a persisted bit in hiddenAppsMask.
//
// Single source of truth for the Apps menu — add a new app here, then provide the
// matching `goTo<App>()` in ActivityManager and assign a stable, never-reused AppId.
enum class AppId : uint8_t {
  ReadingStats = 0,
  WeRead = 1,
  Sudoku = 2,
  Gomoku = 3,
  ChineseChess = 4,
  Minesweeper = 5,
  Game2048 = 6,
  UglyAvatar = 7,
  Standby = 8,
  AirPage = 9,
  // 10 was Buddy. Never reused: the value is a persisted bit.
  Sokoban = 11,
  PixelSwitch = 12,
  FileTransfer = 13,
  OpdsBrowser = 14,
  Calculator = 15,
  Woodfish = 16,
  ShelfGames = 17,
  // 18 was ShelfApps. Never reused: the value is a persisted bit.
  // 19 retired in the public edition; never reuse its persisted bit.
  AirNote = 20,
  // 21 was the retired network-lighting trial. Never reuse its persisted bit.
  AirPhoto = 22,
  InfoBoard = 23,
  JapaneseLearning = 24,
  Count = 25,
};

struct AppEntry {
  AppId id;
  StrId titleId;
  UIIcon icon;
  void (ActivityManager::*open)();
};

constexpr AppEntry kAppEntries[] = {
    {AppId::JapaneseLearning, StrId::STR_JP_LEARNING, UIIcon::Text, &ActivityManager::goToJapaneseLearning},
    {AppId::FileTransfer, StrId::STR_FILE_TRANSFER, UIIcon::Transfer, &ActivityManager::goToFileTransfer},
    {AppId::OpdsBrowser, StrId::STR_OPDS_BROWSER, UIIcon::Opds, &ActivityManager::goToBrowser},
#ifdef ENABLE_CHINESE_VERSION
    {AppId::WeRead, StrId::STR_WEREAD_TITLE, UIIcon::WeRead, &ActivityManager::goToWeRead},
#endif
    {AppId::AirPage, StrId::STR_AIRPAGE_TITLE, UIIcon::AirPage, &ActivityManager::goToAirPage},
    {AppId::ReadingStats, StrId::STR_READING_STATS, UIIcon::ReadingStats, &ActivityManager::goToReadingStatsMenu},
    {AppId::Calculator, StrId::STR_CALCULATOR_TITLE, UIIcon::Calculator, &ActivityManager::goToCalculator},
    {AppId::Standby, StrId::STR_STANDBY_TITLE, UIIcon::Standby, &ActivityManager::goToStandby},
    {AppId::InfoBoard, StrId::STR_INFO_BOARD, UIIcon::ReadingStats, &ActivityManager::goToInfoBoard},
    {AppId::AirNote, StrId::STR_AIRNOTE_TITLE, UIIcon::Text, &ActivityManager::goToAirNote},
    {AppId::AirPhoto, StrId::STR_AIRPHOTO_TITLE, UIIcon::Image, &ActivityManager::goToAirPhoto},
    // The shelf, as one row rather than twenty-one more entries: this menu is
    // one screen deep by design and the shelf is already two levels.
    {AppId::ShelfGames, StrId::STR_SHELF_GAMES, UIIcon::Game2048, &ActivityManager::goToShelfGames},
};

constexpr int kAppCount = static_cast<int>(sizeof(kAppEntries) / sizeof(kAppEntries[0]));

constexpr uint32_t appBit(const AppId id) { return uint32_t{1} << static_cast<uint8_t>(id); }

constexpr int visibleAppCount(const uint32_t hiddenMask) {
  int count = 0;
  for (const auto& app : kAppEntries) {
    if ((hiddenMask & appBit(app.id)) == 0) {
      // cppcheck-suppress useStlAlgorithm
      ++count;
    }
  }
  return count;
}

constexpr int catalogIndexOf(const uint8_t id) {
  for (int i = 0; i < kAppCount; ++i) {
    if (static_cast<uint8_t>(kAppEntries[i].id) == id) return i;
  }
  return -1;
}

// The catalog index at `position` of the user's order.
//
// Walks the stored IDs first, then any catalog app the stored order does not
// mention. That tail is not a tidy-up: a firmware that adds an app has to put
// it somewhere, and the alternatives are dropping it (invisible, unreachable)
// or rewriting the user's order behind their back. It goes on the end, where
// it is findable and movable.
//
// A stored ID the catalog no longer has -- Buddy, ShelfApps -- resolves to -1
// and is skipped, which is why retired IDs are never reused.
int orderedCatalogIndex(const int position) {
  if (position < 0 || position >= kAppCount) return -1;
  int seen = 0;
  for (uint8_t i = 0; i < SETTINGS.appOrderCount; ++i) {
    const int index = catalogIndexOf(SETTINGS.appOrder[i]);
    if (index < 0) continue;
    if (seen++ == position) return index;
  }
  for (int index = 0; index < kAppCount; ++index) {
    bool listed = false;
    for (uint8_t i = 0; i < SETTINGS.appOrderCount; ++i) {
      listed = listed || SETTINGS.appOrder[i] == static_cast<uint8_t>(kAppEntries[index].id);
    }
    if (listed) continue;
    if (seen++ == position) return index;
  }
  return -1;
}

int appIndexForVisibleIndex(const uint32_t hiddenMask, const int visibleIndex) {
  int visible = 0;
  for (int position = 0; position < kAppCount; ++position) {
    const int appIndex = orderedCatalogIndex(position);
    if (appIndex < 0 || (hiddenMask & appBit(kAppEntries[appIndex].id)) != 0) continue;
    if (visible++ == visibleIndex) return appIndex;
  }
  return -1;
}

constexpr uint32_t effectiveHiddenMask(const uint32_t hiddenMask, const bool hasOpdsServers,
                                       const bool readsChinese) {
  uint32_t effective = hiddenMask;
  if (!hasOpdsServers) effective |= appBit(AppId::OpdsBrowser);
  if (!readsChinese) effective |= CrossPointSettings::CHINESE_LANGUAGE_APPS_MASK;
  return effective;
}

constexpr bool appIdsAreUnique() {
  for (int i = 0; i < kAppCount; ++i) {
    for (int j = i + 1; j < kAppCount; ++j) {
      if (kAppEntries[i].id == kAppEntries[j].id) return false;
    }
  }
  return true;
}

static_assert(kAppCount <= 32, "the app catalog must fit hiddenAppsMask");
static_assert(static_cast<uint8_t>(AppId::Count) <= 32, "hiddenAppsMask supports at most 32 stable app IDs");
static_assert(static_cast<uint8_t>(AppId::PixelSwitch) == CrossPointSettings::PIXEL_SWITCH_APP_ID,
              "the Pixel Switch app ID must remain stable");
static_assert(static_cast<uint8_t>(AppId::Calculator) == 15, "the Calculator app ID must remain stable");
static_assert(static_cast<uint8_t>(AppId::Woodfish) == 16, "the Woodfish app ID must remain stable");
static_assert(appBit(AppId::Woodfish) == (uint32_t{1} << 16), "Woodfish visibility must use the first widened bit");
static_assert(appIdsAreUnique(), "stable app IDs must not be reused");
static_assert(CrossPointSettings::DEFAULT_HIDDEN_APPS_MASK == 0,
              "this build ships only the wanted apps, so none of them start hidden");
static_assert(visibleAppCount(0) == kAppCount, "a zero mask must show every compiled app");
static_assert(visibleAppCount(UINT32_MAX) == 0, "a full mask must hide every compiled app");
static_assert(visibleAppCount(appBit(AppId::Calculator)) == kAppCount - 1,
              "hiding one catalog app must drop the visible count by one");
static_assert(visibleAppCount(effectiveHiddenMask(0, false, true)) == kAppCount - 1,
              "OPDS must be hidden when no server is configured");
static_assert(visibleAppCount(effectiveHiddenMask(0, true, false)) == kAppCount - 1,
              "a non-Chinese UI must hide WeRead");
static_assert(visibleAppCount(effectiveHiddenMask(0, true, true)) == kAppCount,
              "a Chinese UI must show them, Traditional included");
// appIndexForVisibleIndex now reads SETTINGS.appOrder, so it is no longer a
// constant expression. Its skip-the-hidden half is the tested part and is
// still covered by visibleAppCount's asserts above.
#if 0
static_assert(appIndexForVisibleIndex(appBit(kAppEntries[1].id), 1) == 2,
              "visible indices must skip a hidden middle app");
#endif

}  // namespace

int AppsMenuActivity::getAppCount() { return kAppCount; }

int AppsMenuActivity::getAppIndexAt(const int position) { return orderedCatalogIndex(position); }

bool AppsMenuActivity::moveAppTo(const int from, const int to) {
  if (from == to || from < 0 || from >= kAppCount || to < 0 || to >= kAppCount) return false;

  // Normalise the stored order to the order actually on screen before moving
  // anything. An empty list is a device that has never been reordered and gets
  // seeded; a list written before the catalog grew gets the new app appended.
  //
  // The second case is the one that bites. orderedCatalogIndex puts an unlisted
  // app on the end, so it renders and looks draggable, but its position is past
  // the stored count and the bounds check below rejects it: visible and immovable,
  // which is a worse answer than either. Retired IDs drop out here for the same
  // reason they are skipped when reading -- they resolve to no catalog entry.
  //
  // Reading the whole order before writing any of it matters: orderedCatalogIndex
  // consults appOrderCount, so growing the list mid-walk would move the boundary
  // it is being walked against.
  uint8_t ordered[CrossPointSettings::APP_ORDER_CAPACITY];
  uint8_t ordering = 0;
  for (int i = 0; i < kAppCount && ordering < CrossPointSettings::APP_ORDER_CAPACITY; ++i) {
    const int index = orderedCatalogIndex(i);
    if (index < 0) continue;
    ordered[ordering++] = static_cast<uint8_t>(kAppEntries[index].id);
  }
  for (uint8_t i = 0; i < ordering; ++i) SETTINGS.appOrder[i] = ordered[i];
  SETTINGS.appOrderCount = ordering;

  if (from >= SETTINGS.appOrderCount || to >= SETTINGS.appOrderCount) return false;

  // Remove and re-insert, not swap. A swap would drag whatever sat at the
  // destination back to where the moved app came from, which is not what
  // "put this here" means to anyone holding the thing.
  const uint8_t moved = SETTINGS.appOrder[from];
  if (from < to) {
    for (int i = from; i < to; ++i) SETTINGS.appOrder[i] = SETTINGS.appOrder[i + 1];
  } else {
    for (int i = from; i > to; --i) SETTINGS.appOrder[i] = SETTINGS.appOrder[i - 1];
  }
  SETTINGS.appOrder[to] = moved;
  return true;
}

StrId AppsMenuActivity::getAppTitleId(const int appIndex) {
  return appIndex >= 0 && appIndex < kAppCount ? kAppEntries[appIndex].titleId : StrId::STR_NONE_OPT;
}

bool AppsMenuActivity::isAppVisible(const int appIndex) {
  if (appIndex < 0 || appIndex >= kAppCount) return false;
  const uint32_t hidden = effectiveHiddenMask(SETTINGS.hiddenAppsMask, true, SETTINGS.readsChinese());
  return (hidden & appBit(kAppEntries[appIndex].id)) == 0;
}

bool AppsMenuActivity::setAppVisible(const int appIndex, const bool visible) {
  if (appIndex < 0 || appIndex >= kAppCount) return false;

  const uint32_t bit = appBit(kAppEntries[appIndex].id);
  const uint32_t updatedMask = visible ? SETTINGS.hiddenAppsMask & ~bit : SETTINGS.hiddenAppsMask | bit;
  if (updatedMask == SETTINGS.hiddenAppsMask) return false;

  SETTINGS.hiddenAppsMask = updatedMask;
  return true;
}

int AppsMenuActivity::getVisibleAppCount() {
  return visibleAppCount(
      effectiveHiddenMask(SETTINGS.hiddenAppsMask, OPDS_STORE.hasServers(), SETTINGS.readsChinese()));
}

void AppsMenuActivity::selectMainTabContentEdge(const MainTabContentEdge edge) {
  nav.selected = MainTabs::contentEdgeIndex(edge, getVisibleAppCount());
  nav.follow(getVisibleAppCount());
}

int AppsMenuActivity::getAppIndexForVisibleIndex(const int visibleIndex) {
  return appIndexForVisibleIndex(
      effectiveHiddenMask(SETTINGS.hiddenAppsMask, OPDS_STORE.hasServers(), SETTINGS.readsChinese()), visibleIndex);
}

void AppsMenuActivity::onEnter() {
  UiListActivity::onEnter();
  rebuildRowItems();
}

void AppsMenuActivity::rebuildRowItems() {
  rowItems.clear();
  rowItems.reserve(static_cast<size_t>(getVisibleAppCount()));
  for (int visibleIndex = 0; visibleIndex < getVisibleAppCount(); ++visibleIndex) {
    const int appIndex = getAppIndexForVisibleIndex(visibleIndex);
    if (appIndex < 0) continue;
    fui::ListItem item;
    item.label = I18N.get(kAppEntries[appIndex].titleId);
    // The INX app assets are canonical, MSB-first Mask1 bitmaps, like SDK list icons.
    item.icon.data = InxAppIcons::get(kAppEntries[appIndex].icon);
    item.icon.width = InxAppIcons::size;
    item.icon.height = InxAppIcons::size;
    item.icon.format = fui::BitmapFormat::Mask1;
    item.actionValue = static_cast<int16_t>(visibleIndex);
    rowItems.push_back(item);
  }
}

bool AppsMenuActivity::usesIconLayout() const {
  return UITheme::getInstance().hasMainTabs() &&
         InxGridGeometry::layoutFrom(SETTINGS.inxAppsLayout) == InxItemLayout::Icons;
}

int AppsMenuActivity::iconIndexFromPoint(const int x, const int y) const {
  const auto& metrics = UITheme::getInstance().getMetrics();
  const int top = metrics.topPadding + metrics.headerHeight + metrics.verticalSpacing;
  const int height = renderer.getScreenHeight() - top - metrics.buttonHintsHeight - metrics.verticalSpacing;
  return InxGridGeometry::indexFromPoint(x, y - top, renderer.getScreenWidth(), height,
                                         InxGridGeometry::pageStart(nav.selected, getVisibleAppCount()),
                                         getVisibleAppCount());
}

void AppsMenuActivity::openSelected() {
  const int appIndex = getAppIndexForVisibleIndex(nav.selected);
  if (appIndex >= 0) (activityManager.*kAppEntries[appIndex].open)();
}

void AppsMenuActivity::activateIndex(const int index) {
  app.clearTapFlash();
  nav.selected = index;
  openSelected();
}

bool AppsMenuActivity::handleCustomInput() {
  if (!usesIconLayout()) return false;

  const int visibleCount = getVisibleAppCount();
  int x = 0;
  int y = 0;
  if (mappedInput.wasScreenTouchDown(x, y)) {
    const int touched = iconIndexFromPoint(x, y);
    if (touched >= 0 && touched != nav.selected) {
      nav.selected = touched;
      requestUpdate();
    }
    return true;
  }
  if (mappedInput.wasScreenTapped(x, y)) {
    const int touched = iconIndexFromPoint(x, y);
    if (touched >= 0) {
      nav.selected = touched;
      openSelected();
    }
    return true;
  }
  const auto swipe = mappedInput.wasSwipe();
  if (swipe == MappedInputManager::SwipeDir::Up) {
    nav.selected = ButtonNavigator::nextPageIndex(nav.selected, visibleCount, InxGridGeometry::itemsPerPage);
    requestUpdate();
    return true;
  }
  if (swipe == MappedInputManager::SwipeDir::Down) {
    nav.selected = ButtonNavigator::previousPageIndex(nav.selected, visibleCount, InxGridGeometry::itemsPerPage);
    requestUpdate();
    return true;
  }
  return false;
}

void AppsMenuActivity::drawIconGrid(const Rect& rect, const int visibleCount, const bool showSelection) const {
  const int start = InxGridGeometry::pageStart(nav.selected, visibleCount);
  const int cellWidth = rect.width / InxGridGeometry::columns;
  const int cellHeight = rect.height / InxGridGeometry::rows;
  const int lineHeight = renderer.getLineHeight(uiScaleSpec().bodyFontId);
  constexpr int iconScale = 2;
  constexpr int iconSize = InxAppIcons::size * iconScale;

  for (int slot = 0; slot < InxGridGeometry::itemsPerPage && start + slot < visibleCount; ++slot) {
    const int visibleIndex = start + slot;
    const int appIndex = getAppIndexForVisibleIndex(visibleIndex);
    if (appIndex < 0) continue;
    const int column = slot % InxGridGeometry::columns;
    const int row = slot / InxGridGeometry::columns;
    const Rect cell{rect.x + column * cellWidth + 4, rect.y + row * cellHeight + 4, cellWidth - 8, cellHeight - 8};
    const bool isSelected = showSelection && visibleIndex == nav.selected;
    if (isSelected) renderer.fillRect(cell.x, cell.y, cell.width, cell.height, true);

    const int iconX = cell.x + (cell.width - iconSize) / 2;
    const int iconY = cell.y + std::max(5, (cell.height - iconSize - lineHeight - 8) / 2);
    InxAppIcons::draw(renderer, kAppEntries[appIndex].icon, iconX, iconY, iconScale, isSelected);
    const std::string label =
        renderer.truncatedText(uiScaleSpec().bodyFontId, I18N.get(kAppEntries[appIndex].titleId), std::max(1, cell.width - 8));
    const int labelX = cell.x + (cell.width - renderer.getTextWidth(uiScaleSpec().bodyFontId, label.c_str())) / 2;
    renderer.drawText(uiScaleSpec().bodyFontId, labelX, iconY + iconSize + 8, label.c_str(), !isSelected);
  }

  GUI.drawSideScrollBar(renderer, rect, visibleCount, start, InxGridGeometry::itemsPerPage);
}

void AppsMenuActivity::buildScreen(UiScreen& screen) {
  const auto& metrics = UITheme::getInstance().getMetrics();
  const int sw = renderer.getScreenWidth();
  const int sh = renderer.getScreenHeight();
  const int listY = metrics.topPadding + metrics.headerHeight + metrics.verticalSpacing;
  const int listH = sh - listY - metrics.buttonHintsHeight - metrics.verticalSpacing;
  const int visibleCount = getVisibleAppCount();
  const bool showSelection = showMainTabContentSelection();

  if (visibleCount == 0) {
    UITheme::drawCenteredWrappedText(renderer, Rect{0, listY, sw, listH}, uiScaleSpec().bodyFontId, tr(STR_NO_APPS_ENABLED), 2);
  } else if (usesIconLayout()) {
    drawIconGrid(Rect{0, listY, sw, listH}, visibleCount, showSelection);
  } else {
    const Rect safe = UITheme::getInstance().getScreenSafeArea(renderer, true, false);
    screen.setContentMargin(fui::Insets{static_cast<int16_t>(listY), static_cast<int16_t>(sw - (safe.x + safe.width)),
                                        static_cast<int16_t>(sh - (safe.y + safe.height)),
                                        static_cast<int16_t>(safe.x)});
    fui::ListProps props;
    props.items = rowItems.data();
    props.count = static_cast<uint16_t>(rowItems.size());
    props.action = ACTION_ROW;
    props.inputMask = fui::InputTouch;
    syncListViewport(screen, props);
    screen.list(props);
  }
}

void AppsMenuActivity::drawChrome() {
  const auto& metrics = UITheme::getInstance().getMetrics();
  drawPageHeader(Rect{0, metrics.topPadding, renderer.getScreenWidth(), metrics.headerHeight}, tr(STR_APPS_TITLE));
}

void AppsMenuActivity::drawFooter() {
  const int visibleCount = getVisibleAppCount();
  const auto labels = mainTabButtonLabels(tr(STR_BACK), tr(STR_SELECT), visibleCount > 1);
  GUI.drawButtonHints(renderer, labels.btn1, labels.btn2, labels.btn3, labels.btn4);
}

void AppsMenuActivity::onBackButton() { activityManager.goHome(); }
