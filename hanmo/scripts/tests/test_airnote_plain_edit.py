'Host test of AirNote plain note read/write against faulting storage.'
from pathlib import Path
import subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[2]
FAKE=r'''
#pragma once
#include <algorithm>
#include <cstring>
#include <map>
#include <string>
struct FakeStorage;
struct HalFile { FakeStorage* fs=nullptr;std::string path;size_t pos=0;bool readOnly=true,good=false;
 explicit operator bool()const{return good;}size_t size()const;int read(char*,size_t);size_t write(const char*,size_t);void flush(){}bool close(){good=false;return true;}};
struct FakeStorage {std::map<std::string,std::string> files;bool failWrite=false,failRename=false,failRemove=false;int stagedWrites=0,renameCalls=0,failAt=0;
 bool exists(const char* p)const{return files.count(p)!=0;}
 bool remove(const char* p){if(failRemove)return false;return files.erase(p)!=0;}
 bool rename(const char* a,const char* b){++renameCalls;if(failRename||renameCalls==failAt||!files.count(a)||files.count(b))return false;files[b]=files.at(a);files.erase(a);return true;}
 bool openFileForRead(const char*,const char* p,HalFile& out){if(!exists(p))return false;out={this,p,0,true,true};return true;}
 bool openFileForWrite(const char*,const char* p,HalFile& out){files[p].clear();out={this,p,0,false,true};++stagedWrites;return true;}
};
inline size_t HalFile::size()const{return fs->files.at(path).size();}
inline int HalFile::read(char* data,size_t n){if(!good||!readOnly)return -1;const auto& s=fs->files.at(path);size_t count=std::min(n,s.size()-pos);memcpy(data,s.data()+pos,count);pos+=count;return static_cast<int>(count);}
inline size_t HalFile::write(const char* data,size_t n){if(!good||readOnly)return 0;size_t count=fs->failWrite&&n?n-1:n;fs->files.at(path).append(data,count);return count;}
'''
CASE=r'''
#include "HalStorage.h"
#include "AirNotePlainEdit.h"
#include "AirNoteTodoEdit.h"
#include <cassert>
int main(){
 FakeStorage fs;std::string first;assert(AirNoteTodoEdit::createNote("memo","one\ntwo\nthree",first));fs.files["/AirNote/memo.txt"]=first;
 std::string snapshot,title,body;assert(AirNotePlainEdit::readPlain(fs,"/AirNote/memo.txt",snapshot,title,body));
 assert(title=="memo"&&body=="one\ntwo\nthree"&&snapshot==first);
 int evictions=0;auto evict=[&](const std::string&){++evictions;return true;};
 assert(AirNotePlainEdit::savePlain(fs,"/AirNote/memo.txt",snapshot,"one\nchanged\nthird",evict)==AirNotePlainEdit::SaveResult::Saved);
 const std::string updated=AirNotePolicy::noteContent("memo","one\nchanged\nthird");
 assert(fs.files.at("/AirNote/memo.txt")==updated&&evictions==1&&fs.stagedWrites==1);
 assert(!fs.exists("/AirNote/.memo.txt.part")&&!fs.exists("/AirNote/.memo.txt.bak"));
 assert(AirNotePlainEdit::savePlain(fs,"/AirNote/memo.txt",snapshot,"stale edit",evict)==AirNotePlainEdit::SaveResult::Conflict);
 assert(fs.stagedWrites==1&&fs.files.at("/AirNote/memo.txt")==updated);
 assert(AirNotePlainEdit::readPlain(fs,"/AirNote/memo.txt",snapshot,title,body));
 assert(AirNotePlainEdit::savePlain(fs,"/AirNote/memo.txt",snapshot,body,evict)==AirNotePlainEdit::SaveResult::Unchanged);
 assert(fs.stagedWrites==1);
 assert(AirNotePlainEdit::savePlain(fs,"/AirNote/memo.txt",snapshot," \n\t ",evict)==AirNotePlainEdit::SaveResult::Invalid);
 assert(AirNotePlainEdit::savePlain(fs,"/AirNote/memo.txt",snapshot,"#!AirNote-Todo:1\n[ ] x",evict)==AirNotePlainEdit::SaveResult::Invalid);
 fs.failWrite=true;assert(AirNotePlainEdit::savePlain(fs,"/AirNote/memo.txt",snapshot,"new\nlines",evict)==AirNotePlainEdit::SaveResult::StorageError);
 assert(fs.files.at("/AirNote/memo.txt")==updated&&!fs.exists("/AirNote/.memo.txt.part"));
 fs.failWrite=false;fs.failRename=true;assert(AirNotePlainEdit::savePlain(fs,"/AirNote/memo.txt",snapshot,"new\nlines",evict)==AirNotePlainEdit::SaveResult::StorageError);
 assert(fs.files.at("/AirNote/memo.txt")==updated);
 fs.failRename=false;
 // Failure after the original was moved aside must restore it from .bak.
 fs.failAt=fs.renameCalls+2;
 assert(AirNotePlainEdit::savePlain(fs,"/AirNote/memo.txt",snapshot,"another\nrevision",evict)==AirNotePlainEdit::SaveResult::StorageError);
 assert(fs.files.at("/AirNote/memo.txt")==updated);
 assert(!fs.exists("/AirNote/.memo.txt.bak")&&!fs.exists("/AirNote/.memo.txt.part"));
 fs.failAt=0;
 assert(!AirNotePlainEdit::readPlain(fs,"/AirNote/../memo.txt",snapshot,title,body));
 fs.files["/AirNote/list.txt"]=AirNotePolicy::noteContent("list","#!AirNote-Todo:1\n[ ] one");
 assert(!AirNotePlainEdit::readPlain(fs,"/AirNote/list.txt",snapshot,title,body));
 assert(!AirNotePlainEdit::readPlain(fs,"/AirNote/missing.txt",snapshot,title,body));
 fs.files["/AirNote/日記.txt"]=AirNotePolicy::noteContent("日記","既有內容\n下一行");
 assert(AirNotePlainEdit::readPlain(fs,"/AirNote/日記.txt",snapshot,title,body));
 assert(title=="日記"&&body=="既有內容\n下一行");
 assert(AirNotePlainEdit::savePlain(fs,"/AirNote/日記.txt",snapshot,"既有內容\n第二行",evict)==AirNotePlainEdit::SaveResult::Saved);
 assert(fs.files.at("/AirNote/日記.txt")==AirNotePolicy::noteContent("日記","既有內容\n第二行"));
}
'''
class AirNotePlainEditTest(unittest.TestCase):
 def test_multiline_roundtrip_and_failure_safety(self):
  with tempfile.TemporaryDirectory() as tmp:
   t=Path(tmp);(t/'HalStorage.h').write_text(FAKE);(t/'main.cpp').write_text(CASE);binary=t/'app'
   build=subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=undefined','-I',str(t),'-I',str(ROOT/'src'),str(t/'main.cpp'),'-o',str(binary)],text=True,capture_output=True)
   self.assertEqual(build.returncode,0,build.stderr)
   run=subprocess.run([str(binary)],text=True,capture_output=True)
   self.assertEqual(run.returncode,0,run.stderr)
