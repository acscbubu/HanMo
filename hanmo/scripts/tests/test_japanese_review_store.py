"""Real-header codec / recoverable SD transactions with HAL-shaped fault injection."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(os.environ.get('JAPANESE_REVIEW_TEST_ROOT', Path(__file__).resolve().parents[2]))
FAKE_STORAGE = r'''
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
 ~HalFile();explicit operator bool()const{return opened;}
 size_t size()const;int read(void*,size_t);size_t write(const void*,size_t);
 void flush();bool close();
};
struct FakeFS {
 std::map<std::string,std::vector<uint8_t>> files;
 std::vector<std::map<std::string,std::vector<uint8_t>>> cuts;
 std::vector<std::string> events;
 std::set<int> failRenames;
 std::function<void(FakeFS&,const std::string&)> afterRead;
 bool available=true,shortWrite=false,corruptClose=false,dirFail=false,requireLock=false,failWriteClose=false;
 std::string failReadPath,failOpenPath,failClosePath,failRemovePath;
 int handles=0,writes=0,renames=0,failRenameAt=0,reads=0,failReadAt=0;
 bool ready()const{assert(!requireLock || transactionDepth>0);return available;}
 void snapshot(const std::string& event){events.push_back(event);cuts.push_back(files);}
 static void allowed(const char* path){assert(std::string(path).rfind("/.crosspoint/japanese-review-v1.bin",0)==0);}
 bool ensureDirectoryExists(const char* path){assert(std::string(path)=="/.crosspoint");return available && !dirFail;}
 bool exists(const char* p)const{return available && files.count(p);}
 bool remove(const char* p){allowed(p);assert(handles==0);if(!available || failRemovePath==p)return false;bool ok=files.erase(p);snapshot(std::string("remove:")+p);return ok;}
 bool rename(const char* from,const char* to){allowed(from);allowed(to);assert(handles==0);++renames;events.push_back("rename-attempt");if(!available || renames==failRenameAt || failRenames.count(renames) || !exists(from) || exists(to))return false;files[to]=files.at(from);files.erase(from);snapshot(std::string("rename:")+from+"->"+to);return true;}
 bool openFileForRead(const char*,const char* p,HalFile& f){allowed(p);if(!available || failOpenPath==p || !exists(p))return false;assert(!f.opened);f.fs=this;f.path=p;f.reading=true;f.opened=true;++handles;return true;}
 bool openFileForWrite(const char*,const char* p,HalFile& f){allowed(p);if(!available || failOpenPath==p)return false;assert(!f.opened);files[p].clear();f.fs=this;f.path=p;f.reading=false;f.opened=true;++handles;++writes;snapshot(std::string("open-write:")+p);return true;}
};
inline HalFile::~HalFile(){if(opened)close();}
inline size_t HalFile::size()const{return fs->files.at(path).size();}
inline int HalFile::read(void* out,size_t n){assert(opened && reading);++fs->reads;fs->events.push_back(std::string("read:")+path);if(fs->failReadPath==path || fs->reads==fs->failReadAt)return -1;const auto& bytes=fs->files.at(path);size_t count=std::min(n,bytes.size());std::memcpy(out,bytes.data(),count);if(fs->afterRead)fs->afterRead(*fs,path);return static_cast<int>(count);}
inline size_t HalFile::write(const void* in,size_t n){assert(opened && !reading);size_t count=fs->shortWrite && n?n-1:n;const auto* raw=static_cast<const uint8_t*>(in);fs->files[path].assign(raw,raw+count);fs->snapshot(std::string("write:")+path);return count;}
inline void HalFile::flush(){assert(opened);fs->snapshot(std::string("flush:")+path);}
inline bool HalFile::close(){if(!opened)return true;opened=false;--fs->handles;bool ok=fs->failClosePath!=path && (reading || !fs->failWriteClose);if(!reading && fs->corruptClose && fs->files[path].size()>8)fs->files[path][8]^=1;fs->snapshot(std::string("close:")+path);return ok;}
'''


class ReviewStoreTests(unittest.TestCase):
    def run_cpp(self, body, hardware=False):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            (temp / 'HalStorage.h').write_text(FAKE_STORAGE)
            (temp / 'main.cpp').write_text('#include "activities/apps/japanese/JapaneseReviewStore.h"\n#include <cassert>\nusing namespace japanese::review;\nint main(){\n' + body + '\n}\n')
            built = subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-fsanitize=undefined', '-fno-sanitize-recover=all', *(['-DARDUINO_ARCH_ESP32=1'] if hardware else []), '-I', str(temp), '-I', str(ROOT / 'src'), str(temp / 'main.cpp'), '-o', str(temp / 'test')], text=True, capture_output=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run([str(temp / 'test')], text=True, capture_output=True)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)

    def test_codec_fixed_little_endian_shared_ids_and_atomic_crc_rejection(self):
        self.run_cpp(r'''
Progress p;assert(applyRating(p,45,Rating::Known,kMinDay));assert(recordSentence(p,5,true));
auto bytes=encodeProgress(p);static_assert(kProgressBytes==613);
assert(bytes[4]==1 && bytes[5]==45 && bytes[6]==1 && bytes[7]==6);
assert(bytes[8]==2 && bytes[9]==0 && bytes[10]==0 && bytes[11]==0);
assert(bytes[16]==5 && bytes[17]==32);
for(int i=0;i<6;++i)assert(bytes[18+i]==i);
for(int i=0;i<45;++i)assert(bytes[24+13*i]==japanese::Words::cardIdAt(i));
assert(bytes[24+13*44+1]==static_cast<uint8_t>(kMinDay+7));
Progress decoded;assert(decodeProgress(bytes,decoded));assert(encodeProgress(decoded)==bytes);
Progress sentinel;assert(recordSentence(sentinel,3,true));auto before=encodeProgress(sentinel);
bytes[kProgressBytes-1]^=1;assert(!decodeProgress(bytes,sentinel));assert(encodeProgress(sentinel)==before);
bytes=encodeProgress(Progress{});assert(decodeProgress(bytes,decoded));assert(decoded.revision==0);
''')

    def test_valid_crc_does_not_authorize_unknown_schema_ids_or_impossible_state(self):
        self.run_cpp(r'''
Progress good;assert(applyRating(good,0,Rating::Known,kMinDay));
Progress out;assert(recordSentence(out,4,true));const auto before=encodeProgress(out);
auto reject=[&](auto b){detail::put(b.data()+kProgressBytes-4,detail::checksum(b.data(),kProgressBytes-4),4);assert(!decodeProgress(b,out));assert(encodeProgress(out)==before);};
for(int offset: {0,1,2,3,4,5,6,7,18,23}) {auto b=encodeProgress(good);b[offset]^=1;reject(b);}
for(int id: {0,44,46,255}) {auto b=encodeProgress(good);b[24+13]=id;reject(b);}
auto b=encodeProgress(good);b[16]=6;reject(b);b=encodeProgress(good);b[17]=64;reject(b);
for(int field: {1,5,9,11,12}) {b=encodeProgress(good);b[24+13+field]=1;reject(b);}
for(int rating: {0,4,255}) {b=encodeProgress(good);b[24+12]=rating;reject(b);}
for(int interval: {0,1,2,3,8,31,255}) {b=encodeProgress(good);b[24+11]=interval;reject(b);}
b=encodeProgress(good);detail::put(b.data()+24+1,kMinDay+8,4);reject(b);
b=encodeProgress(good);detail::put(b.data()+24+5,kMinDay-1,4);reject(b);
b=encodeProgress(good);detail::put(b.data()+12,0,4);reject(b);
b=encodeProgress(good);detail::put(b.data()+12,kMinDay+1,4);reject(b);
b=encodeProgress(good);detail::put(b.data()+8,0,4);reject(b);
Progress sentence;assert(recordSentence(sentence,5,true));assert(decodeProgress(encodeProgress(sentence),out));assert(out.latestDay==0);
good.words[0].reviews=65535;good.revision=65535;assert(decodeProgress(encodeProgress(good),out));
assert(applyRating(good,0,Rating::Known,good.words[0].dueDay));assert(decodeProgress(encodeProgress(good),out));assert(out.words[0].reviews==65535);
// Array order is not identity: explicitly carried IDs restore to logical indexes.
auto shuffled=encodeProgress(good);for(int j=0;j<13;++j)std::swap(shuffled[24+j],shuffled[24+44*13+j]);
detail::put(shuffled.data()+kProgressBytes-4,detail::checksum(shuffled.data(),kProgressBytes-4),4);
assert(decodeProgress(shuffled,out));assert(encodeProgress(out)==encodeProgress(good));
''')

    def test_first_commit_reopens_exact_snapshot_and_no_sd_is_not_empty(self):
        self.run_cpp(r'''
FakeFS fs;Progress p;assert(recordSentence(p,2,true));
assert(loadProgress(fs,p)==LoadStatus::Empty);assert(p.revision==0);
assert(recordSentence(p,5,true));const Progress empty;
assert(saveProgress(fs,p,&empty));assert(fs.handles==0 && fs.writes==1);
const auto encoded=encodeProgress(p);assert(fs.files[kProgressPath]==std::vector<uint8_t>(encoded.begin(),encoded.end()));
assert(!fs.exists(kProgressPart) && !fs.exists(kProgressBackup));
Progress restored;assert(loadProgress(fs,restored)==LoadStatus::Loaded);assert(encodeProgress(restored)==encoded);
assert(std::count(fs.events.begin(),fs.events.end(),std::string("read:")+kProgressPart)==1);
assert(std::count(fs.events.begin(),fs.events.end(),std::string("read:")+kProgressPath)>=2);
fs.available=false;auto before=encodeProgress(restored);assert(loadProgress(fs,restored)==LoadStatus::StorageError);assert(encodeProgress(restored)==before);
assert(!saveProgress(fs,p,&empty));assert(fs.writes==1);
FakeFS absent;absent.available=false;assert(loadProgress(absent,restored)==LoadStatus::StorageError);
''')

    def test_replacement_faults_preserve_previous_committed_progress(self):
        self.run_cpp(r'''
Progress old;assert(applyRating(old,7,Rating::Familiar,kMinDay));auto next=old;assert(recordSentence(next,3,true));
const auto a=encodeProgress(old);const std::vector<uint8_t> oldBytes(a.begin(),a.end());
FakeFS healthy;healthy.files[kProgressPath]=oldBytes;
assert(saveProgress(healthy,next,&old));Progress reopened;assert(loadProgress(healthy,reopened)==LoadStatus::Loaded);
assert(encodeProgress(reopened)==encodeProgress(next));assert(healthy.handles==0);
for(int fault=0;fault<10;++fault) {
 FakeFS fs;fs.files[kProgressPath]=oldBytes;
 if(fault==0)fs.shortWrite=true;
 if(fault==1)fs.failWriteClose=true;
 if(fault==2)fs.corruptClose=true;
 if(fault==3)fs.failReadPath=kProgressPart;
 if(fault==4)fs.failOpenPath=kProgressPart;
 if(fault==5)fs.dirFail=true;
 if(fault==6)fs.failRenameAt=1;
 if(fault==7)fs.failRenameAt=2;
 if(fault==8){fs.files[kProgressPart]={1};fs.failRemovePath=kProgressPart;}
 if(fault==9){fs.files[kProgressBackup]=oldBytes;fs.failRemovePath=kProgressBackup;}
 assert(!saveProgress(fs,next,&old));assert(fs.handles==0);
 assert((fs.exists(kProgressPath) && fs.files[kProgressPath]==oldBytes) || (fs.exists(kProgressBackup) && fs.files[kProgressBackup]==oldBytes));
 fs.shortWrite=fs.corruptClose=fs.dirFail=fs.failWriteClose=false;fs.failReadPath=fs.failOpenPath=fs.failClosePath=fs.failRemovePath="";fs.failRenameAt=0;
 assert(loadProgress(fs,reopened)==LoadStatus::Loaded);assert(encodeProgress(reopened)==a);
}
''')

    def test_power_cut_recovery_validates_backup_and_never_promotes_part(self):
        self.run_cpp(r'''
Progress old;assert(applyRating(old,1,Rating::Again,kMinDay));auto next=old;assert(recordSentence(next,5,true));
auto a=encodeProgress(old),b=encodeProgress(next);std::vector<uint8_t> oldBytes(a.begin(),a.end()),newBytes(b.begin(),b.end());
FakeFS committed;committed.files[kProgressPath]=oldBytes;assert(saveProgress(committed,next,&old));
for(const auto& cut:committed.cuts) {FakeFS reboot;reboot.files=cut;Progress p;assert(loadProgress(reboot,p)==LoadStatus::Loaded);assert(encodeProgress(p)==a || encodeProgress(p)==b);assert(reboot.handles==0);}
FakeFS backup;backup.files[kProgressBackup]=oldBytes;backup.files[kProgressPart]=newBytes;Progress p;
assert(loadProgress(backup,p)==LoadStatus::Loaded);assert(encodeProgress(p)==a && backup.files[kProgressPath]==oldBytes);
assert(backup.files[kProgressPart]==newBytes); // staging is not committed
FakeFS part;part.files[kProgressPart]=newBytes;assert(loadProgress(part,p)==LoadStatus::Empty);assert(p.revision==0 && part.files[kProgressPart]==newBytes && part.writes==0);
FakeFS bad;bad.files[kProgressBackup]=oldBytes;bad.files[kProgressBackup][9]^=1;assert(recordSentence(p,2,true));const auto sentinel=encodeProgress(p);
assert(loadProgress(bad,p)==LoadStatus::Corrupt && encodeProgress(p)==sentinel);assert(!bad.exists(kProgressPath));assert(!saveProgress(bad,next,&old));
FakeFS conflict;conflict.files[kProgressPath]={0};conflict.files[kProgressBackup]=oldBytes;auto initial=conflict.files;
assert(loadProgress(conflict,p)==LoadStatus::Corrupt);assert(conflict.files==initial && encodeProgress(p)==sentinel);
FakeFS failure;failure.files[kProgressBackup]=oldBytes;failure.failRenameAt=1;
assert(loadProgress(failure,p)==LoadStatus::StorageError && encodeProgress(p)==sentinel && failure.files[kProgressBackup]==oldBytes);
failure.failRenameAt=0;failure.failReadPath=kProgressBackup;assert(loadProgress(failure,p)==LoadStatus::StorageError && !failure.exists(kProgressPath));
''')

    def test_exact_expected_conflict_revision_guard_and_staging_time_conflict(self):
        self.run_cpp(r'''
Progress old;assert(recordSentence(old,1,true));auto next=old;assert(recordSentence(next,2,true));
auto a=encodeProgress(old);std::vector<uint8_t> oldBytes(a.begin(),a.end());FakeFS fs;fs.files[kProgressPath]=oldBytes;
Progress wrong=old;wrong.sentencePosition=4;assert(!saveProgress(fs,next,&wrong));assert(fs.writes==0 && fs.files[kProgressPath]==oldBytes);
auto same=old;assert(!saveProgress(fs,same,&old));auto jump=next;++jump.revision;assert(!saveProgress(fs,jump,&old));assert(fs.writes==0);
Progress overflow=old;overflow.revision=UINT32_MAX;auto ov=encodeProgress(overflow);fs.files[kProgressPath]={ov.begin(),ov.end()};assert(!saveProgress(fs,next,&overflow));assert(fs.writes==0);
fs.files[kProgressPath]=oldBytes;
auto concurrent=old;assert(recordSentence(concurrent,4,true));auto c=encodeProgress(concurrent);std::vector<uint8_t> external(c.begin(),c.end());
fs.afterRead=[&](FakeFS& f,const std::string& path){if(path==kProgressPart) f.files[kProgressPath]=external;};
assert(!saveProgress(fs,next,&old));assert(fs.files[kProgressPath]==external && fs.renames==0 && !fs.exists(kProgressBackup));
FakeFS fresh;Progress initial;auto first=initial;assert(recordSentence(first,2,true));
fresh.afterRead=[&](FakeFS& f,const std::string& path){if(path==kProgressPart)f.files[kProgressBackup]=external;};
assert(!saveProgress(fresh,first,&initial));assert(fresh.files[kProgressBackup]==external && !fresh.exists(kProgressPath));
''')

    def test_revision_increment_cannot_authorize_reset_or_multi_event_write(self):
        self.run_cpp(r'''
Progress old;assert(applyRating(old,0,Rating::Again,kMinDay));assert(recordSentence(old,5,true));
auto a=encodeProgress(old);FakeFS fs;fs.files[kProgressPath]={a.begin(),a.end()};
Progress reset;reset.revision=old.revision+1;assert(!saveProgress(fs,reset,&old));assert(fs.writes==0);
auto erased=old;erased.sentenceReadMask=0;++erased.revision;assert(!saveProgress(fs,erased,&old));
auto duplicate=old;++duplicate.revision;assert(!saveProgress(fs,duplicate,&old));
auto bulk=old;assert(applyRating(bulk,1,Rating::Known,kMinDay));assert(applyRating(bulk,2,Rating::Known,kMinDay));--bulk.revision;
assert(!saveProgress(fs,bulk,&old));assert(fs.writes==0 && fs.files[kProgressPath]==std::vector<uint8_t>(a.begin(),a.end()));
auto next=old;assert(applyRating(next,0,Rating::Known,kMinDay+1));assert(saveProgress(fs,next,&old));
auto sentence=next;assert(recordSentence(sentence,3,true));assert(saveProgress(fs,sentence,&next));
''')


    def test_hardware_hal_transaction_guard_is_scoped_across_load_and_save(self):
        self.run_cpp(r'''
FakeFS fs;fs.requireLock=true;Progress p;assert(transactionDepth==0);
assert(loadProgress(fs,p)==LoadStatus::Empty);assert(transactionDepth==0);
assert(recordSentence(p,1,true));const Progress empty;assert(saveProgress(fs,p,&empty));assert(transactionDepth==0);
assert(loadProgress(fs,p)==LoadStatus::Loaded);assert(transactionDepth==0);
fs.available=false;assert(!saveProgress(fs,p,&empty));assert(transactionDepth==0);
''', hardware=True)


    def test_final_live_readback_failure_never_claims_saved_and_retry_is_not_duplicate(self):
        self.run_cpp(r'''
Progress old;assert(applyRating(old,0,Rating::Again,kMinDay));auto next=old;assert(recordSentence(next,4,true));
auto a=encodeProgress(old),b=encodeProgress(next);std::vector<uint8_t> oldBytes(a.begin(),a.end()),newBytes(b.begin(),b.end());
for(int fault=0;fault<3;++fault){
 FakeFS fs;fs.files[kProgressPath]=oldBytes;
 fs.afterRead=[&](FakeFS& f,const std::string& path){
  if(path==kProgressPart && fault==0)f.failReadAt=f.reads+2;
  if(path==kProgressPath && f.reads==4 && fault==1)f.failClosePath=kProgressPath;
  if(path==kProgressPath && f.reads==3 && fault==2)f.failOpenPath=kProgressPath;
 };
 assert(!saveProgress(fs,next,&old));assert(fs.handles==0);
 assert(fs.files[kProgressPath]==newBytes && fs.files[kProgressBackup]==oldBytes);
 fs.afterRead={};fs.failReadAt=0;fs.failClosePath=fs.failOpenPath="";
 Progress p;assert(loadProgress(fs,p)==LoadStatus::Loaded);const int writes=fs.writes;
 assert(encodeProgress(p)==b);assert(!saveProgress(fs,next,&old));assert(fs.writes==writes);
}
// A valid but different snapshot swapped after staging read is not success.
FakeFS corrupt;corrupt.files[kProgressPath]=oldBytes;
auto other=old;assert(recordSentence(other,5,true));auto wrong=encodeProgress(other);
corrupt.afterRead=[&](FakeFS& f,const std::string& path){if(path==kProgressPart)f.files[kProgressPart]={wrong.begin(),wrong.end()};};
assert(!saveProgress(corrupt,next,&old));assert(corrupt.files[kProgressBackup]==oldBytes); // final mismatch preserves backup
''')

    def test_corrupt_failed_reads_and_future_format_do_not_modify_live_or_output(self):
        self.run_cpp(r'''
Progress old;assert(recordSentence(old,2,true));auto a=encodeProgress(old);auto next=old;assert(recordSentence(next,3,true));
for(int fault=0;fault<7;++fault){FakeFS fs;fs.files[kProgressPath]={a.begin(),a.end()};
 if(fault==0)fs.files[kProgressPath].pop_back();
 if(fault==1)fs.files[kProgressPath].push_back(0);
 if(fault==2)fs.files[kProgressPath][28]^=1;
 if(fault==3){auto b=a;b[4]=2;detail::put(b.data()+kProgressBytes-4,detail::checksum(b.data(),kProgressBytes-4),4);fs.files[kProgressPath]={b.begin(),b.end()};}
 if(fault==4)fs.failReadPath=kProgressPath;
 if(fault==5)fs.failClosePath=kProgressPath;
 if(fault==6)fs.failOpenPath=kProgressPath;
 const auto before=fs.files;Progress sentinel;assert(recordSentence(sentinel,5,true));auto state=encodeProgress(sentinel);
 assert(loadProgress(fs,sentinel)==(fault<4?LoadStatus::Corrupt:LoadStatus::StorageError));assert(encodeProgress(sentinel)==state && fs.handles==0);
 assert(!saveProgress(fs,next,&old));assert(fs.files==before && fs.writes==0);
}
''')

    def test_failed_rollback_and_cleanup_leave_reopenable_commit(self):
        self.run_cpp(r'''
Progress old;assert(recordSentence(old,1,true));auto next=old;assert(recordSentence(next,2,true));auto a=encodeProgress(old);
FakeFS fs;fs.files[kProgressPath]={a.begin(),a.end()};fs.failRenames={2,3};assert(!saveProgress(fs,next,&old));
assert(!fs.exists(kProgressPath) && fs.files[kProgressBackup]==std::vector<uint8_t>(a.begin(),a.end()));
fs.failRenames.clear();Progress p;assert(loadProgress(fs,p)==LoadStatus::Loaded && encodeProgress(p)==a);
fs.afterRead=[](FakeFS& f,const std::string& path){if(path==kProgressPart)f.failRemovePath=kProgressBackup;};
assert(saveProgress(fs,next,&old));assert(fs.exists(kProgressBackup));assert(loadProgress(fs,p)==LoadStatus::Loaded && encodeProgress(p)==encodeProgress(next));
''')


if __name__ == '__main__':
    unittest.main()
