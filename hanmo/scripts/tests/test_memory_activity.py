"""Compile the actual Activity, Flow, core and screens with hardware-only seams.

FreeInkUI, ToyboxScreen and the paint/reveal gates remain production code.
Activity/Input/renderer/font/shelf seams only record boundary effects; they do
not implement game routing. No firmware build or hardware acceptance implied.
"""
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
GAME_DIR = ROOT / "src/apps_local/memory"
OWNED = ("MemoryActivity.h", "MemoryActivity.cpp", "MemoryFlow.h")

ACTIVITY_BOUNDARY = r'''
#pragma once
#include <memory>
#include <string>
#include <utility>
#include <vector>
#include <cstring>
#include "../../lib/GfxRenderer/RevealedInteractions.h"
namespace fui = freeink::ui;
struct RenderLock {};
struct TextCall { fui::Rect box; std::string value; };
struct StrokeCall { fui::Rect box; uint8_t width; };
class GfxRenderer {
 public:
  fui::DeviceContext device;
  std::vector<TextCall> texts;
  std::vector<StrokeCall> strokes;
  bool autoPaint = true;
  int displays = 0;
  int fonts = 0;
  GfxRenderer() {
    device.width = 480; device.height = 800; device.hasTouch = true;
    device.safeArea = {10, 0, 10, 0};
  }
  void clearScreen() { texts.clear(); strokes.clear(); }
  void displayBuffer() { ++displays; if (autoPaint) paintclock::notePainted(); }
};
class MappedInputManager {
 public:
  enum class Button { Back, Confirm, Up, Down, Left, Right };
  bool back = false, tapped = false;
  int x = 0, y = 0;
  bool wasReleased(Button b) const { return b == Button::Back && back; }
  bool wasScreenTapped(int& tx, int& ty) const {
    if (!tapped) return false;
    tx = x; ty = y; return true;
  }
  struct Labels { const char* btn1; const char* btn2; const char* btn3; const char* btn4; };
  Labels mapLabels(const char* a, const char* b, const char* c, const char* d) const { return {a,b,c,d}; }
};
class Activity {
 protected:
  std::string name;
  GfxRenderer& renderer;
  MappedInputManager& mappedInput;
  paintclock::SurfaceGate surfaceGate;
 public:
  int updates = 0, entries = 0;
  Activity(std::string n, GfxRenderer& r, MappedInputManager& i)
      : name(std::move(n)), renderer(r), mappedInput(i) {}
  virtual ~Activity() = default;
  virtual void onEnter() { ++entries; }
  virtual void loop() {}
  virtual void render(RenderLock&&) {}
  virtual void requestUpdate(bool = false) { ++updates; }
  virtual uint32_t surfaceMeaning() const { return 0; }
  bool surfaceRevealed() const { return surfaceGate.routable(surfaceMeaning()); }
  void noteSurfaceBuilt() { surfaceGate.noteBuilt(surfaceMeaning()); }
};
'''

RENDERER_BOUNDARY = r'''
#pragma once
#include <cassert>
#include "../../activities/Activity.h"
#include "ToyboxScreen.h"
namespace freeink { namespace ui {
class GfxRendererTarget : public DrawTarget {
  GfxRenderer& renderer_;
 public:
  explicit GfxRendererTarget(GfxRenderer& r) : renderer_(r) {}
  DeviceContext deviceContext() const { return renderer_.device; }
  Size measureText(FontId font, const char* text, TextStyle) const override {
    return {static_cast<int16_t>(text ? std::strlen(text) * (font == toybox::kSmallFont ? 7 : 12) : 0),
            lineHeight(font)};
  }
  int16_t lineHeight(FontId font) const override {
    return font == toybox::kSmallFont ? toybox::kTileCut.lineHeight :
           font == toybox::kDisplayFont ? toybox::kDisplayCut.lineHeight : toybox::kUiCut.lineHeight;
  }
  void fill(Rect, Paint, uint8_t, uint8_t) override {}
  void stroke(Rect box, Paint, uint8_t width, uint8_t, uint8_t) override {
    renderer_.strokes.push_back({box, width});
  }
  void line(Point, Point, uint8_t, Paint) override {}
  void triangle(Point, Point, Point, Paint) override {}
  void text(Rect box, const char* value, TextStyle) override {
    renderer_.texts.push_back({box, value ? value : ""});
  }
  void bitmap(Rect, BitmapRef, BitmapMode, Paint, Rotation) override {}
};
}}
namespace toybox {
inline fui::GfxRendererTarget makeTarget(GfxRenderer& renderer) { return fui::GfxRendererTarget(renderer); }
inline void reportOverflow(const Interactions& hits, const char*) { assert(!hits.overflowed()); }
}
'''

HARNESS = r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include <memory>
#include <string>
#include <utility>
#include "MemoryScreens.h"
// Inspect private state without changing the actual production class/API.
#define private public
#include "MemoryActivity.h"
#undef private

namespace mm = memorymatch;
namespace ui = memoryui;
inline int leaveCount = 0;
inline int seedCalls = 0;
inline uint32_t nextSeed = 0x12345678u;
namespace shelf { void leave(GfxRenderer&, MappedInputManager&) { ++leaveCount; } }
namespace toybox { uint32_t seed() { ++seedCalls; return nextSeed++; } }

static bool sameGame(const mm::Game& a, const mm::Game& b) {
  for (int i = 0; i < mm::kMaxCells; ++i)
    if (a.face[i] != b.face[i] || a.matched[i] != b.matched[i]) return false;
  return a.firstPick == b.firstPick && a.secondPick == b.secondPick && a.moves == b.moves &&
         a.matchedPairs == b.matchedPairs && a.level == b.level && a.phase == b.phase;
}
static void draw(MemoryActivity& a) { a.noteSurfaceBuilt(); a.render(RenderLock{}); }
static void tap(MemoryActivity& a, MappedInputManager& input, fui::Rect box) {
  input.tapped = true; input.x = box.x + box.width / 2; input.y = box.y + box.height / 2;
  a.loop(); input.tapped = false;
}
static fui::Rect actionRect(const MemoryActivity& a, fui::ActionId action, int value = 0) {
  for (size_t i = 0; i < a.interactions.count(); ++i) {
    const auto& h = a.interactions.data()[i];
    if (h.action == action && h.value == value) return h.rect;
  }
  assert(false && "screen must register requested control"); return {};
}
static void card(MemoryActivity& a, GfxRenderer& renderer, MappedInputManager& input, int index) {
  tap(a, input, ui::cardRect(renderer.device, a.game, index));
}
static void pressBack(MemoryActivity& a, MappedInputManager& input) {
  input.back = true; a.loop(); input.back = false;
}
static bool hasText(const GfxRenderer& r, const char* value) {
  for (const auto& text : r.texts) if (text.value == value) return true;
  return false;
}
static void start(MemoryActivity& a, GfxRenderer& r, MappedInputManager& input, int level) {
  a.onEnter(); draw(a);
  const uint32_t seed = nextSeed;
  tap(a, input, actionRect(a, ui::ActionLevel, level));
  mm::Game expected{}; mm::start(expected, level, seed);
  assert(sameGame(a.game, expected) && "level action must deliver explicit seed to actual core");
  assert(a.screen == mm::Screen::Board);
  draw(a); assert(hasText(r, "SELECT A CARD"));
}
static void solve(MemoryActivity& a, GfxRenderer& r, MappedInputManager& input) {
  for (int i = 0; i < mm::cellCount(a.game); ++i) {
    if (mm::isMatched(a.game, i)) continue;
    int mate = i + 1;
    while (mate < mm::cellCount(a.game) && mm::faceAt(a.game, mate) != mm::faceAt(a.game, i)) ++mate;
    assert(mate < mm::cellCount(a.game));
    card(a, r, input, i); draw(a); card(a, r, input, mate); draw(a);
  }
  assert(a.screen == mm::Screen::Done && mm::complete(a.game));
}

int main(int argc, char** argv) {
  assert(argc == 2);
  GfxRenderer r; MappedInputManager input;
  auto instance = MemoryActivity::create(r, input);
  assert(instance != nullptr);
  auto& a = static_cast<MemoryActivity&>(*instance);
  const std::string scenario = argv[1];
  if (scenario == "playable") {
    for (int level = 0; level < mm::kLevelCount; ++level) {
      start(a, r, input, level);
      assert(a.selectedLevel == level && a.cursor == mm::kNoCell);
      assert(a.interactions.count() == 1 && a.interactions.count() <= toybox::kMaxInteractions);
      const int beforeUpdates = a.updates;
      card(a, r, input, 0);
      assert(a.game.phase == mm::Phase::OneExposed && a.game.firstPick == 0 && a.game.moves == 0);
      assert(a.cursor == 0 && a.updates == beforeUpdates + 1);
      draw(a);
      const auto inset = ui::cardRect(r.device, a.game, 0).inset(fui::Insets{4,4,4,4});
      bool outlined = false;
      for (const auto& s : r.strokes)
        if (s.box.x == inset.x && s.box.y == inset.y && s.box.width == inset.width &&
            s.box.height == inset.height && s.width == 3) outlined = true;
      assert(outlined && "Activity must pass cursor to real BoardModel");
      const mm::Game before = a.game;
      card(a, r, input, 0); // duplicate is rejected, not a fake pair
      assert(sameGame(a.game, before) && a.updates == beforeUpdates + 1);
      solve(a, r, input);
      assert(a.game.moves == mm::pairCount(a.game));
      assert(a.interactions.count() == 2 && hasText(r, "COMPLETE - TAP AGAIN"));
      pressBack(a, input);
      assert(a.screen == mm::Screen::Menu);
      pressBack(a, input);
    }
    assert(seedCalls == mm::kLevelCount);
    assert(leaveCount == mm::kLevelCount);
    puts("playable: actual Activity level->geometry->core->Done, cursor and bounded real controls OK");
  } else if (scenario == "mismatch") {
    for (int level = 0; level < mm::kLevelCount; ++level) {
      start(a, r, input, level);
      const int seeds = seedCalls;
      const int updates = a.updates;
      a.routeAction(fui::ActionEvent{ui::ActionNext});
      assert(a.updates == updates && a.game.phase == mm::Phase::Ready);
      card(a, r, input, 0); draw(a);
      int wrong = 1;
      while (mm::faceAt(a.game, wrong) == mm::faceAt(a.game, 0)) ++wrong;
      card(a, r, input, wrong); draw(a);
      assert(mm::awaitingMismatch(a.game) && a.game.moves == 1 && a.cursor == wrong);
      assert(hasText(r, "MISMATCH - PRESS NEXT") && a.interactions.count() == 2);
      const mm::Game before = a.game;
      const int blockedUpdates = a.updates;
      for (int repaint = 0; repaint < 3; ++repaint) {
        for (int index = 0; index < mm::cellCount(a.game); ++index) card(a, r, input, index);
        a.loop(); draw(a);
        assert(sameGame(a.game, before) && "card taps/idle/render must not acknowledge mismatch");
        assert(a.updates == blockedUpdates && seedCalls == seeds);
      }
      const auto next = actionRect(a, ui::ActionNext);
      tap(a, input, next);
      assert(a.game.phase == mm::Phase::Ready && a.game.moves == 1);
      assert(a.game.firstPick == mm::kNoCell && a.game.secondPick == mm::kNoCell);
      assert(a.cursor == mm::kNoCell && a.updates == blockedUpdates + 1 && seedCalls == seeds);
      tap(a, input, next); // old NEXT cannot perform another state change
      assert(a.updates == blockedUpdates + 1);
      draw(a); card(a, r, input, wrong);
      assert(a.game.firstPick == wrong && a.game.phase == mm::Phase::OneExposed);
    }
    puts("mismatch: actual Activity holds both faces, blocks cards and acknowledges only explicit NEXT OK");
  } else if (scenario == "navigation") {
    assert(mm::back(mm::Screen::Menu) == mm::Screen::Menu);
    assert(mm::back(mm::Screen::Board) == mm::Screen::Menu);
    assert(mm::back(mm::Screen::Done) == mm::Screen::Menu);
    assert(mm::leavesApp(mm::Screen::Menu));
    assert(!mm::leavesApp(mm::Screen::Board) && !mm::leavesApp(mm::Screen::Done));
    a.onEnter();
    assert(a.entries == 1 && a.updates == 1 && seedCalls == 0 && r.fonts == 1);
    assert(a.screen == mm::Screen::Menu && !a.interactionsReady);
    input.tapped = true; a.loop(); input.tapped = false;
    assert(seedCalls == 0 && a.updates == 1);
    draw(a); pressBack(a, input); assert(leaveCount == 1);
    for (int phase = 0; phase < 3; ++phase) {
      start(a, r, input, 2);
      if (phase == 1) {
        card(a, r, input, 0); draw(a);
        int wrong = 1; while (a.game.face[wrong] == a.game.face[0]) ++wrong;
        card(a, r, input, wrong); draw(a);
      } else if (phase == 2) { solve(a, r, input); }
      const mm::Game before = a.game;
      const int leaves = leaveCount;
      pressBack(a, input);
      assert(a.screen == mm::Screen::Menu && leaveCount == leaves && sameGame(a.game, before));
      assert(a.cursor == mm::kNoCell && !a.interactionsReady);
      draw(a); assert(a.selectedLevel == 2 && a.interactions.count() == mm::kLevelCount);
      pressBack(a, input); assert(leaveCount == leaves + 1);
    }
    for (int phase = 0; phase < 3; ++phase) {
      start(a, r, input, 1);
      if (phase == 1) {
        card(a, r, input, 0); draw(a);
        int wrong = 1; while (a.game.face[wrong] == a.game.face[0]) ++wrong;
        card(a, r, input, wrong); draw(a);
      } else if (phase == 2) { solve(a, r, input); }
      const int leaves = leaveCount;
      tap(a, input, actionRect(a, ui::ActionMenu));
      assert(leaveCount == leaves + 1 && "board MENU must leave to the owning shelf");
    }
    // Back has priority over a simultaneous level tap: one gesture, one action.
    a.onEnter(); draw(a);
    const auto level = actionRect(a, ui::ActionLevel, 0);
    input.tapped = true; input.x = level.x + 1; input.y = level.y + 1;
    const int seeds = seedCalls, leaves = leaveCount;
    pressBack(a, input); input.tapped = false;
    assert(seedCalls == seeds && leaveCount == leaves + 1);
    puts("navigation: actual lifecycle, Back depth and board MENU shelf exits OK");
  } else if (scenario == "again") {
    for (int level = 0; level < mm::kLevelCount; ++level) {
      start(a, r, input, level);
      const int seeds = seedCalls;
      a.routeAction(fui::ActionEvent{ui::ActionAgain});
      assert(seedCalls == seeds);
      solve(a, r, input);
      const uint32_t seed = nextSeed;
      tap(a, input, actionRect(a, ui::ActionAgain));
      mm::Game expected{}; mm::start(expected, level, seed);
      assert(seedCalls == seeds + 1 && sameGame(a.game, expected));
      assert(a.screen == mm::Screen::Board && a.selectedLevel == level && a.cursor == mm::kNoCell);
      draw(a); assert(a.interactions.count() == 1 && hasText(r, "SELECT A CARD"));
    }
    puts("again: fresh explicit seed, same chosen level, counters and picks reset OK");
  } else if (scenario == "reveal") {
    a.onEnter(); draw(a);
    const uint32_t menuMeaning = a.surfaceMeaning();
    tap(a, input, actionRect(a, ui::ActionLevel, 3));
    const uint32_t liveMeaning = a.surfaceMeaning();
    assert(menuMeaning != liveMeaning);
    r.autoPaint = false; draw(a);
    card(a, r, input, 0);
    assert(a.game.phase == mm::Phase::Ready && "new geometry is inert until completed board paint");
    paintclock::notePainted();
    card(a, r, input, 0);
    assert(a.game.phase == mm::Phase::OneExposed && a.surfaceMeaning() == liveMeaning);
    draw(a); // unchanged live geometry must admit the intentional second card mid-repaint
    int wrong = 1; while (a.game.face[wrong] == a.game.face[0]) ++wrong;
    card(a, r, input, wrong);
    assert(mm::awaitingMismatch(a.game) && a.surfaceMeaning() != liveMeaning);
    draw(a); paintclock::notePainted();
    tap(a, input, actionRect(a, ui::ActionNext));
    assert(a.surfaceMeaning() == liveMeaning && a.game.phase == mm::Phase::Ready);
    draw(a); card(a, r, input, wrong);
    assert(a.game.phase == mm::Phase::Ready && "mismatch->live transition needs completed paint");
    paintclock::notePainted(); card(a, r, input, wrong);
    assert(a.game.firstPick == wrong);
    const uint32_t selectedMeaning = a.surfaceMeaning();
    a.cursor = 5; ++a.game.moves;
    assert(a.surfaceMeaning() == selectedMeaning && "cursor/content must not change geometry meaning");
    a.game.level = 0;
    assert(a.surfaceMeaning() != selectedMeaning && "grid level drives the pixel-to-card map");
    puts("reveal: real SurfaceGate blocks unseen menu/level/live changes, admits consecutive picks OK");
  } else { return 2; }
}
'''


def compile_activity(folder):
    """Copy unchanged production units; substitute only the hardware boundary."""
    folder = pathlib.Path(folder)
    for filename in OWNED:
        if not (GAME_DIR / filename).exists():
            raise AssertionError("missing playable integration file: " + filename)
    rels = ["src/apps_local/memory/" + f for f in OWNED]
    rels += ["src/apps_local/memory/MemoryCore.h", "src/apps_local/memory/MemoryScreens.h",
             "src/apps_local/memory/MemoryScreens.cpp", "lib/GfxRenderer/RevealedInteractions.h",
             "lib/GfxRenderer/PaintClock.h"]
    rels += [str(p.relative_to(ROOT)) for p in (ROOT / "src/apps_local/ui").glob("*.h")
             if p.name in {"ToyboxScreen.h", "ToyboxTokens.h", "ToyboxText.h", "ToyboxMetrics.h"}]
    for rel in rels:
        target = folder / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, target)
    seams = {
        "src/activities/Activity.h": ACTIVITY_BOUNDARY,
        "src/apps_local/ui/ToyboxTheme.h": RENDERER_BOUNDARY,
        "src/apps_local/ui/Toybox.h": '#pragma once\n',
        "src/apps_local/ui/ToyboxFonts.h": '#pragma once\nnamespace toybox { inline void ensureFonts(GfxRenderer& r) { ++r.fonts; } }\n',
        "src/apps_local/ui/ToyboxSeed.h": (ROOT / "src/apps_local/ui/ToyboxSeed.h").read_text(),
        "src/apps_local/Shelf.h": '#pragma once\nnamespace shelf { void leave(GfxRenderer&, MappedInputManager&); }\n',
        "src/components/UITheme.h": '#pragma once\nstruct GuiBoundary { void drawButtonHints(GfxRenderer&, const char*, const char*, const char*, const char*) {} };\ninline GuiBoundary GUI;\n',
        "Memory.h": '#pragma once\n#include <memory>\n#include <new>\n#include <utility>\ntemplate<class T, class... Args> std::unique_ptr<T> makeUniqueNoThrow(Args&&... args) { return std::unique_ptr<T>(new (std::nothrow) T(std::forward<Args>(args)...)); }\n',
    }
    for rel, text in seams.items():
        target = folder / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    harness = folder / "activity_host.cpp"
    harness.write_text(HARNESS, encoding="utf-8")
    exe = folder / "activity_host"
    sdk = ROOT / "freeink-sdk/libs/ui/FreeInkUI"
    cmd = ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-Wno-comment",
           "-I", str(folder), "-I", str(folder / "src/apps_local/memory"),
           "-I", str(folder / "src"), "-I", str(sdk / "include"),
           "-I", str(ROOT / "freeink-sdk/libs/assets/Icons/include"),
           str(harness), str(folder / "src/apps_local/memory/MemoryActivity.cpp"),
           str(folder / "src/apps_local/memory/MemoryScreens.cpp"),
           str(sdk / "src/FreeInkUI.cpp"), "-o", str(exe)]
    compiled = subprocess.run(cmd, capture_output=True, text=True)
    if compiled.returncode:
        raise AssertionError("actual Activity host compile failed:\n" + compiled.stderr)
    return exe


class MemoryActivityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.exe = compile_activity(cls.tmp.name)

    def run_scenario(self, scenario):
        result = subprocess.run([str(self.exe), scenario], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())

    def test_playable_level_to_completed_board_uses_real_activity_and_screens(self):
        self.run_scenario("playable")

    def test_wrong_faces_persist_until_explicit_next(self):
        self.run_scenario("mismatch")

    def test_back_depth_and_menu_leave_to_owning_shelf(self):
        self.run_scenario("navigation")

    def test_again_redeals_same_level_with_new_explicit_seed(self):
        self.run_scenario("again")

    def test_geometry_waits_for_paint_but_not_transient_selection(self):
        self.run_scenario("reveal")

    def test_activity_uses_only_logical_input_and_screen_owned_controls(self):
        header = (GAME_DIR / "MemoryActivity.h").read_text()
        source = (GAME_DIR / "MemoryActivity.cpp").read_text()
        flow = (GAME_DIR / "MemoryFlow.h").read_text()
        self.assertIn('#include "../../activities/Activity.h"', header)
        for token in ("HalGPIO", "BTN_", "millis(", "delay(", "sleep(", "<chrono>", "random_device"):
            self.assertFalse(token in source + header + flow, token)
        self.assertEqual(source.count("toybox::seed()"), 1)
        for token in ("toybox::Frame", "toybox::Screen", "buildMenu", "buildBoard", "model.cursor = cursor",
                      "model.game = &game", "interactions.route", "surfaceRevealed()", "cardAt"):
            self.assertIn(token, source)
        self.assertNotRegex(source, r"(?:surface|screen)\.button\(|interactions\.(?:add|register)")
        self.assertNotRegex(source, r"(?:getScreenWidth|getScreenHeight)\([^)]*\)\s*[!=]=\s*(?:480|800)")
        for filename in (*OWNED,):
            self.assertNotIn(b"\r", (GAME_DIR / filename).read_bytes())
        self.assertNotIn(b"\r", pathlib.Path(__file__).read_bytes())


if __name__ == "__main__":
    unittest.main()
