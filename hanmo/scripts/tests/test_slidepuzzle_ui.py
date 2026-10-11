"""Actual SlidePuzzle Activity + Screens + FreeInkUI, hardware seams only."""
import hashlib
import pathlib
import shutil
import subprocess
import tempfile
import unittest

from scripts.tests.test_memory_activity import ACTIVITY_BOUNDARY, RENDERER_BOUNDARY

ROOT = pathlib.Path(__file__).resolve().parents[2]
GAME_DIR = ROOT / "src/apps_local/slidepuzzle"
OWNED = ("SlidePuzzleActivity.h", "SlidePuzzleActivity.cpp", "SlidePuzzleFlow.h",
         "SlidePuzzleScreens.h", "SlidePuzzleScreens.cpp")

HARNESS = r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include <memory>
#include <string>
#include <utility>
#include "SlidePuzzleScreens.h"
#define private public
#include "SlidePuzzleActivity.h"
#undef private
namespace sp = slidepuzzle;
namespace ui = slidepuzzleui;
inline int leaves = 0, seedCalls = 0;
inline uint32_t nextSeed = 20261006u;
namespace shelf { void leave(GfxRenderer&, MappedInputManager&) { ++leaves; } }
namespace toybox { uint32_t seed() { ++seedCalls; return nextSeed++; } }
static void draw(SlidePuzzleActivity& a) { a.noteSurfaceBuilt(); a.render(RenderLock{}); }
static void tap(SlidePuzzleActivity& a, MappedInputManager& i, fui::Rect r) {
  assert(!r.empty()); i.tapped = true; i.x = r.x + r.width / 2; i.y = r.y + r.height / 2;
  a.loop(); i.tapped = false;
}
static fui::Rect action(const SlidePuzzleActivity& a, fui::ActionId id, int value = 0) {
  for (size_t h = 0; h < a.interactions.count(); ++h)
    if (a.interactions.data()[h].action == id && a.interactions.data()[h].value == value)
      return a.interactions.data()[h].rect;
  assert(false && "real screen must register requested action"); return {};
}
static bool text(const GfxRenderer& r, const std::string& s) {
  for (const auto& t : r.texts) if (t.value == s) return true;
  return false;
}
static void start(SlidePuzzleActivity& a, GfxRenderer& r, MappedInputManager& i, int width) {
  a.onEnter(); draw(a);
  const uint32_t seed = nextSeed;
  tap(a, i, action(a, ui::ActionSize, width));
  sp::Game expected{}; sp::shuffle(expected, width, seed);
  assert(std::memcmp(&a.game, &expected, sizeof(expected)) == 0);
  assert(a.screen == sp::Screen::Board && a.selectedWidth == width);
  assert(a.game.moves == 0 && sp::solvable(a.game) && !sp::solved(a.game));
  draw(a);
  char status[64]; std::snprintf(status, sizeof(status), "%d X %d   0 MOVES", width, width);
  assert(text(r, status));
}
int main(int argc, char** argv) {
  assert(argc == 2); GfxRenderer r; MappedInputManager input;
  auto instance = SlidePuzzleActivity::create(r, input); assert(instance);
  auto& a = static_cast<SlidePuzzleActivity&>(*instance);
  const std::string scenario = argv[1];
  if (scenario == "menu") {
    a.onEnter(); assert(a.entries == 1 && r.fonts == 1 && a.updates == 1 && seedCalls == 0);
    assert(a.screen == sp::Screen::Menu && !a.interactionsReady);
    draw(a);
    assert(text(r, "SLIDE PUZZLE") && text(r, "SELECTED: 3 X 3"));
    assert(a.interactions.count() == static_cast<size_t>(sp::kMaxWidth - sp::kMinWidth + 1));
    for (int width = sp::kMinWidth; width <= sp::kMaxWidth; ++width) {
      char label[24]; std::snprintf(label, sizeof(label), "%d X %d", width, width);
      assert(text(r, label));
      const auto row = action(a, ui::ActionSize, width);
      assert(row.width >= 44 && row.height >= 44);
      assert(row.x >= r.device.safeRect().x && row.right() <= r.device.safeRect().right());
      if (width > sp::kMinWidth)
        assert(row.y - action(a, ui::ActionSize, width - 1).bottom() >= 6);
    }
    for (int width = sp::kMinWidth; width <= sp::kMaxWidth; ++width) {
      start(a, r, input, width);
      assert(a.interactions.count() == 1 && a.interactions.count() <= toybox::kMaxInteractions);
    }
    assert(seedCalls == sp::kMaxWidth - sp::kMinWidth + 1);
    puts("menu: all core sizes, visible selection, actual explicit-seeded solvable unsolved board OK");
  } else if (scenario == "paint") {
    for (int width = sp::kMinWidth; width <= sp::kMaxWidth; ++width) {
      start(a, r, input, width);
      for (int number = 1; number < sp::cellCount(a.game); ++number)
        assert(text(r, std::to_string(number)) && "board must draw every numbered tile");
      assert(!text(r, "0") && "blank must remain unnumbered");
      assert(text(r, "TAP A TILE NEXT TO THE BLANK"));
      assert(a.interactions.count() == 1);
    }
    puts("paint: actual screen draws all tile numbers and an unnumbered blank OK");
  } else if (scenario == "play") {
    for (int width = sp::kMinWidth; width <= sp::kMaxWidth; ++width) {
      start(a, r, input, width);
      const sp::Game dealt = a.game;
      for (int index = 0; index < sp::cellCount(dealt); ++index) {
        a.game = dealt; a.screen = sp::Screen::Board; draw(a);
        sp::Game expected = a.game;
        const int updates = a.updates;
        const bool moved = sp::slide(expected, index % width, index / width);
        tap(a, input, ui::cellRect(r.device, a.game, index));
        assert(std::memcmp(&a.game, &expected, sizeof(expected)) == 0 &&
               "geometry tap must slide only an adjacent tile, including blank/illegal no-op");
        assert(a.updates == updates + (moved ? 1 : 0));
        assert(seedCalls == width - sp::kMinWidth + 1);
      }
      sp::reset(a.game, width);
      assert(sp::slide(a.game, width - 2, width - 1));
      a.game.moves = 0; a.screen = sp::Screen::Board; draw(a);
      tap(a, input, ui::cellRect(r.device, a.game, sp::cellCount(a.game) - 1));
      assert(sp::solved(a.game) && a.screen == sp::Screen::Done && a.game.moves == 1);
      assert(!a.interactionsReady && "Done transition must disarm stale table");
      draw(a);
      assert(text(r, "DONE - PUZZLE SOLVED") && text(r, "AGAIN") && text(r, "MENU"));
      assert(a.interactions.count() == 2 && a.interactions.count() <= toybox::kMaxInteractions);
      char status[64]; std::snprintf(status, sizeof(status), "%d X %d   1 MOVES", width, width);
      assert(text(r, status));
      const sp::Game before = a.game;
      const int updates = a.updates;
      for (int index = 0; index < sp::cellCount(a.game); ++index)
        tap(a, input, ui::cellRect(r.device, a.game, index));
      assert(std::memcmp(&a.game, &before, sizeof(before)) == 0 && a.updates == updates);
    }
    puts("play: actual geometry taps accept only adjacent tiles, count slides, reach inert Done OK");
  } else if (scenario == "navigation") {
    for (int width = sp::kMinWidth; width <= sp::kMaxWidth; ++width) {
      start(a, r, input, width);
      int seedCount = seedCalls, leaveCount = leaves;
      const sp::Game dealt = a.game;
      input.back = true; a.loop(); input.back = false;
      assert(a.screen == sp::Screen::Menu && leaves == leaveCount && !a.interactionsReady);
      assert(seedCalls == seedCount && std::memcmp(&dealt, &a.game, sizeof(dealt)) == 0);
      draw(a);
      char selected[32]; std::snprintf(selected, sizeof(selected), "SELECTED: %d X %d", width, width);
      assert(text(r, selected));
      input.back = true; a.loop(); input.back = false;
      assert(leaves == leaveCount + 1 && seedCalls == seedCount);
      tap(a, input, action(a, ui::ActionSize, width)); draw(a);
      tap(a, input, action(a, ui::ActionMenu));
      assert(a.screen == sp::Screen::Menu && leaves == leaveCount + 1);
      draw(a); tap(a, input, action(a, ui::ActionSize, width)); draw(a);
      seedCount = seedCalls;
      a.routeAction(fui::ActionEvent{ui::ActionAgain});
      assert(seedCalls == seedCount && "AGAIN is inactive during play");
      sp::reset(a.game, width); assert(sp::slide(a.game, width - 2, width - 1));
      a.game.moves = 41; draw(a);
      tap(a, input, ui::cellRect(r.device, a.game, sp::cellCount(a.game) - 1)); draw(a);
      assert(a.screen == sp::Screen::Done);
      const uint32_t seed = nextSeed;
      const auto again = action(a, ui::ActionAgain);
      tap(a, input, again);
      sp::Game expected{}; sp::shuffle(expected, width, seed);
      assert(a.screen == sp::Screen::Board && a.selectedWidth == width && a.game.moves == 0);
      assert(seedCalls == seedCount + 1 && std::memcmp(&a.game, &expected, sizeof(expected)) == 0);
      assert(!a.interactionsReady);
      tap(a, input, again); assert(seedCalls == seedCount + 1 && "old AGAIN tap cannot replay twice");
      draw(a);
      for (int destination = 0; destination < 2; ++destination) {
        sp::reset(a.game, width); assert(sp::slide(a.game, width - 2, width - 1));
        a.game.moves = 0; draw(a);
        tap(a, input, ui::cellRect(r.device, a.game, sp::cellCount(a.game) - 1)); draw(a);
        if (destination == 0) { tap(a, input, action(a, ui::ActionMenu)); }
        else { input.back = true; a.loop(); input.back = false; }
        assert(a.screen == sp::Screen::Menu && leaves == leaveCount + 1 && !a.interactionsReady);
        draw(a); assert(text(r, selected));
        tap(a, input, action(a, ui::ActionSize, width)); draw(a);
      }
    }
    a.onEnter(); draw(a);
    const auto row = action(a, ui::ActionSize, sp::kMinWidth);
    input.back = true; input.tapped = true; input.x = row.x + 1; input.y = row.y + 1;
    const int seedCount = seedCalls, leaveCount = leaves;
    a.loop(); input.back = false; input.tapped = false;
    assert(seedCalls == seedCount && leaves == leaveCount + 1 && "Back wins over simultaneous tap");
    puts("navigation: Back/Menu depth, selection persistence, same-size AGAIN with one fresh seed OK");
  } else if (scenario == "geometry") {
    const int dimensions[][2] = {{480,800}, {800,480}, {600,800}, {800,600}};
    for (const auto& dims : dimensions) {
      r.device.width = dims[0]; r.device.height = dims[1]; r.device.safeArea = {10,21,18,17};
      for (int width = sp::kMinWidth; width <= sp::kMaxWidth; ++width) {
        start(a, r, input, width);
        a.game.moves = 123; draw(a);
        const auto safe = r.device.safeRect();
        const auto footer = action(a, ui::ActionMenu);
        for (int index = 0; index < sp::cellCount(a.game); ++index) {
          const auto cell = ui::cellRect(r.device, a.game, index);
          assert(cell.width >= 44 && cell.height == cell.width);
          assert(cell.x >= safe.x && cell.right() <= safe.right() && cell.y >= toybox::kBodyTop);
          assert(cell.bottom() <= footer.y - 6 && footer.bottom() <= safe.bottom());
          assert(ui::cellAt(r.device, a.game, cell.x, cell.y) == index);
          assert(ui::cellAt(r.device, a.game, cell.right() - 1, cell.bottom() - 1) == index);
          assert(ui::cellAt(r.device, a.game, cell.x + cell.width / 2, cell.y + cell.height / 2) == index);
          bool drawn = false;
          for (const auto& s : r.strokes)
            if (s.box.x == cell.x && s.box.y == cell.y && s.box.width == cell.width && s.box.height == cell.height)
              drawn = true;
          assert(drawn && "paint and cellAt must use exactly cellRect");
          int numbers = 0;
          for (const auto& t : r.texts) {
            if (!cell.contains(t.box.x + t.box.width / 2, t.box.y + t.box.height / 2)) continue;
            ++numbers; assert(t.value == std::to_string(a.game.tile[index]));
          }
          assert(numbers == (a.game.tile[index] == sp::kEmpty ? 0 : 1));
          fui::InputSnapshot tapInput{}; tapInput.touchReleased = true;
          tapInput.touchX = cell.x + cell.width / 2; tapInput.touchY = cell.y + cell.height / 2;
          assert(a.interactions.route(tapInput).action == fui::NO_ACTION && "tiles must not consume interaction slots");
          if (index % width + 1 < width) {
            const auto next = ui::cellRect(r.device, a.game, index + 1);
            assert(next.x - cell.right() == 6);
            for (int x = cell.right(); x < next.x; ++x)
              assert(ui::cellAt(r.device, a.game, x, cell.y) == -1);
          }
          if (index + width < sp::cellCount(a.game)) {
            const auto below = ui::cellRect(r.device, a.game, index + width);
            assert(below.y - cell.bottom() == 6);
            for (int y = cell.bottom(); y < below.y; ++y)
              assert(ui::cellAt(r.device, a.game, cell.x, y) == -1);
          }
        }
        assert(ui::cellRect(r.device, a.game, -1).empty());
        assert(ui::cellRect(r.device, a.game, sp::cellCount(a.game)).empty());
        assert(ui::cellAt(r.device, a.game, -1, -1) == -1);
        assert(ui::cellAt(r.device, a.game, footer.x, footer.y) == -1);
        const auto before = ui::cellRect(r.device, a.game, sp::cellCount(a.game) - 1);
        a.screen = sp::Screen::Done; draw(a);
        const auto after = ui::cellRect(r.device, a.game, sp::cellCount(a.game) - 1);
        assert(before.x == after.x && before.y == after.y && before.width == after.width && before.height == after.height);
        const auto menu = action(a, ui::ActionMenu), again = action(a, ui::ActionAgain);
        assert(again.x - menu.right() >= 6 && menu.height >= 44 && again.height >= 44);
        assert(menu.bottom() <= safe.bottom() && again.right() <= safe.right());
        assert(a.interactions.count() == 2 && !a.interactions.overflowed());
        std::printf("geometry: %d x %d size %d, square cell %d, only %zu controls OK\n",
                    dims[0], dims[1], width, before.width, a.interactions.count());
      }
    }
  } else if (scenario == "reveal") {
    a.onEnter(); draw(a);
    const uint32_t menuMeaning = a.surfaceMeaning();
    tap(a, input, action(a, ui::ActionSize, sp::kMaxWidth));
    const uint32_t boardMeaning = a.surfaceMeaning();
    assert(boardMeaning != menuMeaning);
    int index = 0;
    while (!sp::canSlide(a.game, index % a.game.width, index / a.game.width)) ++index;
    const sp::Game dealt = a.game;
    tap(a, input, ui::cellRect(r.device, a.game, index));
    assert(std::memcmp(&a.game, &dealt, sizeof(dealt)) == 0 && "no input before new table exists");
    r.autoPaint = false; draw(a);
    tap(a, input, ui::cellRect(r.device, a.game, index));
    assert(std::memcmp(&a.game, &dealt, sizeof(dealt)) == 0 && "unseen menu-to-board geometry must be inert");
    paintclock::notePainted();
    sp::Game expected = a.game; assert(sp::slide(expected, index % a.game.width, index / a.game.width));
    tap(a, input, ui::cellRect(r.device, a.game, index));
    assert(std::memcmp(&a.game, &expected, sizeof(expected)) == 0 && a.surfaceMeaning() == boardMeaning);
    draw(a);
    int second = 0; while (!sp::canSlide(a.game, second % a.game.width, second / a.game.width)) ++second;
    expected = a.game; assert(sp::slide(expected, second % a.game.width, second / a.game.width));
    tap(a, input, ui::cellRect(r.device, a.game, second));
    assert(std::memcmp(&a.game, &expected, sizeof(expected)) == 0 && "same geometry allows consecutive intentional moves");
    const uint32_t unchanged = a.surfaceMeaning();
    ++a.game.moves; a.selectedWidth = sp::kMinWidth;
    assert(a.surfaceMeaning() == unchanged && "counters/selection are not coordinate meanings");
    a.game.width = sp::kMinWidth;
    assert(a.surfaceMeaning() != unchanged && "size changes pixel-to-cell meaning");
    a.game = dealt;
    const uint32_t live = a.surfaceMeaning();
    sp::reset(a.game, sp::kMaxWidth);
    assert(a.surfaceMeaning() != live && "solved/live meaning must change even at same screen/size");
    a.screen = sp::Screen::Done; draw(a);
    const int seeds = seedCalls;
    tap(a, input, action(a, ui::ActionAgain));
    assert(seedCalls == seeds && "unseen Done controls must not replay");
    paintclock::notePainted(); tap(a, input, action(a, ui::ActionAgain));
    assert(seedCalls == seeds + 1 && a.screen == sp::Screen::Board);
    draw(a);
    index = 0; while (!sp::canSlide(a.game, index % a.game.width, index / a.game.width)) ++index;
    const sp::Game replay = a.game;
    tap(a, input, ui::cellRect(r.device, a.game, index));
    assert(std::memcmp(&a.game, &replay, sizeof(replay)) == 0 && "Done-to-live waits for paint");
    paintclock::notePainted(); tap(a, input, ui::cellRect(r.device, a.game, index));
    assert(a.game.moves == 1);
    puts("reveal: real SurfaceGate/interaction gate block unseen mode, size and live changes; content remains routable OK");
  } else { return 2; }
}
'''


def compile_activity(folder, mutations=None):
    folder = pathlib.Path(folder)
    for filename in OWNED:
        if not (GAME_DIR / filename).exists():
            raise AssertionError("missing playable integration file: " + filename)
    rels = ["src/apps_local/slidepuzzle/" + f for f in (*OWNED, "SlidePuzzleCore.h")]
    rels += ["lib/GfxRenderer/RevealedInteractions.h", "lib/GfxRenderer/PaintClock.h"]
    rels += ["src/apps_local/ui/" + f for f in
             ("ToyboxScreen.h", "ToyboxTokens.h", "ToyboxText.h", "ToyboxMetrics.h")]
    for rel in rels:
        dst = folder / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, dst)
    seams = {
        "src/activities/Activity.h": ACTIVITY_BOUNDARY + '\n#define LOG_ERR(...) ((void)0)\n',
        "src/apps_local/ui/ToyboxTheme.h": RENDERER_BOUNDARY,
        "src/apps_local/ui/ToyboxFonts.h": '#pragma once\nnamespace toybox { inline void ensureFonts(GfxRenderer& r) { ++r.fonts; } }\n',
        "src/apps_local/ui/ToyboxSeed.h": (ROOT / "src/apps_local/ui/ToyboxSeed.h").read_text(),
        "src/apps_local/Shelf.h": '#pragma once\nnamespace shelf { void leave(GfxRenderer&, MappedInputManager&); }\n',
        "src/components/UITheme.h": '#pragma once\nstruct GuiBoundary { void drawButtonHints(GfxRenderer&, const char*, const char*, const char*, const char*) {} };\ninline GuiBoundary GUI;\n',
        "Memory.h": '#pragma once\n#include <memory>\n#include <new>\n#include <utility>\ntemplate<class T, class... Args> std::unique_ptr<T> makeUniqueNoThrow(Args&&... args) { return std::unique_ptr<T>(new (std::nothrow) T(std::forward<Args>(args)...)); }\n',
    }
    for rel, value in seams.items():
        dst = folder / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(value, encoding="utf-8")
    for filename, old, new in mutations or ():
        dst = folder / "src/apps_local/slidepuzzle" / filename
        value = dst.read_text()
        if value.count(old) != 1:
            raise AssertionError("mutation target must be unique: " + old)
        dst.write_text(value.replace(old, new), encoding="utf-8")
    harness = folder / "ui_host.cpp"
    harness.write_text(HARNESS, encoding="utf-8")
    exe = folder / "ui_host"
    sdk = ROOT / "freeink-sdk/libs/ui/FreeInkUI"
    cmd = ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-Wno-comment",
           "-I", str(folder), "-I", str(folder / "src/apps_local/slidepuzzle"),
           "-I", str(folder / "src"), "-I", str(sdk / "include"),
           "-I", str(ROOT / "freeink-sdk/libs/assets/Icons/include"),
           str(harness), str(folder / "src/apps_local/slidepuzzle/SlidePuzzleActivity.cpp"),
           str(folder / "src/apps_local/slidepuzzle/SlidePuzzleScreens.cpp"),
           str(sdk / "src/FreeInkUI.cpp"), "-o", str(exe)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode:
        raise AssertionError("actual Activity/screens host compile failed:\n" + result.stderr)
    return exe


class SlidePuzzleUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.exe = compile_activity(cls.tmp.name)

    def run_scenario(self, name):
        result = subprocess.run([str(self.exe), name], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())

    def test_actual_menu_starts_every_core_size_with_explicit_seed(self):
        self.run_scenario("menu")

    def test_actual_screen_paints_numbers_but_no_blank_number(self):
        self.run_scenario("paint")

    def test_only_adjacent_geometry_taps_move_and_win_enters_done(self):
        self.run_scenario("play")

    def test_back_menu_and_again_follow_actual_activity_depth(self):
        self.run_scenario("navigation")

    def test_real_paint_hit_geometry_safe_area_and_six_pixel_spacing(self):
        self.run_scenario("geometry")

    def test_surface_gate_blocks_unseen_geometry_but_not_tile_contents(self):
        self.run_scenario("reveal")

    def test_logical_input_bounded_controls_and_lf_only_sources(self):
        source = (GAME_DIR / "SlidePuzzleActivity.cpp").read_text()
        all_source = "\n".join((GAME_DIR / f).read_text() for f in OWNED)
        for banned in ("HalGPIO", "BTN_", "millis(", "delay(", "sleep(", "esp_random",
                       "random_device", "mappedInput.update(", "Storage", "NVS", "<chrono>"):
            self.assertFalse(banned in all_source, banned)
        self.assertEqual(source.count("toybox::seed()"), 1)
        for required in ("MappedInputManager::Button::Back", "surfaceRevealed()", "interactions.route",
                         "toybox::Frame", "toybox::Screen", "makeUniqueNoThrow", "LOG_ERR"):
            self.assertIn(required, source)
        for f in (*OWNED,):
            self.assertNotIn(b"\r", (GAME_DIR / f).read_bytes())
        self.assertNotIn(b"\r", pathlib.Path(__file__).read_bytes())

    def test_mutations_are_caught_without_touching_production_sources(self):
        hashes = {f: hashlib.sha256((GAME_DIR / f).read_bytes()).hexdigest() for f in (*OWNED, "SlidePuzzleCore.h")}
        cases = [
            ("SlidePuzzleActivity.cpp", " || !surfaceRevealed()", "", "reveal"),
            ("SlidePuzzleScreens.cpp", "return index;", "return index + 1;", "geometry"),
            ("SlidePuzzleScreens.cpp", "game.tile[index] != slidepuzzle::kEmpty", "true", "paint"),
            ("SlidePuzzleActivity.cpp", "startGame(selectedWidth);", "startGame(sp::kMinWidth);", "navigation"),
            ("SlidePuzzleActivity.cpp", "sp::slide(game, index % game.width, index / game.width)",
             "sp::slide(game, (index + 1) % game.width, (index + 1) / game.width)", "play"),
            ("SlidePuzzleActivity.cpp", "paintclock::mixMeaning(mode, static_cast<uint32_t>(game.width))",
             "paintclock::mixMeaning(mode, 0u)", "reveal"),
        ]
        for filename, old, new, scenario in cases:
            with self.subTest(mutation=old), tempfile.TemporaryDirectory() as folder:
                exe = compile_activity(folder, [(filename, old, new)])
                result = subprocess.run([str(exe), scenario], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0, "mutation escaped: " + old)
                self.assertIn("Assertion", result.stderr)
                print("mutation caught: " + old)
        self.assertEqual(hashes, {f: hashlib.sha256((GAME_DIR / f).read_bytes()).hexdigest() for f in hashes})


if __name__ == "__main__":
    unittest.main()
