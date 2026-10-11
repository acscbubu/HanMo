#include "FileBrowserActivity.h"

#include <FsHelpers.h>
#include <GfxRenderer.h>
#include <HalStorage.h>
#include <I18n.h>
#include <Memory.h>

#include <algorithm>

#include "CrossPointSettings.h"
#include "AirNoteOrdering.h"
#include "AirNotePlainEdit.h"
#include "AirNoteTodoEdit.h"
#include "CrossPointState.h"
#include "InxItemLayout.h"
#include "MappedInputManager.h"
#include "ReadingStatsStore.h"
#include "RecentBooksStore.h"
#include "activities/util/ConfirmationActivity.h"
#include "activities/util/KeyboardEntryActivity.h"
#include "components/UITheme.h"
#include "components/UiAppHelpers.h"
#include "components/icons/inx_library.h"
#include "fontIds.h"
#include "util/BookCacheUtils.h"
#include "util/FileEditUtils.h"

namespace fui = freeink::ui;

namespace {
constexpr unsigned long GO_HOME_MS = 1000;
constexpr size_t NAME_BUFFER_SIZE = 500;
constexpr size_t MAX_COMPONENT_BYTES = 255;
constexpr char MOVE_HERE_ENTRY[] = "\x01";
// Synthetic first row of the AirNote folder. A sentinel rather than a real
// name so it can never collide with a note and never reaches the ordering
// catalogue, which only counts AirNotePolicy::validFileName entries.
constexpr char NEW_NOTE_ENTRY[] = "\x02";
constexpr char MULTI_ACTION_ENTRY[] = "\x03";

std::string cleanEntryName(std::string entry) {
  if (!entry.empty() && entry.back() == '/') entry.pop_back();
  return entry;
}

std::string joinPath(const std::string& parent, const std::string& name) {
  return parent == "/" ? "/" + name : parent + "/" + name;
}
}  // namespace

std::string getFileName(std::string filename);
std::string getFileExtension(const std::string& filename);

FileBrowserActivity::FileBrowserActivity(GfxRenderer& renderer, MappedInputManager& mappedInput,
                                         std::string initialPath, const Mode mode)
    : UiListActivity("FileBrowser", renderer, mappedInput, /*wantsTouchLongPress=*/true),
      mode(mode),
      basepath(initialPath.empty() ? "/" : std::move(initialPath)) {}

void FileBrowserActivity::loadFiles() {
  files.clear();

  auto root = Storage.open(basepath.c_str());
  if (!root || !root.isDirectory()) {
    rebuildRowItems();  // files is empty; also drops any now-stale cached rows
    return;
  }

  root.rewindDirectory();

  if (!fileNameBuffer) {
    LOG_ERR("FileBrowser", "fileNameBuffer not allocated");
    root.close();
    rebuildRowItems();
    return;
  }

  for (auto file = root.openNextFile(); file; file = root.openNextFile()) {
    file.getName(fileNameBuffer.get(), NAME_BUFFER_SIZE);
    const bool isDirectory = file.isDirectory();
    if ((!SETTINGS.showHiddenFiles && fileNameBuffer[0] == '.') ||
        strcmp(fileNameBuffer.get(), "System Volume Information") == 0) {
      continue;
    }

    if (isDirectory) {
      const std::string entryName(fileNameBuffer.get());
      const std::string entryPath = joinPath(basepath, entryName);
      if (browserState != BrowserState::Browsing &&
          (FsHelpers::isProtectedPathComponent(entryName) ||
           (browserState == BrowserState::ChoosingMoveDestination &&
            FsHelpers::isSameOrDescendantPath(entryPath, moveSourcePath)))) {
        continue;
      }
      files.emplace_back(entryName + "/");
    } else {
      if (browserState != BrowserState::Browsing) continue;
      std::string_view filename{fileNameBuffer.get()};
      switch (mode) {
        case Mode::Books:
          if (FsHelpers::hasEpubExtension(filename) || FsHelpers::hasXtcExtension(filename) ||
              FsHelpers::hasTxtExtension(filename) || FsHelpers::hasMarkdownExtension(filename) ||
              FsHelpers::hasBmpExtension(filename) || FsHelpers::hasPngExtension(filename)) {
            files.emplace_back(filename);
          }
          break;
        case Mode::PickFirmware:
          if (FsHelpers::checkFileExtension(filename, ".bin")) files.emplace_back(filename);
          break;
        case Mode::PickBmp:
          if (FsHelpers::hasBmpExtension(filename)) files.emplace_back(filename);
          break;
        case Mode::PickPng:
          if (FsHelpers::hasPngExtension(filename)) files.emplace_back(filename);
          break;
      }
    }
  }
  root.close();
  FsHelpers::sortFileList(files);
  airNoteOrderRevision.clear();
  if(isAirNoteRoot()) {
    // Reuse the browser's existing vector. Catalog scanning adds no file list.
    size_t placed=0;
    if(!AirNoteOrdering::scan([&](const char* name){
      auto begin=files.begin()+placed;
      auto found=std::find(begin,files.end(),name);
      if(found!=files.end()){std::rotate(begin,found,found+1);++placed;}
    },airNoteOrderRevision))FsHelpers::sortFileList(files);
  }
  if (isAirNoteRoot()) files.insert(files.begin(), multiSelecting ? MULTI_ACTION_ENTRY : NEW_NOTE_ENTRY);
  if (browserState != BrowserState::Browsing) files.insert(files.begin(), MOVE_HERE_ENTRY);
  rebuildRowItems();
}

// Derives rowNames/rowExtensions/rowItems from `files`. Called whenever
// `files` changes (end of loadFiles()) so buildScreen() can reuse the cached
// rows on every repaint instead of re-deriving a name/extension string (and a
// ListItem) per file each time it's called.
void FileBrowserActivity::rebuildRowItems() {
  rowsUseFileIcons = UITheme::getInstance().getTheme().showsFileIcons();
  rowNames.resize(files.size());
  rowExtensions.resize(files.size());
  rowItems.clear();
  rowItems.reserve(files.size());
  gridLabels.clear();
  if (usesIconLayout()) {
    gridLabels.resize(files.size());
    const int labelWidth = std::max(1, renderer.getScreenWidth() / InxGridGeometry::columns - 16);
    for (size_t i = 0; i < files.size(); ++i) {
      const char* synthetic = files[i] == MOVE_HERE_ENTRY ? tr(STR_MOVE_HERE)
                              : files[i] == NEW_NOTE_ENTRY ? tr(STR_AIRNOTE_NEW)
                              : files[i] == MULTI_ACTION_ENTRY ? (multiOrderPicking ? tr(STR_AIRNOTE_MULTI_END)
                                                                                : tr(STR_AIRNOTE_MULTI_ACTIONS))
                                                               : nullptr;
      const bool marked = multiSelecting && AirNotePolicy::validFileName(files[i]);
      const std::string gridLabel = synthetic ? std::string(synthetic)
          : marked ? (std::find(multiSelected.begin(), multiSelected.end(), files[i]) != multiSelected.end()
                          ? "[x] " : "[ ] ") + getFileName(files[i])
                   : getFileName(files[i]);
      gridLabels[i] = renderer.truncatedText(UI_10_FONT_ID, gridLabel.c_str(), labelWidth);
    }
  }
  for (size_t i = 0; i < files.size(); i++) {
    const bool synthetic = files[i] == MOVE_HERE_ENTRY || files[i] == NEW_NOTE_ENTRY ||
                           files[i] == MULTI_ACTION_ENTRY;
    rowNames[i] = files[i] == MOVE_HERE_ENTRY ? tr(STR_MOVE_HERE)
                  : files[i] == NEW_NOTE_ENTRY ? tr(STR_AIRNOTE_NEW)
                  : files[i] == MULTI_ACTION_ENTRY ? (multiOrderPicking ? tr(STR_AIRNOTE_MULTI_END)
                                                                      : tr(STR_AIRNOTE_MULTI_ACTIONS))
                  : multiSelecting && AirNotePolicy::validFileName(files[i])
                      ? (std::find(multiSelected.begin(), multiSelected.end(), files[i]) != multiSelected.end()
                          ? "[x] " : "[ ] ") + getFileName(files[i])
                      : getFileName(files[i]);
    rowExtensions[i] = synthetic ? "" : getFileExtension(files[i]);
    fui::ListItem item;
    item.label = rowNames[i].c_str();
    if (!rowExtensions[i].empty()) item.value = rowExtensions[i].c_str();
    if (!synthetic) item.icon = listIconFor(UITheme::getFileIcon(files[i]));
    item.actionValue = static_cast<int16_t>(i);
    rowItems.push_back(item);
  }

  // One SD pass for every CJK filename in the folder; repaints then hit the
  // resident tables instead of re-reading per-string. Getter form: no
  // concatenated copy (a bare-new string append aborts under heap pressure).
  // The last index covers the bottom path band: basepath (possibly a CJK
  // folder name) draws in the same small font, so it must live in the same
  // batch or it would evict the rows' glyphs when the heap gate disables
  // union merging. (prewarmFallbackText appends the truncation ellipsis.)
  struct PrewarmCtx {
    const std::vector<std::string>* names;
    const std::string* path;
  } prewarmCtx{&rowNames, &basepath};
  renderer.prewarmFallbackText(
      uiScaleSpec().smallFontId,
      [](const void* ctx, uint32_t i) -> const char* {
        const auto* c = static_cast<const PrewarmCtx*>(ctx);
        return i < c->names->size() ? (*c->names)[i].c_str() : c->path->c_str();
      },
      &prewarmCtx, static_cast<uint32_t>(rowNames.size()) + 1);
}

bool FileBrowserActivity::usesIconLayout() const {
  return mode == Mode::Books && browserState == BrowserState::Browsing && UITheme::getInstance().hasMainTabs() &&
         InxGridGeometry::layoutFrom(SETTINGS.inxLibraryLayout) == InxItemLayout::Icons;
}

void FileBrowserActivity::drawIconGrid(UiScreen& screen, const fui::Rect rect) const {
  const int start = InxGridGeometry::pageStart(nav.selected, files.size());
  const int cellWidth = rect.width / InxGridGeometry::columns;
  const int cellHeight = rect.height / InxGridGeometry::rows;
  constexpr int iconSize = 72;
  const int lineHeight = renderer.getLineHeight(UI_10_FONT_ID);
  const bool showSelection = showMainTabContentSelection();
  for (int slot = 0; slot < InxGridGeometry::itemsPerPage && start + slot < listCount(); ++slot) {
    const int index = start + slot;
    const int column = slot % InxGridGeometry::columns;
    const int row = slot / InxGridGeometry::columns;
    const Rect cell{rect.x + column * cellWidth + 4, rect.y + row * cellHeight + 4, cellWidth - 8, cellHeight - 8};
    const bool selected = showSelection && index == nav.selected;
    if (selected) renderer.fillRect(cell.x, cell.y, cell.width, cell.height, true);
    const UIIcon type = UITheme::getFileIcon(files[index]);
    const uint8_t* icon = type == UIIcon::Folder ? FolderLarge : (type == UIIcon::Image ? ImageLarge : BookLarge);
    const int iconX = cell.x + (cell.width - iconSize) / 2;
    const int iconY = cell.y + std::max(4, (cell.height - iconSize - lineHeight - 6) / 2);
    if (selected)
      renderer.drawIconInverted(icon, iconX, iconY, iconSize);
    else
      renderer.drawIcon(icon, iconX, iconY, iconSize);
    const char* label =
        index < static_cast<int>(gridLabels.size()) ? gridLabels[index].c_str() : rowNames[index].c_str();
    const int labelX = cell.x + (cell.width - renderer.getTextWidth(UI_10_FONT_ID, label)) / 2;
    renderer.drawText(UI_10_FONT_ID, labelX, iconY + iconSize + 6, label, !selected);
    screen.frame().hit(fui::Rect{static_cast<int16_t>(cell.x), static_cast<int16_t>(cell.y),
                                 static_cast<int16_t>(cell.width), static_cast<int16_t>(cell.height)},
                       ACTION_ROW, static_cast<int16_t>(index), fui::InputTouch | fui::InputLongPress);
  }
  GUI.drawSideScrollBar(renderer, Rect{rect.x, rect.y, rect.width, rect.height}, files.size(), start,
                        InxGridGeometry::itemsPerPage);
}

void FileBrowserActivity::onEnter() {
  UiListActivity::onEnter();

  fileNameBuffer = makeUniqueNoThrow<char[]>(NAME_BUFFER_SIZE);
  if (!fileNameBuffer) {
    LOG_ERR("FileBrowser", "malloc failed for name buffer");
    return;
  }

  auto root = Storage.open(basepath.c_str());
  if (!root) {
    basepath = "/";
    loadFiles();
  } else if (!root.isDirectory()) {
    const std::string oldPath = basepath;
    basepath = FsHelpers::extractFolderPath(basepath);
    loadFiles();

    const auto pos = oldPath.find_last_of('/');
    const std::string fileName = oldPath.substr(pos + 1);
    // The first screen build pulls the viewport to it (ListNav follow-on-build).
    nav.selected = static_cast<int>(findEntry(fileName));
  } else {
    loadFiles();
  }
}

void FileBrowserActivity::onExit() {
  Activity::onExit();
  files.clear();
  rowNames.clear();
  rowExtensions.clear();
  gridLabels.clear();
  rowItems.clear();
  fileNameBuffer.reset();
  moveSourcePath.clear();
  moveSourceEntry.clear();
  moveReturnPath.clear();
  multiSelected.clear();
  multiSelecting = false;
  multiOrderPicking = false;
}

void FileBrowserActivity::selectMainTabContentEdge(const MainTabContentEdge edge) {
  moveSelectionTo(MainTabs::contentEdgeIndex(edge, listCount()));
}

// To avoid traversing directories twice (once for cache clearing, once for deletion),
// we do both in one pass here, instead of using Storage.removeDir
bool FileBrowserActivity::removeDirFile(const std::string& fullPath) {
  auto file = Storage.open(fullPath.c_str());
  if (!file) {
    LOG_ERR("FileBrowser", "Failed to open for metadata clearing: %s", fullPath.c_str());
    return false;
  }

  if (!file.isDirectory()) {
    file.close();
    clearBookCache(fullPath);
    return Storage.remove(fullPath.c_str());
  }
  file.close();

  if (!fileNameBuffer) {
    LOG_ERR("FileBrowser", "fileNameBuffer not allocated");
    return false;
  }

  // Stack of (dirPath, postOrder): postOrder=true means rmdir this path after children are processed.
  std::vector<std::pair<std::string, bool>> stack;
  stack.reserve(16);
  stack.push_back({fullPath, false});

  while (!stack.empty()) {
    auto [currentPath, postOrder] = std::move(stack.back());
    stack.pop_back();

    if (postOrder) {
      if (!Storage.rmdir(currentPath.c_str())) {
        LOG_ERR("FileBrowser", "Failed to rmdir: %s", currentPath.c_str());
        return false;
      }
      continue;
    }

    auto dir = Storage.open(currentPath.c_str());
    if (!dir) {
      LOG_ERR("FileBrowser", "Failed to open dir: %s", currentPath.c_str());
      return false;
    }
    if (!dir.isDirectory()) {
      LOG_ERR("FileBrowser", "Not a directory: %s", currentPath.c_str());
      return false;
    }

    // Push this dir for post-order rmdir (after all children are processed).
    stack.push_back({currentPath, true});

    dir.rewindDirectory();
    for (auto entry = dir.openNextFile(); entry; entry = dir.openNextFile()) {
      entry.getName(fileNameBuffer.get(), NAME_BUFFER_SIZE);
      if (strcmp(fileNameBuffer.get(), ".") == 0 || strcmp(fileNameBuffer.get(), "..") == 0) {
        continue;
      }
      std::string entryPath = currentPath;
      if (entryPath.back() != '/') {
        entryPath += "/";
      }
      entryPath += fileNameBuffer.get();

      const bool isDir = entry.isDirectory();
      entry.close();

      if (isDir) {
        stack.push_back({std::move(entryPath), false});
      } else {
        clearBookCache(entryPath);
        if (!Storage.remove(entryPath.c_str())) {
          LOG_ERR("FileBrowser", "Failed to remove file: %s", entryPath.c_str());
          return false;
        }
      }
    }
  }

  return true;
}

std::string FileBrowserActivity::selectedPath() const {
  if (files.empty() || nav.selected < 0 || nav.selected >= listCount()) return {};
  if (files[nav.selected] == MOVE_HERE_ENTRY) return basepath;
  return joinPath(basepath, cleanEntryName(files[nav.selected]));
}

void FileBrowserActivity::showNotice(const StrId message) {
  constexpr StrId options[] = {StrId::STR_OK_BUTTON};
  { RenderLock lock(*this); editPopup.show(message, options, 1, 0, [](int) {}); }
  requestUpdate();
}

void FileBrowserActivity::showNotice(const std::string& message) {
  const char* options[] = {tr(STR_OK_BUTTON)};
  { RenderLock lock(*this); editPopup.show(message.c_str(), options, 1, 0, [](int) {}); }
  requestUpdate();
}

void FileBrowserActivity::showEditMenu() {
  if (mode != Mode::Books || browserState != BrowserState::Browsing || files.empty() || nav.selected < 0 ||
      nav.selected >= listCount()) {
    return;
  }

  if (files[nav.selected] == NEW_NOTE_ENTRY || files[nav.selected] == MULTI_ACTION_ENTRY ||
      files[nav.selected] == MOVE_HERE_ENTRY) return;
  const std::string entry = cleanEntryName(files[nav.selected]);
  if (FsHelpers::isProtectedPathComponent(entry)) return;

  const char* actions[] = {tr(STR_RENAME), tr(STR_MOVE), tr(STR_DELETE), tr(STR_AIRNOTE_MOVE_TO),
                           tr(STR_AIRNOTE_MULTI_SELECT)};
  const bool canOrder=isAirNoteRoot() && AirNotePolicy::validFileName(files[nav.selected]);
  { RenderLock lock(*this);
    editPopup.show(entry.c_str(), actions, canOrder ? 5 : 3, 0,
                   [this](const int index) { executeEditAction(static_cast<EditAction>(index)); });
  }
  requestUpdate();
}

void FileBrowserActivity::executeEditAction(const EditAction action) {
  switch (action) {
    case EditAction::MultiSelect:
      startMultiSelect();
      return;
    case EditAction::OrderPick: {
      RenderLock lock(*this);
      if(isAirNoteRoot() && nav.selected>=0 && nav.selected<listCount())orderCarrying=files[nav.selected];
      requestUpdate();return;
    }
    case EditAction::Rename:
      promptRename();
      return;
    case EditAction::Move:
      beginMove();
      return;
    case EditAction::Delete:
      if (!files.empty() && nav.selected >= 0 && nav.selected < listCount()) {
        promptDelete(selectedPath(), files[nav.selected]);
      }
      return;
  }
}

bool FileBrowserActivity::isAirNoteRoot() const {
  return mode==Mode::Books && browserState==BrowserState::Browsing && (basepath=="/AirNote" || basepath=="/AirNote/");
}
void FileBrowserActivity::moveAirNote(int target) {
  if(!isAirNoteRoot() || nav.selected<0 || nav.selected>=listCount())return;
  const std::string name=orderCarrying;
  if(!AirNotePolicy::validFileName(name)||target<0||target>=listCount()||!AirNotePolicy::validFileName(files[target]))return;
  size_t position=0;for(int i=0;i<target;++i)if(AirNotePolicy::validFileName(files[i]))++position;
  const auto result=AirNoteOrdering::moveTo(name.c_str(),position,airNoteOrderRevision);
  {
    RenderLock lock(*this);
    orderCarrying.clear();
    loadFiles();
    const auto index=findEntry(name);
    nav.selected=index<files.size()?static_cast<int>(index):0;
    nav.follow(listCount());
  }
  if(result!=AirNoteOrdering::Result::Saved)
    showNotice(result==AirNoteOrdering::Result::Conflict ? StrId::STR_AIRNOTE_ORDER_CHANGED : StrId::STR_TODO_SAVE_FAILED);
  requestUpdate();
}

void FileBrowserActivity::startMultiSelect() {
  if (!isAirNoteRoot() || nav.selected < 0 || nav.selected >= listCount() ||
      !AirNotePolicy::validFileName(files[nav.selected])) return;
  {
    RenderLock lock(*this);
    multiSelected.clear();
    multiSelected.reserve(MAX_SELECTED_NOTES);  // one bounded allocation, not a directory copy
    multiSelected.push_back(files[nav.selected]);
    multiSelecting = true;
    multiOrderPicking = false;
    if (!files.empty() && files[0] == NEW_NOTE_ENTRY) files[0] = MULTI_ACTION_ENTRY;
    rebuildRowItems();
  }
  requestUpdate();
}

void FileBrowserActivity::toggleMultiSelection(const int index) {
  if (!isAirNoteRoot() || !multiSelecting || multiOrderPicking || index < 0 || index >= listCount() ||
      !AirNotePolicy::validFileName(files[index])) return;
  bool atLimit = false;
  {
    RenderLock lock(*this);
    const auto it = std::find(multiSelected.begin(), multiSelected.end(), files[index]);
    if (it != multiSelected.end()) {
      multiSelected.erase(it);
    } else if (multiSelected.size() == MAX_SELECTED_NOTES) {
      atLimit = true;
    } else {
      multiSelected.push_back(files[index]);
    }
    if (!atLimit) rebuildRowItems();
  }
  if (atLimit) showNotice(StrId::STR_AIRNOTE_MULTI_LIMIT);
  else requestUpdate();
}

void FileBrowserActivity::cancelMultiSelect() {
  if (!multiSelecting || browserState != BrowserState::Browsing) return;
  {
    RenderLock lock(*this);
    multiSelected.clear();
    multiSelecting = false;
    multiOrderPicking = false;
    if (!files.empty() && files[0] == MULTI_ACTION_ENTRY) files[0] = NEW_NOTE_ENTRY;
    rebuildRowItems();
  }
  requestUpdate();
}

void FileBrowserActivity::showMultiActions() {
  if (!isAirNoteRoot() || !multiSelecting || multiOrderPicking || multiSelected.empty()) return;
  const char* actions[] = {tr(STR_AIRNOTE_MULTI_REORDER), tr(STR_AIRNOTE_MULTI_MOVE),
                           tr(STR_AIRNOTE_MULTI_DELETE)};
  // Do not show a new popup on this popup's own callback (it would destroy
  // the still-running std::function). Notices use the separate editPopup.
  { RenderLock lock(*this);
    multiPopup.show(tr(STR_AIRNOTE_MULTI_ACTIONS), actions, 3, 0, [this](int index) {
      if (index == 0) beginMultiOrder();
      else if (index == 1) beginMultiMove();
      else if (index == 2) promptMultiDelete();
    });
  }
  requestUpdate();
}

void FileBrowserActivity::beginMultiOrder() {
  if (!isAirNoteRoot() || !multiSelecting || multiSelected.empty()) return;
  {
    RenderLock lock(*this);
    multiOrderPicking = true;
    rebuildRowItems();
  }
  requestUpdate();
}

void FileBrowserActivity::completeMultiOrder(const int target) {
  if (!isAirNoteRoot() || !multiSelecting || !multiOrderPicking || multiSelected.empty() ||
      multiSelected.size() > MAX_SELECTED_NOTES || target < 0 || target >= listCount()) return;
  const bool append = files[target] == MULTI_ACTION_ENTRY;
  if (!append && (!AirNotePolicy::validFileName(files[target]) ||
                  std::find(multiSelected.begin(), multiSelected.end(), files[target]) != multiSelected.end())) return;
  // Preserve the visible catalog order even if notes were checked in a different order.
  std::vector<std::string> ordered;
  ordered.reserve(multiSelected.size());
  for (const auto& name : files) {
    if (std::find(multiSelected.begin(), multiSelected.end(), name) != multiSelected.end())
      ordered.push_back(name);
  }
  if (ordered.size() != multiSelected.size()) return;  // stale/invalid/duplicate selection
  const std::string focus = ordered.front();
  const auto result = AirNoteOrdering::moveManyBefore(ordered, append ? nullptr : files[target].c_str(),
                                                      airNoteOrderRevision);
  {
    RenderLock lock(*this);
    multiOrderPicking = false;
    multiSelecting = false;
    multiSelected.clear();
    loadFiles();  // also refresh a stale revision after a web edit
    nav.selected = static_cast<int>(findEntry(focus));
    nav.follow(listCount());
  }
  if (result != AirNoteOrdering::Result::Saved)
    showNotice(result == AirNoteOrdering::Result::Conflict ? StrId::STR_AIRNOTE_ORDER_CHANGED
                                                           : StrId::STR_TODO_SAVE_FAILED);
  requestUpdate();
}

void FileBrowserActivity::promptRename() {
  if (files.empty() || nav.selected < 0 || nav.selected >= listCount()) return;

  const std::string entry = files[nav.selected];
  const std::string oldPath = selectedPath();
  const bool isDirectory = entry.back() == '/';
  const std::string extension = isDirectory ? std::string() : getFileExtension(entry);
  const size_t maxLength = MAX_COMPONENT_BYTES > extension.size() ? MAX_COMPONENT_BYTES - extension.size() : 0;
  const std::string initialName = isDirectory ? cleanEntryName(entry) : getFileName(entry);
  const int returnIndex = nav.selected;
  const std::string returnPath = basepath;

  auto handler = [this, oldPath, extension, isDirectory, returnIndex, returnPath](const ActivityResult& result) {
    if (result.isCancelled || !std::holds_alternative<KeyboardResult>(result.data)) return;

    const std::string& name = std::get<KeyboardResult>(result.data).text;
    if (!FsHelpers::isValidPathComponent(name) || FsHelpers::isProtectedPathComponent(name)) {
      showNotice(StrId::STR_INVALID_FILE_NAME);
      return;
    }

    const std::string newEntry = FileEditUtils::withPreservedExtension(name, extension);
    const std::string newPath = joinPath(returnPath, newEntry);
    if (newPath == oldPath) return;
    if (Storage.exists(newPath.c_str())) {
      showNotice(StrId::STR_TARGET_EXISTS);
      return;
    }
    if (!Storage.rename(oldPath.c_str(), newPath.c_str())) {
      LOG_ERR("FileBrowser", "Failed to rename %s to %s", oldPath.c_str(), newPath.c_str());
      showNotice(StrId::STR_FILE_OPERATION_FAILED);
      return;
    }

    const bool dataOk = relocatePathData(oldPath, newPath, isDirectory);
    finishEdit(returnPath, returnIndex, newEntry + (isDirectory ? "/" : ""));
    if (!dataOk) showNotice(StrId::STR_FILE_DATA_MIGRATION_FAILED);
  };

  if (!startActivityForResultWith<KeyboardEntryActivity>(std::move(handler), tr(STR_RENAME), initialName, maxLength,
                                                         InputType::Text)) {
    showNotice(StrId::STR_FILE_OPERATION_FAILED);
  }
}

void FileBrowserActivity::promptNewNote() {
  if (!isAirNoteRoot()) return;
  const char* types[] = {tr(STR_AIRNOTE_NEW_TEXT), tr(STR_AIRNOTE_NEW_CHECKLIST)};
  editPopup.show(tr(STR_AIRNOTE_NEW), types, 2, 0,
                 [this](const int index) { promptNewNoteTitle(index == 1); });
  requestUpdate();
}
void FileBrowserActivity::promptNewNoteTitle(const bool checklist) {
  auto handler = [this, checklist](const ActivityResult& result) {
    if (result.isCancelled || !std::holds_alternative<KeyboardResult>(result.data)) return;
    const std::string title = std::get<KeyboardResult>(result.data).text;
    if (!AirNotePolicy::validTitle(title)) {
      showNotice(StrId::STR_INVALID_FILE_NAME);
      return;
    }
    promptNewNoteBody(checklist, title);
  };
  if (!startActivityForResultWith<KeyboardEntryActivity>(std::move(handler), tr(STR_AIRNOTE_TITLE_PROMPT),
                                                         std::string(), AirNotePolicy::kMaxTitleBytes,
                                                         InputType::Text)) {
    showNotice(StrId::STR_AIRNOTE_CREATE_FAILED);
  }
}
void FileBrowserActivity::promptNewNoteBody(const bool checklist, const std::string& title,
                                             const std::string& draft, const bool retry) {
  // Keep checklist entry as a single item; plain notes use a multiline draft
  // and are not created until the user explicitly saves visible body text.
  auto handler = [this, checklist, title](const ActivityResult& result) {
    if (result.isCancelled || !std::holds_alternative<KeyboardResult>(result.data)) return;
    const std::string updated = std::get<KeyboardResult>(result.data).text;
    if (!createAirNote(checklist, title, updated)) promptNewNoteBody(checklist, title, updated, true);
  };
  if (!startActivityForResultWith<KeyboardEntryActivity>(
          std::move(handler), retry ? tr(STR_AIRNOTE_CREATE_FAILED)
                                    : checklist ? tr(STR_AIRNOTE_FIRST_ITEM) : tr(STR_AIRNOTE_NEW_TEXT),
          draft, checklist ? AirNoteTodo::maxItemBytes : AirNotePolicy::kMaxBodyBytes,
          checklist ? InputType::Text : InputType::Multiline)) {
    showNotice(StrId::STR_AIRNOTE_CREATE_FAILED);
  }
}
bool FileBrowserActivity::createAirNote(const bool checklist, const std::string& title,
                                        const std::string& body) {
  std::string content;
  if (!(checklist ? AirNoteTodoEdit::createChecklist(title, body, content)
                  : AirNoteTodoEdit::createNote(title, body, content)) ||
      !Storage.ensureDirectoryExists(AirNotePolicy::kDirectory)) {
    return false;
  }
  const std::string directory(AirNotePolicy::kDirectory);
  std::string name;
  if (!AirNoteTodoEdit::uniqueFileName(
          title, [&directory](const std::string& candidate) {
            return Storage.exists((directory + "/" + candidate).c_str());
          },
          name)) {
    return false;
  }
  const std::string path = directory + "/" + name;
  const std::string staging = AirNotePlainEdit::sibling(path, ".part");
  // Do not expose a half-written .txt to the note list, even if SD cleanup
  // itself fails. Retry may clear a stale hidden staging file.
  if (Storage.exists(staging.c_str()) && !Storage.remove(staging.c_str())) return false;
  HalFile file;
  if (!Storage.openFileForWrite("AirNote", staging, file)) return false;
  const bool written = file.write(content.data(), content.size()) == content.size();
  if (written) file.flush();
  const bool closed = file.close();
  if (!written || !closed || Storage.exists(path.c_str()) ||
      !Storage.rename(staging.c_str(), path.c_str())) {
    Storage.remove(staging.c_str());
    LOG_ERR("FileBrowser", "Failed to create AirNote: %s", path.c_str());
    return false;
  }
  finishEdit(basepath, nav.selected, name);
  return true;
}
bool FileBrowserActivity::promptEditAirNote(const std::string& path) {
  if (!isAirNoteRoot() || !AirNotePlainEdit::notePath(path)) return false;
  std::string original, title, body;
  if (!AirNotePlainEdit::readPlain(Storage, path, original, title, body)) return false;
  promptTextDraft(path, original, title, body);
  return true;
}
void FileBrowserActivity::promptTextDraft(const std::string& path, const std::string& original,
                                          const std::string& title, const std::string& draft, const bool retry) {
  auto handler = [this, path, original, title](const ActivityResult& result) {
    if (result.isCancelled || !std::holds_alternative<KeyboardResult>(result.data)) return;
    const std::string updated = std::get<KeyboardResult>(result.data).text;
    const auto status = AirNotePlainEdit::savePlain(
        Storage, path, original, updated,
        [](const std::string& notePath) { return clearBookCache(notePath); });
    if (status == AirNotePlainEdit::SaveResult::Saved || status == AirNotePlainEdit::SaveResult::Unchanged) {
      finishEdit(basepath, nav.selected, path.substr(path.find_last_of('/') + 1));
    } else {
      // Keep the unsaved text in the keyboard if SD/other editor changes
      // prevent commit. The original snapshot still guards every retry.
      promptTextDraft(path, original, title, updated, true);
    }
  };
  if (!startActivityForResultWith<KeyboardEntryActivity>(
          std::move(handler), retry ? std::string(tr(STR_FILE_OPERATION_FAILED)) : title,
          draft, AirNotePolicy::kMaxBodyBytes, InputType::Multiline)) {
    showNotice(StrId::STR_FILE_OPERATION_FAILED);
  }
}
void FileBrowserActivity::beginMultiMove() {
  if (!isAirNoteRoot() || !multiSelecting || multiSelected.empty()) return;
  {
    RenderLock lock(*this);
    moveReturnPath = basepath;
    moveReturnIndex = nav.selected;
    browserState = BrowserState::ChoosingMultiMoveDestination;
    multiOrderPicking = false;
    loadFiles();
    nav.selected = 0;
    nav.top = 0;
  }
  requestUpdate();
}

void FileBrowserActivity::completeMultiMove() {
  if (browserState != BrowserState::ChoosingMultiMoveDestination || !multiSelecting ||
      multiSelected.empty() || multiSelected.size() > MAX_SELECTED_NOTES) return;
  if (basepath == moveReturnPath || basepath == AirNotePolicy::kDirectory) {
    showNotice(StrId::STR_CANNOT_MOVE_HERE);
    return;
  }
  // Validate the WHOLE destination and ALL source/target paths before the
  // first rename. No implicit mkdir and no hidden/protected SD locations.
  if (basepath.empty() || basepath.front() != '/') {
    showNotice(StrId::STR_CANNOT_MOVE_HERE);
    return;
  }
  for (size_t first = 1; first < basepath.size();) {
    const size_t end = basepath.find('/', first);
    const std::string_view component(basepath.data() + first,
                                     (end == std::string::npos ? basepath.size() : end) - first);
    if (!FsHelpers::isValidPathComponent(component) || FsHelpers::isProtectedPathComponent(component)) {
      showNotice(StrId::STR_CANNOT_MOVE_HERE);
      return;
    }
    if (end == std::string::npos) break;
    first = end + 1;
    if (first == basepath.size()) {
      showNotice(StrId::STR_CANNOT_MOVE_HERE);
      return;
    }
  }
  auto directory = Storage.open(basepath.c_str());
  if (!directory || !directory.isDirectory()) {
    showNotice(StrId::STR_CANNOT_MOVE_HERE);
    return;
  }
  directory.close();
  for (size_t i = 0; i < multiSelected.size(); ++i) {
    const auto& name = multiSelected[i];
    if (!AirNotePolicy::validFileName(name) || FsHelpers::isProtectedPathComponent(name) ||
        std::find(multiSelected.begin(), multiSelected.begin() + i, name) != multiSelected.begin() + i) {
      showNotice(StrId::STR_INVALID_FILE_NAME);
      return;
    }
    const auto source = Storage.open(joinPath(AirNotePolicy::kDirectory, name).c_str());
    if (!source || source.isDirectory()) {
      showNotice(StrId::STR_FILE_OPERATION_FAILED);
      return;
    }
    if (Storage.exists(joinPath(basepath, name).c_str())) {
      showNotice(StrId::STR_TARGET_EXISTS);
      return;
    }
  }
  unsigned moved = 0, metadataFailed = 0;
  const unsigned total = static_cast<unsigned>(multiSelected.size());
  for (const auto& name : multiSelected) {
    const std::string source = joinPath(AirNotePolicy::kDirectory, name);
    const std::string destination = joinPath(basepath, name);
    // Recheck against concurrent device-web writes. Never overwrite a file
    // created after the preflight; count failures instead of claiming success.
    auto file = Storage.open(source.c_str());
    const bool regular = file && !file.isDirectory();
    if (file) file.close();  // FAT must not rename an open source
    if (!regular || Storage.exists(destination.c_str()) ||
        !Storage.rename(source.c_str(), destination.c_str())) {
      LOG_ERR("FileBrowser", "Bulk move failed: %s to %s", source.c_str(), destination.c_str());
      continue;
    }
    ++moved;
    if (!relocatePathData(source, destination, false)) ++metadataFailed;
  }
  {
    RenderLock lock(*this);
    browserState = BrowserState::Browsing;
    basepath = moveReturnPath;
    moveReturnPath.clear();
    multiSelecting = false;
    multiSelected.clear();
    loadFiles();
    nav.selected = files.empty() ? 0 : std::clamp(moveReturnIndex, 0, listCount() - 1);
    nav.follow(listCount());
  }
  if (moved != total || metadataFailed) {
    char result[160];
    snprintf(result, sizeof(result), tr(STR_AIRNOTE_MULTI_MOVE_RESULT), moved, total, metadataFailed);
    showNotice(std::string(result));
  }
  requestUpdate(true);
}

void FileBrowserActivity::promptMultiDelete() {
  if (!isAirNoteRoot() || !multiSelecting || multiSelected.empty() ||
      multiSelected.size() > MAX_SELECTED_NOTES) return;
  // The callback keeps exactly the checked names; a cancelled confirmation
  // leaves the selection and SD untouched.
  const auto names = multiSelected;
  char body[160];
  snprintf(body, sizeof(body), tr(STR_AIRNOTE_MULTI_DELETE_CONFIRM),
           static_cast<unsigned>(names.size()));
  auto handler = [this, names](const ActivityResult& result) {
    if (!result.isCancelled) performMultiDelete(names);
  };
  if (!startActivityForResultWith<ConfirmationActivity>(std::move(handler),
                                                         tr(STR_AIRNOTE_MULTI_DELETE), std::string(body)))
    showNotice(StrId::STR_FILE_OPERATION_FAILED);
}

void FileBrowserActivity::performMultiDelete(const std::vector<std::string>& names) {
  if (!isAirNoteRoot() || !multiSelecting || names.empty() || names.size() > MAX_SELECTED_NOTES) return;
  unsigned deleted = 0, cacheFailures = 0;
  const unsigned total = static_cast<unsigned>(names.size());
  for (size_t i = 0; i < names.size(); ++i) {
    const auto& name = names[i];
    if (!AirNotePolicy::validFileName(name) || FsHelpers::isProtectedPathComponent(name) ||
        std::find(names.begin(), names.begin() + i, name) != names.begin() + i ||
        std::find(multiSelected.begin(), multiSelected.end(), name) == multiSelected.end()) continue;
    const std::string path = joinPath(AirNotePolicy::kDirectory, name);
    auto file = Storage.open(path.c_str());
    const bool regular = file && !file.isDirectory();
    if (file) file.close();  // remove only after releasing the open handle
    if (!regular || !Storage.remove(path.c_str())) {
      LOG_ERR("FileBrowser", "Bulk delete failed: %s", path.c_str());
      continue;
    }
    ++deleted;
    if (!clearBookCache(path)) ++cacheFailures;  // only after a successful removal
  }
  {
    RenderLock lock(*this);
    multiSelected.clear();
    multiSelecting = false;
    multiOrderPicking = false;
    loadFiles();  // .order may contain stale names; scan filters missing notes
    nav.selected = files.empty() ? 0 : std::clamp(nav.selected, 0, listCount() - 1);
    nav.follow(listCount());
  }
  if (deleted != total || cacheFailures) {
    char result[128];
    snprintf(result, sizeof(result), tr(STR_AIRNOTE_MULTI_DELETE_RESULT), deleted, total, cacheFailures);
    showNotice(std::string(result));
  }
  requestUpdate(true);
}

void FileBrowserActivity::beginMove() {
  if (files.empty() || nav.selected < 0 || nav.selected >= listCount()) return;
  moveSourceEntry = files[nav.selected];
  moveSourcePath = selectedPath();
  moveReturnPath = basepath;
  moveReturnIndex = nav.selected;
  moveSourceIsDirectory = moveSourceEntry.back() == '/';
  browserState = BrowserState::ChoosingMoveDestination;
  {
    RenderLock lock(*this);
    loadFiles();
    nav.selected = 0;
    nav.top = 0;
  }
  requestUpdate();
}

void FileBrowserActivity::cancelMove() {
  const std::string returnPath = moveReturnPath;
  const std::string sourceEntry = moveSourceEntry;
  const int returnIndex = moveReturnIndex;
  browserState = BrowserState::Browsing;
  finishEdit(returnPath, returnIndex, sourceEntry);
  moveSourcePath.clear();
  moveSourceEntry.clear();
  moveReturnPath.clear();
}

void FileBrowserActivity::completeMove() {
  if (browserState != BrowserState::ChoosingMoveDestination || moveSourcePath.empty()) return;

  const std::string cleanSourceEntry = cleanEntryName(moveSourceEntry);
  const std::string newPath = joinPath(basepath, cleanSourceEntry);
  const auto destinationError = FileEditUtils::validateMoveDestination(
      moveSourcePath, moveReturnPath, basepath, moveSourceIsDirectory, Storage.exists(newPath.c_str()));
  switch (destinationError) {
    case FileEditUtils::MoveDestinationError::None:
      break;
    case FileEditUtils::MoveDestinationError::SameDirectory:
    case FileEditUtils::MoveDestinationError::OwnDescendant:
      showNotice(StrId::STR_CANNOT_MOVE_HERE);
      return;
    case FileEditUtils::MoveDestinationError::TargetExists:
      showNotice(StrId::STR_TARGET_EXISTS);
      return;
  }
  if (!Storage.rename(moveSourcePath.c_str(), newPath.c_str())) {
    LOG_ERR("FileBrowser", "Failed to move %s to %s", moveSourcePath.c_str(), newPath.c_str());
    showNotice(StrId::STR_FILE_OPERATION_FAILED);
    return;
  }

  const bool dataOk = relocatePathData(moveSourcePath, newPath, moveSourceIsDirectory);
  const std::string returnPath = moveReturnPath;
  const int returnIndex = moveReturnIndex;
  browserState = BrowserState::Browsing;
  finishEdit(returnPath, returnIndex);
  moveSourcePath.clear();
  moveSourceEntry.clear();
  moveReturnPath.clear();
  if (!dataOk) showNotice(StrId::STR_FILE_DATA_MIGRATION_FAILED);
}

bool FileBrowserActivity::relocateDirectoryData(const std::string& oldPath, const std::string& newPath) {
  if (!fileNameBuffer) return false;

  bool ok = true;
  std::vector<std::string> directories;
  directories.reserve(16);
  directories.push_back(newPath);
  while (!directories.empty()) {
    std::string directoryPath = std::move(directories.back());
    directories.pop_back();
    auto directory = Storage.open(directoryPath.c_str());
    if (!directory || !directory.isDirectory()) {
      LOG_ERR("FileBrowser", "Failed to scan moved directory: %s", directoryPath.c_str());
      ok = false;
      continue;
    }

    directory.rewindDirectory();
    for (auto entry = directory.openNextFile(); entry; entry = directory.openNextFile()) {
      entry.getName(fileNameBuffer.get(), NAME_BUFFER_SIZE);
      if (strcmp(fileNameBuffer.get(), ".") == 0 || strcmp(fileNameBuffer.get(), "..") == 0) continue;
      const std::string entryPath = joinPath(directoryPath, fileNameBuffer.get());
      if (entry.isDirectory()) {
        directories.push_back(entryPath);
        continue;
      }
      const std::string oldEntryPath = FsHelpers::rebasePath(entryPath, newPath, oldPath);
      if (!relocateBookArtifacts(oldEntryPath, entryPath)) ok = false;
    }
  }

  if (!RECENT_BOOKS.updatePathPrefix(oldPath, newPath)) ok = false;
  if (!READING_STATS.updateBookPathPrefix(oldPath, newPath)) ok = false;
  if (FsHelpers::isSameOrDescendantPath(APP_STATE.openEpubPath, oldPath)) {
    APP_STATE.openEpubPath = FsHelpers::rebasePath(APP_STATE.openEpubPath, oldPath, newPath);
    if (!APP_STATE.saveToFile()) ok = false;
  }
  return ok;
}

bool FileBrowserActivity::relocatePathData(const std::string& oldPath, const std::string& newPath,
                                           const bool isDirectory) {
  if (isDirectory) return relocateDirectoryData(oldPath, newPath);
  return relocateBookArtifacts(oldPath, newPath) && relocateBookReferences(oldPath, newPath);
}

void FileBrowserActivity::finishEdit(const std::string& returnPath, const int fallbackIndex,
                                     const std::string& selectedEntry) {
  RenderLock lock(*this);
  basepath = returnPath;
  loadFiles();
  if (!selectedEntry.empty()) {
    nav.selected = static_cast<int>(findEntry(selectedEntry));
  } else if (files.empty()) {
    nav.selected = 0;
  } else {
    nav.selected = std::clamp(fallbackIndex, 0, listCount() - 1);
  }
  nav.follow(listCount());
  lock.unlock();
  requestUpdate(true);
}

void FileBrowserActivity::promptDelete(const std::string& fullPath, const std::string& entry) {
  const int returnIndex = nav.selected;
  auto handler = [this, fullPath, returnIndex](const ActivityResult& result) {
    if (result.isCancelled) return;
    if (removeDirFile(fullPath)) {
      finishEdit(basepath, returnIndex);
      return;
    }
    LOG_ERR("FileBrowser", "Failed to delete: %s", fullPath.c_str());
    showNotice(StrId::STR_FILE_OPERATION_FAILED);
  };

  const std::string heading = tr(STR_DELETE) + std::string("? ");
  if (!startActivityForResultWith<ConfirmationActivity>(std::move(handler), heading, cleanEntryName(entry))) {
    showNotice(StrId::STR_FILE_OPERATION_FAILED);
  }
}

void FileBrowserActivity::activateIndex(const int index) {
  (void)index;  // base already synced nav.selected to the tapped row
  // Activation navigates or opens; a lingering flash would gray an unrelated
  // row on the next list.
  app.clearTapFlash();
  activateSelected();
}

void FileBrowserActivity::onRowLongPress(const int index) {
  if (multiSelecting && browserState == BrowserState::Browsing) {
    app.clearTapFlash();
    if (multiOrderPicking) completeMultiOrder(index);
    else showMultiActions();
    return;
  }
  if (!orderCarrying.empty()) {
    // Long-pressing the note already in hand is not a move onto itself; it is
    // the way back to the edit menu that the pick-up gesture displaced from
    // the first press, so touch-only users keep rename/move/delete.
    if (index >= 0 && index < listCount() && files[index] == orderCarrying) {
      {
        RenderLock lock(*this);
        orderCarrying.clear();
      }
      app.clearTapFlash();
      showEditMenu();
      return;
    }
    moveAirNote(index);
    return;
  }
  (void)index;  // base already synced nav.selected to the pressed row
  app.clearTapFlash();
  // Inside the AirNote folder a long press picks the note up immediately and
  // the next tap drops it: one gesture, no menu asking where to put it.
  if (isAirNoteRoot() && nav.selected >= 0 && nav.selected < listCount() &&
      AirNotePolicy::validFileName(files[nav.selected])) {
    {
      RenderLock lock(*this);
      orderCarrying = files[nav.selected];
    }
    requestUpdate();
    return;
  }
  showEditMenu();
}

void FileBrowserActivity::activateSelected() {
  if (multiSelecting && browserState == BrowserState::Browsing) {
    if (multiOrderPicking) completeMultiOrder(nav.selected);
    else if (nav.selected >= 0 && nav.selected < listCount() && files[nav.selected] == MULTI_ACTION_ENTRY)
      showMultiActions();
    else toggleMultiSelection(nav.selected);
    return;
  }
  if(!orderCarrying.empty()){moveAirNote(nav.selected);return;}
  if (files.empty()) return;
  // A touch activation can carry a row index captured before a delete/reload
  // shrank the list; the next render re-registers the rows.
  if (nav.selected < 0 || nav.selected >= listCount()) return;

  const std::string& entry = files[nav.selected];
  if (entry == MOVE_HERE_ENTRY) {
    if (browserState == BrowserState::ChoosingMultiMoveDestination) completeMultiMove();
    else if (browserState == BrowserState::ChoosingMoveDestination) completeMove();
    return;
  }
  if (entry == NEW_NOTE_ENTRY) {
    promptNewNote();
    return;
  }
  const bool isDirectory = (entry.back() == '/');

  if (mode != Mode::Books && !isDirectory) {
    std::string cleanBasePath = basepath;
    if (cleanBasePath.back() != '/') cleanBasePath += "/";
    ActivityResult res{FilePathResult{cleanBasePath + entry}};
    res.isCancelled = false;
    setResult(std::move(res));
    finish();
    return;
  }

  if (mode == Mode::Books && browserState == BrowserState::Browsing && mappedInput.getHeldTime() >= GO_HOME_MS) {
    showEditMenu();
    return;
  }

  RenderLock lock(*this);
  if (basepath.back() != '/') basepath += "/";
  if (isDirectory) {
    basepath += entry.substr(0, entry.length() - 1);
    loadFiles();
    nav.selected = 0;
    nav.top = 0;
    lock.unlock();
    requestUpdate();
  } else {
    const std::string fullPath = basepath + entry;
    lock.unlock();
    // AirNote's ordinary TXT notes open directly in the editable multiline
    // draft; checklists and unrecognized books retain their existing route.
    if (isAirNoteRoot() && AirNotePolicy::validFileName(entry) && promptEditAirNote(fullPath)) return;
    onSelectBook(fullPath);
  }
}

bool FileBrowserActivity::handleCustomInput() {
  if(!orderCarrying.empty() && mappedInput.wasReleased(MappedInputManager::Button::Back)){
    {RenderLock lock(*this);orderCarrying.clear();}requestUpdate();return true;
  }
  if (editPopup.handleInput(mappedInput, [this] { requestUpdate(); })) return true;
  if (multiPopup.handleInput(mappedInput, [this] { requestUpdate(); })) return true;
  if (multiSelecting && browserState == BrowserState::Browsing &&
      mappedInput.wasReleased(MappedInputManager::Button::Back)) {
    if (multiOrderPicking) {
      { RenderLock lock(*this); multiOrderPicking = false; rebuildRowItems(); }
      requestUpdate();
    } else {
      cancelMultiSelect();
    }
    return true;
  }

  if (usesIconLayout()) {
    const auto swipe = mappedInput.wasSwipe();
    if (swipe == MappedInputManager::SwipeDir::Up || swipe == MappedInputManager::SwipeDir::Down) {
      const int next =
          swipe == MappedInputManager::SwipeDir::Up
              ? ButtonNavigator::nextPageIndex(nav.selected, listCount(), InxGridGeometry::itemsPerPage)
              : ButtonNavigator::previousPageIndex(nav.selected, listCount(), InxGridGeometry::itemsPerPage);
      moveSelectionTo(next);
      return true;
    }
  }

  // Long press BACK (1s+) goes to root folder (Books mode only).
  // In firmware-pick mode we keep navigation simple: short Back = up dir / cancel.
  if (mode == Mode::Books && browserState == BrowserState::Browsing &&
      mappedInput.wasReleased(MappedInputManager::Button::Back) && mappedInput.getHeldTime() >= GO_HOME_MS &&
      basepath != "/") {
    {
      // buildScreen() runs on the render task and reads basepath plus the
      // row caches rebuildRowItems() frees; mutate only under the render lock.
      RenderLock lock(*this);
      basepath = "/";
      loadFiles();
      nav.selected = 0;
      nav.top = 0;
    }
    requestUpdate();
    return true;
  }

  return false;
}

bool FileBrowserActivity::handleButtons() {
  if (mappedInput.wasReleased(MappedInputManager::Button::Confirm)) {
    activateSelected();
    return true;
  }

  if (mappedInput.wasReleased(MappedInputManager::Button::Back)) {
    // Short press: go up one directory, or go home if at root
    if (mappedInput.getHeldTime() < GO_HOME_MS) {
      if (basepath != "/") {
        const std::string oldPath = basepath;

        {
          // buildScreen() runs on the render task and reads basepath plus the
          // row caches rebuildRowItems() frees; mutate only under the render lock.
          RenderLock lock(*this);
          basepath.replace(basepath.find_last_of('/'), std::string::npos, "");
          if (basepath.empty()) basepath = "/";
          loadFiles();

          const auto pos = oldPath.find_last_of('/');
          const std::string dirName = oldPath.substr(pos + 1) + "/";
          nav.selected = static_cast<int>(findEntry(dirName));
          nav.top = 0;
          nav.follow(listCount());
        }

        requestUpdate();
      } else if (browserState == BrowserState::ChoosingMultiMoveDestination) {
        {
          RenderLock lock(*this);
          browserState = BrowserState::Browsing;
          basepath = moveReturnPath;
          moveReturnPath.clear();
          loadFiles();
          nav.selected = files.empty() ? 0 : std::clamp(moveReturnIndex, 0, listCount() - 1);
          nav.follow(listCount());
        }
        requestUpdate();
      } else if (browserState == BrowserState::ChoosingMoveDestination) {
        cancelMove();
      } else if (mode != Mode::Books) {
        ActivityResult res;
        res.isCancelled = true;
        setResult(std::move(res));
        finish();
      } else {
        onGoHome();
      }
    }
    return true;
  }

  return false;
}

std::string getFileName(std::string filename) {
  if (filename.back() == '/') {
    filename.pop_back();
    if (!UITheme::getInstance().getTheme().showsFileIcons()) {
      return "[" + filename + "]";
    }
    return filename;
  }
  const auto pos = filename.rfind('.');
  return filename.substr(0, pos);
}

std::string getFileExtension(const std::string& filename) {
  if (filename.back() == '/') {
    return "";
  }
  const auto pos = filename.rfind('.');
  return filename.substr(pos);
}

void FileBrowserActivity::buildScreen(UiScreen& screen) {
  const auto& metrics = UITheme::getInstance().getMetrics();
  // Content below the GUI.drawHeader band, above the button hints.
  screen.setContentMarginFromScreen(fui::Insets{static_cast<int16_t>(metrics.topPadding + metrics.headerHeight), 0,
                                                static_cast<int16_t>(metrics.buttonHintsHeight), 0});
  screen.spacer(static_cast<int16_t>(metrics.verticalSpacing));

  // Full path band at the bottom: separator on top, left-truncated so the
  // deepest directory stays visible.
  {
    const int pathLineHeight = renderer.getLineHeight(SMALL_FONT_ID);
    const fui::Rect band = screen.takeBottom(static_cast<int16_t>(pathLineHeight + metrics.verticalSpacing));
    screen.target().fill(fui::Rect{band.x, band.y, band.width, 3}, fui::Paint::solid(fui::Color::Black));
    const int pathY =
        band.y + metrics.verticalSpacing / 2 + (band.height - metrics.verticalSpacing / 2 - pathLineHeight) / 2;
    const int pathMaxWidth = band.width - metrics.contentSidePadding * 2;
    const char* pathStr = basepath.c_str();
    const char* pathDisplay = pathStr;
    char leftTruncBuf[256];
    if (renderer.getTextWidth(SMALL_FONT_ID, pathStr) > pathMaxWidth) {
      const char ellipsis[] = "\xe2\x80\xa6";  // UTF-8 ellipsis (…)
      const int ellipsisWidth = renderer.getTextWidth(SMALL_FONT_ID, ellipsis);
      const int available = pathMaxWidth - ellipsisWidth;
      // Walk forward from the start until the suffix fits, skipping UTF-8 continuation bytes
      const char* p = pathStr;
      while (*p) {
        if (renderer.getTextWidth(SMALL_FONT_ID, p) <= available) break;
        ++p;
        while (*p && (static_cast<unsigned char>(*p) & 0xC0) == 0x80) ++p;
      }
      snprintf(leftTruncBuf, sizeof(leftTruncBuf), "%s%s", ellipsis, p);
      pathDisplay = leftTruncBuf;
    }
    renderer.drawText(SMALL_FONT_ID, band.x + metrics.contentSidePadding, pathY, pathDisplay);
  }

  if (files.empty()) {
    screen.centeredText(mode == Mode::PickFirmware ? tr(STR_NO_BIN_FILES) : tr(STR_NO_FILES_FOUND),
                        screen.theme().bodyText);
    return;
  }

  // rowNames/rowExtensions/rowItems are built once per loadFiles() call (see
  // rebuildRowItems()) and reused here. getFileName()'s folder-bracket format
  // depends on the theme, so a theme change picked up while this activity was
  // paused underneath another screen invalidates the cache before it's read.
  if (rowsUseFileIcons != UITheme::getInstance().getTheme().showsFileIcons()) {
    rebuildRowItems();
  }

  if (usesIconLayout()) {
    nav.visibleRows = InxGridGeometry::itemsPerPage;
    nav.drawnRows = InxGridGeometry::itemsPerPage;
    nav.top = InxGridGeometry::pageStart(nav.selected, listCount());
    drawIconGrid(screen, screen.body());
    return;
  }

  fui::ListProps props;
  props.items = rowItems.data();
  props.count = static_cast<uint16_t>(rowItems.size());
  props.action = ACTION_ROW;
  // Tap opens/navigates; long-press prompts delete (physical buttons stay in loop()).
  props.inputMask = fui::InputTouch | fui::InputLongPress;
  props.valueInset = 8;  // air between the extension and the row edge
  // Match the pre-FreeInkUI file-list size while keeping two-line wrapping for
  // long names.
  fui::TextStyle label = screen.theme().bodyText;
  label.maxLines = 2;
  props.labelText = label;
  // The trailing value here is just the short extension: skip the balanced
  // 60%-band wrap cap and let both name lines run the full width before it.
  props.balanceWrappedLabelWithValue = false;
  // Wrapped two-line names shrink how many rows fit a page, so the last row
  // of a page can end up in leftover space: draw it as a partial preview so
  // files past the fold are visibly present, not silently absent.
  props.partialTrailingRow = true;
  syncListViewport(screen, props);
  screen.list(props);
}

void FileBrowserActivity::drawChrome() {
  const auto pageWidth = renderer.getScreenWidth();
  const auto& metrics = UITheme::getInstance().getMetrics();

  std::string folderName = browserState != BrowserState::Browsing ? std::string(tr(STR_MOVE))
                           : mode == Mode::PickFirmware ? std::string(tr(STR_SELECT_FIRMWARE_FILE))
                           : (mode == Mode::PickPng || mode == Mode::PickBmp) ? std::string(tr(STR_CUSTOM_IMAGE))
                                                        : ((basepath == "/") ? std::string(tr(STR_SD_CARD))
                                                                             : basepath.substr(basepath.rfind('/') + 1));
  // Header via GUI.drawHeader (already FreeInkUI-themed) for the battery
  // indicator; the rest of the screen renders through the app.
  drawPageHeader(Rect{0, metrics.topPadding, pageWidth, metrics.headerHeight},
                 multiSelecting && browserState == BrowserState::Browsing
                     ? (multiOrderPicking ? tr(STR_AIRNOTE_PICK_TARGET) : tr(STR_AIRNOTE_MULTI_SELECT))
                                 : (orderCarrying.empty() ? folderName.c_str() : tr(STR_AIRNOTE_PICK_TARGET)));
}

void FileBrowserActivity::drawFooter() {
  const char* backLabel =
      browserState != BrowserState::Browsing
          ? tr(STR_BACK)
          : ((basepath == "/") ? (mode != Mode::Books ? tr(STR_BACK) : tr(STR_HOME)) : tr(STR_BACK));
  // In PickFirmware mode, Confirm on a .bin returns the path to the caller (not "open"); show
  // STR_SELECT instead. Directories in the same picker still descend, so keep STR_OPEN there.
  const bool selectingFile = mode != Mode::Books && !files.empty() && nav.selected >= 0 && nav.selected < listCount() &&
                             files[nav.selected].back() != '/';
  const bool movingHere = browserState != BrowserState::Browsing && !files.empty() &&
                          nav.selected >= 0 && nav.selected < listCount() && files[nav.selected] == MOVE_HERE_ENTRY;
  const char* confirmLabel =
      files.empty() ? "" : movingHere ? tr(STR_MOVE_HERE)
                   : multiSelecting && browserState == BrowserState::Browsing
                       ? (multiOrderPicking ? tr(STR_AIRNOTE_MULTI_REORDER) : tr(STR_SELECT))
                   : (selectingFile ? tr(STR_SELECT) : tr(STR_OPEN));
  const auto labels = mainTabButtonLabels(backLabel, confirmLabel, !files.empty());
  GUI.drawButtonHints(renderer, labels.btn1, labels.btn2, labels.btn3, labels.btn4);
}

void FileBrowserActivity::render(RenderLock&& lock) {
  if (editPopup.processRender(renderer, mappedInput)) return;
  if (multiPopup.processRender(renderer, mappedInput)) return;
  UiListActivity::render(std::move(lock));
}

size_t FileBrowserActivity::findEntry(const std::string& name) const {
  for (size_t i = 0; i < files.size(); i++)
    if (files[i] == name) return i;
  return 0;
}
