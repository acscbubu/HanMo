"""Host tests of real FileBrowserActivity method bodies against fault-injecting HAL/input fakes."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'src/activities/home/FileBrowserActivity.cpp'
METHODS = ('showEditMenu', 'executeEditAction', 'isAirNoteRoot', 'activateIndex',
           'onRowLongPress', 'activateSelected', 'handleCustomInput', 'handleButtons',
           'startMultiSelect', 'toggleMultiSelection', 'cancelMultiSelect',
           'showMultiActions', 'beginMultiOrder', 'completeMultiOrder',
           'beginMultiMove', 'completeMultiMove', 'promptMultiDelete', 'performMultiDelete')

def method(source, name):
    match = re.search(r'^(?:void|bool) FileBrowserActivity::' + name + r'\s*\(', source, re.M)
    if not match:
        raise AssertionError('missing FileBrowserActivity::' + name)
    start = source.find('{', match.end())
    depth = 0
    for pos in range(start, len(source)):
        if source[pos] == '{':
            depth += 1
        if source[pos] == '}':
            depth -= 1
            if depth == 0:
                return source[match.start():pos + 1]
    raise AssertionError('unclosed FileBrowserActivity::' + name)

STUB = r'''
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <functional>
#include <map>
#include <set>
#include <string>
#include <vector>
#include <variant>
#include <cstdint>
#include <string_view>
#define LOG_ERR(...) ((void)0)
using std::string;
constexpr char NEW_NOTE_ENTRY[]="\x02", MOVE_HERE_ENTRY[]="\x01", MULTI_ACTION_ENTRY[]="\x03";
constexpr unsigned long GO_HOME_MS=1000;
string cleanEntryName(string s){if(!s.empty()&&s.back()=='/')s.pop_back();return s;}
string joinPath(const string& p,const string& n){return p=="/"?"/"+n:p+"/"+n;}
namespace AirNotePolicy { constexpr char kDirectory[]="/AirNote"; bool validFileName(const string& s){return s.size()>4 && s.substr(s.size()-4)==".txt" && s[0]!='.' && s.find('/')==string::npos;} }
namespace FsHelpers {bool isValidPathComponent(std::string_view s){return !s.empty()&&s.find('/')==s.npos;}bool isProtectedPathComponent(std::string_view s){return s.empty()||s[0]=='.'||s=="XTCache"||s=="System Volume Information";} }
enum class StrId {STR_OK_BUTTON,STR_RENAME,STR_MOVE,STR_DELETE,STR_AIRNOTE_MOVE_TO,
 STR_AIRNOTE_ORDER_CHANGED,STR_TODO_SAVE_FAILED,STR_FILE_OPERATION_FAILED,
 STR_INVALID_FILE_NAME,STR_TARGET_EXISTS,STR_CANNOT_MOVE_HERE,STR_FILE_DATA_MIGRATION_FAILED,
 STR_AIRNOTE_MULTI_SELECT,STR_AIRNOTE_MULTI_ACTIONS,STR_AIRNOTE_MULTI_REORDER,
 STR_AIRNOTE_MULTI_MOVE,STR_AIRNOTE_MULTI_DELETE,STR_AIRNOTE_MULTI_LIMIT,
 STR_AIRNOTE_MULTI_END,STR_AIRNOTE_MULTI_DELETE_CONFIRM,
 STR_AIRNOTE_MULTI_MOVE_RESULT,STR_AIRNOTE_MULTI_DELETE_RESULT};
const char* translate(StrId id){switch(id){
 case StrId::STR_AIRNOTE_MULTI_MOVE_RESULT:return "Moved %u/%u (metadata errors %u)";
 case StrId::STR_AIRNOTE_MULTI_DELETE_RESULT:return "Deleted %u/%u (cache errors %u)";
 case StrId::STR_AIRNOTE_MULTI_DELETE_CONFIRM:return "Delete %u selected notes?";
 default:return "label";}}
#define tr(id) translate(StrId::id)
struct RenderLock {template<class T>RenderLock(T&){} void unlock(){} };
struct MappedInputManager {
 enum class Button{Back,Confirm}; enum class SwipeDir{None,Up,Down};
 bool back=false,confirm=false;unsigned held=0;
 bool wasReleased(Button b){return b==Button::Back?back:confirm;}
 unsigned getHeldTime(){return held;}
 SwipeDir wasSwipe(){return SwipeDir::None;}
};
struct OptionPopup {
 std::function<void(int)> callback;int count=0;string title;
 void show(const char* t,const char* const*,int n,int,std::function<void(int)> cb){title=t;count=n;callback=std::move(cb);}
 bool handleInput(MappedInputManager&,std::function<void()>){return false;}
 void select(int n){auto cb=callback;callback=nullptr;cb(n);}
};
std::map<string,int> activeFiles;
struct HalFile {
 bool good=false,dir=false;string path;
 HalFile(bool g,bool d,const char* p):good(g),dir(d),path(p){if(good&&!dir)++activeFiles[path];}
 HalFile(const HalFile&)=delete;HalFile& operator=(const HalFile&)=delete;
 ~HalFile(){close();}
 void close(){if(good&&!dir)--activeFiles[path];good=false;}
 explicit operator bool()const{return good;}bool isDirectory()const{return dir;}
};
struct FakeStorage {
 std::map<string,string> data;std::set<string> dirs{"/","/AirNote","/Archive","/Other","/XTCache"};
 int renames=0, failRename=0, removes=0, failRemove=0;
 bool exists(const char* p){return data.count(p)||dirs.count(p);}
 HalFile open(const char* p){return {exists(p),dirs.count(p)!=0,p};}
 bool rename(const char* a,const char* b){++renames;if(renames==failRename||activeFiles[a]||!data.count(a)||exists(b))return false;data[b]=data[a];data.erase(a);return true;}
 bool remove(const char* p){++removes;if(removes==failRemove||activeFiles[p])return false;return data.erase(p)!=0;}
} Storage;
namespace AirNoteOrdering {
 enum class Result{Saved,Conflict,Missing,StorageError};
 Result next=Result::Saved;int calls=0;std::vector<string> names;string before,expected;
 Result moveManyBefore(const std::vector<string>& n,const char* b,const string& e){calls++;names=n;before=b?b:"<end>";expected=e;return next;}
}
int caches=0;string cacheFailure;bool clearBookCache(const string& path){++caches;return path!=cacheFailure;}
struct FilePathResult{string path;};struct ActivityResult{bool isCancelled=false;ActivityResult()=default;ActivityResult(FilePathResult){}ActivityResult(bool b):isCancelled(b){}};class ConfirmationActivity{};
struct ButtonNavigator{static int nextPageIndex(int,int,int){return 0;}static int previousPageIndex(int,int,int){return 0;}};struct InxGridGeometry{static constexpr int itemsPerPage=8;};
struct FileBrowserActivity {
 static constexpr size_t MAX_SELECTED_NOTES=32;
 enum class Mode{Books,PickFirmware};enum class EditAction:uint8_t{Rename,Move,Delete,OrderPick,MultiSelect};
 enum class BrowserState:uint8_t{Browsing,ChoosingMoveDestination,ChoosingMultiMoveDestination};
 Mode mode=Mode::Books;BrowserState browserState=BrowserState::Browsing;
 string basepath="/AirNote",orderCarrying,airNoteOrderRevision="revision",moveSourcePath,moveReturnPath,moveSourceEntry;
 std::vector<string> files{NEW_NOTE_ENTRY,"a.txt","b.txt","c.txt"},multiSelected;
 bool multiSelecting=false,multiOrderPicking=false;
 int moveReturnIndex=0;struct {int selected=1,top=0;void follow(int){};} nav;
 struct {void clearTapFlash(){}} app; MappedInputManager mappedInput;
 OptionPopup editPopup,multiPopup;StrId notice=StrId::STR_OK_BUTTON;string noticeText,confirmationBody;
 int redraws=0,rebuilt=0;bool home=false;std::function<void(const ActivityResult&)> confirmation;
 int listCount()const{return static_cast<int>(files.size());}
 void requestUpdate(bool=false){++redraws;}
 void rebuildRowItems(){++rebuilt;}
 void loadFiles(){files=basepath=="/AirNote"?std::vector<string>{NEW_NOTE_ENTRY,"a.txt","b.txt","c.txt"}:
     std::vector<string>{MOVE_HERE_ENTRY,"Other/"};if(multiSelecting && browserState==BrowserState::Browsing)files[0]=MULTI_ACTION_ENTRY;}
 size_t findEntry(const string& name){auto i=std::find(files.begin(),files.end(),name);return i==files.end()?0:i-files.begin();}
 string selectedPath()const{return joinPath(basepath,cleanEntryName(files[nav.selected]));}
 void showNotice(StrId id){notice=id;}
 void showNotice(const string& text){noticeText=text;}
 void moveAirNote(int){}
 void promptRename(){} void beginMove(){} void completeMove(){} void cancelMove(){} void promptDelete(const string&,const string&){}
 void promptNewNote(){}string openedBook,editedPlain;bool supportsPlain=false;
 bool promptEditAirNote(const string& path){editedPlain=path;return supportsPlain;}
 void onSelectBook(const string& path){openedBook=path;}void onGoHome(){home=true;}
 void finish(){}void setResult(ActivityResult){} void finishEdit(const string&,int,const string& selected=string()){(void)selected;}
 bool usesIconLayout()const{return false;}void moveSelectionTo(int n){nav.selected=n;}
 bool relocatePathData(const string&,const string&,bool){return true;}
 template<class T,class F>bool startActivityForResultWith(F&& fn,const string&,const string& body){confirmation=std::forward<F>(fn);confirmationBody=body;return true;}
 void showEditMenu();void executeEditAction(EditAction);bool isAirNoteRoot()const;
 void activateIndex(int);void onRowLongPress(int);void activateSelected();bool handleCustomInput();bool handleButtons();
 void startMultiSelect();void toggleMultiSelection(int);void cancelMultiSelect();
 void showMultiActions();void beginMultiOrder();void completeMultiOrder(int);
 void beginMultiMove();void completeMultiMove();void promptMultiDelete();void performMultiDelete(const std::vector<string>&);
};
'''

MAIN = r'''
int main(){
 auto reset=[](){activeFiles.clear();Storage=FakeStorage{};Storage.data={{"/AirNote/a.txt","a"},{"/AirNote/b.txt","b"},{"/AirNote/c.txt","c"}};
  AirNoteOrdering::next=AirNoteOrdering::Result::Saved;AirNoteOrdering::calls=0;caches=0;cacheFailure.clear();};
 reset();FileBrowserActivity a;
 // Tapping a plain note opens editing; checklists still use the reader route.
 reset();FileBrowserActivity plain;plain.supportsPlain=true;plain.activateSelected();
 assert(plain.editedPlain=="/AirNote/a.txt"&&plain.openedBook.empty());
 FileBrowserActivity checklist;checklist.activateSelected();
 assert(checklist.editedPlain=="/AirNote/a.txt"&&checklist.openedBook=="/AirNote/a.txt");
 // Entry is explicit: first press picks a single note; pressing it again reveals the note menu.
 a.onRowLongPress(1);assert(a.orderCarrying=="a.txt");a.onRowLongPress(1);
 assert(a.orderCarrying.empty()&&a.editPopup.count==5);a.editPopup.select(4);
 assert(a.multiSelecting&&a.multiSelected==std::vector<string>{"a.txt"});
 // Touch and confirm release toggle; synthetic actions row is never selected.
 a.nav.selected=2;a.activateIndex(2);assert(a.multiSelected.size()==2);
 a.nav.selected=3;a.mappedInput.confirm=true;a.handleButtons();a.mappedInput.confirm=false;
 assert(a.multiSelected.size()==3);
 a.nav.selected=0;a.activateIndex(0);assert(a.multiSelected.size()==3&&a.multiPopup.count==3);
 a.multiPopup.select(0);assert(a.multiOrderPicking&&a.files[0]==MULTI_ACTION_ENTRY);
 // Catalog order, not toggle order, is submitted as an inseparable block.
 a.toggleMultiSelection(1);a.toggleMultiSelection(1);
 a.nav.selected=2;a.activateIndex(2);assert(AirNoteOrdering::calls==0); // selected target is not a drop
 a.nav.selected=0;a.activateIndex(0);assert(AirNoteOrdering::calls==1);
 assert((AirNoteOrdering::names==std::vector<string>{"a.txt","b.txt","c.txt"}));
 assert(AirNoteOrdering::before=="<end>"&&AirNoteOrdering::expected=="revision"&&!a.multiSelecting);
 // Stale catalog cannot be overwritten, and the list is refreshed.
 reset();FileBrowserActivity stale;stale.startMultiSelect();stale.toggleMultiSelection(2);stale.beginMultiOrder();
 AirNoteOrdering::next=AirNoteOrdering::Result::Conflict;stale.completeMultiOrder(3);
 assert(stale.notice==StrId::STR_AIRNOTE_ORDER_CHANGED&&stale.rebuilt>=1);
 // Collision or protected destination stops all moves before any rename.
 reset();FileBrowserActivity m;m.startMultiSelect();m.toggleMultiSelection(2);m.beginMultiMove();
 m.basepath="/Archive";Storage.data["/Archive/b.txt"]="existing";m.completeMultiMove();
 assert(Storage.renames==0&&m.browserState==FileBrowserActivity::BrowserState::ChoosingMultiMoveDestination);
 Storage.data.erase("/Archive/b.txt");m.basepath="/XTCache";m.completeMultiMove();assert(Storage.renames==0);
 m.basepath="/Archive";Storage.failRename=2;m.completeMultiMove();
 assert(Storage.data.count("/Archive/a.txt")&&Storage.data.count("/AirNote/b.txt"));
 assert(m.noticeText.find("1/2")!=string::npos&&m.browserState==FileBrowserActivity::BrowserState::Browsing);
 // Cancel is the safe default; only successful removes evict caches.
 reset();FileBrowserActivity d;d.startMultiSelect();d.toggleMultiSelection(2);d.promptMultiDelete();
 assert(d.confirmation&&d.confirmationBody.find("2")!=string::npos);
 d.confirmation(ActivityResult{true});assert(Storage.removes==0);
 d.promptMultiDelete();Storage.failRemove=2;d.confirmation(ActivityResult{false});
 assert(Storage.data.count("/AirNote/b.txt")&&caches==1);
 assert(d.noticeText.find("1/2")!=string::npos&&!d.multiSelecting);
 // Back consumes the selection gesture instead of leaving the folder.
 reset();FileBrowserActivity back;back.startMultiSelect();back.mappedInput.back=true;
 assert(back.handleCustomInput()&&!back.multiSelecting&&back.basepath=="/AirNote");
 // Bounded selection never includes synthetic/folder/non-TXT entries.
 reset();FileBrowserActivity limit;limit.startMultiSelect();
 for(int i=0;i<32;++i)limit.files.push_back("n"+std::to_string(i)+".txt");
 limit.files.push_back("folder/");limit.files.push_back("evil.png");
 for(int i=0;i<31;++i)limit.toggleMultiSelection(4+i);
 assert(limit.multiSelected.size()==32);
 limit.toggleMultiSelection(35);limit.toggleMultiSelection(36);limit.toggleMultiSelection(0);
 assert(limit.multiSelected.size()==32);
 limit.toggleMultiSelection(35);assert(limit.notice==StrId::STR_AIRNOTE_MULTI_LIMIT);
 limit.toggleMultiSelection(1);limit.toggleMultiSelection(35);
 assert(limit.multiSelected.size()==32);
 // The picker may browse elsewhere, but Back at SD root restores the root selection.
 reset();FileBrowserActivity cancel;cancel.startMultiSelect();cancel.beginMultiMove();
 cancel.basepath="/";cancel.mappedInput.back=true;assert(cancel.handleButtons());
 assert(cancel.basepath=="/AirNote"&&cancel.multiSelecting&&cancel.files[0]==MULTI_ACTION_ENTRY);
 // A missing selected source blocks ALL folder moves in preflight.
 reset();FileBrowserActivity missing;missing.startMultiSelect();missing.toggleMultiSelection(2);
 missing.beginMultiMove();missing.basepath="/Archive";Storage.data.erase("/AirNote/b.txt");
 missing.completeMultiMove();assert(Storage.renames==0&&Storage.data.count("/AirNote/a.txt"));
 // A note replaced with a directory after confirmation is skipped and never cache-cleared.
 reset();FileBrowserActivity replaced;replaced.startMultiSelect();replaced.toggleMultiSelection(2);
 replaced.promptMultiDelete();Storage.data.erase("/AirNote/b.txt");Storage.dirs.insert("/AirNote/b.txt");
 replaced.confirmation(ActivityResult{false});assert(caches==1&&Storage.dirs.count("/AirNote/b.txt"));
 assert(replaced.noticeText.find("1/2")!=string::npos);
 // A failed cache cleanup after a successful delete cannot be called all-success.
 reset();FileBrowserActivity cache;cache.startMultiSelect();cache.toggleMultiSelection(2);
 cacheFailure="/AirNote/a.txt";cache.promptMultiDelete();cache.confirmation(ActivityResult{false});
 assert(!Storage.data.count("/AirNote/a.txt")&&!Storage.data.count("/AirNote/b.txt"));
 assert(cache.noticeText.find("2/2")!=string::npos&&cache.noticeText.find("cache errors 1")!=string::npos);
}
'''

class AirNoteBulkBrowserTest(unittest.TestCase):
    def test_real_browser_input_order_move_and_delete(self):
        source = SOURCE.read_text()
        bodies = '\n\n'.join(method(source, name) for name in METHODS)
        with tempfile.TemporaryDirectory() as tmp:
            test = Path(tmp) / 'browser.cpp'
            binary = Path(tmp) / 'browser'
            test.write_text(STUB + '\n' + bodies + '\n' + MAIN)
            subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-fsanitize=undefined',
                            '-fno-omit-frame-pointer', str(test), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)

if __name__ == '__main__':
    unittest.main()
