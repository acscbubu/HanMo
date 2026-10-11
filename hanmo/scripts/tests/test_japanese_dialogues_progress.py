"""Real v4 store/legacy codec exercised with HAL-shaped fault injection only."""
from pathlib import Path
import os
import subprocess
import unittest

ROOT = Path(os.environ.get('JAPANESE_DIALOGUES_TEST_ROOT', Path(__file__).resolve().parents[2]))
BUILD = ROOT / 'build/japanese-basic30-progress/store'
HAL = r'''
#pragma once
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <functional>
#include <map>
#include <set>
#include <string>
#include <vector>
struct FakeFS;
inline int transactionDepth=0;
class HalStorage {
 public:
 struct StorageLock {StorageLock(){++transactionDepth;}~StorageLock(){--transactionDepth;}};
};
struct HalFile {
 FakeFS* fs=nullptr;std::string path;bool reading=false,opened=false;
 ~HalFile();size_t size()const;int read(void*,size_t);size_t write(const void*,size_t);
 void flush();bool close();
};
struct FakeFS {
 std::map<std::string,std::vector<uint8_t>> files;
 std::vector<std::map<std::string,std::vector<uint8_t>>> cuts;
 std::vector<std::string> events;
 std::set<int> failRenames;
 std::function<void(FakeFS&,const std::string&)> afterRead;
 bool available=true,shortRead=false,shortWrite=false,corruptClose=false,dirFail=false,requireLock=false,failWriteClose=false;
 std::string failReadPath,failOpenPath,failClosePath,failRemovePath;
 int handles=0,writes=0,renames=0,failRenameAt=0,reads=0,failReadAt=0;
 bool ready()const{assert(!requireLock || transactionDepth>0);return available;}
 void snapshot(const std::string& event){events.push_back(event);cuts.push_back(files);}
 static bool v4(const char* p){return std::string(p)=="/.crosspoint/japanese-sentences-v4.bin" || std::string(p)=="/.crosspoint/japanese-sentences-v4.bin.part" || std::string(p)=="/.crosspoint/japanese-sentences-v4.bin.bak";}
 static void readAllowed(const char* p){assert(v4(p) || std::string(p)=="/.crosspoint/japanese-sentences-v2.bin" || std::string(p)=="/.crosspoint/japanese-sentences-v2.bin.bak" || std::string(p)=="/.crosspoint/japanese-review-v1.bin" || std::string(p)=="/.crosspoint/japanese-review-v1.bin.bak");}
 bool ensureDirectoryExists(const char* p){assert(std::string(p)=="/.crosspoint");return available && !dirFail;}
 bool exists(const char* p)const{readAllowed(p);return available && files.count(p);}
 bool remove(const char* p){assert(v4(p));assert(handles==0);if(!available || failRemovePath==p)return false;bool ok=files.erase(p);snapshot(std::string("remove:")+p);return ok;}
 bool rename(const char* from,const char* to){assert(v4(from) && v4(to));assert(handles==0);++renames;events.push_back("rename-attempt");if(!available || renames==failRenameAt || failRenames.count(renames) || !exists(from) || exists(to))return false;files[to]=files.at(from);files.erase(from);snapshot(std::string("rename:")+from+"->"+to);return true;}
 bool openFileForRead(const char*,const char* p,HalFile& f){readAllowed(p);if(!available || failOpenPath==p || !exists(p))return false;assert(!f.opened);f.fs=this;f.path=p;f.reading=true;f.opened=true;++handles;events.push_back(std::string("open-read:")+p);return true;}
 bool openFileForWrite(const char*,const char* p,HalFile& f){assert(v4(p));if(!available || failOpenPath==p)return false;assert(!f.opened);files[p].clear();f.fs=this;f.path=p;f.reading=false;f.opened=true;++handles;++writes;snapshot(std::string("open-write:")+p);return true;}
};
inline HalFile::~HalFile(){if(opened)close();}
inline size_t HalFile::size()const{return fs->files.at(path).size();}
inline int HalFile::read(void* out,size_t n){assert(opened && reading);++fs->reads;fs->events.push_back(std::string("read:")+path);if(fs->failReadPath==path || fs->reads==fs->failReadAt)return -1;const auto& b=fs->files.at(path);size_t count=std::min(n,b.size());if(fs->shortRead && count)--count;std::memcpy(out,b.data(),count);if(fs->afterRead)fs->afterRead(*fs,path);return static_cast<int>(count);}
inline size_t HalFile::write(const void* in,size_t n){assert(opened && !reading);size_t count=fs->shortWrite && n?n-1:n;const auto* raw=static_cast<const uint8_t*>(in);fs->files[path].assign(raw,raw+count);fs->snapshot(std::string("write:")+path);return count;}
inline void HalFile::flush(){assert(opened);fs->snapshot(std::string("flush:")+path);}
inline bool HalFile::close(){if(!opened)return true;opened=false;--fs->handles;bool ok=fs->failClosePath!=path && (reading || !fs->failWriteClose);if(!reading && fs->corruptClose && fs->files[path].size()>8)fs->files[path][8]^=1;fs->snapshot(std::string("close:")+path);return ok;}
'''

class DialoguesProgressTests(unittest.TestCase):
    def run_cpp(self, source, hardware=False):
        directory = BUILD / self._testMethodName
        directory.mkdir(parents=True, exist_ok=True)
        (directory/'HalStorage.h').write_text(HAL)
        cpp, exe = directory/'main.cpp', directory/'store'
        cpp.write_text('#include "activities/apps/japanese/JapaneseSentenceProgressStore.h"\n#include <cassert>\n#include <iostream>\nusing namespace japanese::sentenceprogress;\ntemplate<typename T> std::vector<uint8_t> vec(const T& b){return {b.begin(),b.end()};}\nint main(){\n'+source+'\n}\n')
        command = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-fsanitize=undefined', '-fno-sanitize-recover=all', *(['-DARDUINO_ARCH_ESP32=1'] if hardware else []), '-I',str(directory), '-I',str(ROOT/'src'),str(cpp),'-o',str(exe)]
        compiled = subprocess.run(command, capture_output=True, text=True)
        (directory/'compile.log').write_text(' '.join(command)+'\n'+compiled.stdout+compiled.stderr)
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        run = subprocess.run([str(exe)], capture_output=True, text=True)
        (directory/'runtime.log').write_text(run.stdout+run.stderr)
        self.assertEqual(run.returncode, 0, run.stderr)
        return run.stdout

    def test_exact_schema_ids_length_le_crc_roundtrip_and_atomic_rejection(self):
        self.run_cpp(r'''
Progress p;for(int c=0;c<9;++c)for(int l=0;l<30;++l)assert(record(p,c,l,true));
p.revision=0x12345678;auto bytes=encodeProgress(p);static_assert(kProgressBytes==648);
assert(bytes[0]=='J' && bytes[1]=='S' && bytes[2]=='P' && bytes[3]=='4');
assert(bytes[4]==4 && bytes[5]==9 && bytes[6]==30 && bytes[7]==0);
assert(bytes[8]==14 && bytes[9]==1 && bytes[10]==34 && bytes[11]==0);
assert(bytes[12]==3 && bytes[13]==0 && bytes[14]==136 && bytes[15]==2);
assert(detail::get(bytes.data()+16,4)==0x4A534403u);
assert(bytes[20]==0x78 && bytes[21]==0x56 && bytes[22]==0x34 && bytes[23]==0x12 && bytes[24]==8);
for(int i=0;i<9;++i){assert(bytes[25+i]==29 && bytes[68+i]==i && bytes[77+i]==30);assert(detail::get(bytes.data()+86+2*i,2)==unsigned(i*30));}
for(int c=0;c<9;++c)for(int j=0;j<30;++j)assert(detail::get(bytes.data()+104+2*(30*c+j),2)==unsigned(j<6?6*c+j:54+24*c+j-6));
for(int i=0;i<33;++i){assert(bytes[34+i]==255);}assert(bytes[67]==63);
Progress out;assert(decodeProgress(bytes,out) && encodeProgress(out)==bytes);
assert(record(out,0,3,false));auto sentinel=encodeProgress(out);
for(size_t i=0;i<bytes.size();++i){auto b=bytes;b[i]^=1;assert(!decodeProgress(b,out) && encodeProgress(out)==sentinel);}
auto reject=[&](auto b){detail::put(b.data()+644,detail::checksum(b.data(),644),4);assert(!decodeProgress(b,out) && encodeProgress(out)==sentinel);};
for(int offset=0;offset<20;++offset){auto b=bytes;b[offset]^=1;reject(b);}
for(int offset=68;offset<644;++offset){auto b=bytes;b[offset]^=1;reject(b);}
auto b=bytes;b[24]=9;reject(b);for(int i=0;i<9;++i){b=bytes;b[25+i]=30;reject(b);}
for(int value:{64,128,255}){b=bytes;b[67]=value;reject(b);}
Progress imported;imported.positions[0]=5;imported.readBits[0]=63;assert(decodeProgress(encodeProgress(imported),out) && out.revision==0);
''')

    def test_read_only_legacy_import_preserves_all_45_word_bytes_and_backup(self):
        self.run_cpp(r'''
japanese::review::Progress legacy;
for(int i=0;i<japanese::Words::kCount;++i)assert(japanese::review::applyRating(legacy,japanese::Words::cardIdAt(i),japanese::review::Rating::Known,japanese::review::kMinDay));
assert(japanese::review::recordSentence(legacy,5,true));legacy.sentenceReadMask=63;
const auto bytes=japanese::review::encodeProgress(legacy);
for(bool backup:{false,true}){
 FakeFS fs;const auto path=backup?japanese::review::kProgressBackup:japanese::review::kProgressPath;
 fs.files[path]=vec(bytes);fs.files["/canary.bin"]={3,1,4};const auto original=fs.files;
 Progress p;assert(loadProgress(fs,p)==LoadStatus::Imported);
 assert(p.revision==0 && p.lastCategory==0 && p.positions[0]==5 && p.readBits[0]==63);
 for(int c=1;c<9;++c){assert(p.positions[c]==0 && readCount(p,c)==0);}assert(readCount(p,0)==6);
 assert(fs.files==original && fs.writes==0 && fs.renames==0 && fs.handles==0);
 japanese::review::Progress reread;assert(japanese::review::decodeProgress(bytes,reread));
 for(int i=0;i<45;++i)assert(reread.words[i].reviews==1 && reread.words[i].rating==3);
}
FakeFS absent;Progress p;assert(record(p,8,5,true));assert(loadProgress(absent,p)==LoadStatus::Empty && p.revision==0);
for(int fault=0;fault<6;++fault){FakeFS fs;fs.files[japanese::review::kProgressPath]=vec(bytes);
 if(fault==0)fs.files[japanese::review::kProgressPath].pop_back();
 if(fault==1)fs.files[japanese::review::kProgressPath][40]^=1;
 if(fault==2){auto bad=bytes;bad[4]=2;japanese::review::detail::put(bad.data()+bad.size()-4,japanese::review::detail::checksum(bad.data(),bad.size()-4),4);fs.files[japanese::review::kProgressPath]=vec(bad);}
 if(fault==3)fs.failReadPath=japanese::review::kProgressPath;
 if(fault==4)fs.failOpenPath=japanese::review::kProgressPath;
 if(fault==5)fs.failClosePath=japanese::review::kProgressPath;
 const auto before=fs.files;p=Progress{};assert(record(p,1,4,true));auto state=encodeProgress(p);
 assert(loadProgress(fs,p)==(fault<3?LoadStatus::Corrupt:LoadStatus::StorageError));
 assert(encodeProgress(p)==state && fs.files==before && fs.writes==0 && fs.renames==0 && fs.handles==0);
}
FakeFS current;Progress v2;assert(record(v2,8,5,true));current.files[kProgressPath]=vec(encodeProgress(v2));
current.files[japanese::review::kProgressPath]={0};assert(loadProgress(current,p)==LoadStatus::Loaded && encodeProgress(p)==encodeProgress(v2));
for(const auto& e:current.events)assert(e.find("japanese-review")==std::string::npos);
current.files[kProgressPath][4]=5;auto before=current.files;assert(loadProgress(current,p)==LoadStatus::Corrupt && current.files==before);
absent.available=false;auto state=encodeProgress(p);assert(loadProgress(absent,p)==LoadStatus::StorageError && encodeProgress(p)==state);
''')

    def test_first_save_accepts_imported_empty_and_one_bounded_270_card_merge(self):
        self.run_cpp(r'''
for(bool imported:{false,true}){
 FakeFS fs;japanese::review::Progress legacy;
 for(int i=0;i<45;++i)assert(japanese::review::applyRating(legacy,japanese::Words::cardIdAt(i),japanese::review::Rating::Familiar,japanese::review::kMinDay));
 assert(japanese::review::recordSentence(legacy,4,true));const auto legacyBytes=japanese::review::encodeProgress(legacy);
 if(imported)fs.files[japanese::review::kProgressPath]=vec(legacyBytes);
 fs.files["/canary.bin"]={1,2,3};Progress base,pending;
 assert(loadProgress(fs,base)==(imported?LoadStatus::Imported:LoadStatus::Empty));
 for(int c=0;c<9;++c)for(int l=0;l<30;++l)assert(record(pending,c,l,true));
 auto desired=base;assert(mergePending(desired,pending,511,true) && desired.revision==1);
 assert(saveProgress(fs,desired,&base) && fs.writes==1 && fs.handles==0);
 Progress reopened;assert(loadProgress(fs,reopened)==LoadStatus::Loaded && encodeProgress(reopened)==encodeProgress(desired));
 for(int c=0;c<9;++c)assert(readCount(reopened,c)==30 && reopened.positions[c]==29);
 assert(fs.files[kProgressPath]==vec(encodeProgress(desired)) && !fs.exists(kProgressPart) && !fs.exists(kProgressBackup));
 assert(fs.files["/canary.bin"]==std::vector<uint8_t>({1,2,3}));
 if(imported)assert(fs.files[japanese::review::kProgressPath]==vec(legacyBytes));
 for(const auto& cut:fs.cuts){FakeFS reboot;reboot.files=cut;Progress recovered;auto status=loadProgress(reboot,recovered);
  assert(status==LoadStatus::Loaded || status==(imported?LoadStatus::Imported:LoadStatus::Empty));
  assert(encodeProgress(recovered)==encodeProgress(status==LoadStatus::Loaded?desired:base));
  if(imported)assert(reboot.files[japanese::review::kProgressPath]==vec(legacyBytes));
 }
 assert(!saveProgress(fs,desired,&base) && fs.writes==1); // uncertain-success stale retry cannot duplicate
 for(int bad=0;bad<5;++bad){auto invalid=desired;
  if(bad==0){invalid.revision+=2;invalid.positions[8]=4;}
  if(bad==1)++invalid.revision;
  if(bad==2){++invalid.revision;invalid.readBits[6]=0;}
  if(bad==3){++invalid.revision;invalid.positions[8]=30;}
  if(bad==4){++invalid.revision;invalid.lastCategory=9;}
  assert(!saveProgress(fs,invalid,&desired) && fs.writes==1);
 }
 auto overflow=desired;overflow.revision=UINT32_MAX;fs.files[kProgressPath]=vec(encodeProgress(overflow));
 assert(!saveProgress(fs,desired,&overflow) && fs.writes==1);
}
FakeFS fs;Progress empty,next;assert(record(next,2,5,true));Progress wrong;wrong.positions[1]=2;
assert(!saveProgress(fs,next,&wrong) && fs.writes==0);assert(saveProgress(fs,next) && fs.writes==1);
fs.available=false;assert(!saveProgress(fs,next,&empty) && fs.writes==1);
''')

    def test_replacement_and_hal_faults_keep_recoverable_old_commit(self):
        self.run_cpp(r'''
Progress old;assert(record(old,1,4,true));auto next=old;assert(record(next,8,5,true));
const auto a=encodeProgress(old),b=encodeProgress(next);
japanese::review::Progress legacy;for(int i=0;i<45;++i)assert(japanese::review::applyRating(legacy,japanese::Words::cardIdAt(i),japanese::review::Rating::Known,japanese::review::kMinDay));
const auto v1=japanese::review::encodeProgress(legacy);auto older=legacy;older.sentencePosition=4;const auto v1backup=japanese::review::encodeProgress(older);
FakeFS healthy;healthy.files[kProgressPath]=vec(a);healthy.files[japanese::review::kProgressPath]=vec(v1);healthy.files[japanese::review::kProgressBackup]=vec(v1backup);assert(saveProgress(healthy,next,&old));
Progress out;assert(loadProgress(healthy,out)==LoadStatus::Loaded && encodeProgress(out)==b);
for(int fault=0;fault<11;++fault){
 FakeFS fs;fs.files[kProgressPath]=vec(a);fs.files["/canary.bin"]={42};fs.files[japanese::review::kProgressPath]=vec(v1);fs.files[japanese::review::kProgressBackup]=vec(v1backup);
 if(fault==0)fs.shortWrite=true;
 if(fault==1)fs.failWriteClose=true;
 if(fault==2)fs.corruptClose=true;
 if(fault==3)fs.failReadPath=kProgressPart;
 if(fault==4)fs.failOpenPath=kProgressPart;
 if(fault==5)fs.failClosePath=kProgressPart;
 if(fault==6)fs.dirFail=true;
 if(fault==7)fs.failRenameAt=1;
 if(fault==8)fs.failRenameAt=2;
 if(fault==9){fs.files[kProgressPart]={0};fs.failRemovePath=kProgressPart;}
 if(fault==10){fs.files[kProgressBackup]=vec(a);fs.failRemovePath=kProgressBackup;}
 assert(!saveProgress(fs,next,&old) && fs.handles==0);
 assert((fs.files.count(kProgressPath) && fs.files[kProgressPath]==vec(a)) || (fs.files.count(kProgressBackup) && fs.files[kProgressBackup]==vec(a)));
 assert(fs.files["/canary.bin"]==std::vector<uint8_t>({42}));
 assert(fs.files[japanese::review::kProgressPath]==vec(v1) && fs.files[japanese::review::kProgressBackup]==vec(v1backup));
 fs.shortWrite=fs.failWriteClose=fs.corruptClose=fs.dirFail=false;fs.failOpenPath=fs.failReadPath=fs.failClosePath=fs.failRemovePath="";fs.failRenameAt=0;
 assert(loadProgress(fs,out)==LoadStatus::Loaded && encodeProgress(out)==a);
}
for(const auto& cut:healthy.cuts){FakeFS reboot;reboot.files=cut;assert(loadProgress(reboot,out)==LoadStatus::Loaded);assert(encodeProgress(out)==a || encodeProgress(out)==b);}
FakeFS rollback;rollback.files[kProgressPath]=vec(a);rollback.failRenames={2,3};assert(!saveProgress(rollback,next,&old));
assert(!rollback.exists(kProgressPath) && rollback.files[kProgressBackup]==vec(a));rollback.failRenames.clear();assert(loadProgress(rollback,out)==LoadStatus::Loaded && encodeProgress(out)==a);
FakeFS cleanup;cleanup.files[kProgressPath]=vec(a);cleanup.afterRead=[](FakeFS& f,const std::string& path){if(path==kProgressPart)f.failRemovePath=kProgressBackup;};
assert(saveProgress(cleanup,next,&old) && cleanup.exists(kProgressBackup));assert(loadProgress(cleanup,out)==LoadStatus::Loaded && encodeProgress(out)==b);
''')

    def test_expected_is_rechecked_at_commit_for_loaded_empty_imported_concurrency(self):
        self.run_cpp(r'''
Progress old;assert(record(old,0,1,true));auto next=old;assert(record(next,8,5,true));auto concurrent=old;assert(record(concurrent,3,4,true));
const auto a=encodeProgress(old),c=encodeProgress(concurrent);
for(int fault=0;fault<5;++fault){FakeFS fs;fs.files[kProgressPath]=vec(a);
 fs.afterRead=[&](FakeFS& f,const std::string& path){if(path==kProgressPart){
  if(fault==0)f.files[kProgressPath]=vec(c);
  if(fault==1)f.files.erase(kProgressPath);
  if(fault==2)f.files[kProgressPath][4]=5;
  if(fault==3)f.failReadPath=kProgressPath;
  if(fault==4)f.available=false;
 }};
 assert(!saveProgress(fs,next,&old) && fs.renames==0 && fs.handles==0);
 if(fault==0)assert(fs.files[kProgressPath]==vec(c));
 if(fault==1)assert(!fs.files.count(kProgressPath));
}
for(int fault=0;fault<3;++fault){FakeFS fs;Progress empty,first;assert(record(first,1,2,true));
 fs.afterRead=[&](FakeFS& f,const std::string& path){if(path==kProgressPart){
  if(fault==0)f.files[kProgressPath]=vec(c);
  if(fault==1)f.files[kProgressBackup]=vec(c);
  if(fault==2)f.files[japanese::review::kProgressPath]={0};
 }};
 assert(!saveProgress(fs,first,&empty) && fs.renames==0 && fs.handles==0);
}
japanese::review::Progress legacy;assert(japanese::review::recordSentence(legacy,4,true));auto v1=japanese::review::encodeProgress(legacy);
for(int fault=0;fault<3;++fault){FakeFS fs;fs.files[japanese::review::kProgressPath]=vec(v1);Progress imported;
 assert(loadProgress(fs,imported)==LoadStatus::Imported);auto desired=imported;assert(record(desired,4,2,true));
 auto external=legacy;assert(japanese::review::recordSentence(external,5,true));auto changed=japanese::review::encodeProgress(external);
 fs.afterRead=[&](FakeFS& f,const std::string& path){if(path==kProgressPart){
  if(fault==0)f.files[japanese::review::kProgressPath]=vec(changed);
  if(fault==1)f.files.erase(japanese::review::kProgressPath);
  if(fault==2)f.files[japanese::review::kProgressPath][4]=2;
 }};
 assert(!saveProgress(fs,desired,&imported) && fs.renames==0 && !fs.exists(kProgressPath) && fs.handles==0);
 if(fault==0)assert(fs.files[japanese::review::kProgressPath]==vec(changed));
}
// Previously committed v2 disappears: old expected cannot authorize a reset/import.
FakeFS disappeared;assert(!saveProgress(disappeared,next,&old) && disappeared.writes==0);
''')

    def test_uncertain_commit_exact_readback_and_retry_merge_are_not_duplicate(self):
        self.run_cpp(r'''
Progress old;assert(record(old,1,4,true));auto desired=old;assert(record(desired,8,5,true));
const auto a=encodeProgress(old),b=encodeProgress(desired);
for(int fault=0;fault<5;++fault){FakeFS fs;fs.files[kProgressPath]=vec(a);
 fs.afterRead=[&](FakeFS& f,const std::string& path){
  if(path==kProgressPart && fault==0)f.failReadAt=f.reads+2;
  if(path==kProgressPath && f.reads==3 && fault==1)f.failOpenPath=kProgressPath;
  if(path==kProgressPath && f.reads==4 && fault==2)f.failClosePath=kProgressPath;
  if(path==kProgressPart && fault==3){auto other=old;assert(record(other,5,2,true));f.files[kProgressPart]=vec(encodeProgress(other));}
  if(path==kProgressPath && f.reads==3 && fault==4)f.files.erase(kProgressPart);
 };
 assert(!saveProgress(fs,desired,&old) && fs.handles==0);
 assert(fs.files.count(kProgressPath));
 fs.afterRead={};fs.failReadAt=0;fs.failOpenPath=fs.failClosePath="";
 Progress reopened;assert(loadProgress(fs,reopened)==LoadStatus::Loaded);
 if(fault<3){assert(encodeProgress(reopened)==b && fs.files[kProgressBackup]==vec(a));
  const int writes=fs.writes;assert(!mergePending(reopened,desired,1u<<8,true));
  assert(!saveProgress(fs,desired,&old) && fs.writes==writes);
 }else if(fault==3){assert(encodeProgress(reopened)!=b && fs.files[kProgressBackup]==vec(a));}
 else {assert(encodeProgress(reopened)==a);}
}
// First initialization may commit despite failed final verification too.
FakeFS first;Progress empty,pending;assert(record(pending,8,5,true));
first.afterRead=[](FakeFS& f,const std::string& path){if(path==kProgressPart)f.failReadPath=kProgressPath;};
assert(!saveProgress(first,pending,&empty) && first.files[kProgressPath]==vec(encodeProgress(pending)));
first.afterRead={};first.failReadPath="";Progress current;assert(loadProgress(first,current)==LoadStatus::Loaded);
assert(!mergePending(current,pending,1u<<8,true) && first.writes==1);
''')

    def test_recovery_corrupt_future_and_read_errors_fail_closed_without_import(self):
        self.run_cpp(r'''
Progress old;assert(record(old,2,4,true));auto next=old;assert(record(next,8,5,true));const auto a=encodeProgress(old),b=encodeProgress(next);
japanese::review::Progress legacy;const auto v1=japanese::review::encodeProgress(legacy);
for(bool backup:{false,true})for(int fault=0;fault<10;++fault){FakeFS fs;const auto path=backup?kProgressBackup:kProgressPath;
 fs.files[path]=vec(a);fs.files[kProgressPart]=vec(b);fs.files[japanese::review::kProgressPath]=vec(v1);
 if(fault==0)fs.files[path].pop_back();
 if(fault==1)fs.files[path].push_back(0);
 if(fault==2)fs.files[path][32]^=1;
 if(fault==3){auto bad=a;bad[4]=5;detail::put(bad.data()+644,detail::checksum(bad.data(),644),4);fs.files[path]=vec(bad);}
 if(fault==4)fs.failOpenPath=path;
 if(fault==5)fs.failReadPath=path;
 if(fault==6)fs.failClosePath=path;
 if(fault==7)fs.available=false;
 if(fault==8 && backup)fs.failRenames={1,2};
 if(fault==9 && backup)fs.failReadPath=kProgressPath;
 const auto files=fs.files;Progress sentinel;assert(record(sentinel,6,1,true));const auto before=encodeProgress(sentinel);
 auto status=loadProgress(fs,sentinel);
 if(fault<8 || backup){assert(status==(fault<4?LoadStatus::Corrupt:LoadStatus::StorageError) && encodeProgress(sentinel)==before);
  assert(!saveProgress(fs,next,&old) && fs.writes==0);
  if(fault!=9)assert(fs.files==files);
 }else assert(status==LoadStatus::Loaded);
 assert(fs.handles==0 && fs.files[japanese::review::kProgressPath]==vec(v1));
}
FakeFS backup;backup.files[kProgressBackup]=vec(a);backup.files[kProgressPart]=vec(b);Progress recovered;
assert(loadProgress(backup,recovered)==LoadStatus::Loaded && encodeProgress(recovered)==a && backup.files[kProgressPart]==vec(b));
FakeFS part;part.files[kProgressPart]=vec(b);assert(loadProgress(part,recovered)==LoadStatus::Empty && recovered.revision==0 && part.writes==0);
FakeFS conflict;conflict.files[kProgressPath]={0};conflict.files[kProgressBackup]=vec(a);auto before=conflict.files;
assert(loadProgress(conflict,recovered)==LoadStatus::Corrupt && conflict.files==before);
''')

    def test_hardware_transaction_lock_encloses_import_and_load_save(self):
        self.run_cpp(r'''
FakeFS fs;fs.requireLock=true;Progress empty,p;assert(transactionDepth==0);
assert(loadProgress(fs,p)==LoadStatus::Empty && transactionDepth==0);
assert(record(p,8,5,true));assert(saveProgress(fs,p,&empty) && transactionDepth==0);
assert(loadProgress(fs,p)==LoadStatus::Loaded && transactionDepth==0);
auto next=p;assert(record(next,4,3,true));assert(saveProgress(fs,next,&p) && transactionDepth==0);
fs.available=false;assert(!saveProgress(fs,next,&p) && transactionDepth==0);
FakeFS legacy;legacy.requireLock=true;japanese::review::Progress v1;auto bytes=japanese::review::encodeProgress(v1);
legacy.files[japanese::review::kProgressPath]=vec(bytes);assert(loadProgress(legacy,p)==LoadStatus::Imported && transactionDepth==0);
assert(record(p,1,2,true));assert(saveProgress(legacy,p,&empty) && transactionDepth==0);
''', hardware=True)

    def test_removed_media_or_committed_file_during_read_never_claims_success(self):
        self.run_cpp(r'''
Progress old;assert(record(old,2,5,true));auto desired=old;assert(record(desired,8,5,true));const auto a=encodeProgress(old);
for(bool absent:{false,true}){
 FakeFS fs;fs.files[kProgressPath]=vec(a);
 fs.afterRead=[&](FakeFS& f,const std::string& path){if(path==kProgressPath && f.reads==4){if(absent)f.files.erase(path);else f.available=false;}};
 assert(!saveProgress(fs,desired,&old) && fs.handles==0 && fs.files[kProgressBackup]==vec(a));
 fs.afterRead={};fs.available=true;Progress restored;assert(loadProgress(fs,restored)==LoadStatus::Loaded);
 assert(encodeProgress(restored)==(absent?a:encodeProgress(desired)));
}
for(bool backup:{false,true}){FakeFS fs;const auto path=backup?kProgressBackup:kProgressPath;fs.files[path]=vec(a);
 fs.afterRead=[&](FakeFS& f,const std::string& p){if(p==kProgressPath)f.files.erase(p);};
 Progress sentinel;assert(record(sentinel,5,1,true));auto before=encodeProgress(sentinel);
 assert(loadProgress(fs,sentinel)==LoadStatus::StorageError && encodeProgress(sentinel)==before && fs.handles==0);
}
japanese::review::Progress v1;const auto legacy=japanese::review::encodeProgress(v1);FakeFS fs;fs.files[japanese::review::kProgressPath]=vec(legacy);
fs.afterRead=[](FakeFS& f,const std::string&){f.available=false;};Progress out;assert(record(out,3,2,true));auto before=encodeProgress(out);
assert(loadProgress(fs,out)==LoadStatus::StorageError && encodeProgress(out)==before && fs.writes==0);
''')

if __name__ == '__main__':
    unittest.main()
