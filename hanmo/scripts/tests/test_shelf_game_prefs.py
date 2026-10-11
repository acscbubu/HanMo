"""Compile the actual card-independent Games preferences with host g++."""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/apps_local/ShelfGamePrefs.cpp"

HARNESS = r'''
#include "ShelfGamePrefs.h"
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>

const char* const names[] = {"CHESS", "BISCUIT", "PET", "GO"};
auto visible = [](int) { return false; };
auto hideChess = [](int item) { return item == 0; };

void repairFooter(std::string& text) {
  const size_t footer = text.rfind("END\t");
  assert(footer != std::string::npos);
  uint32_t hash = 2166136261u;
  for (size_t i = 0; i < footer; ++i)
    hash = (hash ^ static_cast<uint8_t>(text[i])) * 16777619u;
  char line[16];
  std::snprintf(line, sizeof(line), "END\t%08X\n", hash);
  text.replace(footer, std::string::npos, line);
}

int main(int argc, char** argv) {
  assert(argc == 2);
  const std::string scenario = argv[1];
  shelf::GamePrefs prefs(names, 4);
  if (scenario == "ordering") {
    assert(prefs.itemAt(0, false, visible) == 0);
    assert(prefs.moveToTop(2));
    assert(prefs.itemAt(0, false, visible) == 2);
    assert(prefs.moveDown(2));
    assert(prefs.itemAt(1, false, visible) == 2);
    assert(prefs.moveUp(2));
    assert(prefs.itemAt(0, false, visible) == 2);
    assert(!prefs.moveUp(2));
    assert(!prefs.moveDown(99));
    // Reordering a visible neighbor must not stop at a hidden registry row.
    shelf::GamePrefs withHidden(names, 4);
    assert(withHidden.moveAheadOf(3, 0));
    assert(withHidden.itemAt(0, false, hideChess) == 3);
    assert(withHidden.moveBehind(3, 1));
    assert(withHidden.itemAt(1, false, hideChess) == 3);
    assert(!withHidden.moveAheadOf(3, 3));
  } else if (scenario == "favorites") {
    assert(prefs.setFavorite(3, true));
    assert(prefs.setFavorite(1, true));
    assert(!prefs.setFavorite(1, true));
    assert(prefs.itemAt(0, false, visible) == 1);
    assert(prefs.itemAt(1, false, visible) == 3);
    assert(prefs.count(true, visible) == 2);
    assert(prefs.itemAt(0, true, visible) == 1);
    assert(prefs.itemAt(2, true, visible) == -1);
    assert(prefs.rowFor(3, false, visible) == 1);
    assert(prefs.moveUp(3));
    assert(prefs.itemAt(0, false, visible) == 3);
    assert(!prefs.moveUp(3)); // already first in favorite group
    assert(prefs.setFavorite(3, false));
    assert(prefs.itemAt(0, false, visible) == 1);
    assert(prefs.count(true, visible) == 1);
  } else if (scenario == "hidden") {
    assert(prefs.moveToTop(3));
    assert(prefs.setFavorite(2, true));
    assert(prefs.count(false, hideChess) == 3);
    assert(prefs.itemAt(0, false, hideChess) == 2);
    assert(prefs.itemAt(1, false, hideChess) == 3);
    assert(prefs.rowFor(3, false, hideChess) == 1);
    assert(prefs.rowFor(0, false, hideChess) == 2); // hidden: next visible row
    assert(prefs.count(true, hideChess) == 1);
    assert(prefs.itemAt(-1, false, visible) == -1);
  } else if (scenario == "roundtrip") {
    assert(prefs.moveToTop(2));
    assert(prefs.setFavorite(3, true));
    std::string saved = prefs.format();
    shelf::GamePrefs loaded(names, 4);
    assert(loaded.parse(saved.data(), saved.size()));
    assert(loaded.isFavorite(3));
    assert(loaded.itemAt(0, false, visible) == 3);
    assert(loaded.itemAt(1, false, visible) == 2);
    assert(saved == loaded.format());
    // Registry changes: no title is mistaken for a new index; new games append.
    const char* const changed[] = {"PET", "NEW", "CHESS", "GO"};
    shelf::GamePrefs migrated(changed, 4);
    assert(migrated.parse(saved.data(), saved.size()));
    assert(migrated.itemAt(0, false, visible) == 3); // GO retains favorite
    assert(migrated.itemAt(1, false, visible) == 0);
    assert(migrated.itemAt(3, false, visible) == 1);
    assert(migrated.isFavorite(3));
    shelf::GamePrefs stale(names, 4);
    assert(stale.setFavorite(1, true)); // BISCUIT is retired from changed registry
    const std::string staleFile = stale.format();
    shelf::GamePrefs withoutBiscuit(changed, 4);
    assert(withoutBiscuit.parse(staleFile.data(), staleFile.size()));
    assert(withoutBiscuit.count(true, visible) == 0);
    assert(withoutBiscuit.itemAt(0, false, visible) == 2); // CHESS stays first
  } else if (scenario == "corruption") {
    assert(prefs.moveToTop(2));
    const std::string good = prefs.format();
    assert(!prefs.parse(good.data(), good.size() - 2)); // truncated footer
    assert(prefs.itemAt(0, false, visible) == 2); // failure is transactional
    std::string bad = good;
    bad[bad.find("CHESS")] = 'X';
    assert(!prefs.parse(bad.data(), bad.size())); // checksum
    bad = good;
    bad.replace(0, 4, "SGP9");
    assert(!prefs.parse(bad.data(), bad.size())); // unknown version
    bad = good;
    bad.insert(bad.find("END"), "N\tCHESS\n");
    repairFooter(bad);
    assert(!prefs.parse(bad.data(), bad.size())); // duplicate known title
    bad = good;
    bad.insert(bad.find("END"), "F\tNOT IN REGISTRY\n");
    repairFooter(bad);
    assert(prefs.parse(bad.data(), bad.size())); // future/retired title ignored
    assert(prefs.itemAt(0, false, visible) == 2);
    shelf::GamePrefs defaults(names, 4);
    assert(!defaults.parse("", 0));
    assert(defaults.itemAt(0, false, visible) == 0);
  } else {
    return 2;
  }
}
'''


SCREEN_HARNESS = r'''
#include "ShelfScreen.h"
#include "player/PlayerAvatar.h"
#include <cassert>
#include <cstring>
#include <cstdio>

namespace fui = freeink::ui;
namespace player {
int16_t avatarPixels(AvatarSize) { return 32; }
void drawAvatar(fui::DrawTarget&, const fui::Rect&, const char*, AvatarSize, fui::Color) {}
}

struct Fake : fui::DrawTarget {
  fui::Size measureText(fui::FontId, const char* s, fui::TextStyle) const override {
    return {static_cast<int16_t>(s ? std::strlen(s) * 6 : 0), 12};
  }
  int16_t lineHeight(fui::FontId) const override { return 12; }
  void fill(fui::Rect, fui::Paint, uint8_t, uint8_t) override {}
  void stroke(fui::Rect, fui::Paint, uint8_t, uint8_t, uint8_t) override {}
  void line(fui::Point, fui::Point, uint8_t, fui::Paint) override { ++lines; }
  int lines = 0;
  void triangle(fui::Point, fui::Point, fui::Point, fui::Paint) override {}
  void text(fui::Rect, const char*, fui::TextStyle) override {}
  void bitmap(fui::Rect, fui::BitmapRef, fui::BitmapMode, fui::Paint, fui::Rotation) override {}
};

int main() {
  Fake target;
  fui::DeviceContext device;
  device.width = 480;
  device.height = 800;
  device.hasTouch = true;
  fui::InputSnapshot none{};
  toybox::Interactions hits;
  toybox::Frame frame(target, device, none, hits);
  toybox::Screen screen(frame);
  fui::ListItem item{};
  item.label = "CHESS";
  item.actionValue = 0;
  const fui::ListItem items[] = {item};
  const bool stars[] = {true};
  shelfui::MenuModel model;
  model.title = "GAMES";
  model.games = true;
  model.stars = stars;
  model.items = items;
  model.count = 1;
  shelfui::buildMenu(screen, model);
  assert(target.lines >= 5); // favorite row has a visible star marker
  assert(!hits.overflowed());
  bool foundFavorites = false, foundRow = false, foundChooser = false;
  fui::Rect favoritesRect{};
  for (size_t i = 0; i < hits.count(); ++i) {
    const auto& hit = hits.data()[i];
    if (hit.action == shelfui::ActionFavorites) { foundFavorites = true; favoritesRect = hit.rect; }
    if (hit.action == shelfui::ActionOpen) {
      foundRow = true;
      assert(hit.inputMask & fui::InputLongPress);
      fui::InputSnapshot longPress{};
      longPress.touchReleased = true;
      longPress.longPress = true;
      longPress.touchX = static_cast<int16_t>(hit.rect.x + 8);
      longPress.touchY = static_cast<int16_t>(hit.rect.y + 8);
      const auto event = hits.route(longPress);
      assert(event.action == shelfui::ActionOpen && event.longPress && event.value == 0);
    }
    if (hit.action == shelfui::ActionChoose) foundChooser = true;
  }
  assert(foundFavorites && foundRow && foundChooser);
  for (size_t i = 0; i < hits.count(); ++i) {
    const auto& hit = hits.data()[i];
    if (hit.action != shelfui::ActionChoose) continue;
    assert(hit.rect.right() <= favoritesRect.x || hit.rect.x >= favoritesRect.right() ||
           hit.rect.bottom() <= favoritesRect.y || hit.rect.y >= favoritesRect.bottom());
  }
  fui::InputSnapshot tap{};
  tap.touchReleased = true;
  tap.touchX = static_cast<int16_t>(favoritesRect.x + favoritesRect.width / 2);
  tap.touchY = static_cast<int16_t>(favoritesRect.y + favoritesRect.height / 2);
  assert(hits.route(tap).action == shelfui::ActionFavorites);

  {
    toybox::Frame emptyFrame(target, device, none, hits);
    toybox::Screen emptyScreen(emptyFrame);
    model.favoritesOnly = true;
    model.count = 0;
    shelfui::buildMenu(emptyScreen, model);
    assert(!hits.overflowed());
    bool foundExit = false;
    for (size_t i = 0; i < hits.count(); ++i) {
      const auto& hit = hits.data()[i];
      if (hit.rect.y >= toybox::kBodyTop && hit.action == shelfui::ActionFavorites) {
        foundExit = true;
        break;
      }
    }
    assert(foundExit); // empty favorites filter is not a dead end
  }
  {
    toybox::Frame actionsFrame(target, device, none, hits);
    toybox::Screen actionsScreen(actionsFrame);
    model.actionTitle = "CHESS";
    model.actionFavorite = true;
    shelfui::buildMenu(actionsScreen, model);
    assert(!hits.overflowed());
    bool foundMenu = false, foundDone = false;
    for (size_t i = 0; i < hits.count(); ++i) {
      if (hits.data()[i].action == shelfui::ActionGameActions) foundMenu = true;
      if (hits.data()[i].action == shelfui::ActionCancelActions) foundDone = true;
      assert(hits.data()[i].action != shelfui::ActionOpen);
    }
    assert(foundMenu && foundDone);
  }
  {
    toybox::Frame chooserFrame(target, device, none, hits);
    toybox::Screen chooserScreen(chooserFrame);
    const bool checks[] = {true};
    model.actionTitle = nullptr;
    model.checks = checks;
    model.count = 1;
    shelfui::buildMenu(chooserScreen, model);
    assert(!hits.overflowed());
    bool foundToggle = false;
    for (size_t i = 0; i < hits.count(); ++i) {
      if (hits.data()[i].action == shelfui::ActionToggleShown) foundToggle = true;
      assert(hits.data()[i].action != shelfui::ActionFavorites);
      assert(hits.data()[i].action != shelfui::ActionOpen);
    }
    assert(foundToggle);
  }
  puts("Games header/row touch routes, chooser, menu and empty exit OK");
}

'''

class ShelfGamePrefsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        harness = pathlib.Path(cls.tmp.name) / "game_prefs_test.cpp"
        harness.write_text(HARNESS)
        cls.exe = pathlib.Path(cls.tmp.name) / "game_prefs_test"
        subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                        "-I", str(SOURCE.parent), str(harness), str(SOURCE),
                        "-o", str(cls.exe)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_manual_order(self):
        subprocess.run([str(self.exe), "ordering"], check=True)

    def test_favorites_and_filter(self):
        subprocess.run([str(self.exe), "favorites"], check=True)

    def test_hidden_and_row_mapping(self):
        subprocess.run([str(self.exe), "hidden"], check=True)

    def test_title_keyed_roundtrip_and_changed_registry(self):
        subprocess.run([str(self.exe), "roundtrip"], check=True)

    def test_corrupt_and_truncated_file_leaves_previous_state(self):
        subprocess.run([str(self.exe), "corruption"], check=True)

    def test_real_freeink_touch_routes_and_empty_exit(self):
        harness = pathlib.Path(self.tmp.name) / "shelf_screen_host.cpp"
        harness.write_text(SCREEN_HARNESS)
        sdk = ROOT / "freeink-sdk/libs/ui/FreeInkUI"
        exe = pathlib.Path(self.tmp.name) / "shelf_screen_host"
        subprocess.run([
            "g++", "-std=c++17", "-Wall", "-Wextra", "-Wno-comment",
            "-I", str(ROOT / "src/apps_local"), "-I", str(ROOT / "src"),
            "-I", str(sdk / "include"),
            "-I", str(ROOT / "freeink-sdk/libs/assets/Icons/include"),
            str(harness), str(ROOT / "src/apps_local/ShelfScreen.cpp"),
            str(sdk / "src/FreeInkUI.cpp"), "-o", str(exe),
        ], check=True)
        subprocess.run([str(exe)], check=True)

    def test_touch_actions_and_mode_exit_are_wired(self):
        screen = (ROOT / "src/apps_local/ShelfScreen.cpp").read_text()
        folder = (ROOT / "src/apps_local/ShelfFolderActivity.cpp").read_text()
        shelf = (ROOT / "src/apps_local/Shelf.cpp").read_text()
        self.assertIn("ActionFavorites", screen)
        self.assertIn("ActionGameActions", screen)
        self.assertIn("InputLongPress", screen)
        self.assertIn("wasScreenLongPress", folder)
        self.assertIn("setFavoritesOnly", folder)
        self.assertIn("interactionsReady = false", folder)
        self.assertIn("shelf::moveGameToTop", folder)
        self.assertIn("shelf::setGameFavorite", folder)
        self.assertIn("shelf-game-prefs.cfg", shelf)
        self.assertIn("shelf-game-prefs.bak", shelf)
        self.assertIn("shelf-game-prefs.tmp", shelf)


if __name__ == "__main__":
    unittest.main()
