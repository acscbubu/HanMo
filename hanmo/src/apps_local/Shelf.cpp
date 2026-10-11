#include "Shelf.h"

#include <HalStorage.h>
#include <Logging.h>
#include <strings.h>

#include <cstdio>
#include <cstdlib>
#include <string>

#include "../activities/ActivityManager.h"
#include "../activities/apps/2048/Game2048Activity.h"
#include "../activities/apps/gomoku/GomokuMenuActivity.h"
#include "../activities/apps/pixel-switch/PixelSwitchActivity.h"
#include "../activities/apps/sokoban/SokobanGameActivity.h"
#include "../activities/apps/sudoku/SudokuMenuActivity.h"
#ifdef ENABLE_CHINESE_VERSION
#include "../activities/apps/chinese-chess/ChineseChessMenuActivity.h"
#endif
#include "../components/icons/inx_apps.h"
#include "ShelfFolderActivity.h"
#include "ShelfGamePrefs.h"
#include "ShelfHidden.h"
#include "ShelfState.h"
#include "battleship/BattleshipActivity.h"
#include "checkers/CheckersActivity.h"
#include "connectfour/ConnectFourActivity.h"
#include "connections/ConnectionsActivity.h"
#include "dungeon/DungeonActivity.h"
#include "forehead/ForeheadActivity.h"
#include "go/GoActivity.h"
#include "imported_minesweeper/ImportedMinesweeperActivity.h"
#include "insider/InsiderActivity.h"
#include "jaipur/JaipurActivity.h"
#include "knucklebones/KnucklebonesActivity.h"
#include "memory/MemoryActivity.h"
#include "reversi/ReversiActivity.h"
#include "slidepuzzle/SlidePuzzleActivity.h"
#include "mahjong/MahjongActivity.h"
#include "backgammon/BackgammonActivity.h"
#include "tilerummy/TileRummyActivity.h"
#include "picross/PicrossActivity.h"
#include "player/PlayerActivity.h"
#include "seasalt/SeaSaltActivity.h"
#include "solitaire/SolitaireActivity.h"
#include "toybattle/ToyBattleActivity.h"
#include "ui/ToyboxIcons.h"
#include "wavelength/WavelengthActivity.h"
#include "yahtzee/YahtzeeActivity.h"

namespace {

// This firmware's own games, which were loose rows on the Apps menu until the
// folder existed to hold them. Two things they need that the imported ones
// bring with them:
//
//   * a create() of the shape Item wants. Upstream activities are opened
//     through ActivityManager::replaceActivityWith<T>, so there is no static
//     factory to point at; make<T> is that factory, once, for all of them.
//   * an icon as a freeink::Icon. Their art is the 32x32 INX app grid, which
//     stores a bare std::array, so each is wrapped with the geometry the
//     renderer needs. Optical centre is the middle: these are drawn on a grid,
//     not on a baseline.
//
// Titles are the raw uppercase the rest of the folder uses, NOT tr(). Two
// reasons, and either alone would settle it. Item::title is the identity the
// hidden-items file and the resume-on-wake state are keyed on, so a
// translated one would orphan both the moment the language changed. And the
// folder draws its rows in the toybox typeface, which is Latin-only at 20pt
// while the built-in CJK tops out at 12 -- a Chinese label here would be
// blank boxes, or a glyph eight points short of its neighbours.
template <typename T>
std::unique_ptr<Activity> make(GfxRenderer& renderer, MappedInputManager& mappedInput) {
  return makeUniqueNoThrow<T>(renderer, mappedInput);
}

std::unique_ptr<Activity> makeBiscuitMinesweeper(GfxRenderer& renderer, MappedInputManager& mappedInput) {
  return makeUniqueNoThrow<ImportedMinesweeperActivity>(renderer, mappedInput, imported_minesweeper::Variant::Biscuit);
}

constexpr freeink::Icon inxIcon(const InxAppIcons::Icon& art) {
  return freeink::Icon{InxAppIcons::size, InxAppIcons::size, InxAppIcons::size / 2, art.data()};
}

constexpr freeink::Icon icon_inx_sudoku = inxIcon(InxAppIcons::Sudoku);
constexpr freeink::Icon icon_inx_gomoku = inxIcon(InxAppIcons::Gomoku);
constexpr freeink::Icon icon_inx_sokoban = inxIcon(InxAppIcons::Sokoban);
constexpr freeink::Icon icon_inx_2048 = inxIcon(InxAppIcons::Game2048);
constexpr freeink::Icon icon_inx_pixelswitch = inxIcon(InxAppIcons::PixelSwitch);
constexpr freeink::Icon icon_inx_minesweeper = inxIcon(InxAppIcons::Minesweeper);
#ifdef ENABLE_CHINESE_VERSION
constexpr freeink::Icon icon_inx_chinesechess = inxIcon(InxAppIcons::ChineseChess);
#endif

// Icons come from tools_local/toybox/icons.txt via Lucide. Picked for silhouette
// rather than literalness: a crown, a hull, a grid and a card suit share no
// shape, so a row is scannable before the label is read.
constexpr shelf::Item kGames[] = {
    {"BATTLESHIP", &icon_battleship_32, &BattleshipActivity::create},
    {"CONNECTIONS", &icon_connections_32, &ConnectionsActivity::create},
    {"SOLITAIRE", &icon_solitaire_32, &SolitaireActivity::create},
    {"D&DIAGRAMS", &icon_dungeon_32, &DungeonActivity::create},
    {"INSIDER", &icon_insider_32, &InsiderActivity::create},
    {"JAIPUR", &icon_jaipur_32, &JaipurActivity::create},
    {"SEA SALT", &icon_seasalt_32, &SeaSaltActivity::create},
    {"CHECKERS", &icon_checkers_32, &CheckersActivity::create},
    {"CONNECT FOUR", &icon_connectfour_32, &ConnectFourActivity::create},
    {"YAHTZEE", &icon_yahtzee_32, &YahtzeeActivity::create},
    {"KNUCKLEBONES", &icon_knucklebones_32, &KnucklebonesActivity::create},
    {"PICROSS", &icon_picross_32, &PicrossActivity::create},
    {"TOY BATTLE", &icon_toybattle_32, &ToyBattleActivity::create},
    {"FOREHEAD", &icon_forehead_32, &ForeheadActivity::create},
    {"WAVELENGTH", &icon_wavelength_32, &WavelengthActivity::create},
    {"GO", &icon_go_32, &GoActivity::create},
    {"SUDOKU", &icon_inx_sudoku, &make<SudokuMenuActivity>},
    {"GOMOKU", &icon_inx_gomoku, &make<GomokuMenuActivity>},
    {"SOKOBAN", &icon_inx_sokoban, &make<SokobanGameActivity>},
#ifdef ENABLE_CHINESE_VERSION
    {"CHINESE CHESS", &icon_inx_chinesechess, &make<ChineseChessMenuActivity>},
#endif
    {"2048", &icon_inx_2048, &make<Game2048Activity>},
    {"PIXEL SWITCH", &icon_inx_pixelswitch, &make<PixelSwitchActivity>},
    {"MINESWEEPER BISCUIT", &icon_inx_minesweeper, &makeBiscuitMinesweeper},
    {"MEMORY MATCH", &icon_memory_32, &MemoryActivity::create},
    {"REVERSI", &icon_reversi_32, &ReversiActivity::create},
    {"SLIDE PUZZLE", &icon_slidepuzzle_32, &SlidePuzzleActivity::create},
    {"MAHJONG SOLITAIRE", &icon_mahjong_32, &MahjongActivity::create},
    {"BACKGAMMON", &icon_backgammon_32, &BackgammonActivity::create},
    {"TILE RUMMY", &icon_tilerummy_32, &TileRummyActivity::create},
};

// The two rows Home grows, in reading order. Titles are Title Case because
// these sit in upstream's Home list and have to look like it; the folder screen
// shouts its own header, which is our side of the line. A third folder is one row here and
// nothing else: the Home hook counts this table rather than knowing its length.
constexpr shelf::Folder kFolders[] = {
    {"Games", UIIcon::Game2048, &icon_games_32, kGames, static_cast<int>(sizeof(kGames) / sizeof(shelf::Item)), true},
};

constexpr int kFolderCount = static_cast<int>(sizeof(kFolders) / sizeof(kFolders[0]));
constexpr int kGameFolder = 0;
constexpr int kGameCount = static_cast<int>(sizeof(kGames) / sizeof(kGames[0]));
static_assert(kGameCount <= shelf::GamePrefs::kMaxGames, "raise GamePrefs::kMaxGames before adding games");

// An item with no icon draws a blank gutter and nothing says so. Caught at
// compile time rather than in a test, because a test can be forgotten and this
// cannot: a new row without an icon does not build.
constexpr bool everyItemHasAnIcon() {
  for (const auto& folder : kFolders) {
    for (int i = 0; i < folder.count; ++i) {
      if (folder.items[i].icon == nullptr) return false;
    }
  }
  return true;
}
static_assert(everyItemHasAnIcon(), "every shelf item needs an icon; see tools_local/toybox/icons.txt");

constexpr bool everyFolderHasAMark() {
  for (const auto& folder : kFolders) {
    if (folder.mark == nullptr) return false;
  }
  return true;
}
static_assert(everyFolderHasAMark(), "every shelf folder needs a mark; see tools_local/toybox/icons.txt");

// Beside the reader's own state and the player's name, so clearing
// `.crosspoint/` clears this too and there is one place to look. Inside the
// guard because the host build has no storage and an unused constant is a
// -Werror failure there.
#if defined(ARDUINO_ARCH_ESP32) || defined(SIMULATOR)
constexpr char kStatePath[] = "/.crosspoint/shelf.cfg";
// Beside it rather than inside it. The position is one short line a navigation
// rewrites constantly; this is a list that changes a handful of times in a
// device's life, and the two have no reason to share a write, a buffer or a
// parser -- shelf.cfg's is a fixed 96 bytes precisely because it is small.
constexpr char kHiddenPath[] = "/.crosspoint/shelf-hidden.cfg";
constexpr char kGamePrefsPath[] = "/.crosspoint/shelf-game-prefs.cfg";
constexpr char kGamePrefsBackup[] = "/.crosspoint/shelf-game-prefs.bak";
constexpr char kGamePrefsTemp[] = "/.crosspoint/shelf-game-prefs.tmp";
#endif

// Where leave() sends an app. Set when an item is opened, read when it leaves.
// -1 means "nothing is open below Home", which is what a folder itself sees.
int openFolderIndex = -1;

// The remembered position, mirroring /.crosspoint/shelf.cfg:
//
// - `lastFolder`: which shelf row Home should land on when you come back out.
//   CrossPoint restores Home's selection by matching the departing activity's
//   name against its own HomeMenuItem list, which cannot know about ours, so
//   without this you leave GAMES and the cursor is sitting on Browse Files.
// - `resumeRow`: per folder, the row it reopens on. The row of the item last
//   opened from it, or -- when you paged and then walked out without opening
//   anything -- the first row of the page you were looking at. It is the page
//   you were ON, not the page holding the game you last played; those are the
//   same thing until you browse and leave, and browsing and leaving is the case
//   that was wrong.
// - `openTitle`: the item that was open when the device went to sleep, which is
//   what wake reopens instead of dropping you on Home.
//
// All of it survives the device going to sleep, which none of it did before.
// `main.cpp` deep-sleeps on the idle timeout and says of it that wake is
// effectively a chip reset, so every time Mario put the device down and came
// back the shelf had forgotten which game he was playing.
//
// Written next to the reader's own state rather than into CrossPointState,
// which is upstream's file: a fork-local fact belongs in a fork-local file, and
// player.cfg already established the pattern.
shelf::State state;
bool stateLoaded = false;

// The items no folder shows, by title, mirroring shelf-hidden.cfg. Loaded on
// the first question anyone asks of it and not at boot, because the shelf has
// no init hook -- the same lazy load the position uses, for the same reason.
shelf::HiddenSet hiddenItems;
bool hiddenLoaded = false;

// Bounded live order and flags; only serialized titles cross firmware builds.
const char* gameTitles[kGameCount] = {};
shelf::GamePrefs gamePrefs(gameTitles, kGameCount);
bool gamePrefsLoaded = false;

// The Activity that the open item launched, by name. `openFolderIndex` alone
// cannot answer "is that item still what is on screen": the Home gesture leaves
// an app without going through leave(), so a sleep from Home would otherwise
// record the game you left ten minutes ago as still open. A pushed sub-screen
// (the frontlight panel) also fails this check, and falls back to Home the way
// every wake used to.
std::string openActivityName;

// A title that does not fit the state file cannot be resumed, and would fail
// silently at the write. Caught at compile time instead, next to the icon and
// mark checks, so a long-titled new game does not build.
constexpr bool everyTitleFitsTheStateFile() {
  for (const auto& folder : kFolders) {
    for (int i = 0; i < folder.count; ++i) {
      if (shelf::constexprLength(folder.items[i].title) > shelf::MAX_ITEM_TITLE) return false;
    }
  }
  return true;
}
static_assert(everyTitleFitsTheStateFile(), "shelf item titles must fit shelf::MAX_ITEM_TITLE; see ShelfState.h");
static_assert(kFolderCount <= shelf::MAX_FOLDERS, "raise shelf::MAX_FOLDERS in ShelfState.h");

// Row limits as the registry stands now, for parseState's clamp.
const int* itemLimits() {
  static int limits[shelf::MAX_FOLDERS] = {};
  for (int i = 0; i < kFolderCount; ++i) limits[i] = kFolders[i].count - 1;
  return limits;
}

// The folder and row of the item with this title, case-insensitively. The one
// place a title is turned back into a row, shared by wake and by the
// autostart environment variable.
bool findItemByTitle(const char* title, int& folder, int& item) {
  for (int f = 0; f < kFolderCount; ++f) {
    for (int i = 0; i < kFolders[f].count; ++i) {
      if (strcasecmp(kFolders[f].items[i].title, title) == 0) {
        folder = f;
        item = i;
        return true;
      }
    }
  }
  return false;
}

// The parse and the format live in ShelfState.cpp, where a host test can reach
// them without a card: the file has to survive a truncated write, a file
// written before wake could resume, and a game renamed since it was written.
void loadState() {
  stateLoaded = true;
#if defined(ARDUINO_ARCH_ESP32) || defined(SIMULATOR)
  if (!Storage.exists(kStatePath)) return;
  char buffer[96] = {};
  if (Storage.readFileToBuffer(kStatePath, buffer, sizeof(buffer)) == 0) return;
  // Fails quietly: the worst a corrupt file can cost is starting at the top,
  // and there is nothing for anyone to do about it.
  shelf::parseState(buffer, kFolderCount, itemLimits(), state);
#endif
}

void saveState() {
#if defined(ARDUINO_ARCH_ESP32) || defined(SIMULATOR)
  char line[96];
  const size_t used = shelf::formatState(state, kFolderCount, line, sizeof(line));
  if (used == 0) {
    LOG_ERR("SHELF", "State line did not fit %d bytes", static_cast<int>(sizeof(line)));
    return;
  }
  Storage.writeFile(kStatePath, String(line));
#endif
}

// Every path that reads or writes the remembered position goes through this
// first. Lazily rather than at boot because the shelf has no init hook, and
// unconditionally rather than only on the read paths because openFolder passes
// the current resumeRow back in: without the load, the first navigation of a
// session would write the defaults over the saved file and the persistence
// would silently do nothing.
void ensureLoaded() {
  if (!stateLoaded) loadState();
}

// The hidden list, read once. Read whole rather than into a fixed buffer: the
// worst case is every item in the registry, and that grows every time Mario
// adds a game -- a buffer sized for today is a setting silently lost on the
// day the twenty-first one lands.
void ensureHiddenLoaded() {
  if (hiddenLoaded) return;
  hiddenLoaded = true;
#if defined(ARDUINO_ARCH_ESP32) || defined(SIMULATOR)
  if (!Storage.exists(kHiddenPath)) return;
  shelf::parseHidden(Storage.readFile(kHiddenPath).c_str(), hiddenItems);
#endif
}

bool readGamePrefs(const char* path, shelf::GamePrefs& into) {
#if defined(ARDUINO_ARCH_ESP32) || defined(SIMULATOR)
  // An extra byte detects an oversized file even if its prefix looks valid.
  char text[shelf::GamePrefs::kMaxFileBytes + 2] = {};
  const size_t bytes = Storage.readFileToBuffer(path, text, sizeof(text));
  return bytes > 0 && bytes <= shelf::GamePrefs::kMaxFileBytes && into.parse(text, bytes);
#else
  (void)path;
  (void)into;
  return false;
#endif
}

void ensureGamePrefsLoaded() {
  if (gamePrefsLoaded) return;
  for (int i = 0; i < kGameCount; ++i) gameTitles[i] = kGames[i].title;
  gamePrefsLoaded = true;
#if defined(ARDUINO_ARCH_ESP32) || defined(SIMULATOR)
#if defined(ARDUINO_ARCH_ESP32)
  HalStorage::StorageLock lock;
#endif
  if (readGamePrefs(kGamePrefsPath, gamePrefs)) return;
  if (readGamePrefs(kGamePrefsBackup, gamePrefs)) {
    LOG_INF("SHELF", "Recovered Games preferences from backup");
    return;
  }
  if (readGamePrefs(kGamePrefsTemp, gamePrefs)) {
    LOG_INF("SHELF", "Recovered interrupted first Games preferences write");
  }
#endif
}

void saveGamePrefs() {
#if defined(ARDUINO_ARCH_ESP32) || defined(SIMULATOR)
#if defined(ARDUINO_ARCH_ESP32)
  HalStorage::StorageLock lock;
#endif
  const std::string text = gamePrefs.format();
  if (text.size() > shelf::GamePrefs::kMaxFileBytes || !Storage.ensureDirectoryExists("/.crosspoint") ||
      !Storage.writeFile(kGamePrefsTemp, String(text.c_str()))) {
    LOG_ERR("SHELF", "Could not stage Games preferences");
    return;
  }
  shelf::GamePrefs candidate(gameTitles, kGameCount);
  if (!readGamePrefs(kGamePrefsTemp, candidate) || candidate.format() != text) {
    LOG_ERR("SHELF", "Games preferences staging failed verification");
    return;  // Previous primary/backup are still untouched.
  }
  shelf::GamePrefs prior(gameTitles, kGameCount);
  if (readGamePrefs(kGamePrefsPath, prior)) {
    if (Storage.exists(kGamePrefsBackup) && !Storage.remove(kGamePrefsBackup)) return;
    if (!Storage.rename(kGamePrefsPath, kGamePrefsBackup)) return;
  } else if (Storage.exists(kGamePrefsPath) && !Storage.remove(kGamePrefsPath)) {
    return;  // A valid backup, if any, remains intact.
  }
  if (!Storage.rename(kGamePrefsTemp, kGamePrefsPath)) {
    LOG_ERR("SHELF", "Could not install Games preferences; backup remains readable");
    return;
  }
  shelf::GamePrefs written(gameTitles, kGameCount);
  if (!readGamePrefs(kGamePrefsPath, written) || written.format() != text) {
    LOG_ERR("SHELF", "Games preferences failed post-write verification; backup remains readable");
  }
#endif
}

void saveHiddenItems() {
#if defined(ARDUINO_ARCH_ESP32) || defined(SIMULATOR)
  // An empty set writes an empty file rather than removing it: a file that
  // exists and says nothing is hidden is one state, and a missing file that
  // means the same thing is the same state by another route. One write path,
  // and `exists` above is the only place that has to know both.
  if (!Storage.writeFile(kHiddenPath, String(shelf::formatHidden(hiddenItems).c_str()))) {
    LOG_ERR("SHELF", "Could not write %s; the list is only in RAM until the next boot", kHiddenPath);
  }
#endif
}

// Only when something actually changed. Opening a folder happens on every Back,
// and SPIFFS sectors have a finite erase count, so an unconditional write here
// would be a write per navigation for no gain.
void saveIfChanged(const int folder, const int row) {
  ensureLoaded();
  if (state.lastFolder == folder && (folder < 0 || state.resumeRow[folder] == row)) return;
  state.lastFolder = folder;
  if (folder >= 0) state.resumeRow[folder] = row;
  saveState();
}

// The item wake should reopen, or none. Kept separate from saveIfChanged
// because the two facts change on different events: the position changes as you
// navigate, this changes when an item opens, closes, or is left behind.
void setOpenTitle(const char* title) {
  ensureLoaded();
  const char* wanted = title == nullptr ? "" : title;
  if (strcmp(state.openTitle, wanted) == 0) return;
  snprintf(state.openTitle, sizeof(state.openTitle), "%s", wanted);
  saveState();
}

// Replaces the running activity, or logs and stays put. Every launch in this
// file funnels through here so an OOM cannot leave the shelf thinking it opened
// something it did not.
bool replaceWith(std::unique_ptr<Activity> activity, const char* what) {
  if (!activity) {
    LOG_ERR("SHELF", "OOM opening %s", what);
    return false;
  }
  activityManager.replaceActivity(std::move(activity));
  // Read back from the activity itself rather than written down beside the
  // registry: a table mapping titles to activity names would be a second copy
  // of a fact the activity already carries, and would rot the first time one is
  // renamed. Asked after the request, because Activity::name is not ours to
  // read directly.
  openActivityName = activityManager.currentActivityName();
  return true;
}

}  // namespace

namespace shelf {

const Folder* folders() { return kFolders; }

int folderCount() { return kFolderCount; }

void openFolder(const int index, GfxRenderer& renderer, MappedInputManager& mappedInput) {
  if (index < 0 || index >= kFolderCount) {
    LOG_ERR("SHELF", "Bad folder index: %d", index);
    return;
  }
  // Opening a folder means nothing below it is open any more. Clearing here
  // rather than in leave() keeps the fact true even when a folder is reached by
  // some route that did not go through leave().
  openFolderIndex = -1;
  ensureLoaded();
  saveIfChanged(index, state.resumeRow[index]);
  setOpenTitle(nullptr);
  replaceWith(ShelfFolderActivity::create(renderer, mappedInput, index), kFolders[index].title);
}

bool openItem(const int folder, const int item, GfxRenderer& renderer, MappedInputManager& mappedInput) {
  if (folder < 0 || folder >= kFolderCount) {
    LOG_ERR("SHELF", "Bad folder index: %d", folder);
    return false;
  }
  const Folder& parent = kFolders[folder];
  if (item < 0 || item >= parent.count) {
    LOG_ERR("SHELF", "Bad item index %d in %s", item, parent.title);
    return false;
  }

  // Recorded before the launch, not after: replaceActivity destroys the caller,
  // so there is no "after" to run in.
  openFolderIndex = folder;
  saveIfChanged(folder, item);
  setOpenTitle(parent.items[item].title);
  if (!replaceWith(parent.items[item].create(renderer, mappedInput), parent.items[item].title)) {
    openFolderIndex = -1;
    setOpenTitle(nullptr);
    return false;
  }
  return true;
}

// A folder's titles, by row, for the conversions in ShelfHidden.h.
auto titlesOf(const int folder) {
  return [folder](const int i) { return kFolders[folder].items[i].title; };
}

bool isHidden(const int folder, const int item) {
  if (folder < 0 || folder >= kFolderCount) return false;
  if (item < 0 || item >= kFolders[folder].count) return false;
  ensureHiddenLoaded();
  return hiddenItems.contains(kFolders[folder].items[item].title);
}

void setHidden(const int folder, const int item, const bool hide) {
  if (folder < 0 || folder >= kFolderCount) {
    LOG_ERR("SHELF", "Bad folder index: %d", folder);
    return;
  }
  if (item < 0 || item >= kFolders[folder].count) {
    LOG_ERR("SHELF", "Bad item index %d in %s", item, kFolders[folder].title);
    return;
  }
  ensureHiddenLoaded();
  if (!hiddenItems.set(kFolders[folder].items[item].title, hide)) return;
  LOG_INF("SHELF", "%s is now %s", kFolders[folder].items[item].title, hide ? "hidden" : "shown");
  saveHiddenItems();
}

// Games use the bounded title-keyed ordering (favorite group first), then
// exclude hidden items. Other folders retain the old registry-order mapping.
int shownCount(const int folder, const bool favoritesOnly) {
  if (folder < 0 || folder >= kFolderCount) return 0;
  ensureHiddenLoaded();
  if (folder != kGameFolder) return shownCountIn(hiddenItems, kFolders[folder].count, titlesOf(folder));
  ensureGamePrefsLoaded();
  return gamePrefs.count(favoritesOnly,
                         [&](const int item) { return hiddenItems.contains(kFolders[folder].items[item].title); });
}

int shownItem(const int folder, const int row, const bool favoritesOnly) {
  if (folder < 0 || folder >= kFolderCount) return -1;
  ensureHiddenLoaded();
  if (folder != kGameFolder) return shownItemIn(hiddenItems, kFolders[folder].count, row, titlesOf(folder));
  ensureGamePrefsLoaded();
  return gamePrefs.itemAt(row, favoritesOnly,
                          [&](const int item) { return hiddenItems.contains(kFolders[folder].items[item].title); });
}

int shownRowFor(const int folder, const int item, const bool favoritesOnly) {
  if (folder < 0 || folder >= kFolderCount) return 0;
  ensureHiddenLoaded();
  if (folder != kGameFolder) return shownRowForIn(hiddenItems, kFolders[folder].count, item, titlesOf(folder));
  ensureGamePrefsLoaded();
  return gamePrefs.rowFor(item, favoritesOnly, [&](const int current) {
    return hiddenItems.contains(kFolders[folder].items[current].title);
  });
}

bool isGameFavorite(const int folder, const int item) {
  if (folder != kGameFolder || item < 0 || item >= kGameCount) return false;
  ensureGamePrefsLoaded();
  return gamePrefs.isFavorite(item);
}

void setGameFavorite(const int folder, const int item, const bool favorite) {
  if (folder != kGameFolder || item < 0 || item >= kGameCount) return;
  ensureGamePrefsLoaded();
  if (gamePrefs.setFavorite(item, favorite)) saveGamePrefs();
}

void moveGameUp(const int folder, const int item) {
  if (folder != kGameFolder || item < 0 || item >= kGameCount || isHidden(folder, item)) return;
  ensureGamePrefsLoaded();
  const int neighbor = shownItem(folder, shownRowFor(folder, item) - 1);
  if (gamePrefs.moveAheadOf(item, neighbor)) saveGamePrefs();
}

void moveGameDown(const int folder, const int item) {
  if (folder != kGameFolder || item < 0 || item >= kGameCount || isHidden(folder, item)) return;
  ensureGamePrefsLoaded();
  const int neighbor = shownItem(folder, shownRowFor(folder, item) + 1);
  if (gamePrefs.moveBehind(item, neighbor)) saveGamePrefs();
}

void moveGameToTop(const int folder, const int item) {
  if (folder != kGameFolder) return;
  ensureGamePrefsLoaded();
  if (gamePrefs.moveToTop(item)) saveGamePrefs();
}

void autostartFromEnv(GfxRenderer& renderer, MappedInputManager& mappedInput) {
  // Once per process: leaving the app afterwards must land on the shelf like
  // any other exit, not bounce straight back in.
  static bool consumed = false;
  if (consumed) {
    return;
  }
  const char* wanted = std::getenv("CROSSPLAY_AUTOSTART");
  if (wanted == nullptr || *wanted == '\0') {
    return;
  }
  consumed = true;
  int folder = -1;
  int item = -1;
  if (!findItemByTitle(wanted, folder, item)) {
    LOG_ERR("SHELF", "Autostart: no item titled '%s'", wanted);
    return;
  }
  LOG_INF("SHELF", "Autostart into %s", kFolders[folder].items[item].title);
  openItem(folder, item, renderer, mappedInput);
}

void rememberForWake(const char* currentActivityName) {
  ensureLoaded();
  if (state.openTitle[0] == '\0') return;
  // An item is only still open if the activity it launched is the one on
  // screen. Leaving a game by the Home gesture never passes through leave(),
  // so without this a sleep taken on Home would resume into the game you left.
  const char* onScreen = currentActivityName == nullptr ? "" : currentActivityName;
  if (openActivityName.empty() || openActivityName != onScreen) {
    LOG_DBG("SHELF", "Sleeping on %s, not %s: nothing to resume", onScreen, state.openTitle);
    setOpenTitle(nullptr);
  }
}

bool resumeFromWake(GfxRenderer& renderer, MappedInputManager& mappedInput) {
  ensureLoaded();
  if (state.openTitle[0] == '\0') return false;

  int folder = -1;
  int item = -1;
  if (!findItemByTitle(state.openTitle, folder, item)) {
    // The card outlives firmware updates, so the item may have been renamed or
    // removed since it was written. Home, and forget it.
    LOG_INF("SHELF", "Wake: nothing titled '%s' any more", state.openTitle);
    setOpenTitle(nullptr);
    return false;
  }

  LOG_INF("SHELF", "Wake: resuming %s", kFolders[folder].items[item].title);
  return openItem(folder, item, renderer, mappedInput);
}

void openPlayer(GfxRenderer& renderer, MappedInputManager& mappedInput) {
  // Only the folder footer offers it, and only a folder that shows the name, so
  // lastFolder is the folder we are standing in. Recorded before the launch for
  // the same reason openItem does it: replaceActivity destroys the caller.
  ensureLoaded();
  openFolderIndex = state.lastFolder;
  setOpenTitle(nullptr);
  if (!replaceWith(PlayerActivity::create(renderer, mappedInput), "Player")) {
    openFolderIndex = -1;
  }
}

void leave(GfxRenderer& renderer, MappedInputManager& mappedInput) {
  if (openFolderIndex >= 0) {
    openFolder(openFolderIndex, renderer, mappedInput);
    return;
  }
  // Upstream's Home carries the folder rows itself; here they hang off the
  // Apps menu, so that is the screen a folder came from and the one it owes
  // the user back.
  activityManager.goToApps();
}

int lastFolderOnHome() {
  ensureLoaded();
  return state.lastFolder;
}

int resumeRowIn(const int index) {
  ensureLoaded();
  if (index < 0 || index >= kFolderCount) return 0;
  // Stored as the ITEM, answered as the ROW. The conversion is here, beside the
  // file, and not in the folder that asks: those are the only two units in this
  // feature and the whole hazard is a caller holding one while believing the
  // other -- they are both small ints in the same range, so nothing would say
  // so. The folder does hold items, at the two points where it must (opening
  // one, hiding one) and through ONE named function that produces them
  // (ShelfFolderActivity::itemAtRow); what it never does is store one in a
  // variable that means a row.
  return shownRowFor(index, state.resumeRow[index], false);
}

void rememberRowIn(const int index, const int row, const bool favoritesOnly) {
  if (index < 0 || index >= kFolderCount) {
    LOG_ERR("SHELF", "Bad folder index: %d", index);
    return;
  }
  // `row` is a SHOWN row, so this is also the range check: a row past the end
  // of what the folder is showing has no item and is refused, which is the same
  // guard the registry count used to give when the two were the same number.
  const int item = shownItem(index, row, favoritesOnly);
  if (item < 0) {
    LOG_ERR("SHELF", "Bad row %d in %s", row, kFolders[index].title);
    return;
  }
  saveIfChanged(index, item);
}

}  // namespace shelf
