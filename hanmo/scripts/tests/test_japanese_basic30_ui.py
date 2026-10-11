"""All nine Topics30 categories, real Activity/core/v4 store/UI engine.
Historical filename retained; full paint acceptance requires parent generation.
"""
import unittest
from scripts.tests import test_japanese_dialogues_ui as ui

class JapaneseBasic30RuntimeTests(unittest.TestCase):
    setUpClass = classmethod(ui.JapaneseDialoguesRuntimeTests.setUpClass.__func__)
    run_cpp = ui.JapaneseDialoguesRuntimeTests.run_cpp

    def test_every_picker_denominator30_no_entry_writes(self):
        self.run_cpp(r'''int main(){
 const StrId keys[]={StrId::STR_JP_DIALOGUES_BASIC,StrId::STR_JP_DIALOGUES_DAILY,StrId::STR_JP_DIALOGUES_RESTAURANT,
 StrId::STR_JP_DIALOGUES_SHOPPING,StrId::STR_JP_DIALOGUES_TRANSPORT,StrId::STR_JP_DIALOGUES_HOTEL,
 StrId::STR_JP_DIALOGUES_DIRECTIONS,StrId::STR_JP_DIALOGUES_SOCIAL,StrId::STR_JP_DIALOGUES_EMERGENCY};
 for(int language=0;language<3;++language){Storage=FakeFS{};I18N.language=language;
 GfxRenderer r;MappedInputManager i;JapaneseSentencesActivity a(r,i);a.onEnter();
 for(int c=0;c<9;++c){paint(a);
 const std::string expected=std::string("> ")+I18N.get(keys[c])+"  0 / 30";
 assert(has(r,expected.c_str()));
 assert(Storage.writes==0 && Storage.renames==0);
 release(a,i,B::Down);}
 a.onExit();}
}''', require_current_content=False)

    def test_basic_header_and_committed_read_denominator30(self):
        self.run_cpp(r'''int main(){
 GfxRenderer r;MappedInputManager i;JapaneseSentencesActivity a(r,i);a.onEnter();a.action(10);paint(a);
 assert(has(r,"1 / 30"));
 const auto label=std::string(I18N.get(StrId::STR_JP_SENTENCES_PROGRESS))+" 0 / 30";
 assert(has(r,label.c_str()));
 assert(!a.lesson_.revealed());
}''', require_current_content=False)

    def test_real_v2_all54_and_mixed_maps_every_category_read_counts_readonly(self):
        self.run_cpp(r"""
int main(){using namespace japanese::sentenceprogress;
 const StrId keys[]={StrId::STR_JP_DIALOGUES_BASIC,StrId::STR_JP_DIALOGUES_DAILY,StrId::STR_JP_DIALOGUES_RESTAURANT,
 StrId::STR_JP_DIALOGUES_SHOPPING,StrId::STR_JP_DIALOGUES_TRANSPORT,StrId::STR_JP_DIALOGUES_HOTEL,
 StrId::STR_JP_DIALOGUES_DIRECTIONS,StrId::STR_JP_DIALOGUES_SOCIAL,StrId::STR_JP_DIALOGUES_EMERGENCY};
 for(int mode=0;mode<2;++mode)for(bool backup:{false,true}){
 Storage=FakeFS{};auto old=basic30fixture::v2Bytes(mode);
 Storage.files[backup?basic30fixture::v2bak:basic30fixture::v2]=old;
 Storage.files[basic30fixture::v2part]={3,1,4};
 japanese::review::Progress word;
 for(int n=0;n<45;++n)assert(japanese::review::applyRating(word,japanese::Words::cardIdAt(n),japanese::review::Rating::Known,japanese::review::kMinDay));
 const auto w=japanese::review::encodeProgress(word);
 Storage.files[japanese::review::kProgressPath]={w.begin(),w.end()};
 Storage.files[japanese::review::kProgressBackup]={8,5,2};
 Storage.files[japanese::review::kProgressPart]={9,7,6};Storage.files["/canary.bin"]={7,3,9};
 const auto originals=Storage.files;
 GfxRenderer r;MappedInputManager i;JapaneseSentencesActivity a(r,i);a.onEnter();
 assert(a.picker_ && a.selectedCategory_==8 && a.pending_.revision==91);
 assert(Storage.writes==0 && Storage.renames==0 && Storage.files==originals);
 for(int c=0;c<9;++c){assert(a.pending_.positions[c]==c%6);
  for(int j=0;j<30;++j)assert(isRead(a.progress_,c*30+j)==(j<6 && (mode==0 || (c*6+j)%3==1)));
  assert(readCount(a.progress_,c)==(mode==0?6:2));
  a.selectedCategory_=c;paint(a);
  const auto label=std::string("> ")+I18N.get(keys[c])+(mode==0?"  6 / 30":"  2 / 30");
  assert(has(r,label.c_str()));
 }
 // First newly authored item per category starts unread, not a shifted old bit.
 for(int c=0;c<9;++c){a.action(10+c);assert(a.lesson_.position()==c%6 && !a.lesson_.revealed());
  while(a.lesson_.position()<6)release(a,i,B::Right);
  release(a,i,B::Confirm);assert(a.lesson_.revealed() && isRead(a.progress_,c*30+6));
  release(a,i,B::Back);
 }
 for(const auto& oldFile:originals)assert(Storage.files.at(oldFile.first)==oldFile.second);
 assert(Storage.files.at(kProgressPath).size()==648);
 a.onExit();const int writes=Storage.writes;a.onEnter();assert(Storage.writes==writes && a.picker_);
 for(int c=0;c<9;++c){a.action(10+c);assert(a.lesson_.position()==6 && !a.lesson_.revealed());a.action(0);}
 a.onExit();
 }
}
""", require_current_content=False)

    def test_all_category_endpoints29_physical_resume_and_bitmap_beyond255(self):
        self.run_cpp(r"""
int main(){using namespace japanese::sentenceprogress;
 GfxRenderer r;MappedInputManager i;JapaneseSentencesActivity a(r,i);a.onEnter();
 for(int c=0;c<9;++c){a.action(10+c);assert(a.lesson_.count()==30 && a.lesson_.globalPosition()==c*30);
  for(int n=0;n<30;++n){assert(a.lesson_.position()==n && a.lesson_.globalPosition()==c*30+n);
   release(a,i,B::Confirm);assert(a.lesson_.revealed() && isRead(a.progress_,c*30+n));
   const int writes=Storage.writes,updates=a.updates;const auto before=encodeProgress(a.progress_);
   release(a,i,B::Right);
   if(n==29){assert(a.lesson_.position()==29 && a.lesson_.revealed() && Storage.writes==writes && a.updates==updates && encodeProgress(a.progress_)==before);}
   else assert(a.lesson_.position()==n+1 && !a.lesson_.revealed());
  }
  assert(readCount(a.progress_,c)==30);release(a,i,B::Back);assert(a.picker_ && a.finishes==0);
 }
 assert(isRead(a.progress_,255) && isRead(a.progress_,256) && isRead(a.progress_,269));
 assert(!isRead(a.progress_,270) && !isRead(a.progress_,271) && (a.progress_.readBits[33]&0xc0)==0);
 a.onExit();const int writes=Storage.writes;a.onEnter();assert(a.picker_ && a.selectedCategory_==8 && Storage.writes==writes);
 for(int c=0;c<9;++c){a.action(10+c);assert(a.lesson_.position()==29 && !a.lesson_.revealed());
  for(int n=29;n>0;--n){release(a,i,B::Left);assert(a.lesson_.position()==n-1 && !a.lesson_.revealed());}
  const int w=Storage.writes,u=a.updates;release(a,i,B::Left);assert(a.lesson_.position()==0 && Storage.writes==w && a.updates==u);
  a.action(0);
 }
 a.action(0);assert(a.finishes==1 && !a.routingReady());
}
""", require_current_content=False)

    def test_every_category29_actual_controls_touch_stale_next_and_resume_hidden(self):
        self.run_cpp(r"""
int main(){using namespace japanese::sentenceprogress;
 for(int c=0;c<9;++c){Storage=FakeFS{};GfxRenderer r;MappedInputManager i;JapaneseSentencesActivity a(r,i);a.onEnter();a.action(10+c);
  for(int n=0;n<28;++n){release(a,i,B::Right);}paint(a);assert(has(r,"29 / 30"));
  auto next=find(r,I18N.get(StrId::STR_KANA_NEXT));
  touch(a,i,next.x+next.width/2,next.y+next.height/2);
  assert(a.lesson_.position()==29 && !a.lesson_.revealed() && !a.routingReady());
  const int writes=Storage.writes,updates=a.updates;
  touch(a,i,next.x+next.width/2,next.y+next.height/2);
  assert(a.lesson_.position()==29 && Storage.writes==writes && a.updates==updates); // stale table before republish
  paint(a);assert(has(r,"30 / 30") && !a.lesson_.canNext());
  next=find(r,I18N.get(StrId::STR_KANA_NEXT));assert(next.color==int(fui::Color::LightGray));
  touch(a,i,next.x+next.width/2,next.y+next.height/2);assert(a.lesson_.position()==29 && Storage.writes==writes);
  release(a,i,B::Confirm);assert(a.lesson_.revealed() && isRead(a.progress_,c*30+29));paint(a);
  assert(has(r,"30 / 30"));next=find(r,I18N.get(StrId::STR_KANA_NEXT));assert(next.color==int(fui::Color::LightGray));
  const auto bytes=encodeProgress(a.progress_);const int w=Storage.writes,u=a.updates;
  release(a,i,B::Right);assert(a.lesson_.position()==29 && a.lesson_.revealed() && a.updates==u);
  touch(a,i,next.x+next.width/2,next.y+next.height/2);assert(Storage.writes==w && encodeProgress(a.progress_)==bytes);
  tap(a,i,r,StrId::STR_BACK);assert(a.picker_ && a.finishes==0);a.action(10+c);
  assert(a.lesson_.position()==29 && !a.lesson_.revealed());paint(a);assert(has(r,"30 / 30"));a.onExit();
 }
}
""")

    def test_high_id269_failed_reveal_pending_explicit_retry_once_and_legacy_bytes(self):
        self.run_cpp(r"""
int main(){using namespace japanese::sentenceprogress;
 Storage.files[basic30fixture::v2]=basic30fixture::v2Bytes(1);Storage.files[basic30fixture::v2bak]={5,8};Storage.files[basic30fixture::v2part]={4,1};
 japanese::review::Progress words;for(int n=0;n<45;++n)assert(japanese::review::applyRating(words,japanese::Words::cardIdAt(n),japanese::review::Rating::Known,japanese::review::kMinDay));
 const auto w=japanese::review::encodeProgress(words);Storage.files[japanese::review::kProgressPath]={w.begin(),w.end()};
 Storage.files[japanese::review::kProgressBackup]={7,2};Storage.files[japanese::review::kProgressPart]={6,3};Storage.files["/canary.bin"]={2,9};
 const auto legacy=Storage.files;Progress seed;assert(record(seed,8,29,false));const auto b=encodeProgress(seed);Storage.files[kProgressPath]={b.begin(),b.end()};
 GfxRenderer r;MappedInputManager i;JapaneseSentencesActivity a(r,i);a.onEnter();a.action(18);assert(a.lesson_.globalPosition()==269);
 Storage.shortWrite=true;release(a,i,B::Confirm);assert(a.retryNeeded() && a.lesson_.revealed() && isRead(a.pending_,269) && !isRead(a.progress_,269));
 const int writes=Storage.writes;release(a,i,B::Confirm);release(a,i,B::Confirm);release(a,i,B::Right);release(a,i,B::Back);
 paint(a);const auto committed=std::string("> ")+I18N.get(StrId::STR_JP_DIALOGUES_EMERGENCY)+"  0 / 30";
 assert(has(r,committed.c_str()) && has(r,I18N.get(StrId::STR_JP_REVIEW_RETRY)));
 a.action(17);release(a,i,B::Confirm);assert(a.lesson_.category()==7 && a.lesson_.revealed());
 assert(Storage.writes==writes && isRead(a.pending_,210) && isRead(a.pending_,269));
 Storage.shortWrite=false;release(a,i,B::Up);assert(!a.retryNeeded() && Storage.writes==writes+1);
 assert(isRead(a.progress_,210) && isRead(a.progress_,269) && readCount(a.progress_,8)==1);
 assert(a.progress_.positions[8]==29 && a.progress_.positions[7]==0 && a.progress_.lastCategory==7);
 release(a,i,B::Up);assert(Storage.writes==writes+1);
 for(const auto& f:legacy)assert(Storage.files.at(f.first)==f.second);
 a.onExit();a.onEnter();assert(a.picker_ && a.selectedCategory_==7);a.action(18);
 assert(a.lesson_.position()==29 && !a.lesson_.revealed() && isRead(a.progress_,269));
}
""", require_current_content=False)

    def test_real_v4_crc_future_table_high_id_reserved_fail_closed_no_legacy_fallback(self):
        self.run_cpp(r"""
int main(){using namespace japanese::sentenceprogress;
 static_assert(kProgressBytes==648 && kReadBytes==34 && kCardCount==270);
 for(int fault=0;fault<7;++fault){Storage=FakeFS{};Progress old;assert(record(old,8,29,true));auto bytes=encodeProgress(old);
  if(fault==0)bytes[646]^=1;
  if(fault==1)bytes[4]=5;
  if(fault==2)bytes[7]=1;
  if(fault==3)bytes[104+2*269]^=1;
  if(fault==4)bytes[86+2*8]=239;
  if(fault==5)bytes[67]|=0x40;
  if(fault==6)bytes[33]=30;
  if(fault!=0)basic30fixture::put(bytes.data()+644,basic30fixture::crc(bytes.data(),644),4);
  Storage.files[kProgressPath]={bytes.begin(),bytes.end()};Storage.files[basic30fixture::v2]=basic30fixture::v2Bytes();
  japanese::review::Progress words;assert(japanese::review::recordSentence(words,5,true));auto w=japanese::review::encodeProgress(words);
  Storage.files[japanese::review::kProgressPath]={w.begin(),w.end()};Storage.files["/canary.bin"]={4,8};const auto before=Storage.files;
  GfxRenderer r;MappedInputManager i;JapaneseSentencesActivity a(r,i);a.onEnter();paint(a);
  assert(a.picker_ && a.retryNeeded() && has(r,I18N.get(StrId::STR_JP_REVIEW_CORRUPT)) && Storage.writes==0);
  a.action(18);for(int n=0;n<29;++n)release(a,i,B::Right);release(a,i,B::Confirm);
  assert(a.lesson_.globalPosition()==269 && a.lesson_.revealed() && isRead(a.pending_,269));release(a,i,B::Up);
  assert(a.retryNeeded() && Storage.writes==0 && Storage.renames==0 && Storage.files==before);
  a.onExit();assert(Storage.files==before);
 }
}
""", require_current_content=False)

    def test_real_v2_invalid_live_blocks_backup_v1_and_preserves_old_files(self):
        self.run_cpp(r"""
int main(){using namespace japanese::sentenceprogress;
 for(int fault=0;fault<6;++fault){Storage=FakeFS{};auto old=basic30fixture::v2Bytes();
  if(fault==0)old[102]^=1;
  if(fault==1)old[4]=3;
  if(fault==2)old[21]=6;
  if(fault==3)old[37]=1;
  if(fault==4)old[46+53]=0;
  if(fault==5)old[36]|=0x80;
  if(fault)basic30fixture::put(old.data()+100,basic30fixture::crc(old.data(),100),4);
  Storage.files[basic30fixture::v2]=old;Storage.files[basic30fixture::v2bak]=basic30fixture::v2Bytes(1);
  Storage.files[basic30fixture::v2part]={9,7,2};japanese::review::Progress words;
  assert(japanese::review::recordSentence(words,5,true));const auto w=japanese::review::encodeProgress(words);
  Storage.files[japanese::review::kProgressPath]={w.begin(),w.end()};Storage.files["/canary.bin"]={4,8};const auto before=Storage.files;
  GfxRenderer r;MappedInputManager i;JapaneseSentencesActivity a(r,i);a.onEnter();paint(a);
  assert(a.picker_ && a.retryNeeded() && a.progress_.revision==0 && has(r,I18N.get(StrId::STR_JP_REVIEW_CORRUPT)));
  for(int c=0;c<9;++c)assert(readCount(a.progress_,c)==0);
  a.action(18);for(int n=0;n<29;++n)release(a,i,B::Right);release(a,i,B::Confirm);release(a,i,B::Up);
  assert(a.lesson_.globalPosition()==269 && isRead(a.pending_,269) && a.retryNeeded());
  a.onExit();assert(Storage.writes==0 && Storage.renames==0 && Storage.files==before);
 }
}
""", require_current_content=False)

if __name__=='__main__':unittest.main()
