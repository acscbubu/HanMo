'Exercise real AirNote device-browser method bodies with a fake SD and keyboard.'
from pathlib import Path
import subprocess, tempfile, unittest
from scripts.tests.test_airnote_plain_edit import FAKE
from scripts.tests.test_airnote_bulk_browser import method
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'src/activities/home/FileBrowserActivity.cpp'
METHODS=('promptNewNoteTitle','promptNewNoteBody','createAirNote','promptEditAirNote','promptTextDraft')
STUB=r'''
#include <cassert>
#include <functional>
#include <string>
#include <variant>
#include <utility>
#include "HalStorage.h"
#include "AirNotePlainEdit.h"
#include "AirNoteTodoEdit.h"
#define LOG_ERR(...) ((void)0)
struct KeyboardEntryActivity{};
enum class InputType{Text,Multiline};
enum class StrId{STR_AIRNOTE_CREATE_FAILED,STR_INVALID_FILE_NAME,STR_TODO_CHANGED,STR_TODO_SAVE_FAILED,STR_FILE_OPERATION_FAILED};
#define tr(id) #id
struct KeyboardResult{std::string text;};
struct ActivityResult{bool isCancelled=false;std::variant<KeyboardResult> data=KeyboardResult{};};
inline FakeStorage Storage;
inline bool clearBookCache(const std::string&){return true;}
struct FileBrowserActivity {
 std::string basepath="/AirNote";struct {int selected=0;}nav;
 InputType lastType=InputType::Text;std::string lastTitle,lastPrefill,notice;size_t lastMax=0;
 std::function<void(const ActivityResult&)> keyboard;int finishCalls=0;
 bool isAirNoteRoot() const{return basepath=="/AirNote";}
 void showNotice(StrId s){notice=s==StrId::STR_TODO_CHANGED?"changed":s==StrId::STR_TODO_SAVE_FAILED?"save failed":"create failed";}
 void finishEdit(const std::string&,int,const std::string&){++finishCalls;}
 template<class T,class F>bool startActivityForResultWith(F&& f,std::string title,std::string prefill,size_t max,InputType type){
  keyboard=std::forward<F>(f);lastTitle=title;lastPrefill=std::move(prefill);lastMax=max;lastType=type;return true;}
 void reply(const std::string& text,bool cancel=false){assert(keyboard);auto f=std::move(keyboard);keyboard=nullptr;ActivityResult result;result.isCancelled=cancel;result.data=KeyboardResult{text};f(result);}
 void promptNewNoteTitle(bool);void promptNewNoteBody(bool,const std::string&,const std::string& = "",bool=false);bool createAirNote(bool,const std::string&,const std::string&);
 bool promptEditAirNote(const std::string&);void promptTextDraft(const std::string&,const std::string&,const std::string&,const std::string&,bool=false);
};
'''
MAIN=r'''
int main(){
 FileBrowserActivity cancelNew;cancelNew.promptNewNoteTitle(false);cancelNew.reply("never created");
 assert(cancelNew.lastType==InputType::Multiline);cancelNew.reply("unsaved text",true);
 assert(!Storage.exists("/AirNote/never created.txt"));
 // A failed SD write must not throw away a long draft; retry keeps the text.
 FileBrowserActivity retryNew;retryNew.promptNewNoteTitle(false);retryNew.reply("journal");
 Storage.failWrite=true;retryNew.reply("first line\nsecond line");
 assert(!Storage.exists("/AirNote/journal.txt"));
 assert(retryNew.keyboard && retryNew.lastPrefill=="first line\nsecond line");
 Storage.failWrite=false;retryNew.reply("first line\nsecond line");
 assert(Storage.files.at("/AirNote/journal.txt")==AirNotePolicy::noteContent("journal","first line\nsecond line"));
 FileBrowserActivity failedCleanup;failedCleanup.promptNewNoteTitle(false);failedCleanup.reply("partial");
 Storage.failWrite=true;Storage.failRemove=true;failedCleanup.reply("must not show broken note");
 assert(!Storage.exists("/AirNote/partial.txt") && failedCleanup.keyboard);
 Storage.failWrite=false;Storage.failRemove=false;
 failedCleanup.reply("must not show broken note");
 assert(Storage.files.at("/AirNote/partial.txt")==AirNotePolicy::noteContent("partial","must not show broken note"));
 FileBrowserActivity a;
 a.promptNewNoteTitle(false);assert(a.lastType==InputType::Text&&a.lastMax==AirNotePolicy::kMaxTitleBytes);
 a.reply("memo");assert(a.lastType==InputType::Multiline && a.lastMax==AirNotePolicy::kMaxBodyBytes);
 assert(!Storage.exists("/AirNote/memo.txt")); // title alone must not leave an empty/invalid file
 a.reply("line one\nline two");assert(Storage.exists("/AirNote/memo.txt"));
 assert(Storage.files.at("/AirNote/memo.txt")==AirNotePolicy::noteContent("memo","line one\nline two"));
 assert(a.finishCalls==1);
 assert(a.promptEditAirNote("/AirNote/memo.txt"));
 assert(a.lastType==InputType::Multiline && a.lastPrefill=="line one\nline two");
 a.reply("cancelled change",true);assert(Storage.files.at("/AirNote/memo.txt")==AirNotePolicy::noteContent("memo","line one\nline two"));
 assert(a.promptEditAirNote("/AirNote/memo.txt"));a.reply("line one\nline two\nline three");
 assert(Storage.files.at("/AirNote/memo.txt")==AirNotePolicy::noteContent("memo","line one\nline two\nline three"));
 assert(a.finishCalls==2);
 // SD or web changes while the editor is open cannot overwrite the new file;
 // the unsaved draft is returned to the keyboard for the user to recover.
 assert(a.promptEditAirNote("/AirNote/memo.txt"));
 const std::string remote=AirNotePolicy::noteContent("memo","modified by web");
 Storage.files["/AirNote/memo.txt"]=remote;
 a.reply("my unsaved\nmultiline draft");
 assert(Storage.files.at("/AirNote/memo.txt")==remote && a.finishCalls==2);
 assert(a.keyboard && a.lastPrefill=="my unsaved\nmultiline draft");
 assert(a.lastTitle=="STR_FILE_OPERATION_FAILED");
 a.reply("",true);
 assert(Storage.files.at("/AirNote/memo.txt")==remote);
 a.promptNewNoteBody(true,"tasks");assert(a.lastType==InputType::Text&&a.lastMax==AirNoteTodo::maxItemBytes);
 a.reply("one");assert(Storage.exists("/AirNote/tasks.txt"));
 assert(!a.promptEditAirNote("/AirNote/tasks.txt"));
 assert(!a.promptEditAirNote("/Other/memo.txt"));
}
'''
class AirNotePlainFlowTest(unittest.TestCase):
 def test_device_title_opens_multiline_and_existing_note_reopens_for_edit(self):
  source=SOURCE.read_text()
  self.assertIn('promptEditAirNote(fullPath)',source)
  methods='\n\n'.join(method(source,name) for name in METHODS)
  with tempfile.TemporaryDirectory() as tmp:
   t=Path(tmp);fake=FAKE.replace('bool exists(const char* p)const{','bool ensureDirectoryExists(const char*){return true;}bool openFileForWrite(const char* tag,const std::string& p,HalFile& out){return openFileForWrite(tag,p.c_str(),out);}bool exists(const char* p)const{')
   (t/'HalStorage.h').write_text(fake);(t/'main.cpp').write_text(STUB+'\n'+methods+'\n'+MAIN)
   binary=t/'app'
   result=subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=undefined','-I',str(t),'-I',str(ROOT/'src'),str(t/'main.cpp'),'-o',str(binary)],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
   run=subprocess.run([str(binary)],capture_output=True,text=True)
   self.assertEqual(run.returncode,0,run.stderr)
