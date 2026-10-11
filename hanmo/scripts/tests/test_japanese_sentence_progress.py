"""Actual Activity + real FUI/core; deterministic SD transaction seam only.
The parent separately exercises the real store and simulator synthetic SD.
"""
import unittest
from scripts.tests import test_japanese_sentences_ui as ui

class JapaneseSentenceProgressTests(unittest.TestCase):
    build_root = ui.ROOT / 'build/japanese-sentence-progress/progress'
    run_cpp = ui.JapaneseSentencesRuntimeTests.run_cpp

    def test_load_restores_every_last_position_hidden_without_writes(self):
        self.run_cpp(r'''
int main() {
  using namespace japanese::review;
  for (int position=0;position<6;++position) {
    resetStore(); loadStatus=LoadStatus::Loaded;
    stored.revision=12; stored.sentencePosition=position; stored.sentenceReadMask=63;
    GfxRenderer r; MappedInputManager input; JapaneseSentencesActivity a(r,input);
    a.onEnter(); paint(a);
    assert(a.lesson_.position()==position && !a.lesson_.revealed());
    const auto& c=japanese::sentences::cards[position];
    assert(has(r,c.japanese) && !has(r,c.romaji) && !has(r,c.meaning));
    input.clear(); for (int i=0;i<10;++i) { a.loop(); paint(a); }
    a.onExit(); assert(loads==1 && saves==0 && stored.revision==12);
  }
}
''')

    def test_each_changed_sentence_transaction_merges_latest_words_and_read_bits(self):
        self.run_cpp(r'''
int main() {
  using namespace japanese::review;
  resetStore(); GfxRenderer r; MappedInputManager input; JapaneseSentencesActivity a(r,input);
  a.onEnter(); paint(a); assert(saves==0);
  a.action(1); assert(saves==0); // endpoint
  stored.words[0]={kMinDay+7,kMinDay,1,7,3};
  stored.words.back()={kMinDay+3,kMinDay,1,3,2};
  stored.latestDay=kMinDay; stored.revision=1; loadStatus=LoadStatus::Loaded;
  const auto wordSnapshot=stored;
  for (int i=0;i<6;++i) {
    a.action(2); assert(a.lesson_.revealed());
    assert(stored.sentencePosition==i);
    assert(stored.sentenceReadMask==((1<<(i+1))-1));
    const int before=saves;
    a.action(2); a.action(2); paint(a); input.clear(); a.loop();
    assert(saves==before); // hiding, repeated reveal, paints and idle never duplicate writes
    assert(stored.latestDay==wordSnapshot.latestDay);
    for (size_t j=0;j<stored.words.size();++j) {
      const auto& x=stored.words[j]; const auto& y=wordSnapshot.words[j];
      assert(x.dueDay==y.dueDay && x.lastRatedDay==y.lastRatedDay && x.reviews==y.reviews &&
             x.intervalDays==y.intervalDays && x.rating==y.rating);
    }
    a.action(3);
    if (i<5) assert(stored.sentencePosition==i+1 && !a.lesson_.revealed() && saves==before+1);
    else assert(saves==before); // next endpoint
  }
  assert(saves==11 && stored.revision==12 && stored.sentenceReadMask==63);
  a.onExit(); assert(saves==11);
  a.onEnter(); assert(a.lesson_.position()==5 && !a.lesson_.revealed());
  a.action(2); assert(saves==11);
}
''')

    def test_footer_reports_committed_read_count_saved_and_readable_load_errors(self):
        self.run_cpp(r'''
int main() {
  using namespace japanese::review;
  for (int language : {0,1,2}) for (auto status : {LoadStatus::Empty,LoadStatus::Loaded,
                                                 LoadStatus::Corrupt,LoadStatus::StorageError}) {
    resetStore(); I18N.language=language; loadStatus=status;
    if (status==LoadStatus::Loaded) { stored.sentenceReadMask=21; stored.revision=3; }
    GfxRenderer r; MappedInputManager input; JapaneseSentencesActivity a(r,input);
    a.onEnter(); paint(a);
    char label[96]; std::snprintf(label,sizeof(label),"%s %d / 6",I18N.get(StrId::STR_JP_SENTENCES_PROGRESS),
                                 status==LoadStatus::Loaded?3:0);
    assert(has(r,label));
    const bool failed=status==LoadStatus::Corrupt || status==LoadStatus::StorageError;
    const auto key=status==LoadStatus::Corrupt?StrId::STR_JP_REVIEW_CORRUPT:
                   status==LoadStatus::StorageError?StrId::STR_JP_REVIEW_STORAGE_ERROR:
                   status==LoadStatus::Loaded?StrId::STR_JP_REVIEW_SAVED:StrId::STR_JP_SENTENCES_SESSION;
    assert(has(r,I18N.get(key)) && has(r,I18N.get(StrId::STR_JP_REVIEW_RETRY))==failed);
    assert(r.boxes.size()==(failed?5:4) && saves==0);
    const auto& count=find(r,label); const auto& message=find(r,I18N.get(key));
    assert(count.y+count.height+4<=message.y);
    for (const auto& b:r.boxes) assert(message.y+message.height+12<=b.rect.y);
    release(a,input,MappedInputManager::Button::Back); assert(a.finishes==1 && saves==0);
  }
  resetStore(); GfxRenderer r; MappedInputManager input; JapaneseSentencesActivity a(r,input);
  a.onEnter(); a.action(2); paint(a);
  assert(has(r,I18N.get(StrId::STR_JP_REVIEW_SAVED)) && saves==1);
  char label[96]; std::snprintf(label,sizeof(label),"%s 1 / 6",I18N.get(StrId::STR_JP_SENTENCES_PROGRESS));
  assert(has(r,label));
}
''')

    def test_failed_write_keeps_reading_pending_until_explicit_retry_merges_new_commits(self):
        self.run_cpp(r'''
int main() {
  using namespace japanese::review;
  resetStore(); GfxRenderer r; MappedInputManager input; JapaneseSentencesActivity a(r,input);
  a.onEnter(); saveFails=true; a.action(2); paint(a);
  assert(a.lesson_.position()==0 && a.lesson_.revealed() && saves==1 && stored.revision==0);
  assert(has(r,I18N.get(StrId::STR_JP_REVIEW_SAVE_ERROR)) && !has(r,I18N.get(StrId::STR_JP_REVIEW_SAVED)));
  for (int i=0;i<10;++i) { input.clear(); a.loop(); paint(a); }
  a.action(2); a.action(2); a.action(3); a.action(2); a.action(2);
  assert(a.lesson_.position()==1 && !a.lesson_.revealed() && saves==1);
  stored.words[0]={kMinDay+7,kMinDay,1,7,3}; stored.latestDay=kMinDay;
  stored.sentencePosition=4; stored.sentenceReadMask=16; stored.revision=8;
  loadStatus=LoadStatus::Loaded; saveFails=false;
  tapLabel(a,input,r,StrId::STR_JP_REVIEW_RETRY); paint(a);
  assert(saves==3 && stored.revision==10 && stored.sentencePosition==1 && stored.sentenceReadMask==19);
  assert(stored.words[0].reviews==1 && stored.words[0].dueDay==kMinDay+7 && stored.latestDay==kMinDay);
  assert(a.lesson_.position()==1 && !a.lesson_.revealed());
  assert(has(r,I18N.get(StrId::STR_JP_REVIEW_SAVED)) && !has(r,I18N.get(StrId::STR_JP_REVIEW_RETRY)));
  a.action(4); paint(a); assert(saves==3); // stale Retry action is inert
}
''')

    def test_retry_after_load_error_restores_without_creating_or_writing_progress(self):
        self.run_cpp(r'''
int main() {
  using namespace japanese::review;
  resetStore(); loadStatus=LoadStatus::StorageError;
  GfxRenderer r; MappedInputManager input; JapaneseSentencesActivity a(r,input);
  a.onEnter(); paint(a); assert(loads==1 && saves==0);
  stored.sentencePosition=4; stored.sentenceReadMask=7; stored.revision=11;
  loadStatus=LoadStatus::Loaded;
  tapLabel(a,input,r,StrId::STR_JP_REVIEW_RETRY); paint(a);
  assert(a.lesson_.position()==4 && !a.lesson_.revealed() && loads==2 && saves==0);
  assert(has(r,I18N.get(StrId::STR_JP_REVIEW_SAVED)) && !has(r,I18N.get(StrId::STR_JP_REVIEW_RETRY)));
  a.onExit(); resetStore(); loadStatus=LoadStatus::StorageError; a.onEnter();
  loadStatus=LoadStatus::Empty;
  tapLabel(a,input,r,StrId::STR_JP_REVIEW_RETRY); paint(a);
  assert(a.lesson_.position()==0 && !a.lesson_.revealed() && saves==0);
  assert(has(r,I18N.get(StrId::STR_JP_SENTENCES_SESSION)) && !has(r,I18N.get(StrId::STR_JP_REVIEW_SAVED)));
}
''')

    def test_missing_or_older_committed_progress_never_resets_review_words(self):
        self.run_cpp(r'''
int main() {
  using namespace japanese::review;
  for (bool missing : {false,true}) {
    resetStore(); loadStatus=LoadStatus::Loaded; stored.revision=12;
    stored.sentenceReadMask=4; stored.words[0]={kMinDay+7,kMinDay,1,7,3}; stored.latestDay=kMinDay;
    GfxRenderer r; MappedInputManager input; JapaneseSentencesActivity a(r,input); a.onEnter();
    if (missing) { loadStatus=LoadStatus::Empty; stored={}; }
    else { stored.revision=11; stored.words[0]={}; stored.latestDay=0; }
    a.action(2); paint(a);
    assert(a.lesson_.revealed() && saves==0);
    assert(has(r,I18N.get(StrId::STR_JP_REVIEW_SAVE_ERROR)) && !has(r,I18N.get(StrId::STR_JP_REVIEW_SAVED)));
    tapLabel(a,input,r,StrId::STR_JP_REVIEW_RETRY); assert(saves==0);
    release(a,input,MappedInputManager::Button::Back); assert(a.finishes==1);
  }
}
''')

    def test_real_store_retry_flushes_all_six_offline_reads_without_bulk_revision(self):
        self.run_cpp(r'''
int main() {
  using namespace japanese::review;
  sentenceStorage.available=false;
  GfxRenderer r; MappedInputManager input; JapaneseSentencesActivity a(r,input);
  a.onEnter(); paint(a);
  for (int i=0;i<6;++i) {
    a.action(2); paint(a);
    assert(a.lesson_.position()==i && a.lesson_.revealed());
    const auto& c=japanese::sentences::cards[i];
    assert(has(r,c.romaji) && has(r,c.meaning));
    assert(has(r,I18N.get(StrId::STR_JP_REVIEW_STORAGE_ERROR)));
    a.action(3);
  }
  assert(sentenceStorage.writes==0);
  sentenceStorage.available=true;
  Progress p; assert(applyRating(p,45,Rating::Known,kMinDay));
  const auto initial=encodeProgress(p);
  sentenceStorage.files[kProgressPath]={initial.begin(),initial.end()};
  tapLabel(a,input,r,StrId::STR_JP_REVIEW_RETRY); paint(a);
  Progress restored; assert(loadProgress(Storage,restored)==LoadStatus::Loaded);
  assert(restored.sentenceReadMask==63 && restored.sentencePosition==5);
  assert(restored.revision==7 && sentenceStorage.writes==6 && sentenceStorage.handles==0);
  assert(restored.words.back().reviews==1 && restored.words.back().dueDay==kMinDay+7);
  assert(restored.latestDay==kMinDay && has(r,I18N.get(StrId::STR_JP_REVIEW_SAVED)));
  a.onExit(); a.onEnter(); assert(a.lesson_.position()==5 && !a.lesson_.revealed());
  a.action(2); assert(sentenceStorage.writes==6);
}
''', real_store=True)

    def test_retry_footer_and_actual_font_metrics_have_separated_real_paint_geometry(self):
        self.run_cpp(r'''
int main() {
  using namespace japanese::review;
  int geometryCases=0;
  for (int language : {0,1,2}) for (int height : {800,900}) for (int uiLine : {24,30,36})
  for (int state=0;state<4;++state) for (int position=0;position<6;++position) for (bool revealed : {false,true}) {
    resetStore(); I18N.language=language;
    loadStatus=state==1?LoadStatus::StorageError:state==2?LoadStatus::Corrupt:LoadStatus::Empty;
    GfxRenderer r; r.height=height; r.smallHeight=uiLine;
    MappedInputManager input; JapaneseSentencesActivity a(r,input); a.onEnter();
    if (state==3) { saveFails=true; a.action(2); if (!revealed) a.action(2); }
    for (int i=0;i<position;++i) a.action(3);
    if (a.lesson_.revealed()!=revealed) a.action(2);
    paint(a);
    char count[96]; int reads=0;
    for (int i=0;i<6;++i) if (a.progress_.sentenceReadMask&(1<<i)) ++reads;
    std::snprintf(count,sizeof(count),"%s %d / 6",I18N.get(StrId::STR_JP_SENTENCES_PROGRESS),reads);
    const auto& footer=find(r,count);
    const auto key=state==1?StrId::STR_JP_REVIEW_STORAGE_ERROR:state==2?StrId::STR_JP_REVIEW_CORRUPT:
                   state==3?StrId::STR_JP_REVIEW_SAVE_ERROR:reads || position?StrId::STR_JP_REVIEW_SAVED:StrId::STR_JP_SENTENCES_SESSION;
    const auto& status=find(r,I18N.get(key));
    assert(footer.y+footer.height+4<=status.y);
    assert(r.boxes.size()==(state?5:4) && !a.app.interactionOverflowed());
    for (size_t n=0;n<r.boxes.size();++n) {
      const auto b=r.boxes[n].rect;
      assert(status.y+status.height+12<=b.y && b.width>=44 && b.height>=44);
      assert(b.x>=12 && b.right()<=r.width-12 && b.bottom()<=r.height-12);
      for (size_t m=n+1;m<r.boxes.size();++m) {
        const auto c=r.boxes[m].rect;
        assert(b.right()+6<=c.x || c.right()+6<=b.x || b.bottom()+6<=c.y || c.bottom()+6<=b.y);
      }
    }
    const auto& c=japanese::sentences::cards[position];
    assert(find(r,c.japanese).font==0x4A53001C && find(r,c.japanese).height==84);
    if (revealed) {
      const auto& last=find(r,c.grammarNotes[1]);
      assert(last.font==0x4A53100C && last.height==36 && last.y+last.height+12<=footer.y);
    }
    for (const auto& d:r.draws) assert(d.x>=12 && d.x+d.width<=r.width-12 && d.y+d.height<=r.height-12);
    if (height==800 && uiLine==36) {
      std::printf("FRAME|%d|%d|%d|%d|%d|%d\n",language,height,uiLine,state,position,revealed);
      for (const auto& d:r.draws) std::printf("DRAW|%d|%d|%d|%d|%d|%d|%s\n",d.font,d.x,d.y,d.width,d.height,d.color,d.text.c_str());
      for (const auto& b:r.boxes) std::printf("BOX|%d|%d|%d|%d\n",b.rect.x,b.rect.y,b.rect.width,b.rect.height);
    }
    ++geometryCases;
  }
  std::printf("GEOMETRY_CASES|%d\n",geometryCases);
}
''')

    def test_real_store_corrupt_and_future_schema_failclosed_without_touching_backup(self):
        self.run_cpp(r'''
int main() {
  using namespace japanese::review;
  for (bool future : {false,true}) {
    sentenceStorage=FakeFS{};
    Progress p; assert(applyRating(p,0,Rating::Known,kMinDay)); assert(recordSentence(p,4,true));
    auto bytes=encodeProgress(p), bad=bytes;
    if (future) {
      bad[4]=2; detail::put(bad.data()+kProgressBytes-4,detail::checksum(bad.data(),kProgressBytes-4),4);
    } else bad[30]^=1;
    sentenceStorage.files[kProgressPath]={bad.begin(),bad.end()};
    sentenceStorage.files[kProgressBackup]={bytes.begin(),bytes.end()};
    const auto files=sentenceStorage.files;
    GfxRenderer r; MappedInputManager input; JapaneseSentencesActivity a(r,input);
    a.onEnter(); paint(a); assert(a.lesson_.position()==0 && !a.lesson_.revealed());
    assert(has(r,I18N.get(StrId::STR_JP_REVIEW_CORRUPT)));
    a.action(2); a.action(3); a.action(2); paint(a);
    for (int i=0;i<2;++i) tapLabel(a,input,r,StrId::STR_JP_REVIEW_RETRY);
    assert(sentenceStorage.writes==0 && sentenceStorage.renames==0 && sentenceStorage.files==files);
    release(a,input,MappedInputManager::Button::Back); assert(a.finishes==1);
  }
}
''', real_store=True)

    def test_real_store_uncertain_committed_save_is_recognized_on_retry_without_duplicate_write(self):
        self.run_cpp(r'''
int main() {
  using namespace japanese::review;
  sentenceStorage.afterRead=[](FakeFS& fs,const std::string& path) {
    if (path==kProgressPart) fs.failReadPath=kProgressPath;
  };
  GfxRenderer r; MappedInputManager input; JapaneseSentencesActivity a(r,input); a.onEnter();
  a.action(2); paint(a);
  assert(a.lesson_.revealed() && sentenceStorage.writes==1 && sentenceStorage.exists(kProgressPath));
  assert(has(r,I18N.get(StrId::STR_JP_REVIEW_SAVE_ERROR)) && !has(r,I18N.get(StrId::STR_JP_REVIEW_SAVED)));
  sentenceStorage.afterRead={}; sentenceStorage.failReadPath="";
  tapLabel(a,input,r,StrId::STR_JP_REVIEW_RETRY); paint(a);
  Progress p; assert(loadProgress(Storage,p)==LoadStatus::Loaded);
  assert(p.revision==1 && p.sentenceReadMask==1 && p.sentencePosition==0 && sentenceStorage.writes==1);
  assert(has(r,I18N.get(StrId::STR_JP_REVIEW_SAVED)) && a.lesson_.revealed());
  a.action(2); a.action(2); assert(sentenceStorage.writes==1);
}
''', real_store=True)

    def test_real_store_staging_conflict_preserves_concurrent_word_ratings_then_retry_merges(self):
        self.run_cpp(r'''
int main() {
  using namespace japanese::review;
  Progress original; assert(applyRating(original,0,Rating::Known,kMinDay));
  auto bytes=encodeProgress(original); sentenceStorage.files[kProgressPath]={bytes.begin(),bytes.end()};
  auto concurrent=original; assert(applyRating(concurrent,45,Rating::Familiar,kMinDay));
  const auto external=encodeProgress(concurrent);
  sentenceStorage.afterRead=[&](FakeFS& fs,const std::string& path) {
    if (path==kProgressPart) fs.files[kProgressPath]={external.begin(),external.end()};
  };
  GfxRenderer r; MappedInputManager input; JapaneseSentencesActivity a(r,input); a.onEnter();
  a.action(2); paint(a);
  assert(a.lesson_.revealed() && sentenceStorage.writes==1 && sentenceStorage.renames==0);
  assert(sentenceStorage.files[kProgressPath]==std::vector<uint8_t>(external.begin(),external.end()));
  for (int i=0;i<10;++i) { input.clear(); a.loop(); paint(a); }
  assert(sentenceStorage.writes==1 && has(r,I18N.get(StrId::STR_JP_REVIEW_SAVE_ERROR)));
  sentenceStorage.afterRead={}; tapLabel(a,input,r,StrId::STR_JP_REVIEW_RETRY);
  Progress p; assert(loadProgress(Storage,p)==LoadStatus::Loaded);
  assert(p.revision==3 && p.sentenceReadMask==1 && sentenceStorage.writes==2);
  assert(p.words[0].reviews==1 && p.words[0].dueDay==kMinDay+7);
  assert(p.words.back().reviews==1 && p.words.back().dueDay==kMinDay+3 && p.latestDay==kMinDay);
}
''', real_store=True)

    def test_real_store_partial_retry_preserves_unsaved_bits_and_hidden_navigation_is_not_read(self):
        self.run_cpp(r'''
int main() {
  using namespace japanese::review;
  sentenceStorage.available=false;
  GfxRenderer r; MappedInputManager input; JapaneseSentencesActivity a(r,input); a.onEnter();
  for (int i=0;i<3;++i) { a.action(2); a.action(3); }
  assert(a.lesson_.position()==3 && !a.lesson_.revealed());
  sentenceStorage.available=true;
  sentenceStorage.afterRead=[](FakeFS& fs,const std::string& path) {
    if (path==kProgressPath) fs.failOpenPath=kProgressPart;
  };
  tapLabel(a,input,r,StrId::STR_JP_REVIEW_RETRY); paint(a);
  Progress partial; assert(loadProgress(Storage,partial)==LoadStatus::Loaded);
  assert(partial.revision==1 && partial.sentenceReadMask==1 && sentenceStorage.writes==1);
  assert(has(r,I18N.get(StrId::STR_JP_REVIEW_SAVE_ERROR)) && a.lesson_.position()==3 && !a.lesson_.revealed());
  sentenceStorage.afterRead={}; sentenceStorage.failOpenPath="";
  tapLabel(a,input,r,StrId::STR_JP_REVIEW_RETRY); paint(a);
  Progress p; assert(loadProgress(Storage,p)==LoadStatus::Loaded);
  assert(p.revision==4 && p.sentenceReadMask==7 && p.sentencePosition==3 && sentenceStorage.writes==4);
  assert(has(r,I18N.get(StrId::STR_JP_REVIEW_SAVED)) && !a.lesson_.revealed());
  a.onExit(); a.onEnter(); assert(a.lesson_.position()==3 && !a.lesson_.revealed());
}
''', real_store=True)

    def test_revision_overflow_reports_error_without_attempting_save(self):
        self.run_cpp(r'''
int main() {
  using namespace japanese::review;
  resetStore(); loadStatus=LoadStatus::Loaded; stored.revision=UINT32_MAX;
  GfxRenderer r; MappedInputManager input; JapaneseSentencesActivity a(r,input); a.onEnter();
  a.action(2); paint(a); assert(a.lesson_.revealed() && saves==0 && stored.sentenceReadMask==0);
  assert(has(r,I18N.get(StrId::STR_JP_REVIEW_SAVE_ERROR)));
  tapLabel(a,input,r,StrId::STR_JP_REVIEW_RETRY); assert(saves==0 && stored.revision==UINT32_MAX);
  release(a,input,MappedInputManager::Button::Back); assert(a.finishes==1);
}
''')

if __name__ == '__main__':
    unittest.main()
