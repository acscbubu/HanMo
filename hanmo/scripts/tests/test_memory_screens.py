"""Exercise real MemoryScreens.cpp + FreeInkUI.cpp, not a screen surrogate."""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
GAME_DIR = ROOT / "src/apps_local/memory"

HARNESS = r'''
#include "MemoryScreens.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

namespace fui = freeink::ui;
namespace mm = memorymatch;
namespace ui = memoryui;

struct TextCall { fui::Rect box; std::string value; fui::TextStyle style; };
struct StrokeCall { fui::Rect box; uint8_t width; };
struct Fake : fui::DrawTarget {
  std::vector<TextCall> texts;
  std::vector<StrokeCall> strokes;
  int lines = 0;
  fui::Size measureText(fui::FontId font, const char* text, fui::TextStyle) const override {
    return {static_cast<int16_t>(text ? std::strlen(text) * (font == toybox::kSmallFont ? 7 : 12) : 0),
            lineHeight(font)};
  }
  int16_t lineHeight(fui::FontId font) const override {
    return font == toybox::kSmallFont ? toybox::kTileCut.lineHeight :
           font == toybox::kDisplayFont ? toybox::kDisplayCut.lineHeight : toybox::kUiCut.lineHeight;
  }
  void fill(fui::Rect, fui::Paint, uint8_t, uint8_t) override {}
  void stroke(fui::Rect box, fui::Paint, uint8_t width, uint8_t, uint8_t) override {
    strokes.push_back({box, width});
  }
  void line(fui::Point, fui::Point, uint8_t, fui::Paint) override { ++lines; }
  void triangle(fui::Point, fui::Point, fui::Point, fui::Paint) override {}
  void text(fui::Rect box, const char* value, fui::TextStyle style) override {
    texts.push_back({box, value ? value : "", style});
  }
  void bitmap(fui::Rect, fui::BitmapRef, fui::BitmapMode, fui::Paint, fui::Rotation) override {}
  bool hasText(const std::string& value) const {
    for (const auto& call : texts) if (call.value == value) return true;
    return false;
  }
};

static fui::DeviceContext device() {
  fui::DeviceContext d;
  d.width = 480;
  d.height = 800;
  d.hasTouch = true;
  d.safeArea = {10, 0, 10, 0};
  return d;
}

static bool disjoint(fui::Rect a, fui::Rect b) {
  return a.right() <= b.x || b.right() <= a.x || a.bottom() <= b.y || b.bottom() <= a.y;
}

static fui::ActionEvent tap(toybox::Interactions& hits, fui::Rect box) {
  fui::InputSnapshot input{};
  input.touchReleased = true;
  input.touchX = static_cast<int16_t>(box.x + box.width / 2);
  input.touchY = static_cast<int16_t>(box.y + box.height / 2);
  return hits.route(input);
}

int main(int argc, char** argv) {
  assert(argc == 2);
  const std::string scenario = argv[1];
  auto d = device();
  fui::InputSnapshot none{};
  Fake target;
  toybox::Interactions hits;
  if (scenario == "menu") {
    ui::MenuModel model;
    assert(model.selected == 0);
    for (int selected = 0; selected < mm::kLevelCount; ++selected) {
      target.texts.clear();
      model.selected = selected;
      toybox::Frame frame(target, d, none, hits);
      toybox::Screen screen(frame);
      ui::buildMenu(screen, model);
      assert(!hits.overflowed() && hits.count() == 4);
      assert(target.hasText("MEMORY MATCH"));
      assert(target.hasText("TAP A LEVEL TO START"));
      for (size_t i = 0; i < hits.count(); ++i) {
        const auto& hit = hits.data()[i];
        assert(hit.action == ui::ActionLevel && hit.value == static_cast<int>(i));
        assert(hit.rect.height >= 80 && hit.rect.width >= 44);
        if (!(hit.rect.y >= toybox::kBodyTop && hit.rect.bottom() <= d.safeRect().bottom())) {
          std::fprintf(stderr, "BAD hit %zu: x=%d y=%d w=%d h=%d bodyTop=%d safeBottom=%d\\n", i, hit.rect.x, hit.rect.y,
                       hit.rect.width, hit.rect.height, toybox::kBodyTop, d.safeRect().bottom());
          assert(false);
        }
        if (i) assert(hit.rect.y - hits.data()[i-1].rect.bottom() >= 6);
        const auto action = tap(hits, hit.rect);
        assert(action.action == ui::ActionLevel && action.value == static_cast<int>(i));
        assert(target.hasText(mm::kLevels[i].name));
        char detail[64];
        std::snprintf(detail, sizeof(detail), "%d CARDS / %d PAIRS / %d X %d",
                      mm::cellsIn(mm::kLevels[i]), mm::pairsIn(mm::kLevels[i]),
                      mm::kLevels[i].columns, mm::kLevels[i].rows);
        assert(target.hasText(detail));
      }
    }
    puts("menu: four large immediate-start level actions OK");
  } else if (scenario == "board") {
    mm::Game game{};
    for (int level = 0; level < mm::kLevelCount; ++level) {
      mm::start(game, level, 123u);
      target.texts.clear();
      target.strokes.clear();
      toybox::Frame frame(target, d, none, hits);
      toybox::Screen screen(frame);
      ui::buildBoard(screen, ui::BoardModel{&game});
      assert(!hits.overflowed() && hits.count() == 1);
      assert(hits.data()[0].action == ui::ActionMenu);
      assert(target.hasText("SELECT A CARD"));
      char progress[64];
      std::snprintf(progress, sizeof(progress), "0/%d PAIRS   0 MOVES", mm::pairCount(game));
      assert(target.hasText(progress));
      assert(target.hasText("MEMORY MATCH"));
      const auto footer = hits.data()[0].rect;
      assert(footer.height >= 44 && footer.bottom() <= d.safeRect().bottom());
      for (int i = 0; i < mm::cellCount(game); ++i) {
        const auto card = ui::cardRect(d, game, i);
        assert(card.width >= 44 && card.height >= 44);
        assert(card.x >= d.safeRect().x && card.right() <= d.safeRect().right());
        assert(card.y >= toybox::kBodyTop + 28 + 6 && card.bottom() <= footer.y - 6);
        assert(ui::cardAt(d, game, card.x, card.y) == i);
        assert(ui::cardAt(d, game, card.right() - 1, card.bottom() - 1) == i);
        assert(ui::cardAt(d, game, card.x + card.width / 2, card.y + card.height / 2) == i);
        assert(tap(hits, card).action == fui::NO_ACTION);
        bool drawn = false;
        for (const auto& stroke : target.strokes)
          if (stroke.box.x == card.x && stroke.box.y == card.y && stroke.box.width == card.width &&
              stroke.box.height == card.height) drawn = true;
        assert(drawn);
        for (const auto& text : target.texts)
          assert(!card.contains(text.box.x + text.box.width / 2, text.box.y + text.box.height / 2));
        for (int j = i + 1; j < mm::cellCount(game); ++j)
          assert(disjoint(card, ui::cardRect(d, game, j)));
        if (i % mm::columnCount(game) + 1 < mm::columnCount(game)) {
          const auto next = ui::cardRect(d, game, i + 1);
          assert(next.x - card.right() == 6);
          for (int x = card.right(); x < next.x; ++x)
            assert(ui::cardAt(d, game, x, card.y) == mm::kNoCell);
        }
        if (i + mm::columnCount(game) < mm::cellCount(game)) {
          const auto below = ui::cardRect(d, game, i + mm::columnCount(game));
          assert(below.y - card.bottom() == 6);
          for (int y = card.bottom(); y < below.y; ++y)
            assert(ui::cardAt(d, game, card.x, y) == mm::kNoCell);
        }
      }
      assert(ui::cardRect(d, game, -1).empty());
      assert(ui::cardRect(d, game, mm::cellCount(game)).empty());
      assert(ui::cardAt(d, game, -1, -1) == mm::kNoCell);
      assert(ui::cardAt(d, game, footer.x, footer.y) == mm::kNoCell);
      const auto first = ui::cardRect(d, game, 0);
      assert(mm::expose(game, ui::cardAt(d, game, first.x, first.y)));
      target.texts.clear();
      toybox::Frame nextFrame(target, d, none, hits);
      toybox::Screen nextScreen(nextFrame);
      ui::buildBoard(nextScreen, ui::BoardModel{&game});
      int faces = 0;
      for (const auto& text : target.texts) {
        if (first.contains(text.box.x + text.box.width / 2, text.box.y + text.box.height / 2)) {
          ++faces;
          assert(text.value == std::to_string(mm::faceAt(game, 0) + 1));
          const auto expected = toybox::inkCentred(first, toybox::kUiCut);
          assert(text.box.y == expected.y && text.style.font == toybox::kUiFont);
        }
      }
      assert(faces == 1);
      std::printf("%s: %dx%d cards, six-pixel gaps, %zu hit(s)\n", mm::levelOf(game).name,
                  first.width, first.height, hits.count());
    }
  } else if (scenario == "mismatch") {
    mm::Game game{};
    for (int level = 0; level < mm::kLevelCount; ++level) {
      mm::start(game, level, 456u);
      const int first = 0;
      int second = 1;
      while (mm::faceAt(game, second) == mm::faceAt(game, first)) ++second;
      assert(mm::expose(game, first) && mm::expose(game, second));
      assert(mm::awaitingMismatch(game));
      const mm::Game before = game;
      auto render = [&]() {
        target.texts.clear();
        toybox::Frame frame(target, d, none, hits);
        toybox::Screen screen(frame);
        ui::buildBoard(screen, ui::BoardModel{&game});
      };
      for (int repaint = 0; repaint < 3; ++repaint) {
        render();
        assert(std::memcmp(&game, &before, sizeof(game)) == 0);
        assert(!hits.overflowed() && hits.count() == 2);
        assert(target.hasText("0/" + std::to_string(mm::pairCount(game)) + " PAIRS   1 MOVES"));
        assert(target.hasText("MISMATCH - PRESS NEXT"));
        fui::Rect next{}, menu{};
        for (size_t h = 0; h < hits.count(); ++h) {
          const auto hit = hits.data()[h];
          assert(hit.rect.bottom() <= d.safeRect().bottom() && hit.rect.height >= 44);
          if (hit.action == ui::ActionNext) next = hit.rect;
          else { assert(hit.action == ui::ActionMenu); menu = hit.rect; }
          for (int i = 0; i < mm::cellCount(game); ++i)
            assert(disjoint(hit.rect, ui::cardRect(d, game, i)));
        }
        assert(!next.empty() && !menu.empty() && disjoint(next, menu));
        assert(next.right() + 6 <= menu.x || menu.right() + 6 <= next.x);
        assert(tap(hits, menu).action == ui::ActionMenu);
        for (int i = 0; i < mm::cellCount(game); ++i) {
          const auto card = ui::cardRect(d, game, i);
          assert(tap(hits, card).action == fui::NO_ACTION);
          int faces = 0;
          for (const auto& text : target.texts) {
            if (!card.contains(text.box.x + text.box.width / 2, text.box.y + text.box.height / 2)) continue;
            ++faces;
            assert(text.value == std::to_string(mm::faceAt(game, i) + 1));
          }
          assert(faces == ((i == first || i == second) ? 1 : 0));
        }
        assert(mm::awaitingMismatch(game));
      }
      fui::Rect next{};
      for (size_t h = 0; h < hits.count(); ++h)
        if (hits.data()[h].action == ui::ActionNext) next = hits.data()[h].rect;
      assert(tap(hits, next).action == ui::ActionNext);
      assert(mm::resolveMismatch(game));
      render();
      assert(hits.count() == 1 && hits.data()[0].action == ui::ActionMenu);
      assert(!target.hasText("NEXT"));
      for (const auto& text : target.texts)
        assert(ui::cardAt(d, game, text.box.x + text.box.width / 2, text.box.y + text.box.height / 2) == mm::kNoCell);
    }
    puts("mismatch: two visible faces persist; only explicit NEXT resolves; controls clear board OK");
  } else if (scenario == "markings") {
    mm::Game game{};
    mm::start(game, 3, 999u);
    int mate = 1;
    while (mm::faceAt(game, mate) != mm::faceAt(game, 0)) ++mate;
    const auto first = ui::cardRect(d, game, 0);
    assert(mm::expose(game, 0) && mm::expose(game, mate));
    target.texts.clear();
    target.strokes.clear();
    toybox::Frame frame(target, d, none, hits);
    toybox::Screen screen(frame);
    ui::buildBoard(screen, ui::BoardModel{&game, 0});
    const auto matchedMark = first.inset(fui::Insets{10, 10, 10, 10});
    const auto cursorMark = first.inset(fui::Insets{4, 4, 4, 4});
    bool matched = false, cursor = false;
    for (const auto& stroke : target.strokes) {
      auto same = [&](const fui::Rect r) {
        return stroke.box.x == r.x && stroke.box.y == r.y && stroke.box.width == r.width &&
               stroke.box.height == r.height;
      };
      if (same(matchedMark) && stroke.width == 1) matched = true;
      if (same(cursorMark) && stroke.width == 3) cursor = true;
    }
    assert(matched && "matched inset must stay detached from the cursor outline");
    assert(cursor && "keyboard cursor needs a detached thick outline");
    assert(target.hasText("1/18 PAIRS   1 MOVES"));
    assert(hits.count() == 1 && hits.data()[0].action == ui::ActionMenu);
    puts("markings: matched inset and detached thick cursor stay distinct; progress updated OK");
  } else if (scenario == "done") {
    mm::Game game{};
    mm::start(game, 0, 777u);
    for (int i = 0; i < mm::cellCount(game); ++i) {
      if (mm::isMatched(game, i)) continue;
      int mate = -1;
      for (int j = i + 1; j < mm::cellCount(game); ++j)
        if (mm::faceAt(game, j) == mm::faceAt(game, i)) { mate = j; break; }
      assert(mate >= 0 && mm::expose(game, i) && mm::expose(game, mate));
    }
    assert(mm::complete(game) && game.matchedPairs == mm::pairCount(game));
    target.texts.clear();
    target.strokes.clear();
    toybox::Frame frame(target, d, none, hits);
    toybox::Screen screen(frame);
    ui::buildBoard(screen, ui::BoardModel{&game});
    assert(!hits.overflowed() && hits.count() == 2);
    assert(hits.count() <= toybox::kMaxInteractions);
    assert(hits.data()[0].action == ui::ActionMenu && hits.data()[1].action == ui::ActionAgain);
    assert(target.hasText("COMPLETE - TAP AGAIN"));
    assert(target.hasText("AGAIN"));
    assert(target.hasText("6/6 PAIRS   6 MOVES"));
    for (size_t h = 0; h < hits.count(); ++h) {
      for (int i = 0; i < mm::cellCount(game); ++i) {
        assert(disjoint(hits.data()[h].rect, ui::cardRect(d, game, i)));
        assert(mm::faceUp(game, i));
        const auto card = ui::cardRect(d, game, i);
        int faceTexts = 0;
        for (const auto& text : target.texts) {
          if (card.contains(text.box.x + text.box.width / 2, text.box.y + text.box.height / 2)) {
            ++faceTexts;
            assert(text.value == std::to_string(mm::faceAt(game, i) + 1));
          }
        }
        assert(faceTexts == 1);
      }
      if (h) assert(hits.data()[h].rect.x - hits.data()[h - 1].rect.right() >= 6);
    }
    const auto again = hits.data()[1].rect;
    assert(tap(hits, again).action == ui::ActionAgain);
    puts("done: last board remains visible with disjoint MENU/AGAIN controls OK");
  } else {
    return 2;
  }
}
'''


class MemoryScreensTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        harness = pathlib.Path(cls.tmp.name) / "memory_screen_host.cpp"
        harness.write_text(HARNESS, encoding="utf-8")
        cls.exe = pathlib.Path(cls.tmp.name) / "memory_screen_host"
        sdk = ROOT / "freeink-sdk/libs/ui/FreeInkUI"
        command = [
            "g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-Wno-comment",
            "-I", str(GAME_DIR), "-I", str(ROOT / "src/apps_local"),
            "-I", str(ROOT / "src"), "-I", str(sdk / "include"),
            "-I", str(ROOT / "freeink-sdk/libs/assets/Icons/include"),
            str(harness), str(GAME_DIR / "MemoryScreens.cpp"),
            str(sdk / "src/FreeInkUI.cpp"), "-o", str(cls.exe),
        ]
        compiled = subprocess.run(command, capture_output=True, text=True)
        if compiled.returncode:
            raise AssertionError("real screen host compile failed:\n" + compiled.stderr)

    def run_scenario(self, name):
        result = subprocess.run([str(self.exe), name], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())

    def test_menu_rows_start_each_explicit_level(self):
        self.run_scenario("menu")

    def test_normal_board_all_levels_conceals_faces_and_maps_card_taps(self):
        self.run_scenario("board")

    def test_mismatch_keeps_wrong_pair_visible_until_explicit_next(self):
        self.run_scenario("mismatch")

    def test_matched_cards_and_cursor_have_distinct_marks(self):
        self.run_scenario("markings")

    def test_done_keeps_last_board_and_exposes_again(self):
        self.run_scenario("done")


if __name__ == "__main__":
    unittest.main()
