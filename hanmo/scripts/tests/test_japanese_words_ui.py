"""Runtime tests: real Words Activity + UiAppHost + FreeInkApp/Screen/interaction routing.
Only hardware renderer, input snapshot, I18n and Activity lifecycle are host seams.
No replacement screen builder or lesson implementation is used.
"""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
INCLUDE = ROOT / "src/activities/apps/japanese"
FUI = ROOT / "freeink-sdk/libs/ui/FreeInkUI/include"
BUILD = ROOT / "build/japanese-words-child/ui"

STUBS = {
    "EpdFontFamily.h": r'''
#pragma once
struct EpdFont { explicit EpdFont(const int*) {} };
struct EpdFontFamily { explicit EpdFontFamily(const EpdFont*) {} };
''',
    "builtinFonts/hanmo_words_44.h": "#pragma once\ninline int hanmo_words_44 = 44;\n",
    "fontIds.h": "#pragma once\ninline constexpr int SMALL_FONT_ID = 1;\n",
    "activities/Activity.h": r'''
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
struct Draw { int font, x, y, width, height; std::string text; };
struct Rect { int x, y, width, height; };
struct TextBlock { Rect rect; std::string text; };
class GfxRenderer {
 public:
  enum class Orientation { Portrait, LandscapeClockwise, PortraitInverted, LandscapeCounterClockwise };
  mutable std::vector<Draw> draws;
  mutable std::vector<TextBlock> blocks;
  std::map<int, EpdFontFamily> fonts;
  Orientation orientation = Orientation::LandscapeClockwise;
  int width = 480, height = 800, displays = 0;
  Orientation getOrientation() const { return orientation; }
  void setOrientation(Orientation o) { orientation = o; }
  int getScreenWidth() const { return width; }
  int getScreenHeight() const { return height; }
  const auto& getFontMap() const { return fonts; }
  void insertFont(int id, const EpdFontFamily& f) { fonts.emplace(id, f); }
  void removeFont(int id) { fonts.erase(id); }
  static int glyphCount(const char* s) {
    int n = 0; for (; *s; ++s) if ((static_cast<unsigned char>(*s) & 0xC0) != 0x80) ++n;
    return n;
  }
  int getTextWidth(int font, const char* s) const {
    return glyphCount(s) * (font == 0x4A52002C ? 88 : 12);
  }
  int getLineHeight(int font) const { return font == 0x4A52002C ? 96 : 24; }
  void drawText(int font, int x, int y, const char* text) const {
    if (text && *text) draws.push_back({font,x,y,getTextWidth(font,text),getLineHeight(font),text});
  }
  void drawCenteredText(int font, int y, const char* text) const {
    drawText(font, (width-getTextWidth(font,text))/2, y, text);
  }
  void clearScreen() { draws.clear(); blocks.clear(); }
  void displayBuffer() { ++displays; }
};
class MappedInputManager {
 public:
  enum class Button { Back, Confirm, Left, Right, Up, Down };
  std::array<bool,6> released{}, held{};
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
  Activity(const char*, GfxRenderer& r, MappedInputManager& m) : renderer(r), mappedInput(m) {}
  virtual ~Activity() = default;
  virtual void onEnter() { ++entries; }
  virtual void onExit() { ++exits; }
  virtual void loop() {}
  virtual void render(RenderLock&&) {}
  virtual void requestUpdate(bool = false) { ++updates; }
  void finish() { ++finishes; }
};
''',
    "components/UITheme.h": r'''
#pragma once
#include "activities/Activity.h"
class BaseTheme {
 public:
  void drawHeader(GfxRenderer& r, const Rect&, const char* title, const char* progress) const {
    r.drawText(1,12,5,title); r.drawText(1,260,5,progress);
  }
};
class UITheme {
 public:
  struct Metrics { int topPadding = 5, headerHeight = 45; };
  static UITheme& getInstance() { static UITheme theme; return theme; }
  const Metrics& getMetrics() const { static Metrics metrics; return metrics; }
  const BaseTheme& getTheme() const { static BaseTheme theme; return theme; }
};
#define GUI UITheme::getInstance().getTheme()
''',
    "FreeInkUIGfxRenderer.h": r'''
#pragma once
#include "activities/Activity.h"
namespace freeink::ui {
class GfxRendererTarget : public DrawTarget {
  const GfxRenderer& r;
 public:
  explicit GfxRendererTarget(const GfxRenderer& renderer) : r(renderer) {}
  DeviceContext deviceContext() const {
    DeviceContext d; d.width = r.getScreenWidth(); d.height = r.getScreenHeight();
    d.hasTouch = true; d.minTouchSize = 44; return d;
  }
  Size measureText(FontId font, const char* s, TextStyle) const override {
    return Size{int16_t(r.getTextWidth(font,s)), int16_t(r.getLineHeight(font))};
  }
  int16_t lineHeight(FontId font) const override { return r.getLineHeight(font); }
  void fill(freeink::ui::Rect, Paint, uint8_t = 0, uint8_t = CornersAll) override {}
  void stroke(freeink::ui::Rect, Paint, uint8_t, uint8_t = 0, uint8_t = CornersAll) override {}
  void line(Point, Point, uint8_t, Paint) override {}
  void triangle(Point, Point, Point, Paint) override {}
  void bitmap(freeink::ui::Rect, BitmapRef, BitmapMode, Paint = Paint::solid(Color::Black), Rotation = Rotation::None) override {}
  void text(freeink::ui::Rect rect, const char* value, TextStyle style) override {
    r.blocks.push_back({{rect.x,rect.y,rect.width,rect.height}, value ? value : ""});
    // Exercise SDK wrapping/alignment too, capturing the actual emitted lines.
    layoutText(*this, rect, value, style, [&](const char* line, freeink::ui::Rect row) {
      r.drawText(style.font, row.x, row.y, line);
    });
  }
};
}
''',
    "UiAppHelpers.h": r'''
#pragma once
#include "components/UiAppHost.h"
#include "activities/Activity.h"
inline freeink::ui::GfxRendererTarget makeUiTarget(const GfxRenderer& r) { return freeink::ui::GfxRendererTarget(r); }
inline void refreshSharedUiThemeTokens(const freeink::ui::GfxRendererTarget&) {}
template <typename App> void applySharedUiTheme(App& app, const freeink::ui::GfxRendererTarget&) {
  auto theme = freeink::ui::themeTokensForLineHeight(24);
  theme.minTouchSize = 44; theme.smallText.font = 1; theme.bodyText.font = 1;
  app.setTheme(theme);
}
inline freeink::ui::InputSnapshot touchSnapshotFrom(const MappedInputManager& input, bool = false) {
  return input.touch; // coordinates already mapped, just like the firmware adapter's result
}
''',
    "I18n.h": r'''
#pragma once
enum class StrId {
  STR_JP_WORDS, STR_BACK, STR_JP_WORDS_PROMPT, STR_JP_WORDS_SESSION, STR_JP_WORDS_DONE,
  STR_KANA_QUIZ_REVEAL, STR_KANA_QUIZ_KNOWN, STR_KANA_QUIZ_AGAIN, STR_KANA_QUIZ_RESTART,
  STR_KANA_QUIZ_REVIEW, STR_KANA_QUIZ_FIRST, STR_KANA_QUIZ_DONE, STR_KANA_QUIZ_SESSION
};
struct I18n {
  static I18n& getInstance() { static I18n i; return i; }
  const char* get(StrId id) const {
    switch (id) {
      case StrId::STR_JP_WORDS: return "單字卡";
      case StrId::STR_BACK: return "返回";
      case StrId::STR_JP_WORDS_PROMPT: return "回想這個單字的意思";
      case StrId::STR_JP_WORDS_SESSION: return "單字結果只留在本次，不保存";
      case StrId::STR_JP_WORDS_DONE: return "本次單字已練完";
      case StrId::STR_KANA_QUIZ_REVEAL: return "看答案";
      case StrId::STR_KANA_QUIZ_KNOWN: return "會";
      case StrId::STR_KANA_QUIZ_AGAIN: return "再練";
      case StrId::STR_KANA_QUIZ_RESTART: return "重新測驗";
      case StrId::STR_KANA_QUIZ_REVIEW: return "重練";
      case StrId::STR_KANA_QUIZ_FIRST: return "第一輪會";
      case StrId::STR_KANA_QUIZ_DONE: return "本次已練完";
      case StrId::STR_KANA_QUIZ_SESSION: return "測驗結果不保存";
    }
    return "";
  }
};
#define I18N I18n::getInstance()
''',
}

PREFIX = r'''
#include <cstdio>
#include <iostream>
#include "activities/Activity.h"
#include "components/UiAppHost.h"
#include "I18n.h"
#include "KanaData.generated.h"
#define private public
#define protected public
#include "JapaneseWordsActivity.h"
#undef protected
#undef private
namespace fui = freeink::ui;
bool has(const GfxRenderer& r, const char* text) {
  for (const auto& draw : r.draws) if (draw.text == text) return true;
  return false;
}
const Draw& find(const GfxRenderer& r, const char* text) {
  for (const auto& draw : r.draws) if (draw.text == text) return draw;
  assert(false && "required rendered text missing");
  return r.draws.front();
}
void paint(JapaneseWordsActivity& activity) { activity.render(RenderLock(activity)); }
void release(JapaneseWordsActivity& activity, MappedInputManager& input, MappedInputManager::Button b) {
  input.clear(); input.released[static_cast<int>(b)] = true; activity.loop(); input.clear();
}
void tap(JapaneseWordsActivity& activity, MappedInputManager& input, int x, int y) {
  input.clear(); input.touch.touchReleased = true; input.touch.touchX = x; input.touch.touchY = y;
  activity.loop(); input.clear();
}
Rect buttonRect(const GfxRenderer& r, StrId id) {
  for (const auto& block : r.blocks) if (block.text == I18N.get(id)) {
    const auto a = block.rect;
    return Rect{a.x-4,a.y-2,a.width+8,a.height+4};
  }
  assert(false && "required button missing"); return {};
}
void tapButton(JapaneseWordsActivity& activity, MappedInputManager& input, const GfxRenderer& r, StrId id) {
  const auto a = buttonRect(r,id);
  tap(activity,input,a.x+a.width/2,a.y+a.height/2);
}
'''


class JapaneseWordsRuntimeTests(unittest.TestCase):
    def run_cpp(self, source):
        directory = BUILD / self._testMethodName
        directory.mkdir(parents=True, exist_ok=True)
        for name, contents in STUBS.items():
            target = directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(contents, encoding="utf-8")
        # Unmodified real host implementation. Relocation only selects the HAL seams.
        host = directory / "UiAppHost.cpp"
        host.write_bytes((ROOT / "src/components/UiAppHost.cpp").read_bytes())
        cpp, exe = directory / "main.cpp", directory / "runtime"
        cpp.write_text(PREFIX + source, encoding="utf-8")
        command = ["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", str(directory),
                   "-I", str(ROOT / "src"), "-I", str(ROOT / "src/components"), "-I", str(INCLUDE), "-I", str(FUI),
                   str(cpp), str(INCLUDE / "JapaneseWordsActivity.cpp"), str(host),
                   str(FUI.parent / "src/FreeInkUI.cpp"), "-o", str(exe)]
        compiled = subprocess.run(command, capture_output=True, text=True)
        (directory / "compile.log").write_text(" ".join(command) + "\n" + compiled.stdout + compiled.stderr, encoding="utf-8")
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        run = subprocess.run([str(exe)], capture_output=True, text=True)
        (directory / "runtime.log").write_text(run.stdout + run.stderr, encoding="utf-8")
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_all_45_fronts_hide_answers_reveal_real_reading_meaning(self):
        self.run_cpp(r'''
int main() {
  GfxRenderer r; MappedInputManager input; JapaneseWordsActivity activity(r,input);
  activity.onEnter();
  for (int i = 0; i < 45; ++i) {
    const auto& card = kana::cards[i < 44 ? i : 45];
    paint(activity);
    assert(has(r,card.example));
    char progress[24]; std::snprintf(progress,sizeof(progress),"%d / 45",i+1);
    const std::array<std::string,7> allowed{card.example,progress,I18N.get(StrId::STR_JP_WORDS),
      I18N.get(StrId::STR_JP_WORDS_PROMPT),I18N.get(StrId::STR_JP_WORDS_SESSION),
      I18N.get(StrId::STR_BACK),I18N.get(StrId::STR_KANA_QUIZ_REVEAL)};
    int wordDraws = 0;
    for (const auto& draw : r.draws) {
      assert(std::find(allowed.begin(),allowed.end(),draw.text) != allowed.end());
      wordDraws += draw.text == card.example;
      std::cout << "FRONT " << i << '\t' << draw.font << '\t' << draw.x << ',' << draw.y << '\t' << draw.text << '\n';
    }
    assert(wordDraws == 1);
    assert(has(r,I18N.get(StrId::STR_JP_WORDS_PROMPT)));
    assert(!has(r,card.meaning) && !has(r,card.exampleRomaji));
    for (const auto* secret : {card.hiragana, card.katakana, card.romaji, card.soundHint})
      if (std::strcmp(secret,card.example) != 0) assert(!has(r,secret));
    const auto& word = find(r,card.example);
    assert(word.font == 0x4A52002C);
    assert(word.x == (r.width-word.width)/2 && word.x >= 12 && word.x+word.width <= r.width-12);
    activity.action(2); activity.action(3); // stale Known / Again while hidden
    assert(activity.lesson_.position() == i && !activity.lesson_.revealed());
    activity.action(1); paint(activity);
    assert(has(r,card.example) && has(r,card.exampleRomaji) && has(r,card.meaning));
    for (const auto& draw : r.draws)
      std::cout << "REVEAL " << i << '\t' << draw.font << '\t' << draw.x << ',' << draw.y << '\t' << draw.text << '\n';
    assert(find(r,card.exampleRomaji).font == 1 && find(r,card.meaning).font == 1);
    assert(!has(r,I18N.get(StrId::STR_JP_WORDS_PROMPT)));
    activity.action(2);
  }
  assert(activity.lesson_.done() && activity.lesson_.firstKnown() == 45);
}
''')

    def test_portrait_lifecycle_releases_only_owned_font_session(self):
        self.run_cpp(r'''
int main() {
  for (auto orientation : {GfxRenderer::Orientation::LandscapeClockwise,
                           GfxRenderer::Orientation::PortraitInverted,
                           GfxRenderer::Orientation::LandscapeCounterClockwise}) {
    GfxRenderer r; r.orientation = orientation;
    MappedInputManager input; JapaneseWordsActivity activity(r,input);
    activity.onEnter();
    assert(activity.entries == 1 && activity.updates > 0);
    assert(r.getOrientation() == GfxRenderer::Orientation::Portrait);
    assert(r.getFontMap().count(0x4A52002C) == 1);
    paint(activity); assert(activity.routingReady());
    activity.action(1); activity.action(2);
    activity.onExit();
    assert(r.getOrientation() == orientation && activity.exits == 1);
    assert(!activity.routingReady() && !r.getFontMap().count(0x4A52002C));
    activity.onEnter();
    assert(activity.lesson_.position() == 0 && activity.lesson_.firstKnown() == 0);
    activity.onExit();
  }
  GfxRenderer r; int data = 44; EpdFont font(&data); EpdFontFamily family(&font);
  r.insertFont(0x4A52002C,family);
  MappedInputManager input; JapaneseWordsActivity activity(r,input);
  activity.onEnter(); activity.onExit();
  assert(r.getFontMap().count(0x4A52002C) == 1); // do not unregister a pre-existing family
}
''')

    def test_physical_reveal_again_known_back_finish_restart(self):
        self.run_cpp(r'''
int main() {
  GfxRenderer r; MappedInputManager input; JapaneseWordsActivity activity(r,input);
  activity.onEnter(); paint(activity);
  using B = MappedInputManager::Button;
  release(activity,input,B::Left); release(activity,input,B::Right);
  assert(activity.lesson_.position() == 0 && !activity.lesson_.revealed());
  release(activity,input,B::Confirm);
  assert(activity.lesson_.revealed());
  release(activity,input,B::Left);
  assert(activity.lesson_.position() == 1 && !activity.lesson_.revealed());
  release(activity,input,B::Right); // hidden remains unmarked
  assert(activity.lesson_.position() == 1);
  release(activity,input,B::Confirm); release(activity,input,B::Right);
  assert(activity.lesson_.position() == 2 && activity.lesson_.firstKnown() == 1);
  for (int i = 2; i < 45; ++i) {
    release(activity,input,B::Confirm); release(activity,input,B::Confirm);
  }
  assert(activity.lesson_.round() == 2 && activity.lesson_.size() == 1);
  assert(activity.lesson_.current() == 0 && activity.lesson_.firstKnown() == 44);
  release(activity,input,B::Confirm); release(activity,input,B::Confirm);
  assert(activity.lesson_.done() && activity.lesson_.firstKnown() == 44);
  release(activity,input,B::Confirm);
  assert(!activity.lesson_.done() && !activity.lesson_.revealed());
  assert(activity.lesson_.position() == 0 && activity.lesson_.firstKnown() == 0);
  release(activity,input,B::Back); assert(activity.finishes == 1);
}
''')

    def test_inherited_confirm_hold_release_is_consumed(self):
        self.run_cpp(r'''
int main() {
  GfxRenderer r; MappedInputManager input;
  using B = MappedInputManager::Button;
  input.held[static_cast<int>(B::Confirm)] = true;
  JapaneseWordsActivity activity(r,input); activity.onEnter(); paint(activity);
  activity.loop(); assert(!activity.lesson_.revealed());
  release(activity,input,B::Confirm); assert(!activity.lesson_.revealed());
  release(activity,input,B::Confirm); assert(activity.lesson_.revealed());
  release(activity,input,B::Back); assert(activity.finishes == 1);
  input.held[static_cast<int>(B::Confirm)] = true;
  JapaneseWordsActivity touched(r,input); touched.onEnter(); paint(touched);
  tapButton(touched,input,r,StrId::STR_KANA_QUIZ_REVEAL);
  assert(touched.lesson_.revealed()); // touch independent of inherited physical hold
  release(touched,input,B::Confirm);
  assert(touched.lesson_.revealed() && touched.lesson_.position() == 0);
  release(touched,input,B::Confirm);
  assert(!touched.lesson_.revealed() && touched.lesson_.position() == 1);
}
''')


    def test_touch_dispatch_enabled_guards_stale_event_return_invalidation(self):
        self.run_cpp(r'''
int main() {
  GfxRenderer r; MappedInputManager input; JapaneseWordsActivity activity(r,input);
  activity.onEnter(); paint(activity);
  assert(has(r,I18N.get(StrId::STR_BACK)) && has(r,I18N.get(StrId::STR_KANA_QUIZ_REVEAL)));
  assert(!has(r,I18N.get(StrId::STR_KANA_QUIZ_KNOWN)) && !has(r,I18N.get(StrId::STR_KANA_QUIZ_AGAIN)));
  assert(!activity.app.interactionOverflowed());
  activity.action(4); assert(activity.lesson_.position() == 0);
  tapButton(activity,input,r,StrId::STR_KANA_QUIZ_REVEAL);
  assert(activity.app.lastEvent().value == 1 && activity.lesson_.revealed());
  paint(activity);
  assert(!has(r,I18N.get(StrId::STR_KANA_QUIZ_REVEAL)));
  const auto back = buttonRect(r,StrId::STR_BACK);
  const auto again = buttonRect(r,StrId::STR_KANA_QUIZ_AGAIN);
  const auto known = buttonRect(r,StrId::STR_KANA_QUIZ_KNOWN);
  for (const auto a : {back,again,known}) {
    assert(a.width >= 44 && a.height >= 44 && a.x >= 12 && a.x+a.width <= r.width-12);
    assert(a.y+a.height <= r.height-12);
  }
  assert(again.x-back.x-back.width >= 6 && known.x-again.x-again.width >= 6);
  tapButton(activity,input,r,StrId::STR_KANA_QUIZ_KNOWN);
  assert(activity.app.lastEvent().value == 2 && activity.lesson_.position() == 1 && !activity.lesson_.revealed());
  const int beforeStale = activity.updates;
  // Still routes through the last published answer table; must NOT mark the new hidden word.
  tap(activity,input,known.x+known.width/2,known.y+known.height/2);
  assert(activity.lesson_.position() == 1 && activity.lesson_.firstKnown() == 1);
  assert(activity.updates > beforeStale); // engine invalidated after rejected event: clear pressed/flash UI
  paint(activity);
  tapButton(activity,input,r,StrId::STR_KANA_QUIZ_REVEAL); paint(activity);
  tapButton(activity,input,r,StrId::STR_KANA_QUIZ_AGAIN);
  assert(activity.app.lastEvent().value == 3 && activity.lesson_.position() == 2 && !activity.lesson_.revealed());
  paint(activity);
  input.touch.touchReleased = true; input.touch.touchX = 300; input.touch.touchY = 760;
  input.released[static_cast<int>(MappedInputManager::Button::Back)] = true;
  activity.loop(); input.clear();
  assert(activity.finishes == 1 && activity.lesson_.position() == 2 && !activity.lesson_.revealed());
  assert(!activity.routingReady()); // Back won over simultaneous Reveal tap
}
''')


    def test_header_progress_retry_round_done_score_session_restart(self):
        self.run_cpp(r'''
int main() {
  GfxRenderer r; MappedInputManager input; JapaneseWordsActivity activity(r,input);
  activity.onEnter(); paint(activity);
  assert(has(r,"1 / 45") && has(r,I18N.get(StrId::STR_JP_WORDS)));
  for (int i = 0; i < 45; ++i) { activity.action(1); activity.action(i == 0 ? 3 : 2); }
  paint(activity);
  assert(has(r,"重練 1   1 / 1") && has(r,"あめ") && !has(r,"ame") && !has(r,"雨"));
  activity.action(1); activity.action(3); paint(activity);
  assert(has(r,"重練 2   1 / 1"));
  activity.action(1); activity.action(2); paint(activity);
  assert(has(r,I18N.get(StrId::STR_JP_WORDS_DONE)) && has(r,"第一輪會 44 / 45"));
  assert(has(r,I18N.get(StrId::STR_JP_WORDS_SESSION)));
  assert(!has(r,"あめ") && !has(r,"ame") && !has(r,"雨"));
  assert(!has(r,I18N.get(StrId::STR_KANA_QUIZ_KNOWN)) && !has(r,I18N.get(StrId::STR_KANA_QUIZ_AGAIN)));
  tapButton(activity,input,r,StrId::STR_KANA_QUIZ_RESTART); paint(activity);
  assert(!activity.lesson_.done() && activity.lesson_.position() == 0 && activity.lesson_.firstKnown() == 0);
  assert(has(r,"1 / 45") && !has(r,"ame") && !has(r,"雨"));
  tapButton(activity,input,r,StrId::STR_BACK); assert(activity.finishes == 1);
}
''')

    def test_portrait_widths_body_font_center_spacing_session_fit(self):
        self.run_cpp(r'''
int main() {
  for (int width : {480,400}) {
    GfxRenderer r; r.width = width; MappedInputManager input; JapaneseWordsActivity activity(r,input);
    activity.onEnter(); paint(activity);
    auto back = buttonRect(r,StrId::STR_BACK), reveal = buttonRect(r,StrId::STR_KANA_QUIZ_REVEAL);
    assert(back.width >= 44 && reveal.width >= 44 && back.height >= 44 && reveal.height >= 44);
    assert(back.x >= 12 && reveal.x+reveal.width <= width-12 && reveal.x-back.x-back.width >= 6);
    activity.action(1); paint(activity);
    back = buttonRect(r,StrId::STR_BACK);
    const auto again = buttonRect(r,StrId::STR_KANA_QUIZ_AGAIN), known = buttonRect(r,StrId::STR_KANA_QUIZ_KNOWN);
    assert(again.width >= 44 && known.width >= 44 && known.height >= 44);
    assert(again.x-back.x-back.width >= 6 && known.x-again.x-again.width >= 6);
    assert(known.x+known.width <= width-12 && known.y+known.height <= r.height-12);
    const auto& word = find(r,"あめ");
    const auto& reading = find(r,"ame"); const auto& meaning = find(r,"雨");
    assert(word.y >= 58 && reading.y >= word.y+word.height+12);
    assert(meaning.y >= reading.y+reading.height+12);
    const auto& session = find(r,I18N.get(StrId::STR_JP_WORDS_SESSION));
    assert(meaning.y+meaning.height+12 <= session.y && session.y+session.height+6 <= known.y);
    assert(reading.x == (width-reading.width)/2 && meaning.x == (width-meaning.width)/2);
  }
}
''')


if __name__ == "__main__":
    unittest.main()
