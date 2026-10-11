#include "AirNoteTodoActivity.h"
#include <HalStorage.h>
#include <I18n.h>
#include <MD5Builder.h>
#include <Memory.h>
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include "AirNoteStore.h"
#include "AirNoteTodoEdit.h"
#include "activities/util/KeyboardEntryActivity.h"
#include "components/SubpageLayout.h"
#include "components/UITheme.h"
#include "util/BookCacheUtils.h"

namespace fui = freeink::ui;
namespace {
std::string hiddenPath(const std::string& path, const char* suffix) {
  return std::string(AirNotePolicy::kDirectory) + "/." + path.substr(path.find_last_of('/') + 1) + suffix;
}
String digest(const char* data, size_t length) {
  MD5Builder md5; md5.begin(); md5.add(reinterpret_cast<const uint8_t*>(data), length); md5.calculate(); return md5.toString();
}
bool matchesFile(const std::string& path, const char* expected) {
  HalFile file;
  if (!Storage.openFileForRead("TODO", path.c_str(), file)) return false;
  const auto size = file.size();
  if (size > AirNotePolicy::kMaxTitleBytes + AirNotePolicy::kMaxBodyBytes + 3) return false;
  MD5Builder md5; md5.begin();
  uint8_t chunk[256];
  size_t remaining = size;
  while (remaining) {
    const size_t want = std::min(remaining, sizeof(chunk));
    if (file.read(chunk, want) != static_cast<int>(want)) return false;
    md5.add(chunk, want); remaining -= want;
  }
  md5.calculate(); return md5.toString() == expected;
}
// Mask1: zero is ink. Fixed 24px checkboxes do not require Unicode glyphs.
// `selected` adds a detached 1px outer ring for multi-select. It cannot replace
// the tick: rows must keep subtitle == nullptr, so the box is the only place an
// item's done state is drawn and both facts have to share one glyph -- hence
// four variants rather than two. The unselected pair stays byte-identical.
constexpr std::array<uint8_t,72> checkbox(bool checked, bool selected=false) {
  std::array<uint8_t,72> bits{};
  for (auto& byte : bits) byte = 255;
  for (int y=0;y<24;++y) for(int x=0;x<24;++x) {
    const bool ring = selected && (x==0 || x==23 || y==0 || y==23);
    const bool inside = x>=2 && x<22 && y>=2 && y<22;
    const bool border = inside && (x<4 || x>=20 || y<4 || y>=20);
    const bool tick = inside && checked && ((x>=6 && x<=10 && y>=x+3 && y<=x+5) ||
                                 (x>=10 && x<=18 && y>=23-x && y<=25-x));
    if (ring || border || tick) bits[y*3+x/8] &= ~(0x80 >> (x%8));
  }
  return bits;
}
constexpr auto emptyBox=checkbox(false), checkedBox=checkbox(true);
constexpr auto pickedEmptyBox=checkbox(false,true), pickedCheckedBox=checkbox(true,true);
}
AirNoteTodoActivity::AirNoteTodoActivity(GfxRenderer& renderer, MappedInputManager& input, std::string path)
 : UiListActivity("AirNoteTodo", renderer, input, true), path_(std::move(path)),
   backup_(hiddenPath(path_, ".bak")), staging_(hiddenPath(path_, ".part")) {}

bool AirNoteTodoActivity::recoverDirectory() {
  HalFile directory = Storage.open(AirNotePolicy::kDirectory);
  if (!directory || !directory.isDirectory()) return false;
  for (HalFile file=directory.openNextFile(); file; file=directory.openNextFile()) {
    char name[128]={}; file.getName(name,sizeof(name)); const bool regular=!file.isDirectory(); file.close();
    const std::string_view entry(name);
    if (regular && entry.size()>5 && entry.front()=='.' && entry.substr(entry.size()-4)==".bak") {
      const std::string original(entry.substr(1,entry.size()-5));
      if (AirNotePolicy::validFileName(original)) {
        const std::string path=std::string(AirNotePolicy::kDirectory)+"/"+original;
        if (!AirNoteStore::recover(Storage,path,hiddenPath(path,".bak"))) return false;
      }
    }
  }
  return true;
}
bool AirNoteTodoActivity::recognizes(const std::string& path) {
  constexpr std::string_view prefix="/AirNote/";
  if (path.compare(0,prefix.size(),prefix)!=0 || !AirNotePolicy::validFileName(std::string_view(path).substr(prefix.size()))) return false;
  if (!AirNoteStore::recover(Storage,path,hiddenPath(path,".bak"))) return false;
  HalFile file; if (!Storage.openFileForRead("TODO",path.c_str(),file)) return false;
  char head[128]={}; const int n=file.read(head,sizeof(head)); if(n<=0)return false;
  const std::string_view view(head,n); const auto split=view.find("\n\n");
  return split!=std::string_view::npos && AirNoteTodo::isTodo(view.substr(split+2));
}
const char* AirNoteTodoActivity::headerTitle() const { return count_ ? content_.get() : tr(STR_AIRNOTE_TITLE); }
void AirNoteTodoActivity::onBackButton() {
 // Mirrors the carrying_ escape: leaving a mode never writes anything.
 if(selecting_){endMultiSelect();return;}
 if(carrying_>=0){{RenderLock lock(*this);carrying_=-1;status_[0]=0;}requestUpdate();return;}
 app.clearTapFlash(); activityManager.goToAirNote();
}
void AirNoteTodoActivity::onEnter() {
  waitForConfirmRelease_=mappedInput.isPressed(MappedInputManager::Button::Confirm);
  if (!load()) std::snprintf(status_.data(),status_.size(),"%s",tr(STR_TODO_READ_FAILED));
  rebuildRows(); UiListActivity::onEnter();
}
bool AirNoteTodoActivity::load() {
  count_=0;
  if (!AirNoteStore::recover(Storage,path_,backup_)) return false;
  HalFile file; if (!Storage.openFileForRead("TODO",path_.c_str(),file)) return false;
  length_=file.size();
  if (!length_ || length_>AirNotePolicy::kMaxTitleBytes+AirNotePolicy::kMaxBodyBytes+3) return false;
  content_=makeUniqueNoThrow<char[]>(length_+1); if(!content_)return false;
  if(file.read(content_.get(),length_)!=static_cast<int>(length_))return false;
  content_[length_]=0;
  std::string_view title,body;
  size_t count=0;
  if(!AirNotePolicy::splitNote({content_.get(),length_},title,body) || !AirNoteTodo::parse(body,items_,count))return false;
  bodyOffset_=title.size()+2;count_=count;
  std::snprintf(revision_.data(),revision_.size(),"%s",digest(content_.get(),length_).c_str());
  delimit(true);status_[0]=0;return true;
}
void AirNoteTodoActivity::delimit(bool forDisplay) {
  content_[bodyOffset_-2]=forDisplay?'\0':'\n';
  for(size_t i=0;i<count_;++i)content_[bodyOffset_+items_[i].offset+4+items_[i].length]=forDisplay?'\0':'\n';
}
void AirNoteTodoActivity::rebuildRows() {
  if(!count_) { rows_[0]={};rows_[0].label=status_.data();rows_[0].enabled=false;return; }
  unsigned done=0;
  for(size_t i=0;i<count_;++i) {
    auto& row=rows_[i];row={};row.label=content_.get()+bodyOffset_+items_[i].offset+4;
    const bool picked=selecting_ && selected_[i];
    row.icon={items_[i].done?(picked?pickedCheckedBox.data():checkedBox.data())
                            :(picked?pickedEmptyBox.data():emptyBox.data()),24,24,fui::BitmapFormat::Mask1};
    row.actionValue=static_cast<int16_t>(i);done+=items_[i].done;
  }
  std::snprintf(progress_.data(),progress_.size(),tr(STR_TODO_PROGRESS),done,static_cast<unsigned>(count_));
  // The actions row takes the add row's slot rather than sitting after it, so a
  // 64-item checklist still has somewhere to open the bulk menu.
  if(selecting_) { auto& acts=rows_[count_];acts={};acts.label=tr(STR_TODO_MULTI_ACTIONS);acts.actionValue=static_cast<int16_t>(count_);return; }
  size_t trailing=count_;
  if(canAdd()) { auto& add=rows_[trailing];add={};add.label=tr(STR_TODO_ADD_ITEM);add.actionValue=static_cast<int16_t>(trailing);++trailing; }
  // Deleting several items used to need the long-press menu; this row says so
  // out loud and still deletes nothing until the confirmation is answered.
  auto& pick=rows_[trailing];pick={};pick.label=tr(STR_TODO_MULTI_SELECT);pick.actionValue=static_cast<int16_t>(trailing);
}
void AirNoteTodoActivity::activateIndex(int index) {
  if(selecting_) {
    // Selecting touches no file: the trailing row opens the bulk menu and every
    // other row only flips its own selection, so the done state never moves.
    if(index==static_cast<int>(count_))showMultiActions(); else toggleSelection(index);
    return;
  }
  if(carrying_>=0){const int from=carrying_;{RenderLock lock(*this);carrying_=-1;status_[0]=0;}moveItem(from,index-from);return;}
  if(canAdd() && index==static_cast<int>(count_)){promptAddItem();return;}
  if(canPick() && index==static_cast<int>(count_)+(canAdd()?1:0)){beginMultiSelect();return;}
  if(index<0 || static_cast<size_t>(index)>=count_)return;
  {
    // Rendering uses pointers into content_; protect delimiter/state changes.
    RenderLock lock(*this);
    if(!AirNoteStore::recover(Storage,path_,backup_) || !matchesFile(path_,revision_.data())) {
      std::snprintf(status_.data(),status_.size(),"%s",tr(STR_TODO_CHANGED));
    } else {
      auto& item=items_[index];const size_t state=bodyOffset_+item.offset+1;
      const char previous=content_[state];content_[state]=item.done?' ':'x';delimit(false);
      const bool saved=saveSerialized();
      if(saved) {
        item.done=!item.done;status_[0]=0;
        std::snprintf(revision_.data(),revision_.size(),"%s",digest(content_.get(),length_).c_str());
      } else {
        content_[state]=previous;Storage.remove(staging_.c_str());
        std::snprintf(status_.data(),status_.size(),"%s",tr(STR_TODO_SAVE_FAILED));
      }
      delimit(true);
    }
    rebuildRows();
  }
  requestUpdate();
}
bool AirNoteTodoActivity::writeContent(const char* data, const size_t length) {
  if(Storage.exists(staging_.c_str()) && !Storage.remove(staging_.c_str()))return false;
  HalFile file;
  if(!Storage.openFileForWrite("TODO",staging_.c_str(),file))return false;
  const bool written=file.write(data,length)==length;
  if(written)file.flush();
  const bool closed=file.close();
  return written && closed && AirNoteStore::replace(Storage,path_,staging_,backup_,clearBookCache);
}
bool AirNoteTodoActivity::saveSerialized() { return writeContent(content_.get(),length_); }
std::string AirNoteTodoActivity::serialized() {
  // Row labels are NUL-terminated in place for drawing; restore the on-disk
  // newlines around the copy so the edit helpers see a real note.
  delimit(false);
  std::string out(content_.get(),length_);
  delimit(true);
  return out;
}
void AirNoteTodoActivity::applyEdit(const std::string& next) {
  bool reloaded=false;
  {
    RenderLock lock(*this);
    if(!AirNoteStore::recover(Storage,path_,backup_) || !matchesFile(path_,revision_.data())) {
      std::snprintf(status_.data(),status_.size(),"%s",tr(STR_TODO_CHANGED));
    } else if(!writeContent(next.data(),next.size())) {
      Storage.remove(staging_.c_str());
      std::snprintf(status_.data(),status_.size(),"%s",tr(STR_TODO_SAVE_FAILED));
    } else if(!load()) {
      std::snprintf(status_.data(),status_.size(),"%s",tr(STR_TODO_READ_FAILED));
    } else {
      reloaded=true;
    }
    rebuildRows();
  }
  if(reloaded)moveSelectionTo(std::min(nav.selected,listCount()-1));
  requestUpdate();
}
void AirNoteTodoActivity::showItemMenu(const int index) {
  if(index<0 || static_cast<size_t>(index)>=count_)return;
  const char* actions[] = {tr(STR_TODO_EDIT_ITEM), tr(STR_TODO_DELETE_ITEM), tr(STR_TODO_MULTI_SELECT)};
  orderPopup_.show(content_.get()+bodyOffset_+items_[index].offset+4, actions, 3, 0,
                   [this,index](const int choice) {
                     if(choice==0)promptEditItem(index);
                     else if(choice==1)deleteItem(index);
                     else beginMultiSelect(index);
                   });
  requestUpdate();
}
unsigned AirNoteTodoActivity::selectedCount() const {
  unsigned chosen=0;for(size_t i=0;i<count_;++i)chosen+=selected_[i];return chosen;
}
void AirNoteTodoActivity::noteSelection() {
  // The same band the pick-up gesture writes tr(STR_AIRNOTE_PICK_TARGET) into;
  // rows cannot carry a subtitle, so the running count has nowhere else to go.
  std::snprintf(status_.data(),status_.size(),tr(STR_TODO_MULTI_SELECTED),selectedCount());
}
void AirNoteTodoActivity::beginMultiSelect() {
  if(!count_ || selecting_)return;
  {
    // Entered from the item menu or the picker row; either may have left an item
    // carried, and one row must never mean both "move here" and "select".
    RenderLock lock(*this);
    carrying_=-1;selecting_=true;selected_.fill(false);
    noteSelection();rebuildRows();
  }
  // Entering from the picker row parks the cursor on a row that just vanished.
  moveSelectionTo(std::min(nav.selected,listCount()-1));
  requestUpdate();
}
void AirNoteTodoActivity::beginMultiSelect(const int index) {
  if(index<0 || static_cast<size_t>(index)>=count_)return;
  beginMultiSelect();
  {RenderLock lock(*this);selected_[index]=true;noteSelection();rebuildRows();}
  requestUpdate();
}
void AirNoteTodoActivity::toggleSelection(const int index) {
  if(index<0 || static_cast<size_t>(index)>=count_)return;
  {RenderLock lock(*this);selected_[index]=!selected_[index];noteSelection();rebuildRows();}
  requestUpdate();
}
void AirNoteTodoActivity::endMultiSelect() {
  {RenderLock lock(*this);selecting_=false;selected_.fill(false);status_[0]=0;rebuildRows();}
  // The actions row is gone and the cursor may have been parked on it.
  moveSelectionTo(std::min(nav.selected,listCount()-1));
  requestUpdate();
}
void AirNoteTodoActivity::showMultiActions() {
  if(!selecting_ || !selectedCount())return;
  const char* actions[] = {tr(STR_TODO_MULTI_DELETE)};
  orderPopup_.show(tr(STR_TODO_MULTI_ACTIONS), actions, 1, 0, [this](const int){promptBulkDelete();});
  requestUpdate();
}
void AirNoteTodoActivity::promptBulkDelete() {
  const unsigned chosen=selectedCount();
  if(!selecting_ || !chosen)return;
  char question[160];
  std::snprintf(question,sizeof(question),tr(STR_TODO_MULTI_DELETE_CONFIRM),chosen);
  // Cancel first AND pre-selected: a mis-tap here cannot be undone. This runs
  // inside orderPopup_'s callback, so it must be a DIFFERENT popup object --
  // re-showing orderPopup_ would free the lambda still executing above us.
  const char* choices[] = {tr(STR_CANCEL), tr(STR_TODO_MULTI_DELETE)};
  confirmPopup_.show(question, choices, 2, 0, [this](const int choice){if(choice==1)performBulkDelete();});
  requestUpdate();
}
void AirNoteTodoActivity::performBulkDelete() {
  std::string next;
  {
    RenderLock lock(*this);
    if(!selecting_)return;
    std::vector<size_t> indices;indices.reserve(count_);
    for(size_t i=0;i<count_;++i)if(selected_[i])indices.push_back(i);
    if(indices.empty())return;
    // parse() rejects an item-less checklist, so refuse the whole request before
    // writing rather than leaving a note the reader can never load again.
    if(indices.size()>=count_) {
      std::snprintf(status_.data(),status_.size(),"%s",tr(STR_TODO_KEEP_ONE));
      rebuildRows();requestUpdate();return;
    }
    // One whole-content transform for the entire selection: applyEdit then gives
    // it the same revision check, staging/backup replace and reload as any edit.
    if(!AirNoteTodoEdit::removeItems(serialized(),indices,next)) {
      std::snprintf(status_.data(),status_.size(),"%s",tr(STR_TODO_SAVE_FAILED));
      rebuildRows();requestUpdate();return;
    }
    // Leave multi-select before the write: the selected line numbers stop
    // meaning anything once the splice lands, and a ring left on a row that
    // shifted up would be a lie. applyEdit reports any failure into status_.
    selecting_=false;selected_.fill(false);status_[0]=0;
    rebuildRows();
  }
  moveSelectionTo(std::min(nav.selected,listCount()-1));
  applyEdit(next);
}
void AirNoteTodoActivity::promptAddItem() {
  if(!canAdd())return;
  const std::string current=[this]{RenderLock lock(*this);return serialized();}();
  auto handler=[this,current](const ActivityResult& result) {
    if(result.isCancelled || !std::holds_alternative<KeyboardResult>(result.data))return;
    std::string next;
    if(!AirNoteTodoEdit::appendItem(current,std::get<KeyboardResult>(result.data).text,next)) {
      {RenderLock lock(*this);std::snprintf(status_.data(),status_.size(),"%s",tr(STR_TODO_SAVE_FAILED));}
      requestUpdate();return;
    }
    applyEdit(next);
  };
  if(!startActivityForResultWith<KeyboardEntryActivity>(std::move(handler),tr(STR_TODO_ADD_ITEM),std::string(),
                                                        AirNoteTodo::maxItemBytes,InputType::Text)) {
    {RenderLock lock(*this);std::snprintf(status_.data(),status_.size(),"%s",tr(STR_TODO_SAVE_FAILED));}
    requestUpdate();
  }
}
void AirNoteTodoActivity::promptEditItem(const int index) {
  if(index<0 || static_cast<size_t>(index)>=count_)return;
  std::string current,label;
  {
    RenderLock lock(*this);
    label.assign(content_.get()+bodyOffset_+items_[index].offset+4,items_[index].length);
    current=serialized();
  }
  auto handler=[this,current,index](const ActivityResult& result) {
    if(result.isCancelled || !std::holds_alternative<KeyboardResult>(result.data))return;
    std::string next;
    if(!AirNoteTodoEdit::relabelItem(current,static_cast<size_t>(index),
                                     std::get<KeyboardResult>(result.data).text,next)) {
      {RenderLock lock(*this);std::snprintf(status_.data(),status_.size(),"%s",tr(STR_TODO_SAVE_FAILED));}
      requestUpdate();return;
    }
    applyEdit(next);
  };
  if(!startActivityForResultWith<KeyboardEntryActivity>(std::move(handler),tr(STR_TODO_EDIT_ITEM),label,
                                                        AirNoteTodo::maxItemBytes,InputType::Text)) {
    {RenderLock lock(*this);std::snprintf(status_.data(),status_.size(),"%s",tr(STR_TODO_SAVE_FAILED));}
    requestUpdate();
  }
}
void AirNoteTodoActivity::deleteItem(const int index) {
  std::string next;
  {
    RenderLock lock(*this);
    // parse() rejects an item-less checklist, so the last one cannot go; the
    // whole note has to be deleted from the file browser instead.
    if(count_<=1) {
      std::snprintf(status_.data(),status_.size(),"%s",tr(STR_TODO_KEEP_ONE));
      rebuildRows();
      requestUpdate();
      return;
    }
    if(!AirNoteTodoEdit::removeItem(serialized(),static_cast<size_t>(index),next)) {
      std::snprintf(status_.data(),status_.size(),"%s",tr(STR_TODO_SAVE_FAILED));
      rebuildRows();
      requestUpdate();
      return;
    }
  }
  applyEdit(next);
}
void AirNoteTodoActivity::moveItem(int index,int direction) {
  const int target=index+direction;
  if(index<0 || target<0 || static_cast<size_t>(index)>=count_ || static_cast<size_t>(target)>=count_)return;
  if(index==target){requestUpdate();return;}
  bool moved=false;
  {
    RenderLock lock(*this);
    if(!AirNoteStore::recover(Storage,path_,backup_) || !matchesFile(path_,revision_.data())) {
      std::snprintf(status_.data(),status_.size(),"%s",tr(STR_TODO_CHANGED));
    } else {
      delimit(false);
      const size_t first=static_cast<size_t>(std::min(index,target));
      const size_t start=bodyOffset_+items_[first].offset;
      const size_t last=static_cast<size_t>(std::max(index,target));
      const size_t middle=index<target?start+items_[first].length+5:bodyOffset_+items_[last].offset;
      const size_t end=bodyOffset_+items_[last].offset+items_[last].length+5; // state, label, newline
      // Rotate whole UTF-8 lines in place, including their checked state. No
      // second 16 KiB buffer; reverse the rotation on any failed SD operation.
      std::rotate(content_.get()+start,content_.get()+middle,content_.get()+end);
      moved=saveSerialized();
      if(moved) {
        status_[0]=0;
        std::snprintf(revision_.data(),revision_.size(),"%s",digest(content_.get(),length_).c_str());
      } else {
        std::rotate(content_.get()+start,content_.get()+start+(end-middle),content_.get()+end);
        Storage.remove(staging_.c_str());
        std::snprintf(status_.data(),status_.size(),"%s",tr(STR_TODO_SAVE_FAILED));
      }
      size_t parsed=0;
      AirNoteTodo::parse({content_.get()+bodyOffset_,length_-bodyOffset_-1},items_,parsed);
      delimit(true);
    }
    rebuildRows();
  }
  if(moved)moveSelectionTo(target);
  requestUpdate();
}
void AirNoteTodoActivity::onRowLongPress(int index) {
  if(index<0 || static_cast<size_t>(index)>=count_)return;
  app.clearTapFlash();
  // Multi-select owns every row while it is on; a pick-up on top of it would
  // give one row two meanings. Back leaves the mode and restores the gesture.
  if(selecting_)return;
  if(carrying_>=0){
    // Same row means "I did not want to move this after all": reach the item
    // menu the pick-up gesture displaced, rather than dropping onto itself.
    if(index==carrying_){{RenderLock lock(*this);carrying_=-1;status_[0]=0;}showItemMenu(index);return;}
    activateIndex(index);return;
  }
  {RenderLock lock(*this);carrying_=index;std::snprintf(status_.data(),status_.size(),"%s",tr(STR_AIRNOTE_PICK_TARGET));}
  requestUpdate();
}
bool AirNoteTodoActivity::handleCustomInput() {
  // Confirmation sits on top of the actions popup, so it gets input first.
  if(confirmPopup_.handleInput(mappedInput,[this]{requestUpdate();}))return true;
  if(orderPopup_.handleInput(mappedInput,[this]{requestUpdate();}))return true;
  if(waitForConfirmRelease_) {
    if(!mappedInput.isPressed(MappedInputManager::Button::Confirm))waitForConfirmRelease_=false;
    return true;
  }
  if(mappedInput.wasLongPressed(MappedInputManager::Button::Confirm,500)) {
    waitForConfirmRelease_=true;onRowLongPress(nav.selected);return true;
  }
  return false;
}
void AirNoteTodoActivity::render(RenderLock&& lock) {
  if(confirmPopup_.processRender(renderer,mappedInput))return;
  if(orderPopup_.processRender(renderer,mappedInput))return;
  UiListActivity::render(std::move(lock));
}
void AirNoteTodoActivity::drawChrome() {
  const auto& metrics = UITheme::getInstance().getMetrics();
  GUI.drawHeader(renderer, Rect{0, metrics.topPadding, renderer.getScreenWidth(), metrics.headerHeight},
                 headerTitle(), count_ ? progress_.data() : nullptr);
  if (count_ && status_[0]) {
    // Errors belong to the whole checklist and remain visible while scrolling.
    const Rect safe = UITheme::getInstance().getScreenSafeArea(renderer, true, false);
    GUI.drawSubHeader(renderer,
                      Rect{safe.x, safe.y + metrics.topPadding + metrics.headerHeight, safe.width, metrics.tabBarHeight},
                      status_.data());
  }
}
void AirNoteTodoActivity::buildScreen(UiScreen& screen) {
  const auto& metrics=UITheme::getInstance().getMetrics();
  const Rect safe=UITheme::getInstance().getScreenSafeArea(renderer,true,false);
  const Rect content=SubpageLayout::contentRect(safe,metrics,count_ && status_[0]);
  screen.setContentMarginFromScreen(fui::Insets{static_cast<int16_t>(content.y),
    static_cast<int16_t>(renderer.getScreenWidth()-content.x-content.width),
    static_cast<int16_t>(renderer.getScreenHeight()-content.y-content.height),static_cast<int16_t>(content.x)});
  fui::ListProps props;props.items=rows_.data();props.count=listCount();props.action=ACTION_ROW;props.inputMask=fui::InputTouch | fui::InputLongPress;
  props.labelText=screen.theme().smallText;props.labelText.maxLines=6;props.iconSize=24;props.rowGap=6;
  syncListViewport(screen,props,false);screen.list(props);
}
