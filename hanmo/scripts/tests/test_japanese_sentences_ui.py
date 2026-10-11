"""Real Sentences Activity + UiAppHost + SDK drawing, wrapping and touch routing.
Hardware renderer/input/I18n/lifecycle are host seams, not lesson replacements.
"""
from pathlib import Path
import json
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
INCLUDE = ROOT / 'src/activities/apps/japanese'
ACTIVITY_SOURCE = INCLUDE / 'JapaneseSentencesActivity.cpp'
FUI = ROOT / 'freeink-sdk/libs/ui/FreeInkUI/include'
BUILD = ROOT / 'build/japanese-sentence-progress/ui'

STUBS = {
'EpdFontFamily.h': r'''
#pragma once
struct EpdFont { explicit EpdFont(const int*) {} };
struct EpdFontFamily { explicit EpdFontFamily(const EpdFont*) {} };
''',
'builtinFonts/hanmo_sentences_28.h': '#pragma once\ninline int hanmo_sentences_28 = 28;\n',
'builtinFonts/hanmo_sentence_notes_12.h': '#pragma once\ninline int hanmo_sentence_notes_12 = 12;\n',
'fontIds.h': '#pragma once\ninline constexpr int SMALL_FONT_ID = 1;\n',
'activities/Activity.h': r'''
#pragma once
#include <FreeInkApp.h>
#include <EpdFontFamily.h>
#include <algorithm>
#include <array>
#include <cassert>
#include <cstring>
#include <map>
#include <string>
#include <vector>
struct Draw { int font,x,y,width,height; std::string text; int color = int(freeink::ui::Color::Black); };
struct Box { freeink::ui::Rect rect; freeink::ui::Paint paint; };
struct Rect { int x,y,width,height; };
class GfxRenderer {
 public:
  enum class Orientation { Portrait, LandscapeClockwise, PortraitInverted, LandscapeCounterClockwise };
  mutable std::vector<Draw> draws;
  mutable std::vector<Box> boxes;
  std::map<int,EpdFontFamily> fonts;
  Orientation orientation = Orientation::LandscapeClockwise;
  int width = 480, height = 800, displays = 0, smallHeight = 24;
  Orientation getOrientation() const { return orientation; }
  void setOrientation(Orientation o) { orientation = o; }
  int getScreenWidth() const { return width; }
  int getScreenHeight() const { return height; }
  const auto& getFontMap() const { return fonts; }
  void insertFont(int id,const EpdFontFamily& f) { fonts.emplace(id,f); }
  void removeFont(int id) { fonts.erase(id); }
  static int glyphCount(const char* s) {
    int n = 0; for (; *s; ++s) if ((static_cast<unsigned char>(*s)&0xC0) != 0x80) ++n;
    return n;
  }
  int getTextWidth(int font,const char* s) const { return glyphCount(s)*(font == 0x4A53001C ? 56 : 18); }
  int getLineHeight(int font) const { return font == 0x4A53001C ? 84 : font == 0x4A53100C ? 36 : smallHeight; }
  void drawText(int font,int x,int y,const char* s) const {
    if (s && *s) draws.push_back({font,x,y,getTextWidth(font,s),getLineHeight(font),s});
  }
  void clearScreen() { draws.clear(); boxes.clear(); }
  void displayBuffer() { ++displays; }
};
class MappedInputManager {
 public:
  enum class Button { Back, Confirm, Left, Right, Up, Down };
  std::array<bool,6> released{},held{};
  freeink::ui::InputSnapshot touch{};
  bool wasReleased(Button b) const { return released[static_cast<int>(b)]; }
  bool isPressed(Button b) const { return held[static_cast<int>(b)]; }
  void clear() { released.fill(false); held.fill(false); touch = {}; }
};
class Activity;
struct RenderLock { explicit RenderLock(Activity&) {} };
class Activity {
 protected:
  GfxRenderer& renderer;
  MappedInputManager& mappedInput;
 public:
  int updates = 0, finishes = 0, entries = 0, exits = 0;
  Activity(const char*,GfxRenderer& r,MappedInputManager& m):renderer(r),mappedInput(m) {}
  virtual ~Activity() = default;
  virtual void onEnter() { ++entries; }
  virtual void onExit() { ++exits; }
  virtual void loop() {}
  virtual void render(RenderLock&&) {}
  virtual void requestUpdate(bool = false) { ++updates; }
  void finish() { ++finishes; }
};
''',
'components/themes/BaseTheme.h': r'''
#pragma once
#include "activities/Activity.h"
struct ThemeMetrics { int topPadding = 5,headerHeight = 45,verticalSpacing = 8,tabBarHeight = 0; };
''',
'components/UITheme.h': r'''
#pragma once
#include "components/themes/BaseTheme.h"
class BaseTheme {
 public:
  void drawHeader(GfxRenderer& r,const Rect&,const char* title,const char* progress) const {
    r.drawText(1,12,5,title); r.drawText(1,r.getScreenWidth()-12-r.getTextWidth(1,progress),5,progress);
  }
};
class UITheme {
 public:
  ThemeMetrics metrics;
  static UITheme& getInstance() { static UITheme t; return t; }
  const ThemeMetrics& getMetrics() const { return metrics; }
  Rect getScreenSafeArea(const GfxRenderer& r,bool = false,bool = false) {
    return Rect{12,0,r.getScreenWidth()-24,r.getScreenHeight()-12};
  }
  const BaseTheme& getTheme() const { static BaseTheme theme; return theme; }
};
#define GUI UITheme::getInstance().getTheme()
''',
'FreeInkUIGfxRenderer.h': r'''
#pragma once
#include "activities/Activity.h"
namespace freeink::ui {
class GfxRendererTarget : public DrawTarget {
  const GfxRenderer& r;
 public:
  explicit GfxRendererTarget(const GfxRenderer& renderer):r(renderer) {}
  DeviceContext deviceContext() const {
    DeviceContext d; d.width = r.getScreenWidth(); d.height = r.getScreenHeight();
    d.hasTouch = true; d.minTouchSize = 44; return d;
  }
  Size measureText(FontId font,const char* s,TextStyle) const override {
    return Size{int16_t(r.getTextWidth(font,s)),int16_t(r.getLineHeight(font))};
  }
  int16_t lineHeight(FontId font) const override { return r.getLineHeight(font); }
  void fill(freeink::ui::Rect rect,Paint paint,uint8_t = 0,uint8_t = CornersAll) override { r.boxes.push_back({rect,paint}); }
  void stroke(freeink::ui::Rect,Paint,uint8_t,uint8_t = 0,uint8_t = CornersAll) override {}
  void line(Point,Point,uint8_t,Paint) override {}
  void triangle(Point,Point,Point,Paint) override {}
  void bitmap(freeink::ui::Rect,BitmapRef,BitmapMode,Paint = Paint::solid(Color::Black),Rotation = Rotation::None) override {}
  void text(freeink::ui::Rect rect,const char* value,TextStyle style) override {
    layoutText(*this,rect,value,style,[&](const char* line,freeink::ui::Rect row) {
      r.drawText(style.font,row.x,row.y,line);
      if (!r.draws.empty()) r.draws.back().color = int(style.color);
    });
  }
};
}
''',
'UiAppHelpers.h': r'''
#pragma once
#include "components/UiAppHost.h"
#include "activities/Activity.h"
inline freeink::ui::GfxRendererTarget makeUiTarget(const GfxRenderer& r) { return freeink::ui::GfxRendererTarget(r); }
inline void refreshSharedUiThemeTokens(const freeink::ui::GfxRendererTarget&) {}
template<typename App> void applySharedUiTheme(App& app,const freeink::ui::GfxRendererTarget& target) {
  auto theme = freeink::ui::themeTokensForLineHeight(target.lineHeight(1));
  theme.minTouchSize = 44; theme.smallText.font = 1; theme.bodyText.font = 1;
  app.setTheme(theme);
}
inline freeink::ui::InputSnapshot touchSnapshotFrom(const MappedInputManager& input,bool = false) { return input.touch; }
''',
'I18n.h': r'''
#pragma once
enum class StrId {
  STR_JP_SENTENCES,STR_BACK,STR_KANA_PREV,STR_KANA_NEXT,
  STR_JP_SENTENCES_REVEAL,STR_JP_SENTENCES_HIDE,STR_JP_SENTENCES_PROMPT,STR_JP_SENTENCES_SESSION,
  STR_JP_SENTENCES_PROGRESS,STR_JP_REVIEW_SAVED,STR_JP_REVIEW_SAVE_ERROR,
  STR_JP_REVIEW_STORAGE_ERROR,STR_JP_REVIEW_CORRUPT,STR_JP_REVIEW_RETRY
};
struct I18n {
  int language = 0;
  static I18n& getInstance() { static I18n i; return i; }
  const char* get(StrId id) const {
    static const char* zh[] = {"短句閱讀","返回","上一張","下一張","看解說","藏解說","先讀短句，再看解說。","讀後可保存進度。","已讀","已保存","保存失敗","SD 無法讀取","進度檔異常","重試"};
    static const char* en[] = {"Short sentences","Back","Previous","Next","Show explanation","Hide explanation","Read first, then reveal.","SD reading progress.","Read","Saved","Save failed","SD unavailable","Progress corrupt","Retry"};
    return (language == 2 ? en : zh)[static_cast<int>(id)];
  }
};
#define I18N I18n::getInstance()
''',
'HalStorage.h': r'''
#pragma once
struct FakeStorage {};
inline FakeStorage sentenceStorage;
#define Storage sentenceStorage
''',
'JapaneseReviewStore.h': r'''
#pragma once
#include "JapaneseReview.h"
#include <cassert>
namespace japanese::review {
enum class LoadStatus { Empty, Loaded, Corrupt, StorageError };
inline Progress stored{}, lastExpected{}, lastProposal{};
inline LoadStatus loadStatus = LoadStatus::Empty;
inline int loads = 0, saves = 0;
inline bool saveFails = false, commitThenFail = false;
inline void (*beforeSave)() = nullptr;
inline bool same(const Progress& a,const Progress& b) {
  if (a.revision != b.revision || a.latestDay != b.latestDay || a.sentencePosition != b.sentencePosition ||
      a.sentenceReadMask != b.sentenceReadMask) return false;
  for (size_t i=0;i<a.words.size();++i) {
    const auto& x=a.words[i]; const auto& y=b.words[i];
    if (x.dueDay!=y.dueDay || x.lastRatedDay!=y.lastRatedDay || x.reviews!=y.reviews ||
        x.intervalDays!=y.intervalDays || x.rating!=y.rating) return false;
  }
  return true;
}
inline void resetStore() {
  stored = {}; lastExpected = {}; lastProposal = {}; loadStatus = LoadStatus::Empty;
  loads = 0; saves = 0; saveFails = false; commitThenFail = false; beforeSave = nullptr;
}
template<class FS> LoadStatus loadProgress(FS&,Progress& out) {
  ++loads;
  if (loadStatus == LoadStatus::Empty) out = {};
  if (loadStatus == LoadStatus::Loaded) out = stored;
  return loadStatus;
}
template<class FS> bool saveProgress(FS&,const Progress& p,const Progress* expected = nullptr) {
  ++saves; assert(expected); lastExpected = *expected; lastProposal = p;
  if (beforeSave) beforeSave();
  if (loadStatus == LoadStatus::Corrupt || loadStatus == LoadStatus::StorageError || !same(*expected,stored)) return false;
  if (saveFails) return false;
  assert(p.revision == stored.revision+1);
  stored = p; loadStatus = LoadStatus::Loaded; return !commitThenFail;
}
}
''',
}

PREFIX = r'''
#include "activities/Activity.h"
#include "components/UiAppHost.h"
#include "components/UITheme.h"
#include "I18n.h"
#include "JapaneseSentences.generated.h"
#include "JapaneseReviewStore.h"
#define private public
#define protected public
#include "JapaneseSentencesActivity.h"
#undef protected
#undef private
namespace fui = freeink::ui;
bool has(const GfxRenderer& r,const char* text) {
  for (const auto& draw:r.draws) if (draw.text == text) return true;
  return false;
}
const Draw& find(const GfxRenderer& r,const char* text) {
  for (const auto& draw:r.draws) if (draw.text == text) return draw;
  assert(false && "required rendered text missing"); return r.draws.front();
}
void paint(JapaneseSentencesActivity& a) { a.render(RenderLock(a)); }
void release(JapaneseSentencesActivity& a,MappedInputManager& input,MappedInputManager::Button b) {
  input.clear(); input.released[static_cast<int>(b)] = true; a.loop(); input.clear();
}
void touch(JapaneseSentencesActivity& a,MappedInputManager& input,int x,int y,bool press = false) {
  input.clear(); input.touch.touchPressed = press; input.touch.touchReleased = !press;
  input.touch.touchX = x; input.touch.touchY = y; a.loop(); input.clear();
}
void tapLabel(JapaneseSentencesActivity& a,MappedInputManager& input,GfxRenderer& r,StrId id) {
  paint(a); auto d = find(r,I18N.get(id)); touch(a,input,d.x+d.width/2,d.y+d.height/2);
}
'''

class JapaneseSentencesRuntimeTests(unittest.TestCase):
    def run_cpp(self, source, real_store=False):
        directory = getattr(self, 'build_root', BUILD) / self._testMethodName
        directory.mkdir(parents=True, exist_ok=True)
        stubs = dict(STUBS)
        # Real authored family advanceY values, not UI-small font estimates.
        for name, advance in [('hanmo_sentences_28', 84), ('hanmo_sentence_notes_12', 36)]:
            font = (ROOT / f'lib/EpdFont/builtinFonts/{name}.h').read_text()
            self.assertRegex(font, rf'EpdFontData {name} = \{{\s*{name}Bitmaps,\s*{name}Glyphs,\s*{name}Intervals,\s*\d+,\s*{advance},')
        # Use the parent's actual three locale values without regenerating I18n.
        keys = re.findall(r'\bSTR_\w+', stubs['I18n.h'].split('struct I18n')[0])
        for variable, locale in [('zh', 'chinese-traditional'), ('en', 'english')]:
            values = dict(re.findall(r'^(STR_\w+): (".*")$', (ROOT / f'lib/I18n/translations/{locale}.yaml').read_text(), re.M))
            array = ','.join(json.dumps(json.loads(values[key]), ensure_ascii=False) for key in keys)
            stubs['I18n.h'] = re.sub(rf'static const char\* {variable}\[\] = \{{.*?\}};',
                                     f'static const char* {variable}[] = {{{array}}};', stubs['I18n.h'])
        values = dict(re.findall(r'^(STR_\w+): (".*")$', (ROOT / 'lib/I18n/translations/chinese.yaml').read_text(), re.M))
        array = ','.join(json.dumps(json.loads(values[key]), ensure_ascii=False) for key in keys)
        stubs['I18n.h'] = stubs['I18n.h'].replace('return (language == 2 ? en : zh)',
                                                 f'static const char* cn[] = {{{array}}};\n    return (language == 2 ? en : language == 1 ? cn : zh)')
        if real_store:
            from scripts.tests.test_japanese_review_store import FAKE_STORAGE
            stubs.pop('JapaneseReviewStore.h')
            (directory / 'JapaneseReviewStore.h').unlink(missing_ok=True)
            stubs['HalStorage.h'] = FAKE_STORAGE + '\ninline FakeFS sentenceStorage;\n#define Storage sentenceStorage\n'
        for name, contents in stubs.items():
            target = directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(contents, encoding='utf-8')
        # Relocate only to select host HAL seams; real shared implementation is untouched.
        host = directory / 'UiAppHost.cpp'
        host.write_bytes((ROOT / 'src/components/UiAppHost.cpp').read_bytes())
        activity = directory / 'JapaneseSentencesActivity.cpp'
        activity.write_bytes(ACTIVITY_SOURCE.read_bytes())
        cpp, exe = directory / 'main.cpp', directory / 'runtime'
        cpp.write_text(PREFIX + source, encoding='utf-8')
        command = ['c++','-std=c++17','-Wall','-Wextra','-Werror','-I',str(directory),
                   '-I',str(ROOT / 'src'),'-I',str(ROOT / 'src/components'),'-I',str(INCLUDE),'-I',str(FUI),
                   str(cpp),str(activity),str(host),
                   str(FUI.parent / 'src/FreeInkUI.cpp'),'-o',str(exe)]
        compiled = subprocess.run(command, capture_output=True, text=True)
        (directory / 'compile.log').write_text(' '.join(command) + '\n' + compiled.stdout + compiled.stderr, encoding='utf-8')
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        run = subprocess.run([str(exe)], capture_output=True, text=True)
        (directory / 'runtime.log').write_text(run.stdout + run.stderr, encoding='utf-8')
        frames = []
        for line in run.stdout.splitlines():
            fields = line.split('|')
            if fields[0] == 'FRAME':
                frames.append({'language': int(fields[1]), 'height': int(fields[2]), 'ui_line': int(fields[3]),
                               'state': int(fields[4]), 'position': int(fields[5]), 'revealed': int(fields[6]),
                               'draws': [], 'boxes': []})
            elif fields[0] == 'DRAW':
                frames[-1]['draws'].append({'font': int(fields[1]), 'x': int(fields[2]), 'y': int(fields[3]),
                                            'width': int(fields[4]), 'height': int(fields[5]),
                                            'color': int(fields[6]), 'text': '|'.join(fields[7:])})
            elif fields[0] == 'BOX':
                frames[-1]['boxes'].append(dict(zip(['x', 'y', 'width', 'height'], map(int, fields[1:]))))
        if frames:
            (directory / 'paint-frames.json').write_text(json.dumps(frames, ensure_ascii=False, indent=2), encoding='utf-8')
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_first_screen_has_only_large_centered_japanese_and_no_answer_leak(self):
        self.run_cpp(r'''
int main() {
  GfxRenderer r; MappedInputManager input; JapaneseSentencesActivity a(r,input);
  a.onEnter(); paint(a);
  const auto& c = japanese::sentences::cards[0];
  assert(has(r,c.japanese));
  const auto& d = find(r,c.japanese);
  assert(d.font == 0x4A53001C && d.x == (r.width-d.width)/2);
  assert(d.x >= 12 && d.x+d.width <= r.width-12);
  assert(!has(r,c.romaji) && !has(r,c.meaning));
  for (const auto* note:c.grammarNotes) assert(!has(r,note));
  assert(has(r,I18N.get(StrId::STR_JP_SENTENCES_PROMPT)));
  assert(has(r,I18N.get(StrId::STR_JP_SENTENCES_SESSION)));
  assert(r.displays == 1 && a.routingReady());
}
''')

    def test_reveal_toggles_all_six_correct_explanations_in_each_locale(self):
        self.run_cpp(r'''
int main() {
  for (int language : {0,1,2}) {
    I18N.language = language;
    japanese::review::resetStore();
    GfxRenderer r; MappedInputManager input; JapaneseSentencesActivity a(r,input);
    a.onEnter();
    for (int i = 0; i < 6; ++i) {
      const auto& c = japanese::sentences::cards[i];
      paint(a);
      assert(has(r,c.japanese) && !has(r,c.romaji) && !has(r,c.meaning));
      for (const auto* note:c.grammarNotes) assert(!has(r,note));
      a.action(2); paint(a);
      assert(a.lesson_.revealed());
      assert(has(r,c.kanaReading) && has(r,c.romaji) && has(r,c.meaning));
      int kanaLines = 0;
      for (const auto& d:r.draws) if (d.text == c.kanaReading) ++kanaLines;
      assert(kanaLines == 2); // sentence + its explicit kana reading
      assert(has(r,c.grammarNotes[0]) && has(r,c.grammarNotes[1]));
      assert(find(r,c.grammarNotes[1]).y >= find(r,c.grammarNotes[0]).y+r.smallHeight+12);
      assert(!has(r,I18N.get(StrId::STR_JP_SENTENCES_PROMPT)));
      for (int other = 0; other < 6; ++other) {
        if (other != i) {
          assert(!has(r,japanese::sentences::cards[other].romaji));
          assert(!has(r,japanese::sentences::cards[other].meaning));
        }
      }
      a.action(2); paint(a);
      assert(!has(r,c.romaji) && !has(r,c.meaning));
      a.action(2); a.action(3);
      if (i < 5) assert(a.lesson_.position() == i+1 && !a.lesson_.revealed());
      else assert(a.lesson_.position() == 5 && a.lesson_.revealed());
    }
  }
}
''')

    def test_physical_confirm_navigation_edges_and_back(self):
        self.run_cpp(r'''
int main() {
  GfxRenderer r; MappedInputManager input; JapaneseSentencesActivity a(r,input);
  a.onEnter(); paint(a); using B = MappedInputManager::Button;
  release(a,input,B::Left); assert(a.lesson_.position() == 0);
  for (int i = 0; i < 5; ++i) {
    release(a,input,B::Confirm); assert(a.lesson_.revealed());
    release(a,input,B::Right); assert(a.lesson_.position() == i+1 && !a.lesson_.revealed());
  }
  release(a,input,B::Confirm); release(a,input,B::Right);
  assert(a.lesson_.position() == 5 && a.lesson_.revealed());
  for (int i = 5; i > 0; --i) {
    release(a,input,B::Left); assert(a.lesson_.position() == i-1 && !a.lesson_.revealed());
  }
  a.action(-100); a.action(100); assert(a.lesson_.position() == 0 && !a.lesson_.revealed());
  release(a,input,B::Back); assert(a.finishes == 1 && !a.routingReady());
}
''')

    def test_touch_reveal_hide_navigation_and_disabled_edges(self):
        self.run_cpp(r'''
int main() {
  GfxRenderer r; MappedInputManager input; JapaneseSentencesActivity a(r,input);
  a.onEnter(); paint(a);
  const auto gray = int(fui::Color::LightGray);
  assert(find(r,I18N.get(StrId::STR_KANA_PREV)).color == gray);
  tapLabel(a,input,r,StrId::STR_KANA_PREV); assert(a.lesson_.position() == 0);
  for (int i = 0; i < 5; ++i) {
    tapLabel(a,input,r,StrId::STR_JP_SENTENCES_REVEAL); assert(a.lesson_.revealed());
    tapLabel(a,input,r,StrId::STR_JP_SENTENCES_HIDE); assert(!a.lesson_.revealed());
    tapLabel(a,input,r,StrId::STR_JP_SENTENCES_REVEAL);
    tapLabel(a,input,r,StrId::STR_KANA_NEXT);
    assert(a.lesson_.position() == i+1 && !a.lesson_.revealed());
  }
  paint(a); assert(find(r,I18N.get(StrId::STR_KANA_NEXT)).color == gray);
  tapLabel(a,input,r,StrId::STR_JP_SENTENCES_REVEAL);
  tapLabel(a,input,r,StrId::STR_KANA_NEXT);
  assert(a.lesson_.position() == 5 && a.lesson_.revealed());
  for (int i = 5; i > 0; --i) {
    tapLabel(a,input,r,StrId::STR_KANA_PREV);
    assert(a.lesson_.position() == i-1 && !a.lesson_.revealed());
  }
  tapLabel(a,input,r,StrId::STR_BACK); assert(a.finishes == 1 && !a.routingReady());
}
''')

    def test_touch_press_release_feedback_updates_and_physical_back_priority(self):
        self.run_cpp(r'''
int main() {
  GfxRenderer r; MappedInputManager input; JapaneseSentencesActivity a(r,input);
  a.onEnter(); paint(a);
  auto d = find(r,I18N.get(StrId::STR_JP_SENTENCES_REVEAL));
  int before = a.updates;
  touch(a,input,d.x+d.width/2,d.y+d.height/2,true);
  assert(!a.lesson_.revealed() && a.app.touchActive() && a.updates > before);
  paint(a);
  before = a.updates;
  touch(a,input,2,2); // cancel release outside any control
  assert(!a.app.touchActive() && !a.lesson_.revealed() && a.updates > before);
  paint(a); d = find(r,I18N.get(StrId::STR_JP_SENTENCES_REVEAL));
  input.touch.touchReleased = true;
  input.touch.touchX = d.x+d.width/2; input.touch.touchY = d.y+d.height/2;
  input.released[int(MappedInputManager::Button::Back)] = true;
  a.loop(); assert(a.finishes == 1 && !a.lesson_.revealed() && !a.routingReady());
}
''')

    def test_layout_no_overlap_and_four_large_separated_touch_rects(self):
        self.run_cpp(r'''
int main() {
  for (int language : {0,1,2}) for (int height : {800,900}) for (int lineHeight : {24,36}) {
    I18N.language = language;
    japanese::review::resetStore();
    GfxRenderer r; r.height = height; r.smallHeight = lineHeight;
    MappedInputManager input; JapaneseSentencesActivity a(r,input); a.onEnter();
    for (int i = 0; i < 6; ++i) {
      for (bool revealed : {false,true}) {
        if (a.lesson_.revealed() != revealed) a.action(2);
        paint(a);
        assert(r.boxes.size() == 4 && !a.app.interactionOverflowed());
        int controlsTop = r.height;
        for (size_t n = 0; n < r.boxes.size(); ++n) {
          const auto b = r.boxes[n].rect;
          controlsTop = std::min(controlsTop,int(b.y));
          assert(b.width >= 44 && b.height >= 44 && b.x >= 12 && b.right() <= r.width-12);
          assert(b.y >= 58 && b.bottom() <= r.height-12);
          for (size_t m = n+1; m < r.boxes.size(); ++m) {
            const auto c = r.boxes[m].rect;
            assert(b.right()+6 <= c.x || c.right()+6 <= b.x || b.bottom()+6 <= c.y || c.bottom()+6 <= b.y);
          }
        }
        const auto& c = japanese::sentences::cards[i];
        for (const auto& d:r.draws) {
          assert(d.x >= 12 && d.x+d.width <= r.width-12 && d.y+d.height <= r.height-12);
          bool inButton = false;
          for (const auto& box:r.boxes) {
            const auto b = box.rect;
            if (d.y >= b.y && d.y < b.bottom() && d.x >= b.x && d.x < b.right()) {
              assert(d.x >= b.x && d.x+d.width <= b.right() && d.y+d.height <= b.bottom());
              inButton = true;
            }
          }
          if (!inButton && d.text != I18N.get(StrId::STR_JP_SENTENCES_SESSION)) {
            assert(d.y+d.height+12 <= controlsTop);
          }
        }
        if (revealed) assert(find(r,c.grammarNotes[1]).y+r.smallHeight+12 <= controlsTop);
      }
      a.action(3);
    }
  }
}
''')

    def test_portrait_font_cleanup_restore_orientation_resume_and_progress(self):
        self.run_cpp(r'''
int main() {
  for (auto orientation : {GfxRenderer::Orientation::LandscapeClockwise,
                           GfxRenderer::Orientation::LandscapeCounterClockwise,
                           GfxRenderer::Orientation::PortraitInverted}) {
    japanese::review::resetStore();
    GfxRenderer r; r.orientation = orientation;
    MappedInputManager input; JapaneseSentencesActivity a(r,input);
    a.onEnter(); paint(a);
    assert(a.entries == 1 && r.orientation == GfxRenderer::Orientation::Portrait);
    assert(r.fonts.count(0x4A53001C) && has(r,I18N.get(StrId::STR_JP_SENTENCES)) && has(r,"1 / 6"));
    a.action(2); a.action(3); paint(a); assert(has(r,"2 / 6"));
    a.onExit();
    assert(r.orientation == orientation && !r.fonts.count(0x4A53001C) && !a.routingReady() && a.exits == 1);
    a.onEnter(); paint(a); assert(a.lesson_.position() == 1 && !a.lesson_.revealed() && has(r,"2 / 6"));
    a.onExit();
  }
  GfxRenderer r; int data = 28; EpdFont font(&data); EpdFontFamily family(&font);
  r.insertFont(0x4A53001C,family);
  MappedInputManager input; JapaneseSentencesActivity a(r,input);
  a.onEnter(); a.onExit(); assert(r.fonts.count(0x4A53001C));
}
''')

    def test_inherited_confirm_is_consumed_touch_is_independent_back_still_exits(self):
        self.run_cpp(r'''
int main() {
  GfxRenderer r; MappedInputManager input; using B = MappedInputManager::Button;
  input.held[int(B::Confirm)] = true;
  JapaneseSentencesActivity a(r,input); a.onEnter(); paint(a);
  a.loop(); assert(!a.lesson_.revealed());
  release(a,input,B::Confirm); assert(!a.lesson_.revealed());
  release(a,input,B::Confirm); assert(a.lesson_.revealed());
  release(a,input,B::Confirm); assert(!a.lesson_.revealed());
  a.onExit();
  input.held[int(B::Confirm)] = true; a.onEnter(); paint(a);
  auto d = find(r,I18N.get(StrId::STR_JP_SENTENCES_REVEAL));
  input.touch.touchReleased = true; input.touch.touchX = d.x+d.width/2; input.touch.touchY = d.y+d.height/2;
  a.loop(); assert(a.lesson_.revealed());
  input.touch = {}; input.released[int(B::Back)] = true;
  a.loop(); assert(a.finishes == 1 && !a.routingReady());
}
''')

    def test_dedicated_notes_font_renders_all_japanese_and_cjk_lesson_fields(self):
        self.run_cpp(r'''
int main() {
  GfxRenderer r; MappedInputManager input; JapaneseSentencesActivity a(r,input);
  a.onEnter(); assert(r.fonts.count(0x4A53100C));
  for (int i = 0; i < 6; ++i) {
    a.action(2); paint(a);
    const auto& c = japanese::sentences::cards[i];
    for (const auto* value : {c.romaji,c.meaning,c.grammarNotes[0],c.grammarNotes[1]})
      assert(find(r,value).font == 0x4A53100C);
    bool kanaWithNotesFont = false;
    for (const auto& d:r.draws)
      if (d.text == c.kanaReading && d.font == 0x4A53100C) kanaWithNotesFont = true;
    assert(kanaWithNotesFont);
    a.action(3);
  }
  a.onExit(); assert(!r.fonts.count(0x4A53100C));
  int data = 12; EpdFont font(&data); EpdFontFamily family(&font);
  r.insertFont(0x4A53100C,family);
  a.onEnter(); a.onExit(); assert(r.fonts.count(0x4A53100C) && !r.fonts.count(0x4A53001C));
}
''')

    def test_inherited_confirm_release_clears_barrier_even_during_touch(self):
        self.run_cpp(r'''
int main() {
  GfxRenderer r; MappedInputManager input; using B = MappedInputManager::Button;
  input.held[int(B::Confirm)] = true;
  JapaneseSentencesActivity a(r,input); a.onEnter(); paint(a);
  auto d = find(r,I18N.get(StrId::STR_JP_SENTENCES_REVEAL));
  input.clear(); input.released[int(B::Confirm)] = true;
  input.touch.touchReleased = true; input.touch.touchX = d.x+d.width/2; input.touch.touchY = d.y+d.height/2;
  a.loop(); assert(a.lesson_.revealed()); // touch is independent; no extra physical toggle
  release(a,input,B::Confirm); assert(!a.lesson_.revealed()); // a fresh gesture must not be swallowed
}
''')

if __name__ == '__main__':
    unittest.main()
