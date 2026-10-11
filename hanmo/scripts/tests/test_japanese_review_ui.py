"""Actual Review Activity TU + unmodified UiAppHost + real FreeInkUI runtime.
Hardware/I18n/time/storage are narrow seams. Review core is the real header.
No shadow SDK geometry, screen builder or interaction implementation.
"""
from pathlib import Path
import json
import os
import shutil
import subprocess
import unittest
from scripts.tests.test_japanese_words_ui import STUBS as WORD_STUBS, PREFIX as WORD_PREFIX

ROOT = Path(__file__).resolve().parents[2]
INCLUDE = ROOT / "src/activities/apps/japanese"
FUI = ROOT / "freeink-sdk/libs/ui/FreeInkUI/include"
BUILD = ROOT / "build/japanese-review-ui"

STUBS = dict(WORD_STUBS)
STUBS["components/UiAppHelpers.h"] = STUBS["UiAppHelpers.h"]
STUBS["I18n.h"] = r'''
#pragma once
enum class StrId {
 STR_BACK, STR_JP_REVIEW, STR_JP_WORDS_PROMPT, STR_KANA_QUIZ_REVEAL,
 STR_JP_REVIEW_START, STR_JP_REVIEW_NEW, STR_JP_REVIEW_DUE, STR_JP_REVIEW_DONE,
 STR_JP_REVIEW_AGAIN, STR_JP_REVIEW_FAMILIAR, STR_JP_REVIEW_KNOWN, STR_JP_REVIEW_SAVED,
 STR_JP_REVIEW_SAVE_ERROR, STR_JP_REVIEW_STORAGE_ERROR, STR_JP_REVIEW_CORRUPT,
 STR_JP_REVIEW_CLOCK, STR_JP_REVIEW_RETRY, STR_JP_REVIEW_COMPLETE, STR_JP_REVIEW_RULES
};
struct I18n {
 static I18n& getInstance() { static I18n i; return i; }
 const char* get(StrId id) const {
  switch (id) {
   case StrId::STR_BACK: return "返回";
   case StrId::STR_JP_REVIEW: return "每日複習";
   case StrId::STR_JP_WORDS_PROMPT: return "回想這個單字的意思";
   case StrId::STR_KANA_QUIZ_REVEAL: return "看答案";
   case StrId::STR_JP_REVIEW_START: return "開始";
   case StrId::STR_JP_REVIEW_NEW: return "新卡";
   case StrId::STR_JP_REVIEW_DUE: return "到期";
   case StrId::STR_JP_REVIEW_DONE: return "今日完成";
   case StrId::STR_JP_REVIEW_AGAIN: return "再練";
   case StrId::STR_JP_REVIEW_FAMILIAR: return "熟悉";
   case StrId::STR_JP_REVIEW_KNOWN: return "會";
   case StrId::STR_JP_REVIEW_SAVED: return "已保存";
   case StrId::STR_JP_REVIEW_SAVE_ERROR: return "保存失敗";
   case StrId::STR_JP_REVIEW_STORAGE_ERROR: return "無法讀取 SD";
   case StrId::STR_JP_REVIEW_CORRUPT: return "進度損壞";
   case StrId::STR_JP_REVIEW_CLOCK: return "請確認日期";
   case StrId::STR_JP_REVIEW_RETRY: return "重試";
   case StrId::STR_JP_REVIEW_COMPLETE: return "今日已完成";
   case StrId::STR_JP_REVIEW_RULES: return "1 / 3 / 7 → 30 日";
  }
  return "";
 }
};
#define I18N I18n::getInstance()
#define tr(id) I18N.get(StrId::id)
'''
STUBS["util/TimeUtils.h"] = r'''
#pragma once
#include <cstdint>
#include <ctime>
namespace TimeUtils {
inline uint32_t epoch = 1791417600, day = 20734;
inline int reads = 0;
inline uint32_t getCurrentValidTimestamp() { ++reads; return epoch; }
inline uint32_t getLocalDayOrdinal(uint32_t seconds) { return seconds ? day : 0; }
inline bool getDateFromDayOrdinal(uint32_t ordinal, int& year, unsigned& month, unsigned& date) {
 const time_t seconds = static_cast<time_t>(ordinal) * 86400;
 std::tm result{}; gmtime_r(&seconds, &result);
 year = result.tm_year + 1900; month = result.tm_mon + 1; date = result.tm_mday; return true;
}
}
'''
STUBS["HalStorage.h"] = "#pragma once\nstruct FakeStorage {};\ninline FakeStorage Storage;\n"
STUBS["JapaneseReviewStore.h"] = r'''
#pragma once
#include <JapaneseReview.h>
#include <array>
namespace japanese::review {
enum class LoadStatus { Empty, Loaded, Corrupt, StorageError };
inline Progress disk{}, lastDesired{}, lastExpected{};
inline LoadStatus loadStatus = LoadStatus::Empty;
inline int writes = 0, loads = 0;
inline bool failWrite = false, commitThenFail = false;
// Only an exact snapshot token for the isolated store seam; NOT a disk codec.
inline auto encodeProgress(const Progress& p) {
 std::array<uint32_t, 6 + 6 * japanese::Words::kCount> bytes{};
 bytes[0]=p.revision; bytes[1]=p.latestDay; bytes[2]=p.sentencePosition; bytes[3]=p.sentenceReadMask;
 for (int i=0; i<japanese::Words::kCount; ++i) {
  const auto& w=p.words[i]; const int base=6+6*i;
  bytes[base]=w.dueDay; bytes[base+1]=w.lastRatedDay; bytes[base+2]=w.reviews;
  bytes[base+3]=w.intervalDays; bytes[base+4]=w.rating;
 }
 return bytes;
}
template<typename FS> LoadStatus loadProgress(FS&, Progress& p) {
 ++loads;
 if (loadStatus==LoadStatus::Empty) p=Progress{};
 if (loadStatus==LoadStatus::Loaded) p=disk;
 return loadStatus;
}
template<typename FS> bool saveProgress(FS&, const Progress& desired, const Progress* expected=nullptr) {
 ++writes; lastDesired=desired; if (expected) lastExpected=*expected;
 if (loadStatus==LoadStatus::Corrupt || loadStatus==LoadStatus::StorageError || !expected) return false;
 const auto base=loadStatus==LoadStatus::Empty ? Progress{} : disk;
 if (encodeProgress(base)!=encodeProgress(*expected)) return false;
 if (failWrite) return false;
 disk=desired; loadStatus=LoadStatus::Loaded;
 return !commitThenFail;
}
}
'''
PREFIX = WORD_PREFIX.replace("JapaneseWordsActivity", "JapaneseReviewActivity")
PREFIX = PREFIX.replace('#include "KanaData.generated.h"', '#include "KanaData.generated.h"\n#include "JapaneseReviewStore.h"\n#include "util/TimeUtils.h"')
PREFIX += r'''
namespace jr = japanese::review;
using B = MappedInputManager::Button;
void start(JapaneseReviewActivity& a, MappedInputManager& in, GfxRenderer& r) {
 paint(a); tapButton(a,in,r,StrId::STR_JP_REVIEW_START); paint(a);
}
'''

class JapaneseReviewRuntimeTests(unittest.TestCase):
    def run_cpp(self, source, stubs=None):
        directory = BUILD / self._testMethodName
        directory.mkdir(parents=True, exist_ok=True)
        for name, content in (stubs or STUBS).items():
            target = directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        # Relocate exact bytes solely to select the explicit hardware/store seams.
        for name in ("JapaneseReviewActivity.h", "JapaneseReviewActivity.cpp"):
            self.assertTrue((INCLUDE / name).is_file(), "Review Activity is not implemented: " + name)
            shutil.copyfile(INCLUDE / name, directory / name)
        host = directory / "UiAppHost.cpp"
        shutil.copyfile(ROOT / "src/components/UiAppHost.cpp", host)
        cpp, exe = directory / "main.cpp", directory / "runtime"
        cpp.write_text(PREFIX + source, encoding="utf-8")
        command = ["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", str(directory),
                   "-I", str(ROOT / "src"), "-I", str(ROOT / "src/components"), "-I", str(INCLUDE), "-I", str(FUI),
                   str(cpp), str(directory / "JapaneseReviewActivity.cpp"), str(host),
                   str(FUI.parent / "src/FreeInkUI.cpp"), "-o", str(exe)]
        command[1:1] = os.environ.get("REVIEW_CXXFLAGS", "").split()
        compiled = subprocess.run(command, capture_output=True, text=True)
        (directory / "compile.log").write_text(" ".join(command) + "\n" + compiled.stdout + compiled.stderr, encoding="utf-8")
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        run = subprocess.run([str(exe)], capture_output=True, text=True)
        (directory / "runtime.log").write_text(run.stdout + run.stderr, encoding="utf-8")
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_dashboard_date_counts_no_writes_font_lifecycle(self):
        self.run_cpp(r'''
int main() {
 GfxRenderer r; MappedInputManager in; JapaneseReviewActivity a(r,in);
 a.onEnter(); paint(a);
 assert(has(r,tr(STR_JP_REVIEW)) && has(r,"2026-10-08"));
 assert(has(r,"新卡 45") && has(r,"到期 0") && has(r,"今日完成 0"));
 assert(has(r,tr(STR_JP_REVIEW_RULES)) && has(r,tr(STR_JP_REVIEW_START)));
 assert(r.fonts.count(0x4A52002C) && r.orientation==GfxRenderer::Orientation::Portrait);
 for (int i=0;i<5;++i) { a.loop(); paint(a); }
 assert(jr::writes==0);
 tapButton(a,in,r,StrId::STR_BACK); assert(a.finishes==1);
 a.onExit(); assert(!a.routingReady() && !r.fonts.count(0x4A52002C));
 assert(r.orientation==GfxRenderer::Orientation::LandscapeClockwise && a.exits==1);
 int data=44; EpdFont font(&data); EpdFontFamily family(&font); r.insertFont(0x4A52002C,family);
 a.onEnter(); a.onExit(); assert(r.fonts.count(0x4A52002C));
}
''')

    def test_dashboard_loaded_stats_failclosed_storage_corrupt_invalid_clock_back(self):
        self.run_cpp(r'''
int main() {
 jr::disk.words[0] = {20734,20731,1,3,2};
 jr::disk.words[1] = {20735,20734,1,1,1};
 jr::disk.words[2] = {20740,20733,1,7,3};
 jr::disk.latestDay=20734; jr::disk.revision=3; jr::loadStatus=jr::LoadStatus::Loaded;
 GfxRenderer r; MappedInputManager in; JapaneseReviewActivity loaded(r,in);
 loaded.onEnter(); paint(loaded);
 assert(has(r,"新卡 42") && has(r,"到期 1") && has(r,"今日完成 1"));
 loaded.onExit();
 for (auto status : {jr::LoadStatus::StorageError, jr::LoadStatus::Corrupt, jr::LoadStatus::Loaded}) {
  for (bool touch : {true,false}) {
   jr::loadStatus=status; TimeUtils::epoch=status==jr::LoadStatus::Loaded ? 0 : 1791417600;
   JapaneseReviewActivity a(r,in); a.onEnter(); paint(a);
   const char* message=status==jr::LoadStatus::Corrupt ? tr(STR_JP_REVIEW_CORRUPT) :
                       status==jr::LoadStatus::StorageError ? tr(STR_JP_REVIEW_STORAGE_ERROR) : tr(STR_JP_REVIEW_CLOCK);
   assert(has(r,message) && !has(r,"新卡 42"));
   tapButton(a,in,r,StrId::STR_JP_REVIEW_START); assert(!a.app.lastEvent());
   if (touch) tapButton(a,in,r,StrId::STR_BACK); else release(a,in,B::Back);
   assert(a.finishes==1); a.onExit();
  }
 }
 TimeUtils::epoch=1791417600; TimeUtils::day=20733; jr::loadStatus=jr::LoadStatus::Loaded;
 JapaneseReviewActivity backward(r,in); backward.onEnter(); paint(backward);
 assert(has(r,tr(STR_JP_REVIEW_CLOCK)) && !has(r,"新卡 42"));
 assert(jr::writes==0);
}
''')

    def test_all_45_hidden_reveal_three_ratings_exact_single_saves_and_complete(self):
        self.run_cpp(r'''
int main() {
 GfxRenderer r; MappedInputManager in; JapaneseReviewActivity a(r,in); a.onEnter();
 start(a,in,r);
 assert(jr::writes==0);
 for (int i=0;i<45;++i) {
  const auto& card=kana::cards[japanese::Words::cardIdAt(i)];
  paint(a); char header[24]; std::snprintf(header,sizeof(header),"%d / 45",i+1);
  assert(has(r,header) && has(r,card.example));
  assert(!has(r,card.exampleRomaji) && !has(r,card.meaning));
  assert(find(r,card.example).font==0x4A52002C);
  a.action(3); a.action(4); a.action(5); assert(jr::writes==i);
  if (i%2) tapButton(a,in,r,StrId::STR_KANA_QUIZ_REVEAL); else release(a,in,B::Confirm);
  paint(a); assert(has(r,card.exampleRomaji) && has(r,card.meaning));
  assert(has(r,tr(STR_JP_REVIEW_AGAIN)) && has(r,tr(STR_JP_REVIEW_FAMILIAR)) && has(r,tr(STR_JP_REVIEW_KNOWN)));
  auto again=buttonRect(r,StrId::STR_JP_REVIEW_AGAIN), familiar=buttonRect(r,StrId::STR_JP_REVIEW_FAMILIAR), known=buttonRect(r,StrId::STR_JP_REVIEW_KNOWN);
  for (const auto b : {again,familiar,known}) assert(b.width>=44 && b.height>=44 && b.x>=12 && b.x+b.width<=r.width-12);
  assert(familiar.x-again.x-again.width>=6 && known.x-familiar.x-familiar.width>=6);
  assert(again.y+again.height+6<=buttonRect(r,StrId::STR_BACK).y);
  if (i%2) tapButton(a,in,r,i%3==0 ? StrId::STR_JP_REVIEW_AGAIN : i%3==1 ? StrId::STR_JP_REVIEW_FAMILIAR : StrId::STR_JP_REVIEW_KNOWN);
  else release(a,in,i%3==0 ? B::Left : i%3==1 ? B::Confirm : B::Right);
  assert(jr::writes==i+1 && jr::disk.revision==static_cast<uint32_t>(i+1));
  assert(jr::disk.words[i].rating==i%3+1 && jr::disk.words[i].reviews==1);
  assert(jr::disk.words[i].intervalDays==(i%3==0 ? 1 : i%3==1 ? 3 : 7));
  assert(jr::lastExpected.revision==static_cast<uint32_t>(i));
  a.action(3); a.action(4); a.action(5); assert(jr::writes==i+1);
 }
 paint(a); assert(has(r,tr(STR_JP_REVIEW_COMPLETE)) && has(r,"今日完成 45"));
 assert(!has(r,tr(STR_KANA_QUIZ_REVEAL)) && !has(r,tr(STR_JP_REVIEW_KNOWN)));
 release(a,in,B::Confirm); assert(jr::writes==45);
 release(a,in,B::Back); paint(a); assert(a.finishes==0 && has(r,"新卡 0"));
 start(a,in,r); assert(has(r,tr(STR_JP_REVIEW_COMPLETE)) && jr::writes==45);
 a.onExit(); JapaneseReviewActivity reopened(r,in); reopened.onEnter(); start(reopened,in,r);
 assert(has(r,tr(STR_JP_REVIEW_COMPLETE)) && jr::writes==45);
}
''')

    def test_start_rereads_day_progress_due_first_and_hidden_geometry(self):
        self.run_cpp(r'''
int main() {
 for (int width : {480,400}) {
  jr::loadStatus=jr::LoadStatus::Empty; jr::disk={}; TimeUtils::day=20734;
  GfxRenderer r; r.width=width; MappedInputManager in; JapaneseReviewActivity a(r,in); a.onEnter(); paint(a);
  jr::disk.words[5]={20735,20732,1,3,2}; jr::disk.words[3]={20734,20731,1,3,2};
  jr::disk.latestDay=20734; jr::loadStatus=jr::LoadStatus::Loaded; TimeUtils::day=20735;
  start(a,in,r); assert(has(r,"2026-10-09") && has(r,kana::cards[3].example));
  assert(jr::writes==0 && !has(r,kana::cards[3].meaning));
  release(a,in,B::Confirm); paint(a);
  const auto& word=find(r,kana::cards[3].example); const auto& reading=find(r,kana::cards[3].exampleRomaji);
  const auto& meaning=find(r,kana::cards[3].meaning); const auto& rules=find(r,tr(STR_JP_REVIEW_RULES));
  assert(word.x==(width-word.width)/2 && word.y>=58);
  assert(reading.y>=word.y+word.height+12 && meaning.y>=reading.y+reading.height+12);
  assert(meaning.y+meaning.height+12<=rules.y);
  const auto back=buttonRect(r,StrId::STR_BACK);
  assert(back.x>=12 && back.x+back.width<=width-12 && back.y+back.height<=r.height-12);
  a.onExit();
 }
 // The dashboard was valid, but Start must refuse a newly-invalid clock.
 jr::loadStatus=jr::LoadStatus::Empty; GfxRenderer r; MappedInputManager in; JapaneseReviewActivity a(r,in);
 a.onEnter(); paint(a); TimeUtils::epoch=0; tapButton(a,in,r,StrId::STR_JP_REVIEW_START); paint(a);
 assert(has(r,tr(STR_JP_REVIEW_CLOCK)) && !has(r,kana::cards[0].example));
}
''')

    def test_inherited_holds_touch_reveal_release_barriers_and_stale_dispatch(self):
        self.run_cpp(r'''
int main() {
 GfxRenderer r; MappedInputManager in;
 for (auto b : {B::Left,B::Confirm,B::Right}) in.held[static_cast<int>(b)]=true;
 JapaneseReviewActivity a(r,in); a.onEnter(); paint(a); a.loop();
 release(a,in,B::Confirm); paint(a); assert(has(r,tr(STR_JP_REVIEW_START)) && jr::writes==0);
 start(a,in,r); assert(!a.session_.revealed());
 in.held[static_cast<int>(B::Right)]=true;
 in.held[static_cast<int>(B::Confirm)]=true;
 const auto reveal=buttonRect(r,StrId::STR_KANA_QUIZ_REVEAL);
 in.touch.touchReleased=true; in.touch.touchX=reveal.x+reveal.width/2; in.touch.touchY=reveal.y+reveal.height/2;
 a.loop(); assert(a.session_.revealed() && jr::writes==0); paint(a);
 in.clear(); in.held[static_cast<int>(B::Confirm)]=true;
 in.released[static_cast<int>(B::Right)]=true; a.loop(); in.clear();
 release(a,in,B::Confirm); assert(a.session_.revealed() && jr::writes==0);
 release(a,in,B::Confirm); assert(jr::writes==1 && !a.session_.revealed());
 paint(a);
 // An unmatched touch snapshot consumes the frame, never falling through to Confirm.
 in.touch.touchPressed=true; in.touch.touchX=1; in.touch.touchY=300;
 in.released[static_cast<int>(B::Confirm)]=true; a.loop(); in.clear();
 assert(!a.session_.revealed() && jr::writes==1);
 release(a,in,B::Confirm); paint(a);
 const auto known=buttonRect(r,StrId::STR_JP_REVIEW_KNOWN);
 tapButton(a,in,r,StrId::STR_JP_REVIEW_KNOWN); assert(jr::writes==2 && a.session_.current()==2);
 tap(a,in,known.x+known.width/2,known.y+known.height/2); assert(jr::writes==2);
 a.action(5); assert(jr::writes==2);
 paint(a); const auto nextReveal=buttonRect(r,StrId::STR_KANA_QUIZ_REVEAL);
 in.touch.touchReleased=true; in.touch.touchX=nextReveal.x+nextReveal.width/2; in.touch.touchY=nextReveal.y+nextReveal.height/2;
 in.released[static_cast<int>(B::Back)]=true; a.loop(); in.clear(); paint(a);
 assert(has(r,tr(STR_JP_REVIEW_START)) && jr::writes==2 && a.finishes==0);
 release(a,in,B::Back); assert(a.finishes==1 && !a.routingReady());
}
''')

    def test_save_failure_keeps_revealed_proposal_blocks_ratings_retry_same_once(self):
        self.run_cpp(r'''
int main() {
 GfxRenderer r; MappedInputManager in; JapaneseReviewActivity a(r,in); a.onEnter(); start(a,in,r);
 release(a,in,B::Confirm); paint(a); jr::failWrite=true;
 tapButton(a,in,r,StrId::STR_JP_REVIEW_AGAIN); paint(a);
 assert(jr::writes==1 && a.session_.current()==0 && a.session_.revealed());
 assert(has(r,tr(STR_JP_REVIEW_SAVE_ERROR)) && !has(r,tr(STR_JP_REVIEW_SAVED)));
 assert(has(r,"1 / 45   再練") && has(r,kana::cards[0].meaning));
 const auto desired=jr::encodeProgress(jr::lastDesired), expected=jr::encodeProgress(jr::lastExpected);
 const auto retry=buttonRect(r,StrId::STR_JP_REVIEW_RETRY), rating=buttonRect(r,StrId::STR_JP_REVIEW_FAMILIAR);
 assert(rating.y+rating.height+6<=retry.y);
 for (auto id : {StrId::STR_JP_REVIEW_AGAIN,StrId::STR_JP_REVIEW_FAMILIAR,StrId::STR_JP_REVIEW_KNOWN}) tapButton(a,in,r,id);
 release(a,in,B::Left); release(a,in,B::Right); a.action(3); a.action(4); a.action(5);
 assert(jr::writes==1 && jr::encodeProgress(jr::lastDesired)==desired);
 const int loads=jr::loads;
 for (int i=0;i<8;++i) { in.clear(); a.loop(); paint(a); }
 assert(jr::writes==1 && jr::loads==loads);
 release(a,in,B::Confirm); paint(a); // explicit Retry via Confirm
 assert(jr::writes==2 && jr::encodeProgress(jr::lastDesired)==desired && jr::encodeProgress(jr::lastExpected)==expected);
 assert(a.session_.revealed() && a.session_.current()==0);
 jr::failWrite=false; tapButton(a,in,r,StrId::STR_JP_REVIEW_RETRY);
 a.action(6); tap(a,in,retry.x+retry.width/2,retry.y+retry.height/2); assert(jr::writes==3);
 paint(a);
 assert(jr::writes==3 && jr::disk.words[0].rating==1 && jr::disk.words[0].reviews==1 && jr::disk.revision==1);
 assert(a.session_.current()==1 && !a.session_.revealed() && has(r,tr(STR_JP_REVIEW_SAVED)));
 // Back discards the failed proposal, keeps failure visible and never writes.
 release(a,in,B::Confirm); jr::failWrite=true; release(a,in,B::Right); paint(a);
 assert(jr::writes==4 && a.session_.revealed());
 tapButton(a,in,r,StrId::STR_BACK); paint(a);
 assert(has(r,tr(STR_JP_REVIEW_SAVE_ERROR)) && has(r,"新卡 44") && jr::writes==4 && a.finishes==0);
 start(a,in,r); assert(a.session_.current()==1 && !a.session_.revealed() && jr::writes==4);
}
''')

    def test_uncertain_save_retry_recognizes_exact_committed_snapshot_no_second_write(self):
        self.run_cpp(r'''
int main() {
 for (int rating=1;rating<=3;++rating) {
  jr::disk={}; jr::loadStatus=jr::LoadStatus::Empty; jr::writes=0; jr::commitThenFail=true;
  GfxRenderer r; MappedInputManager in; JapaneseReviewActivity a(r,in); a.onEnter(); start(a,in,r);
  release(a,in,B::Confirm); a.action(rating+2); paint(a);
  assert(a.session_.revealed() && a.session_.current()==0 && jr::writes==1);
  const auto committed=jr::encodeProgress(jr::disk);
  tapButton(a,in,r,StrId::STR_JP_REVIEW_RETRY); paint(a);
  assert(a.session_.current()==1 && !a.session_.revealed() && jr::writes==1);
  assert(has(r,tr(STR_JP_REVIEW_SAVED)) && jr::encodeProgress(jr::disk)==committed);
  a.action(6); assert(jr::writes==1); a.onExit();
  JapaneseReviewActivity reopened(r,in); reopened.onEnter(); start(reopened,in,r);
  assert(reopened.session_.current()==1 && !reopened.session_.revealed() && jr::writes==1);
 }
}
''')

    def test_retry_corrupt_storage_conflict_never_clobbers_or_advances(self):
        self.run_cpp(r'''
int main() {
 for (int failure=0;failure<5;++failure) {
  jr::disk={}; jr::loadStatus=jr::LoadStatus::Empty; jr::writes=0; jr::failWrite=true;
  GfxRenderer r; MappedInputManager in; JapaneseReviewActivity a(r,in); a.onEnter(); start(a,in,r);
  release(a,in,B::Confirm); release(a,in,B::Right); paint(a); assert(jr::writes==1);
  jr::failWrite=false; jr::loadStatus=jr::LoadStatus::Loaded;
  if (failure==0) jr::loadStatus=jr::LoadStatus::Corrupt;
  if (failure==1) jr::loadStatus=jr::LoadStatus::StorageError;
  if (failure==2) { jr::disk.revision=1; jr::disk.sentencePosition=2; }
  if (failure==3) { jr::disk.sentenceReadMask=1; } // same revision is NOT same snapshot
  if (failure==4) { jr::disk=jr::lastDesired; jr::disk.sentenceReadMask=4; }
  const auto before=jr::encodeProgress(jr::disk);
  tapButton(a,in,r,StrId::STR_JP_REVIEW_RETRY); paint(a);
  assert(jr::writes==1 && jr::encodeProgress(jr::disk)==before);
  assert(a.session_.revealed() && a.session_.current()==0 && has(r,"1 / 45   會"));
  const auto message=failure==0 ? tr(STR_JP_REVIEW_CORRUPT) : failure==1 ? tr(STR_JP_REVIEW_STORAGE_ERROR) : tr(STR_JP_REVIEW_SAVE_ERROR);
  assert(has(r,message) && !has(r,tr(STR_JP_REVIEW_SAVED)));
  release(a,in,B::Left); release(a,in,B::Right); assert(jr::writes==1);
  release(a,in,B::Back); paint(a); release(a,in,B::Back); assert(a.finishes==1 && jr::writes==1);
 }
}
''')

    def test_mid_session_day_change_invalid_clock_latches_blocks_rating_retry_until_dashboard(self):
        self.run_cpp(r'''
int main() {
 for (int scenario=0;scenario<4;++scenario) {
  jr::disk={}; jr::loadStatus=jr::LoadStatus::Empty; jr::writes=0; jr::failWrite=false;
  TimeUtils::day=20734; TimeUtils::epoch=1791417600;
  GfxRenderer r; MappedInputManager in; JapaneseReviewActivity a(r,in); a.onEnter(); start(a,in,r);
  release(a,in,B::Confirm);
  if (scenario==1) { jr::failWrite=true; release(a,in,B::Left); }
  const int writes=jr::writes;
  if (scenario==2) TimeUtils::epoch=0; else TimeUtils::day=20735;
  a.action(scenario==1 ? 6 : 5); paint(a); // must validate even outside the loop
  assert(jr::writes==writes && a.session_.current()==0 && a.session_.revealed());
  assert(has(r,tr(STR_JP_REVIEW_CLOCK)) && !has(r,tr(STR_JP_REVIEW_SAVED)));
  for (int value : {2,3,4,5,6}) a.action(value);
  for (auto id : {StrId::STR_JP_REVIEW_AGAIN,StrId::STR_JP_REVIEW_FAMILIAR,StrId::STR_JP_REVIEW_KNOWN}) tapButton(a,in,r,id);
  if (scenario==1) tapButton(a,in,r,StrId::STR_JP_REVIEW_RETRY);
  assert(jr::writes==writes);
  // Moving the clock back again does NOT make the stale queue safe.
  TimeUtils::epoch=1791417600; TimeUtils::day=20734; a.action(5); assert(jr::writes==writes);
  jr::failWrite=false; TimeUtils::day=20735;
  release(a,in,B::Back); paint(a); assert(has(r,"2026-10-09") && a.finishes==0);
  start(a,in,r); release(a,in,B::Confirm); release(a,in,B::Right);
  assert(jr::writes==writes+1 && jr::disk.words[0].lastRatedDay==20735);
 }
 // Idle loop detects rollover and invalidates once, without rewriting any progress.
 jr::disk={}; jr::loadStatus=jr::LoadStatus::Empty; TimeUtils::day=20734;
 GfxRenderer r; MappedInputManager in; JapaneseReviewActivity a(r,in); a.onEnter(); start(a,in,r);
 const int writes=jr::writes; TimeUtils::day=20735; a.loop(); paint(a);
 assert(has(r,tr(STR_JP_REVIEW_CLOCK)) && jr::writes==writes);
 const int updates=a.updates; a.loop(); a.loop(); assert(a.updates==updates);
}
''')

    def test_core_refusal_maxday_and_revision_overflow_remains_visible_no_write(self):
        self.run_cpp(r'''
int main() {
 for (bool overflow : {false,true}) {
  jr::disk={}; jr::disk.revision=overflow ? UINT32_MAX : 0;
  jr::loadStatus=jr::LoadStatus::Loaded; TimeUtils::day=overflow ? 20734 : jr::kMaxDay;
  GfxRenderer r; MappedInputManager in; JapaneseReviewActivity a(r,in); a.onEnter(); start(a,in,r);
  release(a,in,B::Confirm); release(a,in,B::Right); paint(a);
  assert(jr::writes==0 && a.session_.current()==0 && a.session_.revealed());
  assert(has(r,tr(STR_JP_REVIEW_SAVE_ERROR)) && !has(r,tr(STR_JP_REVIEW_SAVED)));
  release(a,in,B::Back); paint(a); release(a,in,B::Back); assert(a.finishes==1);
 }
}
''')

    def test_touch_snapshots_never_fall_through_to_physical_before_repaint_or_while_held(self):
        self.run_cpp(r'''
int main() {
 GfxRenderer r; MappedInputManager in; JapaneseReviewActivity a(r,in); a.onEnter();
 // The initial interaction table is not ready; an unrelated touch release must
 // not turn a simultaneous Confirm release into Start.
 in.touch.touchReleased=true; in.released[static_cast<int>(B::Confirm)]=true; a.loop(); in.clear();
 assert(a.page_==JapaneseReviewActivity::Page::Dashboard && jr::writes==0);
 start(a,in,r); release(a,in,B::Confirm); // reveal closes routing until repaint
 in.touch.touchReleased=true; in.released[static_cast<int>(B::Confirm)]=true; a.loop(); in.clear();
 assert(jr::writes==0 && a.session_.revealed());
 paint(a);
 // A held finger (including a drag off-target) is still a touch frame.
 in.touch.touchHeld=true; in.touch.touchX=1; in.touch.touchY=300;
 in.released[static_cast<int>(B::Right)]=true; a.loop(); in.clear();
 assert(jr::writes==0 && a.session_.revealed());
 release(a,in,B::Right); assert(jr::writes==1 && !a.session_.revealed());
 a.onExit();
 // Opening this activity cannot inherit a finger-down from its parent entry.
 in.touch.touchHeld=true;
 JapaneseReviewActivity inherited(r,in); inherited.onEnter(); paint(inherited);
 const auto startButton=buttonRect(r,StrId::STR_JP_REVIEW_START);
 in.touch.touchHeld=false; in.touch.touchReleased=true;
 in.touch.touchX=startButton.x+startButton.width/2; in.touch.touchY=startButton.y+startButton.height/2;
 inherited.loop(); in.clear(); paint(inherited);
 assert(inherited.page_==JapaneseReviewActivity::Page::Dashboard && jr::writes==1);
 start(inherited,in,r); assert(inherited.session_.current()==1 && !inherited.session_.revealed());
}
''')

    def test_actual_three_locale_labels_paint_and_hit_without_footer_overlap(self):
        keys = ["STR_BACK", "STR_JP_REVIEW", "STR_JP_WORDS_PROMPT", "STR_KANA_QUIZ_REVEAL",
                "STR_JP_REVIEW_START", "STR_JP_REVIEW_NEW", "STR_JP_REVIEW_DUE", "STR_JP_REVIEW_DONE",
                "STR_JP_REVIEW_AGAIN", "STR_JP_REVIEW_FAMILIAR", "STR_JP_REVIEW_KNOWN", "STR_JP_REVIEW_SAVED",
                "STR_JP_REVIEW_SAVE_ERROR", "STR_JP_REVIEW_STORAGE_ERROR", "STR_JP_REVIEW_CORRUPT",
                "STR_JP_REVIEW_CLOCK", "STR_JP_REVIEW_RETRY", "STR_JP_REVIEW_COMPLETE", "STR_JP_REVIEW_RULES"]
        rows = []
        for filename in ("chinese-traditional.yaml", "chinese.yaml", "english.yaml"):
            strings = {}
            for line in (ROOT / "lib/I18n/translations" / filename).read_text(encoding="utf-8").splitlines():
                key, separator, value = line.partition(":")
                if separator and key in keys:
                    strings[key] = json.loads(value.strip())
            self.assertEqual(set(strings), set(keys), filename + ": missing provided label")
            rows.append("{" + ",".join(json.dumps(strings[key], ensure_ascii=False) for key in keys) + "}")
        stubs = dict(STUBS)
        stubs["I18n.h"] = """#pragma once
enum class StrId { %s };
struct I18n {
 int language=0;
 static I18n& getInstance() { static I18n i; return i; }
 const char* get(StrId id) const {
  static const char* labels[3][%d]={%s};
  return labels[language][static_cast<int>(id)];
 }
};
#define I18N I18n::getInstance()
#define tr(id) I18N.get(StrId::id)
""" % (",".join(keys), len(keys), ",".join(rows))
        self.run_cpp(r'''
int main() {
 for (int language=0;language<3;++language) {
  I18N.language=language; jr::disk={}; jr::loadStatus=jr::LoadStatus::Empty;
  jr::writes=0; jr::failWrite=false;
  GfxRenderer r; MappedInputManager in; JapaneseReviewActivity a(r,in); a.onEnter(); start(a,in,r);
  assert(!has(r,kana::cards[0].meaning));
  tapButton(a,in,r,StrId::STR_KANA_QUIZ_REVEAL); paint(a);
  for (auto id : {StrId::STR_JP_REVIEW_AGAIN,StrId::STR_JP_REVIEW_FAMILIAR,StrId::STR_JP_REVIEW_KNOWN}) {
   assert(has(r,I18N.get(id)));
   const auto b=buttonRect(r,id); const auto& d=find(r,I18N.get(id));
   assert(d.x>=b.x && d.x+d.width<=b.x+b.width && d.y+d.height<=b.y+b.height);
  }
  jr::failWrite=true; tapButton(a,in,r,StrId::STR_JP_REVIEW_FAMILIAR); paint(a);
  assert(has(r,tr(STR_JP_REVIEW_SAVE_ERROR)) && has(r,tr(STR_JP_REVIEW_RETRY)));
  const auto& status=find(r,tr(STR_JP_REVIEW_SAVE_ERROR));
  const auto& rules=find(r,tr(STR_JP_REVIEW_RULES));
  const auto rating=buttonRect(r,StrId::STR_JP_REVIEW_AGAIN), retry=buttonRect(r,StrId::STR_JP_REVIEW_RETRY);
  assert(status.x>=12 && status.x+status.width<=r.width-12);
  assert(status.y+status.height<=rules.y && rules.y+rules.height+6<=rating.y);
  assert(rating.y+rating.height+6<=retry.y);
  jr::failWrite=false; tapButton(a,in,r,StrId::STR_JP_REVIEW_RETRY); paint(a);
  assert(jr::writes==2 && jr::disk.words[0].rating==2 && !a.session_.revealed());
  release(a,in,B::Back); paint(a); tapButton(a,in,r,StrId::STR_BACK); assert(a.finishes==1);
 }
}
''', stubs=stubs)

if __name__ == "__main__":
    unittest.main()
