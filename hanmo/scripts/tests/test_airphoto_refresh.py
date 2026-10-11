"""Panel-frame regression against the real AirPhotoActivity and host display/input shims."""
import pathlib
import subprocess
import tempfile
import unittest

from scripts.tests.test_airphoto_fast_list import PLATFORM, SHIMS, SOURCE


def recording_platform():
    platform = PLATFORM
    changes = [
        ('enum RefreshMode { HALF_REFRESH };',
         'enum RefreshMode { FAST_REFRESH = 0, HALF_REFRESH = 1 };'),
        ('struct RenderLock {};', 'struct RenderLock { static bool peek() { return renderBusy; } ~RenderLock() {} };'),
        ('inline std::string physicalLeftHint, physicalRightHint;',
         'inline std::string physicalLeftHint, physicalRightHint;\ninline bool failOriginalRemove = false, failCoverInstall = false, renderBusy = false;\ninline int coversInstalled = 0, lastCover = -1;'),
        ('if (it != files.end()) files.erase(it);',
         'if (failOriginalRemove) return false;\n      if (it != files.end()) files.erase(it);'),
        ('if (strcmp(path, "/AirPhoto/wide.jpg") == 0) {',
         'if (strcmp(path, "/AirPhoto/a.bmp") == 0) return true;\n      if (strcmp(path, "/AirPhoto/wide.jpg") == 0) {'),
        ('static bool install(const SelectedImage&, bool) { return true; }',
         'static bool install(const SelectedImage&, bool) { ++coversInstalled; return !failCoverInstall; }'),
        ('struct FrameBufferLoan { explicit FrameBufferLoan(GfxRenderer&) {} };',
         'struct FrameBufferLoan { GfxRenderer& r; explicit FrameBufferLoan(GfxRenderer& x) : r(x) {} ~FrameBufferLoan() { r.frameContent.clear(); } };'),
        ('Orientation orientation = Orientation::Portrait;',
         'Orientation orientation = Orientation::Portrait;\n  std::string frameContent;\n  std::vector<std::pair<std::string, HalDisplay::RefreshMode>> frames;\n  int nextMode = -1;'),
        ('void clearScreen() {}', 'void clearScreen() { frameContent = "base:"; }'),
        ('void drawText(int font, int x, int, const char* text) {',
         'void drawText(int font, int x, int, const char* text) {\n    if (strstr(text, "  ")) frameContent += "|header";\n    if (strcmp(text, "a.bmp") == 0 || strcmp(text, "b.bmp") == 0) frameContent += std::string("|name:") + text;'),
        ('void drawBitmap(...) { ++bitmapReads; }',
         'void drawBitmap(...) { ++bitmapReads; frameContent += "|photo:" + lastOpenedPath; }'),
        ('void displayBuffer(HalDisplay::RefreshMode) { ++displayCalls; }',
         'void requestNextRefresh(HalDisplay::RefreshMode mode) { nextMode = mode; }\n  void displayBuffer(HalDisplay::RefreshMode mode = HalDisplay::FAST_REFRESH) {\n    ++displayCalls; frames.emplace_back(frameContent, nextMode < 0 ? mode : static_cast<HalDisplay::RefreshMode>(nextMode)); nextMode = -1;\n  }'),
        ('if (input.popupChoice >= 0) {', 'if (input.popupChoice != -1) {'),
        ('active = false;\n      onSelect(choice);\n      requestUpdate();',
         'active = false;\n      if (choice >= 0) onSelect(choice); // negative: Back / outside tap\n      requestUpdate();'),
        ('void processRender(GfxRenderer&, MappedInputManager&) {}',
         'bool processRender(GfxRenderer& r, MappedInputManager&) const {\n    if (!active) return false;\n    r.frameContent += title;\n    r.displayBuffer(); // The real OptionPopup owns its own FAST panel commit.\n    return true;\n  }'),
        ('bool active = false;\n  std::function<void(int)> onSelect;',
         'bool active = false;\n  std::string title;\n  std::function<void(int)> onSelect;'),
        ('void show(Title, const Label (&)[N], int, int, Callback callback) {\n    active = true; onSelect = callback;',
         'void show(Title, const Label (&)[N], int count, int, Callback callback) {\n    active = true; title = count == 4 ? "|menu" : "|confirm"; onSelect = callback;'),
        ('void drawPopup(GfxRenderer&, const char*) {}',
         'void drawPopup(GfxRenderer& r, const char*) {\n    r.frameContent += "|status"; r.displayBuffer();\n  }'),
        ('void drawButtonHints(GfxRenderer&, const char*, const char*, const char* left, const char* right) {\n    physicalLeftHint = left; physicalRightHint = right;',
         'void drawButtonHints(GfxRenderer& r, const char*, const char*, const char* left, const char* right) {\n    physicalLeftHint = left; physicalRightHint = right; r.frameContent += "|hints";'),
    ]
    for old, new in changes:
        if platform.count(old) != 1:
            raise AssertionError('stale activity shim: ' + old[:70])
        platform = platform.replace(old, new)
    return platform


HARNESS = r'''
#include "FakePlatform.h"
#include "AirPhotoActivity.h"
#include <cstdlib>
#include <iostream>

using Mode = HalDisplay::RefreshMode;
static constexpr const char* photo = "base:|photo:/AirPhoto/a.bmp|hints";
static constexpr const char* list = "base:|header|name:b.bmp|hints";

static void panel(GfxRenderer& r, size_t before, const std::string& expected, Mode mode) {
  if (r.frames.size() != before + 1 || r.frames.back().first != expected || r.frames.back().second != mode) {
    std::cerr << "expected one " << static_cast<int>(mode) << " frame '" << expected << "' after " << before
              << "; got " << r.frames.size() << " frames, last '" << r.frames.back().first
              << "' mode " << static_cast<int>(r.frames.back().second) << "\n";
    std::exit(1);
  }
}
static void render(AirPhotoActivity& a) { a.render(RenderLock{}); }
static void press(AirPhotoActivity& a, MappedInputManager& i, MappedInputManager::Button b) {
  i.reset(); i.release = true; i.released = b; a.loop(); i.reset();
}
static void choose(AirPhotoActivity& a, MappedInputManager& i, int choice) {
  i.reset(); i.popupChoice = choice; a.loop(); i.reset();
}
static void openMenu(AirPhotoActivity& a, MappedInputManager& i, GfxRenderer& r) {
  press(a, i, MappedInputManager::Button::Confirm);
  size_t before = r.frames.size();
  render(a);
  panel(r, before, std::string(photo) + "|menu", Mode::FAST_REFRESH);
}
static void openConfirm(AirPhotoActivity& a, MappedInputManager& i, GfxRenderer& r, int choice) {
  size_t before = r.frames.size();
  choose(a, i, choice); render(a);
  panel(r, before, std::string(photo) + (choice == 1 ? "|menu" : "|confirm"), Mode::HALF_REFRESH);
}
int main(int argc, char** argv) {
  if (argc != 2) return 2;
  const std::string scenario(argv[1]);
  if (scenario == "rotate_jpeg") {
    files = {"a.jpg"};
    GfxRenderer r; MappedInputManager i; AirPhotoActivity a(r, i);
    a.onEnter();
    press(a, i, MappedInputManager::Button::Confirm); // Lazy portrait cache.
    press(a, i, MappedInputManager::Button::Confirm); render(a); // Menu.
    const size_t before = r.frames.size();
    const int decoded = conversions;
    choose(a, i, 0);
    if (r.frames.size() != before) return 11; // Cache work is render-owned.
    render(a);
    panel(r, before, "base:|photo:/AirPhoto/.view/a.jpg.land.bmp|hints", Mode::HALF_REFRESH);
    if (conversions <= decoded || r.orientation != GfxRenderer::Orientation::LandscapeCounterClockwise) return 12;
    return 0;
  }
  files = {"a.bmp", "b.bmp"};
  GfxRenderer r; MappedInputManager i; AirPhotoActivity a(r, i);
  a.onEnter();
  panel(r, 0, "base:|header|name:a.bmp|name:b.bmp|hints", Mode::HALF_REFRESH);
  press(a, i, MappedInputManager::Button::Confirm); // Filename list -> a.bmp.
  panel(r, 1, photo, Mode::HALF_REFRESH);
  openMenu(a, i, r);
  if (scenario == "render_busy") {
    size_t before = r.frames.size();
    renderBusy = true;
    i.popupChoice = 1; a.loop();
    if (r.frames.size() != before || i.popupChoice != 1) return 13;
    renderBusy = false;
    a.loop(); i.reset(); render(a);
    panel(r, before, std::string(photo) + "|menu", Mode::HALF_REFRESH);
    return 0;
  }
  if (scenario == "confirm") {
    openConfirm(a, i, r, 1);
    return 0;
  }
  if (scenario == "cancel") {
    size_t before = r.frames.size();
    choose(a, i, 3); render(a); // explicit Cancel in the menu
    panel(r, before, photo, Mode::HALF_REFRESH);
    openMenu(a, i, r);
    openConfirm(a, i, r, 2);
    before = r.frames.size(); choose(a, i, 0); render(a); // default delete Cancel
    panel(r, before, photo, Mode::HALF_REFRESH);
    if (files.size() != 2) return 3;
    return 0;
  }
  if (scenario == "back_outside") {
    size_t before = r.frames.size();
    choose(a, i, -2); render(a); // Back dismisses menu without selection
    panel(r, before, photo, Mode::HALF_REFRESH);
    openMenu(a, i, r); openConfirm(a, i, r, 1);
    before = r.frames.size(); choose(a, i, -3); render(a); // outside tap dismisses confirmation
    panel(r, before, photo, Mode::HALF_REFRESH);
    return 0;
  }
  if (scenario == "rotate") {
    size_t before = r.frames.size();
    choose(a, i, 0); render(a);
    panel(r, before, photo, Mode::HALF_REFRESH);
    if (r.orientation != GfxRenderer::Orientation::LandscapeCounterClockwise) return 4;
    press(a, i, MappedInputManager::Button::Back);
    panel(r, before + 1, "base:|header|name:a.bmp|name:b.bmp|hints", Mode::HALF_REFRESH);
    if (r.orientation != GfxRenderer::Orientation::Portrait) return 5;
    return 0;
  }
  if (scenario == "cover") {
    openConfirm(a, i, r, 1);
    size_t before = r.frames.size();
    choose(a, i, 1); render(a); // Sleep is the middle cover target.
    panel(r, before, photo, Mode::HALF_REFRESH);
    if (coversInstalled != 1 || lastCover != 1 || files.size() != 2) return 6;
    return 0;
  }
  if (scenario == "cover_boot" || scenario == "cover_shutdown") {
    openConfirm(a, i, r, 1);
    size_t before = r.frames.size();
    const int target = scenario == "cover_boot" ? 0 : 2;
    choose(a, i, target); render(a);
    panel(r, before, photo, Mode::HALF_REFRESH);
    if (coversInstalled != 1 || lastCover != target || files.size() != 2) return 14;
    return 0;
  }
  if (scenario == "cover_failure") {
    openConfirm(a, i, r, 1);
    failCoverInstall = true;
    size_t before = r.frames.size();
    choose(a, i, 1); render(a);
    if (r.frames.size() != before + 2 ||
        r.frames[before].first != std::string(photo) + "|status" ||
        r.frames.back().first != photo || r.frames.back().second != Mode::HALF_REFRESH ||
        files.size() != 2) return 9;
    return 0;
  }
  if (scenario == "delete_failure") {
    openConfirm(a, i, r, 2);
    failOriginalRemove = true;
    size_t before = r.frames.size();
    choose(a, i, 1); render(a);
    if (r.frames.size() != before + 2 ||
        r.frames[before].first != std::string(photo) + "|status" ||
        r.frames.back().first != photo || r.frames.back().second != Mode::HALF_REFRESH ||
        files.size() != 2 || r.orientation != GfxRenderer::Orientation::Portrait) return 10;
    return 0;
  }
  if (scenario == "delete") {
    openConfirm(a, i, r, 2);
    size_t before = r.frames.size();
    const int reads = bitmapReads;
    choose(a, i, 1); render(a);
    panel(r, before, list, Mode::HALF_REFRESH);
    if (files.size() != 1 || files[0] != "b.bmp" || bitmapReads != reads ||
        r.orientation != GfxRenderer::Orientation::Portrait) return 7;
    return 0;
  }
  return 8;
}
'''


class AirPhotoRefreshTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(cls.tmp.name)
        (root / 'FakePlatform.h').write_text(recording_platform())
        for name in SHIMS:
            shim = root / name
            shim.parent.mkdir(parents=True, exist_ok=True)
            shim.write_text('#include "FakePlatform.h"\n')
        (root / 'main.cpp').write_text(HARNESS)
        cover_stub = root / 'AirPhotoActionsStub.cpp'
        cover_stub.write_text('#include "FakePlatform.h"\n#include "AirPhotoActions.h"\n'
                              'namespace airphoto { bool setCover(const char*, Cover cover) { '
                              '++coversInstalled; lastCover = static_cast<int>(cover); '
                              'return !failCoverInstall; } }\n')
        cls.binary = root / 'airphoto_refresh_host'
        build = subprocess.run(
            ['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-I', str(root),
             '-I', str(SOURCE.parent), str(root / 'main.cpp'), str(SOURCE), str(cover_stub), '-o', str(cls.binary)],
            text=True, capture_output=True)
        if build.returncode:
            raise AssertionError('host build failed:\n' + build.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def check_transition(self, scenario):
        result = subprocess.run([str(self.binary), scenario], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_menu_to_cover_and_delete_confirm_has_single_complete_panel_frame(self):
        self.check_transition('confirm')

    def test_popup_input_waits_until_render_lock_is_available(self):
        self.check_transition('render_busy')

    def test_explicit_cancel_restores_photo_in_one_frame(self):
        self.check_transition('cancel')

    def test_back_and_outside_dismissals_restore_photo_in_one_frame(self):
        self.check_transition('back_outside')

    def test_rotate_commits_one_photo_frame_and_returns_upright(self):
        self.check_transition('rotate')

    def test_uncached_jpeg_rotation_defers_decode_and_commits_one_complete_frame(self):
        self.check_transition('rotate_jpeg')

    def test_successful_cover_redraws_photo_once_after_framebuffer_loan(self):
        self.check_transition('cover')

    def test_boot_and_shutdown_chooser_return_to_photo(self):
        self.check_transition('cover_boot')
        self.check_transition('cover_shutdown')

    def test_failed_cover_notice_has_complete_photo_underneath(self):
        self.check_transition('cover_failure')

    def test_delete_commits_one_thumbnail_free_filename_list_frame(self):
        self.check_transition('delete')

    def test_failed_original_delete_keeps_photo_and_clears_confirmation_residue(self):
        self.check_transition('delete_failure')


if __name__ == '__main__':
    unittest.main()
