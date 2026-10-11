"""Topics30 v4 migration tests. Historical filename; all nine categories covered.
Compile the real store/core; replace only SD HAL. No generated topic data needed.
"""
from pathlib import Path
import os
import struct
import unittest
import zlib
from scripts.tests import test_japanese_dialogues_progress as stores

ROOT = stores.ROOT
LEGACY = r'''
[[maybe_unused]] constexpr char v2Live[]="/.crosspoint/japanese-sentences-v2.bin";
constexpr char v2Backup[]="/.crosspoint/japanese-sentences-v2.bin.bak";
constexpr char v2Part[]="/.crosspoint/japanese-sentences-v2.bin.part";
[[maybe_unused]] auto putLE=[](uint8_t* out,uint32_t value,int n){for(int i=0;i<n;++i)out[i]=uint8_t(value>>(i*8));};
[[maybe_unused]] auto fixV2CRC=[&](auto& b){uint32_t crc=0xffffffffu;for(int i=0;i<100;++i){crc^=b[i];for(int j=0;j<8;++j)crc=crc&1?(crc>>1)^0xedb88320u:crc>>1;}putLE(b.data()+100,~crc,4);};
[[maybe_unused]] auto makeV2=[&](uint32_t revision,int last,const std::array<uint8_t,9>& positions,uint64_t mask){
 std::array<uint8_t,104> b{'J','S','P','2',2,9,6,54,7,1};putLE(b.data()+10,104,2);putLE(b.data()+12,0x4a534401u,4);putLE(b.data()+16,revision,4);b[20]=last;
 for(int c=0;c<9;++c){b[21+c]=positions[c];b[37+c]=c;}
 for(int i=0;i<7;++i)b[30+i]=uint8_t(mask>>(i*8));
 for(int i=0;i<54;++i)b[46+i]=i;
 fixV2CRC(b);return b;
};
[[maybe_unused]] auto protectWords=[&](FakeFS& fs){japanese::review::Progress v1;for(int i=0;i<45;++i)assert(japanese::review::applyRating(v1,japanese::Words::cardIdAt(i),japanese::review::Rating::Known,japanese::review::kMinDay));assert(japanese::review::recordSentence(v1,5,true));v1.sentenceReadMask=63;
 fs.files[japanese::review::kProgressPath]=vec(japanese::review::encodeProgress(v1));
 auto older=v1;older.sentencePosition=4;fs.files[japanese::review::kProgressBackup]=vec(japanese::review::encodeProgress(older));
 fs.files[japanese::review::kProgressPart]={9,8,7};fs.files[v2Part]={6,5,4};fs.files["/canary.bin"]={3,2,1};
};
'''


class Basic30ProgressTests(unittest.TestCase):
    def run_cpp(self, source, hardware=False):
        # Lambdas are test fixture encoders, never substitutes for the store.
        return stores.DialoguesProgressTests.run_cpp(self, LEGACY + source, hardware)

    def test_v2_live_backup_maps_every_old_bit_and_mixed_states_readonly(self):
        self.run_cpp(r'''
for(bool backup:{false,true})for(int pattern=0;pattern<58;++pattern){
 uint64_t mask=pattern<54?uint64_t(1)<<pattern:pattern==54?0:pattern==55?((uint64_t(1)<<54)-1):pattern==56?0x15555555555555ull:0x2aaaaaaaaaaaaaull;
 std::array<uint8_t,9> positions{};for(int c=0;c<9;++c)positions[c]=(c+pattern)%6;
 const auto raw=makeV2(0x10203040u+pattern,pattern%9,positions,mask);
 FakeFS fs;protectWords(fs);fs.files[backup?v2Backup:v2Live]=vec(raw);
 if(!backup)fs.files[v2Backup]=vec(makeV2(3,0,{},0));
 const auto before=fs.files;Progress p;assert(record(p,8,29,true));
 assert(loadProgress(fs,p)==LoadStatus::Imported);
 assert(p.revision==0x10203040u+pattern && p.lastCategory==pattern%9 && p.positions==positions);
 for(int c=0;c<9;++c){int count=0;for(int local=0;local<30;++local){bool expected=local<6 && (mask&(uint64_t(1)<<(c*6+local)));assert(isRead(p,c*30+local)==expected);count+=expected;}assert(readCount(p,c)==count);}
 assert(fs.files==before && fs.writes==0 && fs.renames==0 && fs.handles==0);
 for(const auto& cut:fs.cuts)assert(cut==before);
}
''')


    def test_commit_rechecks_raw_legacy_bytes_and_exact_import_source_identity(self):
        self.run_cpp(r'''
for(int mode=0;mode<5;++mode){
 FakeFS fs;protectWords(fs);
 if(mode==1 || mode==2){fs.files[v2Backup]=vec(makeV2(0,0,{},0));}
 if(mode==3){fs.files.erase(japanese::review::kProgressPath);}
 Progress base;assert(loadProgress(fs,base)==LoadStatus::Imported);auto desired=base;assert(record(desired,8,29,true));
 fs.afterRead=[&](FakeFS& f,const std::string& path){if(path!=kProgressPart)return;
  if(mode==0){japanese::review::Progress changed;assert(japanese::review::decodeProgress([&]{std::array<uint8_t,japanese::review::kProgressBytes> b{};std::copy(f.files.at(japanese::review::kProgressPath).begin(),f.files.at(japanese::review::kProgressPath).end(),b.begin());return b;}(),changed));assert(japanese::review::applyRating(changed,japanese::Words::cardIdAt(0),japanese::review::Rating::Again,japanese::review::kMinDay+7));f.files[japanese::review::kProgressPath]=vec(japanese::review::encodeProgress(changed));}
  if(mode==1)f.files[v2Live]=f.files.at(v2Backup); // identical mapped state, different authoritative source
  if(mode==2){f.files.erase(v2Backup);f.files[japanese::review::kProgressPath]=vec(japanese::review::encodeProgress(japanese::review::Progress{}));}
  if(mode==3)f.files[japanese::review::kProgressPath]=f.files.at(japanese::review::kProgressBackup);
  if(mode==4){auto& b=f.files.at(japanese::review::kProgressPath);for(int i=0;i<13;++i)std::swap(b[24+i],b[37+i]);putLE(b.data()+b.size()-4,detail::checksum(b.data(),b.size()-4),4);}
 };
 assert(!saveProgress(fs,desired,&base) && fs.writes==1 && fs.renames==0 && fs.handles==0 && !fs.files.count(kProgressPath));
 assert(fs.files.at(v2Part)==std::vector<uint8_t>({6,5,4}) && fs.files.at(japanese::review::kProgressPart)==std::vector<uint8_t>({9,8,7}) && fs.files.at("/canary.bin")==std::vector<uint8_t>({3,2,1}));
}
''')


    def test_v2_strict_headers_ids_bounds_crc_fail_closed_before_v1_backup(self):
        self.run_cpp(r'''
const auto valid=makeV2(12,8,{0,1,2,3,4,5,0,1,5},(uint64_t(1)<<54)-1);
for(bool backup:{false,true}){
 auto reject=[&](const auto& raw){FakeFS fs;protectWords(fs);const char* path=backup?v2Backup:v2Live;fs.files[path]=vec(raw);if(!backup)fs.files[v2Backup]=vec(valid);const auto files=fs.files;Progress p;assert(record(p,8,29,true));auto before=encodeProgress(p);assert(loadProgress(fs,p)==LoadStatus::Corrupt && encodeProgress(p)==before);assert(!saveProgress(fs,p,&p));assert(fs.files==files && fs.writes==0 && fs.renames==0 && fs.handles==0);};
 for(int offset=0;offset<104;++offset){auto b=valid;b[offset]^=1;reject(b);}
 for(int offset=0;offset<16;++offset){auto b=valid;b[offset]^=1;fixV2CRC(b);reject(b);}
 for(int offset=37;offset<100;++offset){auto b=valid;b[offset]^=1;fixV2CRC(b);reject(b);}
 for(int c=0;c<9;++c)for(int bad:{6,29,30,255}){auto b=valid;b[21+c]=bad;fixV2CRC(b);reject(b);}
 for(int bad:{9,255}){auto b=valid;b[20]=bad;fixV2CRC(b);reject(b);}
 for(int bad:{64,128,255}){auto b=valid;b[36]=bad;fixV2CRC(b);reject(b);}
 for(int n:{0,1,103,105,648}){std::vector<uint8_t> b(valid.begin(),valid.end());b.resize(n);reject(b);}
}
''')


    def test_v2_hal_read_failures_never_mutate_or_publish_import(self):
        self.run_cpp(r'''
const auto raw=makeV2(80,7,{5,4,3,2,1,0,5,4,3},0x123456789abcdull);
for(bool backup:{false,true})for(int fault=0;fault<7;++fault){
 FakeFS fs;protectWords(fs);const char* path=backup?v2Backup:v2Live;fs.files[path]=vec(raw);if(!backup)fs.files[v2Backup]=vec(raw);const auto before=fs.files;
 if(fault==0)fs.available=false;
 if(fault==1)fs.failOpenPath=path;
 if(fault==2)fs.failReadPath=path;
 if(fault==3)fs.shortRead=true;
 if(fault==4)fs.failClosePath=path;
 if(fault==5)fs.afterRead=[&](FakeFS& f,const std::string& p){if(p==path)f.available=false;};
 if(fault==6)fs.afterRead=[&](FakeFS& f,const std::string& p){if(p==path)f.files.erase(p);};
 Progress p;assert(record(p,8,29,true));const auto sentinel=encodeProgress(p);
 assert(loadProgress(fs,p)==LoadStatus::StorageError && encodeProgress(p)==sentinel && fs.writes==0 && fs.renames==0 && fs.handles==0);
 if(fault!=6)assert(fs.files==before);
}
''')

    def test_v4_authority_backup_recovery_part_ignoring_and_v1_only_fallback(self):
        self.run_cpp(r'''
assert(std::string(kProgressPath)=="/.crosspoint/japanese-sentences-v4.bin");
Progress committed;assert(record(committed,8,29,true));const auto current=encodeProgress(committed);
const auto raw=makeV2(5,7,{5,4,3,2,1,0,5,4,3},(uint64_t(1)<<54)-1);
for(bool backup:{false,true}){FakeFS fs;protectWords(fs);fs.files[v2Live]={0};fs.files[v2Backup]=vec(raw);const auto oldfiles=fs.files;
 fs.files[backup?kProgressBackup:kProgressPath]=vec(current);fs.files[kProgressPart]={4,4,4};
 Progress p;assert(loadProgress(fs,p)==LoadStatus::Loaded && encodeProgress(p)==current && fs.writes==0 && fs.renames==(backup?1:0));
 for(const auto& [path,bytes]:oldfiles)assert(fs.files.at(path)==bytes);
 for(const auto& e:fs.events)assert(e.find("read:/.crosspoint/japanese-sentences-v2")==std::string::npos && e.find("read:/.crosspoint/japanese-review-v1")==std::string::npos);
 fs.files[kProgressPath][4]=5;const auto before=fs.files;auto sentinel=encodeProgress(p);assert(loadProgress(fs,p)==LoadStatus::Corrupt && fs.files==before && encodeProgress(p)==sentinel);
}
FakeFS part;part.files[v2Part]=vec(raw);part.files[kProgressPart]=vec(current);part.files[japanese::review::kProgressPart]={3};const auto before=part.files;
Progress p;assert(loadProgress(part,p)==LoadStatus::Empty && part.files==before && part.writes==0 && part.renames==0);
protectWords(part);auto files=part.files;assert(loadProgress(part,p)==LoadStatus::Imported && p.revision==0 && readCount(p,0)==6 && p.positions[0]==5 && part.files==files);
for(int c=1;c<9;++c)assert(readCount(p,c)==0 && p.positions[c]==0);
part.files[v2Backup]=vec(raw);files=part.files;assert(loadProgress(part,p)==LoadStatus::Imported && p.revision==5 && p.lastCategory==7 && part.files==files);
''')


    def test_v2_first_commit_retains_revision_saves_all270_and_keeps_legacy_cuts(self):
        self.run_cpp(r'''
for(bool backup:{false,true}){
 FakeFS fs;protectWords(fs);fs.files[backup?v2Backup:v2Live]=vec(makeV2(123,8,{5,5,5,5,5,5,5,5,5},(uint64_t(1)<<54)-1));if(!backup)fs.files[v2Backup]=vec(makeV2(122,0,{},0));const auto legacy=fs.files;
 Progress base;assert(loadProgress(fs,base)==LoadStatus::Imported && base.revision==123);Progress pending;
 for(int c=0;c<9;++c)for(int l=0;l<30;++l)assert(record(pending,c,l,true));
 Progress desired=base;assert(mergePending(desired,pending,511,true) && desired.revision==124);
 for(int mode=0;mode<6;++mode){auto bad=desired;
  if(mode==0){bad.revision+=2;bad.positions[8]=28;}
  if(mode==1)bad.readBits[0]&=254;
  if(mode==2)bad.readBits[33]|=128;
  if(mode==3)bad.positions[8]=30;
  if(mode==4)bad.lastCategory=9;
  if(mode==5){bad=base;++bad.revision;}
  assert(!saveProgress(fs,bad,&base) && fs.writes==0 && fs.renames==0);
 }
 assert(saveProgress(fs,desired,&base) && fs.writes==1 && fs.handles==0);
 Progress reopened;assert(loadProgress(fs,reopened)==LoadStatus::Loaded && encodeProgress(reopened)==encodeProgress(desired));
 for(int g=0;g<270;++g){assert(isRead(reopened,g));}assert(!isRead(reopened,270) && !isRead(reopened,-1));
 for(int c=0;c<9;++c)assert(readCount(reopened,c)==30 && reopened.positions[c]==29);
 for(const auto& [path,bytes]:legacy)assert(fs.files.at(path)==bytes);
 for(const auto& cut:fs.cuts){FakeFS reboot;reboot.files=cut;Progress p;auto status=loadProgress(reboot,p);assert(status==LoadStatus::Imported || status==LoadStatus::Loaded);assert(encodeProgress(p)==encodeProgress(status==LoadStatus::Loaded?desired:base));for(const auto& [path,bytes]:legacy)assert(reboot.files.at(path)==bytes);}
 assert(!mergePending(reopened,desired,511,true));int writes=fs.writes;assert(!saveProgress(fs,desired,&base) && fs.writes==writes);
 fs.files.erase(kProgressPath);assert(!saveProgress(fs,desired,&desired) && fs.writes==writes); // disappeared v4 cannot reset/import stale expected
}
FakeFS overflow;protectWords(overflow);overflow.files[v2Live]=vec(makeV2(UINT32_MAX,8,{},0));const auto files=overflow.files;Progress p;assert(loadProgress(overflow,p)==LoadStatus::Imported && p.revision==UINT32_MAX);auto next=p;assert(!record(next,8,29,true) && !mergePending(next,Progress{},511,true));next.revision=0;next.positions[8]=29;assert(!saveProgress(overflow,next,&p) && overflow.files==files && overflow.writes==0);
''')


    def test_v2_import_write_faults_and_uncertain_commit_retry_preserve_every_legacy_byte(self):
        self.run_cpp(r'''
for(bool backup:{false,true})for(int fault=0;fault<15;++fault){
 FakeFS fs;protectWords(fs);const char* source=backup?v2Backup:v2Live;fs.files[source]=vec(makeV2(80,7,{5,4,3,2,1,0,5,4,3},0x123456789abcdull));if(!backup)fs.files[v2Backup]=vec(makeV2(79,0,{},0));const auto protectedFiles=fs.files;
 Progress base;assert(loadProgress(fs,base)==LoadStatus::Imported);auto desired=base;assert(record(desired,8,29,true));
 if(fault==0)fs.shortWrite=true;
 if(fault==1)fs.failWriteClose=true;
 if(fault==2)fs.corruptClose=true;
 if(fault==3)fs.failReadPath=kProgressPart;
 if(fault==4)fs.failOpenPath=kProgressPart;
 if(fault==5)fs.failClosePath=kProgressPart;
 if(fault==6)fs.dirFail=true;
 if(fault==7)fs.failRenameAt=1;
 if(fault==8){fs.files[kProgressPart]={1};fs.failRemovePath=kProgressPart;}
 bool staged=false;
 fs.afterRead=[&](FakeFS& f,const std::string& path){
  if(path==kProgressPart){staged=true;
   if(fault==9)f.available=false;
   if(fault==10)f.failReadPath=source;
   if(fault==11)f.failClosePath=source;
   if(fault==12)f.failReadPath=kProgressPath;
  }
  if(path==source && staged && fault==13)f.failClosePath=kProgressPath;
  if(path==source && staged && fault==14)f.files.erase(kProgressPart);
 };
 assert(!saveProgress(fs,desired,&base) && fs.handles==0);
 for(const auto& [path,bytes]:protectedFiles)assert(fs.files.at(path)==bytes);
 for(const auto& cut:fs.cuts)for(const auto& [path,bytes]:protectedFiles)assert(cut.at(path)==bytes);
 fs.shortWrite=fs.shortRead=fs.failWriteClose=fs.corruptClose=fs.dirFail=false;fs.failReadPath=fs.failOpenPath=fs.failClosePath=fs.failRemovePath="";fs.failRenameAt=0;fs.available=true;fs.afterRead={};
 Progress current;const auto status=loadProgress(fs,current);
 if(fault==12 || fault==13){assert(status==LoadStatus::Loaded && encodeProgress(current)==encodeProgress(desired));int writes=fs.writes;assert(!mergePending(current,desired,1u<<8,true) && !saveProgress(fs,desired,&base) && fs.writes==writes);}
 else assert(status==LoadStatus::Imported && encodeProgress(current)==encodeProgress(base));
}
''')


    def test_concurrent_v2_revision_bits_positions_and_status_changes_block_commit(self):
        self.run_cpp(r'''
const auto raw=makeV2(90,7,{5,4,3,2,1,0,5,4,3},0x123456789abcdull);
for(bool backup:{false,true})for(int mode=0;mode<8;++mode){
 FakeFS fs;protectWords(fs);const char* path=backup?v2Backup:v2Live;fs.files[path]=vec(raw);Progress base;assert(loadProgress(fs,base)==LoadStatus::Imported);auto desired=base;assert(record(desired,8,29,true));std::vector<uint8_t> external;
 fs.afterRead=[&](FakeFS& f,const std::string& p){if(p!=kProgressPart)return;auto changed=raw;
  if(mode==0)putLE(changed.data()+16,91,4);
  if(mode==1)changed[30]^=2;
  if(mode==2)changed[25]=2;
  if(mode==3)changed[20]=8;
  if(mode<4){fixV2CRC(changed);external=vec(changed);f.files[path]=external;}
  if(mode==4)f.files.erase(path);
  if(mode==5)f.files[kProgressBackup]=vec(encodeProgress(desired));
  if(mode==6)f.files[path][4]=3;
  if(mode==7)f.failOpenPath=path;
 };
 assert(!saveProgress(fs,desired,&base) && fs.renames==0 && fs.handles==0 && !fs.files.count(kProgressPath));
 if(mode<4)assert(fs.files.at(path)==external);
 if(mode==4)assert(!fs.files.count(path));
 assert(fs.files.at(v2Part)==std::vector<uint8_t>({6,5,4}) && fs.files.at(japanese::review::kProgressPart)==std::vector<uint8_t>({9,8,7}));
}
''')

    def test_cpp_v4_bytes_match_independent_python_struct_zlib_oracle(self):
        output = stores.DialoguesProgressTests.run_cpp(self, r'''
Progress p;p.revision=0x89abcdef;p.lastCategory=8;
for(int c=0;c<9;++c)p.positions[c]=29;
for(int g=0;g<270;++g)if(g%5!=2)p.readBits[g/8]|=uint8_t(1u<<(g%8));
const auto b=encodeProgress(p);Progress decoded;assert(decodeProgress(b,decoded));
FakeFS fs;fs.files[kProgressPath]=vec(b);Progress loaded;assert(loadProgress(fs,loaded)==LoadStatus::Loaded && encodeProgress(loaded)==b && fs.writes==0);
for(uint8_t value:b)std::cout<<"0123456789abcdef"[value>>4]<<"0123456789abcdef"[value&15];
''')
        expected = bytearray(648)
        expected[:8] = b'JSP4' + bytes([4, 9, 30, 0])
        struct.pack_into('<HHHHIIB', expected, 8, 270, 34, 3, 648, 0x4A534403, 0x89ABCDEF, 8)
        expected[25:34] = bytes([29] * 9)
        for global_id in range(270):
            if global_id % 5 != 2:
                expected[34 + global_id // 8] |= 1 << (global_id % 8)
        expected[68:77] = bytes(range(9))
        expected[77:86] = bytes([30] * 9)
        struct.pack_into('<9H', expected, 86, *range(0, 270, 30))
        ids = [c * 6 + j if j < 6 else 54 + c * 24 + j - 6 for c in range(9) for j in range(30)]
        self.assertEqual(sorted(ids), list(range(270)))
        struct.pack_into('<270H', expected, 104, *ids)
        struct.pack_into('<I', expected, 644, zlib.crc32(expected[:644]))
        self.assertEqual(bytes.fromhex(output), bytes(expected))


    def test_v4_replacement_faults_protect_all_v1_v2_live_backup_part_bytes(self):
        self.run_cpp(r'''
Progress old;assert(record(old,0,29,true));auto next=old;assert(record(next,8,29,true));const auto a=encodeProgress(old),b=encodeProgress(next);
for(int fault=0;fault<13;++fault){FakeFS fs;protectWords(fs);fs.files[v2Live]=vec(makeV2(45,4,{5,4,3,2,1,0,5,4,3},(uint64_t(1)<<54)-1));fs.files[v2Backup]=vec(makeV2(44,0,{},0));const auto legacy=fs.files;fs.files[kProgressPath]=vec(a);
 if(fault==0)fs.shortWrite=true;
 if(fault==1)fs.failWriteClose=true;
 if(fault==2)fs.corruptClose=true;
 if(fault==3)fs.failReadPath=kProgressPart;
 if(fault==4)fs.failOpenPath=kProgressPart;
 if(fault==5)fs.failClosePath=kProgressPart;
 if(fault==6)fs.failRenameAt=1;
 if(fault==7)fs.failRenameAt=2;
 if(fault==8){fs.files[kProgressBackup]=vec(a);fs.failRemovePath=kProgressBackup;}
 if(fault==9)fs.failReadAt=4;
 if(fault==10)fs.shortRead=true;
 if(fault==11)fs.available=false;
 if(fault==12)fs.dirFail=true;
 assert(!saveProgress(fs,next,&old) && fs.handles==0);
 for(const auto& [path,bytes]:legacy)assert(fs.files.at(path)==bytes);
 for(const auto& cut:fs.cuts)for(const auto& [path,bytes]:legacy)assert(cut.at(path)==bytes);
 fs.shortWrite=fs.shortRead=fs.failWriteClose=fs.corruptClose=fs.dirFail=false;fs.failReadPath=fs.failOpenPath=fs.failClosePath=fs.failRemovePath="";fs.failRenameAt=fs.failReadAt=0;fs.available=true;
 Progress p;assert(loadProgress(fs,p)==LoadStatus::Loaded && encodeProgress(p)==(fault==9?b:a));
 if(fault==9){auto writes=fs.writes;assert(!mergePending(p,next,1u<<8,true) && !saveProgress(fs,next,&old) && fs.writes==writes);}
}
''')

    def test_v2_import_and_save_hold_real_hardware_transaction_guard(self):
        self.run_cpp(r'''
FakeFS fs;protectWords(fs);fs.files[v2Backup]=vec(makeV2(20,8,{5,5,5,5,5,5,5,5,5},(uint64_t(1)<<54)-1));const auto legacy=fs.files;fs.requireLock=true;Progress p;
assert(loadProgress(fs,p)==LoadStatus::Imported && transactionDepth==0 && p.revision==20);
auto desired=p;assert(record(desired,8,29,true));assert(saveProgress(fs,desired,&p) && transactionDepth==0);
Progress current;assert(loadProgress(fs,current)==LoadStatus::Loaded && transactionDepth==0 && encodeProgress(current)==encodeProgress(desired));
for(const auto& [path,bytes]:legacy)assert(fs.files.at(path)==bytes);
''', hardware=True)


if __name__ == '__main__':
    unittest.main()
