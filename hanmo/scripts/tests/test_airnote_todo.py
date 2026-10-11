"""Host-run actual checklist Activity against fault-injecting HAL stubs."""
from pathlib import Path
import subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[2]
STUB=r"""
#pragma once
#include <algorithm>
#include <array>
#include <cstdio>
#include <cstring>
#include <string>
#include <string_view>
#include <memory>
#include <map>
#include <vector>
#include <cassert>
#include <cstdint>
#include <variant>
#include <functional>
using String=std::string;
inline bool failAllocation=false;
template<class T> auto makeUniqueNoThrow(size_t n) { using E=std::remove_extent_t<T>; return std::unique_ptr<T>(failAllocation?nullptr:new(std::nothrow) E[n]()); }
struct HalFile;
struct FakeStorage {
 std::map<std::string,std::string> files;
 bool shortWrite=false,closeFail=false;int failRename=0,renames=0,writes=0;
 bool exists(const char* p){return files.count(p);}
 bool remove(const char* p){return files.erase(p);}
 bool rename(const char* a,const char* b){if(++renames==failRename||!exists(a)||exists(b))return false;files[b]=files[a];files.erase(a);return true;}
 bool openFileForRead(const char*,const char*,HalFile&);
 bool openFileForWrite(const char*,const char*,HalFile&);
 HalFile open(const char*);
} inline Storage;
struct HalFile {
 std::string path;size_t pos=0,iter=0;bool good=false,dir=false;
 std::vector<std::string> names;
 explicit operator bool()const{return good;}
 size_t size()const{return Storage.files.at(path).size();}
 int read(void* out,size_t n){auto& s=Storage.files[path];n=std::min(n,s.size()-pos);memcpy(out,s.data()+pos,n);pos+=n;return n;}
 size_t write(const char* data,size_t n){if(Storage.shortWrite&&n)n--;Storage.files[path].append(data,n);return n;}
 void flush(){} bool close(){good=false;return !Storage.closeFail;}
 bool isDirectory()const{return dir;}
 void getName(char* out,size_t n){snprintf(out,n,"%s",path.substr(path.find_last_of('/')+1).c_str());}
 HalFile openNextFile(){if(iter==names.size())return {};HalFile f;f.path=names[iter++];f.good=true;return f;}
};
inline bool FakeStorage::openFileForRead(const char*,const char* p,HalFile& f){if(!exists(p))return false;f.path=p;f.good=true;return true;}
inline bool FakeStorage::openFileForWrite(const char*,const char* p,HalFile& f){writes++;files[p]="";f.path=p;f.good=true;return true;}
inline HalFile FakeStorage::open(const char* p){HalFile f;f.good=true;f.dir=true;for(auto& pair:files)f.names.push_back(pair.first);return f;}
struct MD5Builder {
 std::string data;void begin(){data.clear();}void add(const uint8_t* p,size_t n){data.append((const char*)p,n);}void calculate(){}
 String toString(){char out[33];snprintf(out,sizeof(out),"%032llx",(unsigned long long)std::hash<std::string>{}(data));return out;}
};
inline bool clearBookCache(const std::string&){return true;}
enum {STR_AIRNOTE_TITLE,STR_TODO_PROGRESS,STR_TODO_READ_FAILED,STR_TODO_CHANGED,STR_TODO_SAVE_FAILED,STR_AIRNOTE_ORDER_UP,STR_AIRNOTE_ORDER_DOWN,STR_AIRNOTE_PICK_TARGET,STR_TODO_KEEP_ONE,STR_TODO_ADD_ITEM,STR_TODO_EDIT_ITEM,STR_TODO_DELETE_ITEM,STR_TODO_MULTI_SELECT,STR_TODO_MULTI_ACTIONS,STR_TODO_MULTI_DELETE,STR_TODO_MULTI_DELETE_CONFIRM,STR_TODO_MULTI_SELECTED,STR_CANCEL};
inline const char* tr(int key){switch(key){case STR_TODO_PROGRESS:return "Completed %u / %u";case STR_TODO_CHANGED:return "changed";case STR_TODO_SAVE_FAILED:return "save failed";case STR_TODO_READ_FAILED:return "read failed";case STR_TODO_KEEP_ONE:return "keep one";case STR_TODO_ADD_ITEM:return "add";case STR_TODO_EDIT_ITEM:return "edit";case STR_TODO_DELETE_ITEM:return "delete";case STR_TODO_MULTI_SELECT:return "multi select";case STR_TODO_MULTI_ACTIONS:return "multi actions";case STR_TODO_MULTI_DELETE:return "delete selected";case STR_TODO_MULTI_DELETE_CONFIRM:return "confirm delete %u";case STR_TODO_MULTI_SELECTED:return "selected %u";case STR_CANCEL:return "cancel";default:return "AirNote";}}
struct GfxRenderer{int getScreenWidth(){return 480;}int getScreenHeight(){return 800;}};
struct MappedInputManager{enum class Button{Confirm};bool isPressed(Button){return false;}bool wasLongPressed(Button,int){return false;}};struct RenderLock{template<class T>explicit RenderLock(T&){};};
namespace freeink {namespace ui {
 enum class BitmapFormat{Mask1};struct BitmapRef{const uint8_t* data=nullptr;uint16_t width=0,height=0;BitmapFormat format=BitmapFormat::Mask1;};
 struct Text{int maxLines=1;};struct ListItem{const char* label=nullptr;const char* subtitle=nullptr;BitmapRef icon{};int16_t actionValue=0;bool enabled=true;};
 struct Insets{int16_t a,b,c,d;};constexpr int InputTouch=1,InputLongPress=2;
 struct ListProps{ListItem* items;int count=0,action=0,inputMask=0,iconSize=0,rowGap=0;Text labelText;};
}}
struct UiScreen{struct Theme{freeink::ui::Text smallText;}t;auto& theme(){return t;}freeink::ui::Insets margin{}; void setContentMarginFromScreen(freeink::ui::Insets v){margin=v;}void list(freeink::ui::ListProps&){} };
struct Rect{int x=0,y=0,width=480,height=800;};
struct UITheme{static UITheme& getInstance(){static UITheme t;return t;}struct Metrics{int topPadding=10,headerHeight=40,tabBarHeight=20;}m;const Metrics& getMetrics(){return m;}Rect getScreenSafeArea(GfxRenderer&,bool,bool){return {};}};
struct ThemeDraw {std::string title,right,error;void drawHeader(GfxRenderer&,Rect,const char* t,const char* s){title=t?t:"";right=s?s:"";error.clear();}void drawSubHeader(GfxRenderer&,Rect,const char* text){error=text;}} inline GUI;
namespace SubpageLayout{inline Rect contentRect(Rect r,const UITheme::Metrics&,bool warning=false){r.y+=50+(warning?20:0);r.height-=r.y;return r;}}
// Records what the activity offered so the test can drive the real flow.
// choose() mirrors the production handleInput(): the popup deactivates and then
// runs its STILL INSTALLED std::function, so re-show()ing this same popup from
// inside the callback overwrites the running lambda and ASan sees the
// use-after-free -- that is exactly the mistake a second popup member avoids.
struct OptionPopup{
 std::string title;std::vector<std::string> options;int current=0;bool active=false;std::function<void(int)> onSelect;
 void show(const char* t,const char* const* opts,int count,int index,std::function<void(int)> cb){
  title=t?t:"";options.assign(opts,opts+count);current=index;onSelect=std::move(cb);active=true;}
 void choose(int index){assert(active);active=false;if(onSelect)onSelect(index);}
 template<class F>bool handleInput(MappedInputManager&,F){return false;}bool processRender(GfxRenderer&,MappedInputManager&){return false;}};
struct Manager{void goToAirNote(){}} inline activityManager;
struct KeyboardResult{std::string text;};enum class InputType{Text,Password,Url};class KeyboardEntryActivity{};
struct ActivityResult{bool isCancelled=false;std::variant<KeyboardResult> data;};
class UiListActivity {
 public:UiListActivity(const char*,GfxRenderer& r,MappedInputManager& i,bool=false):renderer(r),mappedInput(i){}virtual ~UiListActivity()=default;virtual void onEnter(){}
 public:GfxRenderer& renderer;MappedInputManager& mappedInput;struct {int selected=0;}nav;
 protected:struct App{void clearTapFlash(){}}app;static constexpr int ACTION_ROW=1;
 virtual int listCount()const=0;virtual const char* headerTitle()const=0;virtual void buildScreen(UiScreen&)=0;virtual void drawChrome(){};virtual void activateIndex(int)=0;virtual void onBackButton(){};virtual void onRowLongPress(int){};virtual bool handleCustomInput(){return false;}
 public:virtual void render(RenderLock&&){}
 protected:void moveSelectionTo(int i){nav.selected=i;}
 void requestUpdate(){}void syncListViewport(UiScreen&,freeink::ui::ListProps&,bool){}
 public:std::function<void(const ActivityResult&)> keyboardHandler;std::string keyboardPrefill;size_t keyboardLimit=0;bool keyboardFails=false;
 // Captures the keyboard callback so the test can answer the prompt itself.
 template<class T,class F>bool startActivityForResultWith(F&&h,const char*,std::string prefill,size_t limit,InputType){
  if(keyboardFails)return false;keyboardHandler=std::forward<F>(h);keyboardPrefill=std::move(prefill);keyboardLimit=limit;return true;}
 void answerKeyboard(const std::string& text){ActivityResult r;r.data=KeyboardResult{text};auto h=keyboardHandler;keyboardHandler=nullptr;h(r);}
 void cancelKeyboard(){ActivityResult r;r.isCancelled=true;auto h=keyboardHandler;keyboardHandler=nullptr;h(r);}
};
"""
CODE=r"""
#include "stub.h"
#define private public
#include "src/activities/apps/airnote/AirNoteTodoActivity.cpp"
#undef private
int main(){
 using namespace AirNoteTodo;
 std::string body;Items items;size_t count=0;
 assert(encode("買書\n[x] 充電\n\n[ ] 帶水\r\n",body));assert(parse(body,items,count)&&count==3&&items[1].done);
 assert(!encode("",body));assert(!encode(" \n",body));assert(!encode(std::string(241,'a'),body));
 assert(!encode(std::string("bad\0value",9),body));assert(!encode(std::string("\xc0\xaf",2),body));
 std::string large;for(int i=0;i<64;i++)large+="事項\n";assert(encode(large,body));assert(parse(body,items,count)&&count==64);assert(!encode(large+"extra",body));
 assert(!parse(std::string(marker)+"[q] bad",items,count));assert(!parse(std::string(marker)+"[ ] ok\n",items,count));
 assert(encode("買書\n[x] 充電\n帶水",body));
 const std::string path="/AirNote/準備.txt", original=AirNotePolicy::noteContent("準備",body);
 Storage.files[path]=original;Storage.files["/AirNote/普通.txt"]=AirNotePolicy::noteContent("普通","原本內容");
 assert(AirNoteTodoActivity::recognizes(path));assert(!AirNoteTodoActivity::recognizes("/AirNote/普通.txt"));assert(!AirNoteTodoActivity::recognizes("/Else/準備.txt"));
 GfxRenderer renderer;MappedInputManager input;
 AirNoteTodoActivity activity(renderer,input,path);activity.onEnter();
 assert(activity.count_==3);assert(std::string(activity.rows_[0].label)=="買書");assert(std::string(activity.progress_.data())=="Completed 1 / 3");
 for(size_t i=0;i<activity.count_;++i)assert(activity.rows_[i].subtitle==nullptr);
 activity.drawChrome();assert(GUI.title=="準備"&&GUI.right=="Completed 1 / 3"&&GUI.error.empty());
 UiScreen normal;activity.buildScreen(normal);assert(normal.margin.a==50);
 activity.activateIndex(0);assert(activity.items_[0].done);assert(Storage.files[path].find("[x] 買書")!=std::string::npos);
 activity.drawChrome();assert(GUI.right=="Completed 2 / 3");
 const auto saved=Storage.files[path];
 AirNoteTodoActivity reopened(renderer,input,path);reopened.onEnter();assert(reopened.items_[0].done&&reopened.items_[1].done);
 reopened.activateIndex(1);assert(!reopened.items_[1].done);assert(Storage.files[path].find("[ ] 充電")!=std::string::npos);
 // A stale screen must not overwrite a device/web edit.
 activity.activateIndex(2);assert(!activity.items_[2].done);assert(std::string(activity.status_.data())=="changed");
 // Actual Activity must retain checkbox and disk contents on write/close/rename faults.
 for(int failure=0;failure<4;failure++){
  Storage.files.clear();Storage.files[path]=original;Storage.shortWrite=false;Storage.closeFail=false;Storage.renames=0;Storage.failRename=0;
  AirNoteTodoActivity failing(renderer,input,path);failing.onEnter();
  if(failure==0)Storage.shortWrite=true;if(failure==1)Storage.closeFail=true;if(failure>=2)Storage.failRename=failure-1;
  failing.activateIndex(0);assert(!failing.items_[0].done);assert(Storage.files[path]==original);assert(std::string(failing.status_.data())=="save failed");
  assert(std::string(failing.rows_[0].label)=="買書");
  failing.drawChrome();assert(GUI.error=="save failed"&&GUI.right=="Completed 1 / 3");
  for(size_t i=0;i<failing.count_;++i)assert(failing.rows_[i].subtitle==nullptr);
  UiScreen failed;failing.buildScreen(failed);assert(failed.margin.a==70);
 }
 Storage.shortWrite=false;Storage.closeFail=false;Storage.failRename=0;
 Storage.files.clear();Storage.files["/AirNote/.準備.txt.bak"]=saved;
 assert(AirNoteTodoActivity::recoverDirectory());assert(Storage.files[path]==saved);
 AirNoteTodoActivity recovered(renderer,input,path);recovered.onEnter();assert(recovered.count_==3&&recovered.items_[0].done);

 // Reordering rotates unequal-length UTF-8 lines and keeps each checkbox.
 Storage.files.clear();Storage.files[path]=AirNotePolicy::noteContent("準備",std::string(marker)+"[ ] 米\n[x] 已完成很長的事項\n[ ] 水果");
 AirNoteTodoActivity ordering(renderer,input,path);ordering.onEnter();
 ordering.moveItem(0,1);assert(std::string(ordering.rows_[0].label)=="已完成很長的事項"&&ordering.items_[0].done);
 assert(std::string(ordering.rows_[1].label)=="米"&&!ordering.items_[1].done);
 ordering.moveItem(1,1);assert(std::string(ordering.rows_[2].label)=="米");
 ordering.moveItem(2,-1);assert(std::string(ordering.rows_[1].label)=="米");
 ordering.moveItem(0,2);assert(ordering.items_[2].done);ordering.moveItem(2,-2);assert(ordering.items_[0].done);
 ordering.onRowLongPress(0);assert(ordering.carrying_==0);ordering.activateIndex(2);assert(ordering.carrying_==-1&&ordering.items_[2].done);ordering.moveItem(2,-2);
 ordering.onRowLongPress(0);ordering.onBackButton();assert(ordering.carrying_==-1&&ordering.items_[0].done);
 const auto ordered=Storage.files[path];ordering.moveItem(0,-1);ordering.moveItem(2,1);assert(Storage.files[path]==ordered);
 AirNoteTodoActivity orderReload(renderer,input,path);orderReload.onEnter();assert(orderReload.items_[0].done&&std::string(orderReload.rows_[2].label)=="水果");
 orderReload.activateIndex(2);ordering.moveItem(0,1);assert(std::string(ordering.status_.data())=="changed");
 for(int failure=0;failure<4;failure++){
  Storage.files.clear();Storage.files[path]=ordered;Storage.shortWrite=false;Storage.closeFail=false;Storage.renames=0;Storage.failRename=0;
  AirNoteTodoActivity failing(renderer,input,path);failing.onEnter();
  if(failure==0)Storage.shortWrite=true;if(failure==1)Storage.closeFail=true;if(failure>=2)Storage.failRename=failure-1;
  failing.moveItem(2,-2);assert(Storage.files[path]==ordered);assert(failing.items_[0].done);
  assert(std::string(failing.rows_[0].label)=="已完成很長的事項"&&std::string(failing.rows_[1].label)=="米");
  assert(std::string(failing.status_.data())=="save failed");
 }
 Storage.shortWrite=false;Storage.closeFail=false;Storage.failRename=0;
 // --- add / relabel / delete driven through the real activity ---
 {
  // Real on-disk shape: title, blank line, then the marker-led checklist body.
  auto note=[](const std::string& items){return AirNotePolicy::noteContent("List",std::string(AirNoteTodo::marker)+items);};
  Storage.files.clear();Storage.files[path]=note("[ ] one\n[x] two");
  AirNoteTodoActivity act(renderer,input,path);act.onEnter();
  assert(act.count_==2);assert(act.listCount()==4);  // two items, the add row, the delete picker
  assert(std::string(act.rows_[2].label)=="add"&&std::string(act.rows_[3].label)=="multi select");
  act.activateIndex(2);assert(act.keyboardHandler);assert(act.keyboardLimit==AirNoteTodo::maxItemBytes);
  act.answerKeyboard("three");
  assert(act.count_==3);assert(Storage.files[path]==note("[ ] one\n[x] two\n[ ] three"));
  act.activateIndex(3);act.cancelKeyboard();  // cancelling changes nothing
  assert(act.count_==3&&Storage.files[path]==note("[ ] one\n[x] two\n[ ] three"));
  act.promptEditItem(1);assert(act.keyboardPrefill=="two");
  act.answerKeyboard("second");  // relabelling keeps the checked state
  assert(Storage.files[path]==note("[ ] one\n[x] second\n[ ] three"));
  act.deleteItem(0);
  assert(act.count_==2&&Storage.files[path]==note("[x] second\n[ ] three"));
  act.deleteItem(0);act.deleteItem(0);  // the last item may not go
  assert(act.count_==1&&std::string(act.status_.data())=="keep one");
  assert(Storage.files[path]==note("[ ] three"));
  std::string full;for(int i=0;i<64;++i){full+="[ ] x";if(i<63)full+="\n";}
  Storage.files[path]=note(full);AirNoteTodoActivity big(renderer,input,path);big.onEnter();
  assert(big.count_==64&&big.listCount()==65);  // no add row when full, the picker stays
  assert(std::string(big.rows_[64].label)=="multi select");
 }

 // --- multi-select plus confirmed bulk delete INSIDE one checklist note ---
 {
  auto note=[](const std::string& items){return AirNotePolicy::noteContent("List",std::string(AirNoteTodo::marker)+items);};
  // One whole-content transform, and the whole request is validated up front:
  // a bad index must not splice the good ones out first.
  const std::string three=note("[ ] a\n[x] b\n[ ] c");
  std::string spliced;
  assert(AirNoteTodoEdit::removeItems(three,{0,2},spliced)&&spliced==note("[x] b"));
  assert(AirNoteTodoEdit::removeItems(three,{2,0},spliced)&&spliced==note("[x] b"));  // index order irrelevant
  assert(!AirNoteTodoEdit::removeItems(three,{1,1},spliced)&&spliced.empty());        // a repeat would drop two lines
  assert(!AirNoteTodoEdit::removeItems(three,{3},spliced)&&spliced.empty());          // out of range
  assert(!AirNoteTodoEdit::removeItems(three,{},spliced));
  assert(!AirNoteTodoEdit::removeItems(three,{0,1,2},spliced));                       // parse rejects an empty checklist
  assert(AirNoteTodoEdit::readable(note("[x] b")));

  Storage.files.clear();Storage.files[path]=note("[ ] one\n[x] two\n[ ] three\n[x] four");
  const auto pristine=Storage.files[path];
  AirNoteTodoActivity act(renderer,input,path);act.onEnter();
  assert(act.count_==4&&act.listCount()==6);
  assert(std::string(act.rows_[4].label)=="add"&&std::string(act.rows_[5].label)=="multi select");
  // (a) the item menu's third action enters multi-select with that row selected
  act.onRowLongPress(1);act.onRowLongPress(1);  // pick up, long-press again -> item menu
  assert(act.orderPopup_.active&&act.orderPopup_.options.size()==3);
  assert(act.orderPopup_.options[0]=="edit"&&act.orderPopup_.options[1]=="delete");
  assert(act.orderPopup_.options[2]=="multi select");
  act.orderPopup_.choose(2);
  assert(act.selecting_&&act.selected_[1]&&!act.selected_[0]&&!act.selected_[2]&&!act.selected_[3]);
  assert(act.carrying_==-1);
  assert(act.listCount()==5&&std::string(act.rows_[4].label)=="multi actions");
  assert(std::string(act.status_.data())=="selected 1");
  act.drawChrome();assert(GUI.error=="selected 1");
  // (b) every other row toggles its selection: no done flip, nothing reaches SD
  Storage.writes=0;
  act.activateIndex(2);
  assert(act.selected_[2]&&!act.items_[2].done&&Storage.files[path]==pristine&&Storage.writes==0);
  assert(std::string(act.status_.data())=="selected 2");
  act.drawChrome();assert(GUI.error=="selected 2");
  act.activateIndex(2);assert(!act.selected_[2]&&std::string(act.status_.data())=="selected 1");
  act.activateIndex(2);assert(act.selected_[2]&&Storage.writes==0);
  // Selection shows in the row glyph and NEVER in a subtitle; the done state
  // stays visible while selected, so all four variants must differ.
  assert(act.rows_[1].icon.data!=act.rows_[0].icon.data);
  assert(act.rows_[2].icon.data!=act.rows_[0].icon.data);
  assert(act.rows_[1].icon.data!=act.rows_[2].icon.data);
  assert(act.rows_[3].icon.data!=act.rows_[0].icon.data&&act.rows_[3].icon.data!=act.rows_[1].icon.data);
  for(int i=0;i<act.listCount();++i)assert(act.rows_[i].subtitle==nullptr);
  // (c) the actions row opens the bulk menu, which opens a SECOND popup
  act.activateIndex(4);
  assert(act.orderPopup_.active&&act.orderPopup_.title=="multi actions");
  assert(act.orderPopup_.options.size()==1&&act.orderPopup_.options[0]=="delete selected");
  act.orderPopup_.choose(0);
  assert(!act.orderPopup_.active&&act.confirmPopup_.active);
  assert(act.confirmPopup_.title=="confirm delete 2");
  assert(act.confirmPopup_.options.size()==2&&act.confirmPopup_.options[0]=="cancel");
  assert(act.confirmPopup_.current==0);  // destructive confirmation defaults to Cancel
  act.confirmPopup_.choose(0);
  assert(Storage.files[path]==pristine&&Storage.writes==0&&act.count_==4);
  assert(act.selecting_&&act.selected_[1]&&act.selected_[2]);  // cancelling keeps the selection
  act.activateIndex(4);act.orderPopup_.choose(0);
  act.confirmPopup_.choose(1);
  assert(Storage.writes==1);  // one transform, not one write per item
  assert(act.count_==2&&!act.selecting_);
  assert(Storage.files[path]==note("[ ] one\n[x] four"));
  assert(std::string(act.rows_[0].label)=="one"&&!act.items_[0].done);
  assert(std::string(act.rows_[1].label)=="four"&&act.items_[1].done);
  assert(AirNoteTodoEdit::readable(Storage.files[path]));
  assert(act.listCount()==4&&std::string(act.rows_[2].label)=="add");
  assert(std::string(act.rows_[3].label)=="multi select");
  assert(!act.selected_[0]&&!act.selected_[1]&&act.status_[0]==0);
  act.activateIndex(0);  // the ordinary toggle is back
  assert(act.items_[0].done&&Storage.files[path]==note("[x] one\n[x] four"));

  // (d) selecting every item is refused before anything is written
  Storage.files.clear();Storage.files[path]=note("[ ] one\n[x] two\n[ ] three");
  const auto untouched=Storage.files[path];
  AirNoteTodoActivity all(renderer,input,path);all.onEnter();
  all.onRowLongPress(0);all.onRowLongPress(0);all.orderPopup_.choose(2);
  all.activateIndex(1);all.activateIndex(2);
  assert(all.selected_[0]&&all.selected_[1]&&all.selected_[2]);
  Storage.writes=0;
  all.activateIndex(3);all.orderPopup_.choose(0);
  assert(all.confirmPopup_.title=="confirm delete 3");
  all.confirmPopup_.choose(1);
  assert(Storage.writes==0&&Storage.files[path]==untouched&&all.count_==3&&all.selecting_);
  assert(std::string(all.status_.data())=="keep one");

  // (e) a write / close / rename fault keeps every item and the exact bytes
  for(int failure=0;failure<4;failure++){
   Storage.files.clear();Storage.files[path]=note("[ ] one\n[x] two\n[ ] three");
   const auto before=Storage.files[path];
   Storage.shortWrite=false;Storage.closeFail=false;Storage.renames=0;Storage.failRename=0;
   AirNoteTodoActivity failing(renderer,input,path);failing.onEnter();
   failing.onRowLongPress(0);failing.onRowLongPress(0);failing.orderPopup_.choose(2);
   if(failure==0)Storage.shortWrite=true;if(failure==1)Storage.closeFail=true;if(failure>=2)Storage.failRename=failure-1;
   failing.activateIndex(3);failing.orderPopup_.choose(0);failing.confirmPopup_.choose(1);
   assert(Storage.files[path]==before);
   assert(failing.count_==3&&std::string(failing.rows_[0].label)=="one"&&std::string(failing.rows_[2].label)=="three");
   assert(!failing.items_[0].done&&failing.items_[1].done&&!failing.items_[2].done);
   assert(std::string(failing.status_.data())=="save failed");
  }
  Storage.shortWrite=false;Storage.closeFail=false;Storage.failRename=0;Storage.renames=0;

  // (f) a stale on-disk revision reports the change and writes nothing
  Storage.files.clear();Storage.files[path]=note("[ ] one\n[x] two\n[ ] three");
  AirNoteTodoActivity stale(renderer,input,path);stale.onEnter();
  stale.onRowLongPress(0);stale.onRowLongPress(0);stale.orderPopup_.choose(2);
  Storage.files[path]=note("[ ] one\n[x] two\n[ ] three\n[ ] web");
  const auto webEdit=Storage.files[path];Storage.writes=0;
  stale.activateIndex(3);stale.orderPopup_.choose(0);stale.confirmPopup_.choose(1);
  assert(Storage.writes==0&&Storage.files[path]==webEdit);
  assert(std::string(stale.status_.data())=="changed");

  // (g) Back leaves multi-select without touching the note
  Storage.files.clear();Storage.files[path]=note("[ ] one\n[x] two\n[ ] three");
  const auto kept=Storage.files[path];
  AirNoteTodoActivity backing(renderer,input,path);backing.onEnter();
  backing.onRowLongPress(0);backing.onRowLongPress(0);backing.orderPopup_.choose(2);
  backing.activateIndex(2);assert(backing.selecting_&&backing.selected_[0]&&backing.selected_[2]);
  Storage.writes=0;
  backing.onBackButton();
  assert(!backing.selecting_&&!backing.selected_[0]&&!backing.selected_[2]);
  assert(Storage.files[path]==kept&&Storage.writes==0&&backing.count_==3&&backing.items_[1].done);
  assert(backing.status_[0]==0&&backing.listCount()==5&&std::string(backing.rows_[3].label)=="add");
  assert(std::string(backing.rows_[4].label)=="multi select");
  assert(backing.rows_[0].icon.data==backing.rows_[2].icon.data);  // the rings are gone

  // A full checklist offers no add row, but multi-select still needs its actions row.
  std::string full;for(int i=0;i<64;++i){full+="[ ] x";if(i<63)full+="\n";}
  Storage.files.clear();Storage.files[path]=note(full);
  AirNoteTodoActivity big(renderer,input,path);big.onEnter();
  assert(big.count_==64&&big.listCount()==65);
  big.onRowLongPress(0);big.onRowLongPress(0);big.orderPopup_.choose(2);
  assert(big.selecting_&&big.listCount()==65&&std::string(big.rows_[64].label)=="multi actions");
  Storage.writes=0;big.activateIndex(64);big.orderPopup_.choose(0);big.confirmPopup_.choose(1);
  assert(Storage.writes==1&&big.count_==63&&!big.selecting_&&big.listCount()==65);

  // (h) the picker row under the items enters multi-select with NOTHING chosen,
  // so a stray tap on it can never delete anything on its own.
  Storage.files.clear();Storage.files[path]=note("[ ] one\n[x] two\n[ ] three");
  const auto intact=Storage.files[path];
  AirNoteTodoActivity picker(renderer,input,path);picker.onEnter();
  assert(picker.listCount()==5&&std::string(picker.rows_[3].label)=="add");
  assert(std::string(picker.rows_[4].label)=="multi select");
  Storage.writes=0;picker.nav.selected=4;
  picker.activateIndex(4);
  assert(picker.selecting_&&!picker.selected_[0]&&!picker.selected_[1]&&!picker.selected_[2]);
  assert(std::string(picker.status_.data())=="selected 0");
  assert(picker.listCount()==4&&std::string(picker.rows_[3].label)=="multi actions");
  assert(picker.nav.selected==3);  // the row it was parked on no longer exists
  picker.activateIndex(3);  // nothing chosen yet: the bulk menu stays shut
  assert(!picker.orderPopup_.active&&Storage.writes==0&&Storage.files[path]==intact);
  picker.activateIndex(1);assert(picker.selected_[1]&&std::string(picker.status_.data())=="selected 1");
  picker.activateIndex(3);picker.orderPopup_.choose(0);
  assert(picker.confirmPopup_.active&&picker.confirmPopup_.title=="confirm delete 1");
  assert(picker.confirmPopup_.current==0);
  picker.confirmPopup_.choose(0);
  assert(Storage.writes==0&&Storage.files[path]==intact&&picker.selecting_);
  picker.activateIndex(3);picker.orderPopup_.choose(0);picker.confirmPopup_.choose(1);
  assert(Storage.writes==1&&picker.count_==2&&!picker.selecting_);
  assert(Storage.files[path]==note("[ ] one\n[ ] three"));
  assert(picker.listCount()==4&&std::string(picker.rows_[3].label)=="multi select");
  // Back from the picker row leaves the note exactly as it was.
  picker.activateIndex(3);assert(picker.selecting_);
  picker.onBackButton();
  assert(!picker.selecting_&&picker.listCount()==4&&Storage.writes==1);
 }
 failAllocation=true;AirNoteTodoActivity oom(renderer,input,path);oom.onEnter();assert(oom.count_==0&&std::string(oom.status_.data())=="read failed");
}
"""
class ChecklistTest(unittest.TestCase):
 def test_activity_state_persistence_faults_and_format_limits(self):
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp);(p/'stub.h').write_text(STUB)
   for name in ['HalStorage.h','I18n.h','MD5Builder.h','Memory.h','activities/UiListActivity.h','components/OptionPopup.h','components/SubpageLayout.h','components/UITheme.h','util/BookCacheUtils.h','activities/util/KeyboardEntryActivity.h']:
    f=p/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text('#include "stub.h"\n')
   (p/'test.cpp').write_text(CODE)
   subprocess.run(['g++','-std=c++17','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(p),'-I'+str(ROOT),'-I'+str(ROOT/'src'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
   subprocess.run([str(p/'test')],check=True)
if __name__=='__main__':unittest.main()
