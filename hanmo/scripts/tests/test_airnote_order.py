"""Compile the actual streamed catalog and HAL adapter with injected SD faults."""
from pathlib import Path
import subprocess,tempfile,unittest
from scripts.tests.test_airnote_todo import STUB,ROOT
STUB=STUB.replace('inline HalFile FakeStorage::open(const char* p){HalFile f;f.good=true;f.dir=true;for(auto& pair:files)f.names.push_back(pair.first);return f;}',r"""inline std::string failNoteOpenPath;
inline int failNoteOpenOn=0, noteOpenAttempts=0;
inline bool removeOnNoteOpen=false;
inline HalFile FakeStorage::open(const char* p){HalFile f;f.path=p;if(f.path=="/AirNote"){f.good=true;f.dir=true;for(auto& pair:files)if(pair.first.rfind("/AirNote/",0)==0)f.names.push_back(pair.first);}else {
 if(f.path==failNoteOpenPath && ++noteOpenAttempts==failNoteOpenOn){if(removeOnNoteOpen)files.erase(p);return f;}
 f.good=exists(p);
}return f;}
inline void yield(){} inline void resetTaskWatchdogIfSubscribed(){}
""")
CODE=r"""
#include "stub.h"
#include "src/AirNoteOrdering.h"
std::vector<std::string> list(std::string& rev){std::vector<std::string> out;assert(AirNoteOrdering::scan([&](const char* n){out.push_back(n);},rev));return out;}
int main(){using namespace AirNoteOrdering;
 Storage.files["/AirNote/A.txt"]="unchanged A";Storage.files["/AirNote/B.txt"]="unchanged B";Storage.files["/AirNote/中文.txt"]="unchanged C";
 std::string rev;auto names=list(rev);assert(names.size()==3&&names[0]=="A.txt");
 assert(move("B.txt",-1,rev)==Result::Saved);names=list(rev);assert((names==std::vector<std::string>{"B.txt","A.txt","中文.txt"}));
 assert(Storage.files["/AirNote/B.txt"]=="unchanged B");
 const auto saved=Storage.files[AirNoteOrder::path];const auto oldRev=rev;
 assert(move("B.txt",1,rev)==Result::Saved);names=list(rev);assert(names[0]=="A.txt");
 assert(move("中文.txt",-1,oldRev)==Result::Conflict);assert(move("none.txt",-1,rev)==Result::Missing);
 assert(move("A.txt",-1,rev)==Result::Saved);assert(move("中文.txt",1,rev)==Result::Saved);
 // Recover interrupted rename; ignore deleted/stale rows and external duplicates.
 Storage.files.erase(AirNoteOrder::path);Storage.files[AirNoteOrder::backup]="中文.txt\nA.txt\nA.txt\nMissing.txt\n";
 names=list(rev);assert((names==std::vector<std::string>{"中文.txt","A.txt","B.txt"}));
 for(int fault=0;fault<4;++fault){
  Storage.files[AirNoteOrder::path]=saved;Storage.shortWrite=false;Storage.closeFail=false;Storage.failRename=0;Storage.renames=0;names=list(rev);
  if(fault==0)Storage.shortWrite=true;if(fault==1)Storage.closeFail=true;if(fault>=2)Storage.failRename=fault-1;
  assert(move("A.txt",-1,rev)==Result::StorageError);assert(Storage.files[AirNoteOrder::path]==saved);
 }
 Storage.shortWrite=false;Storage.closeFail=false;Storage.failRename=0;
 Storage.files[AirNoteOrder::path]="../invalid\n";assert(!AirNoteOrdering::scan([](const char*){},rev));assert(rev.empty());
 Storage.files[AirNoteOrder::path]="A.txt";assert(!AirNoteOrdering::scan([](const char*){},rev));
 Storage.files.clear();
 for(int i=0;i<123;++i){char name[40];snprintf(name,sizeof(name),"/AirNote/%03d.txt",i);Storage.files[name]="x";}
 names=list(rev);assert(names.size()==123);
 assert(move("049.txt",1,rev)==Result::Saved);names=list(rev);assert(names[49]=="050.txt"&&names[50]=="049.txt");
 assert(moveTo("000.txt",122,rev)==Result::Saved);names=list(rev);assert(names.back()=="000.txt"&&names[0]=="001.txt");
 assert(moveTo("000.txt",0,rev)==Result::Saved);names=list(rev);assert(names[0]=="000.txt");
 assert(moveTo("000.txt",123,rev)==Result::Missing);assert(moveTo("000.txt",0,rev)==Result::Saved);
 const auto before=Storage.files[AirNoteOrder::path];
 for(int fault=0;fault<4;++fault){Storage.shortWrite=fault==0;Storage.closeFail=fault==1;Storage.failRename=fault>=2?fault-1:0;Storage.renames=0;assert(moveTo("000.txt",122,rev)==Result::StorageError);assert(Storage.files[AirNoteOrder::path]==before);}
 Storage.shortWrite=false;Storage.closeFail=false;Storage.failRename=0;
 auto stale=rev;Storage.files["/AirNote/new.txt"]="new";assert(move("049.txt",1,stale)==Result::Conflict);
 names=list(rev);assert(names.size()==124&&names.back()=="new.txt");
 // Reverse input order must not reverse the selected notes' catalog order.
 Storage.files.clear();
 for(const char* n:{"A.txt","B.txt","C.txt","D.txt","E.txt"})Storage.files[std::string("/AirNote/")+n]=std::string("body ")+n;
 names=list(rev);assert((names==std::vector<std::string>{"A.txt","B.txt","C.txt","D.txt","E.txt"}));
 assert(moveManyBefore({"D.txt","B.txt"},"A.txt",rev)==Result::Saved);
 names=list(rev);assert((names==std::vector<std::string>{"B.txt","D.txt","A.txt","C.txt","E.txt"}));
 assert(Storage.files["/AirNote/D.txt"]=="body D.txt");
 // Append and insert retain catalog order, including a selection spanning the anchor.
 assert(moveManyBefore({"C.txt","A.txt"},nullptr,rev)==Result::Saved);
 names=list(rev);assert((names==std::vector<std::string>{"B.txt","D.txt","E.txt","A.txt","C.txt"}));
 Storage.renames=0;
 assert(moveManyBefore({"C.txt","A.txt"},"D.txt",rev)==Result::Saved);
 assert(Storage.renames==2&&!Storage.exists(AirNoteOrder::backup)&&!Storage.exists(AirNoteOrder::staging));
 names=list(rev);assert((names==std::vector<std::string>{"B.txt","A.txt","C.txt","D.txt","E.txt"}));
 const auto original=Storage.files[AirNoteOrder::path];const auto current=rev;
 assert(moveManyBefore({"A.txt"},nullptr,stale)==Result::Conflict);
 assert(moveManyBefore({},nullptr,rev)==Result::Invalid);
 assert(moveManyBefore({"A.txt","A.txt"},nullptr,rev)==Result::Invalid);
 assert(moveManyBefore({"../bad.txt"},nullptr,rev)==Result::Invalid);
 assert(moveManyBefore({"A.txt"},"A.txt",rev)==Result::Invalid);
 assert(moveManyBefore({"A.txt"},nullptr,"not a revision")==Result::Invalid);
 assert(moveManyBefore({"A.txt"},nullptr,std::string(32,'Z'))==Result::Invalid);
 assert(moveManyBefore({"missing.txt"},nullptr,rev)==Result::Missing);
 assert(moveManyBefore({"A.txt"},"missing.txt",rev)==Result::Missing);
 assert(Storage.files[AirNoteOrder::path]==original&&!Storage.exists(AirNoteOrder::staging));
 Storage.files["/AirNote/F.txt"]="externally added";
 assert(moveManyBefore({"B.txt"},nullptr,current)==Result::Conflict);
 assert(Storage.files[AirNoteOrder::path]==original&&!Storage.exists(AirNoteOrder::staging));
 Storage.files.erase("/AirNote/F.txt");
 for(int fault=0;fault<4;++fault){
  Storage.shortWrite=fault==0;Storage.closeFail=fault==1;
  Storage.failRename=fault>=2?fault-1:0;Storage.renames=0;
  assert(moveManyBefore({"B.txt","E.txt"},"A.txt",current)==Result::StorageError);
  assert(Storage.files[AirNoteOrder::path]==original);
  assert(Storage.files["/AirNote/E.txt"]=="body E.txt");
  assert(!Storage.exists(AirNoteOrder::staging)&&!Storage.exists(AirNoteOrder::backup));
 }
 Storage.shortWrite=false;Storage.closeFail=false;Storage.failRename=0;
 Storage.files[AirNoteOrder::path]="../invalid\n";
 assert(moveManyBefore({"B.txt"},nullptr,current)==Result::StorageError);
 assert(Storage.files[AirNoteOrder::path]=="../invalid\n"&&!Storage.exists(AirNoteOrder::staging));
 Storage.files[AirNoteOrder::path]="B.txt";
 assert(moveManyBefore({"B.txt"},nullptr,current)==Result::StorageError);
 assert(Storage.files[AirNoteOrder::path]=="B.txt"&&!Storage.exists(AirNoteOrder::staging));
 Storage.files[AirNoteOrder::path]="B.txt\nB.txt\n";
 assert(moveManyBefore({"B.txt"},nullptr,current)==Result::StorageError);
 assert(Storage.files[AirNoteOrder::path]=="B.txt\nB.txt\n"&&!Storage.exists(AirNoteOrder::staging));
 Storage.files.erase(AirNoteOrder::path);
 names=list(rev);assert(names.size()==5);
 Storage.failRename=1;Storage.renames=0;
 assert(moveManyBefore({"D.txt","B.txt"},nullptr,rev)==Result::StorageError);
 assert(!Storage.exists(AirNoteOrder::path)&&!Storage.exists(AirNoteOrder::staging));
 Storage.failRename=0;
 assert(moveManyBefore({"D.txt","B.txt"},nullptr,rev)==Result::Saved);
 names=list(rev);assert((names==std::vector<std::string>{"A.txt","C.txt","E.txt","B.txt","D.txt"}));
 Storage.files.clear();
 for(int i=0;i<34;++i){char path[40];snprintf(path,sizeof(path),"/AirNote/%03d.txt",i);Storage.files[path]="x";}
 names=list(rev);assert(names.size()==34);
 std::vector<std::string> batch;batch.reserve(33);
 for(int i=31;i>=0;--i){char name[20];snprintf(name,sizeof(name),"%03d.txt",i);batch.push_back(name);}
 batch.push_back("032.txt");
 assert(moveManyBefore(batch,nullptr,rev)==Result::Invalid);batch.pop_back();
 assert(moveManyBefore(batch,"033.txt",rev)==Result::Saved);
 names=list(rev);assert(names[0]=="032.txt"&&names[1]=="000.txt"&&names[32]=="031.txt"&&names[33]=="033.txt");
}
"""
OPEN_FAILURE_CODE=r"""
#include "stub.h"
#include "src/AirNoteOrdering.h"
int main(){using namespace AirNoteOrdering;
 for(const char* name:{"A.txt","B.txt","C.txt","D.txt"})Storage.files[std::string("/AirNote/")+name]=std::string("body ")+name;
 Storage.files[AirNoteOrder::path]="A.txt\nB.txt\nC.txt\nD.txt\n";
 std::string revision;std::vector<std::string> names;
 assert(scan([&](const char* name){names.emplace_back(name);},revision));
 assert((names==std::vector<std::string>{"A.txt","B.txt","C.txt","D.txt"}));
 const auto original=Storage.files.at(AirNoteOrder::path);
 auto failsClosed=[&](auto reorder){
  failNoteOpenPath="/AirNote/B.txt";failNoteOpenOn=2;noteOpenAttempts=0;Storage.renames=0;
  assert(reorder()==Result::StorageError);assert(noteOpenAttempts==2);
  assert(Storage.renames==0&&Storage.files.at(AirNoteOrder::path)==original);
  assert(!Storage.exists(AirNoteOrder::staging)&&!Storage.exists(AirNoteOrder::backup));
  assert(Storage.files.at("/AirNote/B.txt")=="body B.txt");
  failNoteOpenPath.clear();failNoteOpenOn=0;
 };
 failsClosed([&]{return moveManyBefore({"A.txt"},"D.txt",revision);});
 failsClosed([&]{return move("C.txt",1,revision);});
 failsClosed([&]{return moveTo("A.txt",3,revision);});
 // A real deletion between the revision scan and writer is still a stale row.
 failNoteOpenPath="/AirNote/B.txt";failNoteOpenOn=2;noteOpenAttempts=0;removeOnNoteOpen=true;
 assert(moveManyBefore({"A.txt"},"D.txt",revision)==Result::Saved);
 assert(noteOpenAttempts==2&&!Storage.exists("/AirNote/B.txt"));
 assert(Storage.files.at(AirNoteOrder::path)=="C.txt\nA.txt\nD.txt\n");
 assert(!Storage.exists(AirNoteOrder::staging)&&!Storage.exists(AirNoteOrder::backup));
}
"""
class OrderTest(unittest.TestCase):
 def test_unselected_note_open_failure_during_writer_refuses_commit(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'stub.h').write_text(STUB)
   for name in ['HalStorage.h','MD5Builder.h','util/TaskWatchdog.h']:
    f=p/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text('#include "stub.h"\n')
   (p/'test.cpp').write_text(OPEN_FAILURE_CODE)
   subprocess.run(['g++','-std=c++17','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(p),'-I'+str(ROOT),'-I'+str(ROOT/'src'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
   subprocess.run([str(p/'test')],check=True)
 def test_actual_order_catalog_and_revision_faults(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'stub.h').write_text(STUB)
   for name in ['HalStorage.h','MD5Builder.h','util/TaskWatchdog.h']:
    f=p/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text('#include "stub.h"\n')
   (p/'test.cpp').write_text(CODE)
   subprocess.run(['g++','-std=c++17','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(p),'-I'+str(ROOT),'-I'+str(ROOT/'src'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
   subprocess.run([str(p/'test')],check=True)
if __name__=='__main__':unittest.main()
