'Host behavior tests for Japanese card practice markers and persistence.'
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


FAKE_STORAGE = r'''
#pragma once
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <map>
#include <string>
#include <vector>
struct FakeFS;
struct HalFile {
  FakeFS* fs=nullptr;std::string path;size_t cursor=0;bool reading=false,opened=false;
  explicit operator bool() const{return opened;}
  size_t size() const;
  int read(void* data,size_t n);
  size_t write(const void* data,size_t n);
  void flush() {}
  bool close();
};
struct FakeFS {
  std::map<std::string,std::vector<uint8_t>> files;
  bool failWrite=false,failRead=false,failRemove=false,corruptOnClose=false;
  int renames=0,failRenameAt=0,writes=0;
  bool ensureDirectoryExists(const char*){return true;}
  bool exists(const char* path)const{return files.count(path)!=0;}
  bool remove(const char* path){if(failRemove)return false;return files.erase(path)!=0;}
  bool rename(const char* source,const char* target){
    ++renames;
    if(renames==failRenameAt || !exists(source) || exists(target))return false;
    files[target]=files.at(source);files.erase(source);return true;
  }
  bool openFileForRead(const char*,const char* path,HalFile& f){
    if(!exists(path))return false;
    f={this,path,0,true,true};
    return true;
  }
  bool openFileForWrite(const char*,const char* path,HalFile& f){
    files[path].clear();f={this,path,0,false,true};++writes;return true;
  }
};
inline bool HalFile::close(){
  if(opened && !reading && fs->corruptOnClose && fs->files[path].size()>8)
    fs->files[path][8]^=1;
  opened=false;
  return true;
}
inline size_t HalFile::size()const{return fs->files.at(path).size();}
inline int HalFile::read(void* out,size_t n){
  if(!opened || !reading)return -1;
  const auto& bytes=fs->files.at(path);size_t count=std::min(n,bytes.size()-cursor);
  if(fs->failRead && count>0)--count;
  std::memcpy(out,bytes.data()+cursor,count);cursor+=count;return static_cast<int>(count);
}
inline size_t HalFile::write(const void* data,size_t n){
  if(!opened || reading)return 0;
  size_t count=fs->failWrite && n?n-1:n;
  const auto* raw=static_cast<const uint8_t*>(data);
  fs->files[path].insert(fs->files[path].end(),raw,raw+count);return count;
}
'''


class KanaPracticeTests(unittest.TestCase):
    def compile_and_run(self, source: str, files=None):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            for name, text in (files or {}).items():
                (temp / name).write_text(text)
            (temp / 'main.cpp').write_text(source)
            binary = temp / 'test'
            build = subprocess.run(
                ['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-fsanitize=undefined',
                 '-I', str(temp), '-I', str(ROOT / 'src'), str(temp / 'main.cpp'), '-o', str(binary)],
                text=True, capture_output=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            result = subprocess.run([str(binary)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_user_defined_markers_are_independent_per_absolute_card(self):
        self.compile_and_run(r'''
#include "activities/apps/japanese/KanaPractice.h"
#include <cassert>
int main() {
  kana::Practice p;
  assert(!p.active(7, 0) && !p.active(7, 1) && p.doneCount(0, 46) == 0);
  assert(p.toggle(7, 0)); // star: no forced learned/visited meaning
  assert(p.active(7, 0) && !p.active(7, 1) && p.doneCount(0, 46) == 0);
  assert(p.toggle(7, 1)); // check remains independent
  assert(p.active(7, 0) && p.active(7, 1) && p.doneCount(0, 46) == 0);
  for (int round = 0; round < 5; ++round) {
    assert(p.toggle(7, 2 + round));
    assert(p.active(7, 2 + round));
    assert(p.doneCount(0, 46) == 1 && p.doneCount(5, 5) == 1);
  }
  assert(p.toggle(7, 2));
  assert(!p.active(7, 2) && p.active(7, 6) && p.doneCount(5, 5) == 1);
  for (int round = 1; round < 5; ++round) assert(p.toggle(7, 2 + round));
  assert(p.doneCount(5, 5) == 0 && p.active(7, 0) && p.active(7, 1));
  assert(p.toggle(45, 6) && p.doneCount(0, 46) == 1);
  assert(!p.toggle(46, 0) && !p.toggle(-1, 0) && !p.toggle(7, 7));
  assert(!p.active(46, 0) && p.doneCount(46, 1) == 0 && p.doneCount(0, 47) == 0);
}
''')




    def test_storage_roundtrip_and_reentry_preserve_absolute_card_flags(self):
        self.compile_and_run(r'''
#include "HalStorage.h"
#include "activities/apps/japanese/KanaPracticeStore.h"
#include <cassert>
int main(){
  FakeFS fs;kana::Practice saved;
  assert(kana::loadPractice(fs,saved)==kana::LoadStatus::Empty);
  assert(saved.toggle(7,0) && saved.toggle(7,1) && saved.toggle(7,4));
  assert(saved.toggle(45,6));
  assert(kana::savePractice(fs,saved));
  assert(fs.exists(kana::kPracticePath));
  assert(!fs.exists(kana::kPracticePart) && !fs.exists(kana::kPracticeBackup));
  kana::Practice reopened;
  assert(kana::loadPractice(fs,reopened)==kana::LoadStatus::Loaded);
  assert(reopened.active(7,0) && reopened.active(7,1) && reopened.active(7,4));
  assert(reopened.active(45,6) && reopened.doneCount(0,46)==2);
  // A later visit in a shuffled deck continues to index the same absolute card.
  assert(reopened.toggle(7,4));
  assert(kana::savePractice(fs,reopened));
  kana::Practice again;
  assert(kana::loadPractice(fs,again)==kana::LoadStatus::Loaded);
  assert(again.active(7,0) && again.active(7,1) && !again.active(7,4));
  assert(again.doneCount(5,5)==0 && again.doneCount(0,46)==1);
}
''', {'HalStorage.h': FAKE_STORAGE})



    def test_corruption_partial_write_rename_failure_and_backup_recovery(self):
        self.compile_and_run(r'''
#include "HalStorage.h"
#include "activities/apps/japanese/KanaPracticeStore.h"
#include <cassert>
int main() {
  FakeFS fs; kana::Practice original;
  assert(original.toggle(3,0) && original.toggle(3,4));
  assert(kana::savePractice(fs,original));
  const auto good=fs.files[kana::kPracticePath];
  auto damaged=good;damaged[9]^=1;fs.files[kana::kPracticePath]=damaged;
  kana::Practice sentinel;assert(sentinel.toggle(6,1));
  assert(kana::loadPractice(fs,sentinel)==kana::LoadStatus::Corrupt);
  assert(sentinel.active(6,1) && !sentinel.active(3,0));
  assert(!kana::savePractice(fs,original)); // corrupt SD data is never silently replaced
  assert(fs.files[kana::kPracticePath]==damaged);
  fs.files[kana::kPracticePath]=good;
  fs.failRead=true;
  assert(kana::loadPractice(fs,sentinel)==kana::LoadStatus::StorageError);
  assert(sentinel.active(6,1));
  fs.failRead=false;
  auto changed=original;assert(changed.toggle(3,0) && changed.toggle(45,6));
  fs.failWrite=true;
  assert(!kana::savePractice(fs,changed));
  fs.failWrite=false;
  assert(fs.files[kana::kPracticePath]==good && !fs.exists(kana::kPracticePart));
  fs.failRenameAt=fs.renames+2; // .part->main fails, original restored from .bak
  assert(!kana::savePractice(fs,changed));
  fs.failRenameAt=0;
  assert(fs.files[kana::kPracticePath]==good);
  assert(!fs.exists(kana::kPracticeBackup) && !fs.exists(kana::kPracticePart));
  assert(fs.rename(kana::kPracticePath,kana::kPracticeBackup)); // power cut after old->bak
  kana::Practice restored;
  assert(kana::loadPractice(fs,restored)==kana::LoadStatus::Loaded);
  assert(restored.active(3,0) && restored.active(3,4));
  assert(!fs.exists(kana::kPracticeBackup) && fs.files[kana::kPracticePath]==good);
  fs.files[kana::kPracticePath].push_back(0); // wrong length must not be truncated
  assert(kana::loadPractice(fs,restored)==kana::LoadStatus::Corrupt);
  assert(!kana::savePractice(fs,changed));
}
''', {'HalStorage.h': FAKE_STORAGE})


    def test_external_change_is_not_silently_overwritten(self):
        self.compile_and_run(r'''
#include "HalStorage.h"
#include "activities/apps/japanese/KanaPracticeStore.h"
#include <cassert>
int main(){
  FakeFS fs; kana::Practice seen;
  assert(kana::loadPractice(fs,seen)==kana::LoadStatus::Empty);
  auto first=seen;assert(first.toggle(9,0));
  assert(kana::savePractice(fs,first,&seen));
  kana::Practice external=first;assert(external.toggle(9,1));
  assert(kana::savePractice(fs,external,&first));
  auto stale=first;assert(stale.toggle(9,2));
  assert(!kana::savePractice(fs,stale,&first));
  kana::Practice current;
  assert(kana::loadPractice(fs,current)==kana::LoadStatus::Loaded);
  assert(current.active(9,0) && current.active(9,1) && !current.active(9,2));
}
''', {'HalStorage.h': FAKE_STORAGE})


    def test_staging_is_read_back_before_replacing_existing_progress(self):
        self.compile_and_run(r'''
#include "HalStorage.h"
#include "activities/apps/japanese/KanaPracticeStore.h"
#include <cassert>
int main() {
  FakeFS fs; kana::Practice original; assert(original.toggle(0,0));
  assert(kana::savePractice(fs,original));
  const auto good=fs.files[kana::kPracticePath];
  auto tentative=original;assert(tentative.toggle(0,2));
  fs.corruptOnClose=true;
  assert(!kana::savePractice(fs,tentative,&original));
  fs.corruptOnClose=false;
  assert(fs.files[kana::kPracticePath]==good);
  assert(!fs.exists(kana::kPracticeBackup) && !fs.exists(kana::kPracticePart));
  kana::Practice reread;
  assert(kana::loadPractice(fs,reread)==kana::LoadStatus::Loaded);
  assert(reread.active(0,0) && !reread.active(0,2));
}
''', {'HalStorage.h': FAKE_STORAGE})

if __name__ == '__main__':
    unittest.main()
