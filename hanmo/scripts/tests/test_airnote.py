"""AirNote upload policy and the device/web entry points."""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


class AirNoteTest(unittest.TestCase):
    def test_note_policy_rejects_invalid_input_and_preserves_utf8(self):
        source = r'''
#include "src/AirNotePolicy.h"
#include "src/AirNoteStore.h"
#include <map>
#include <cassert>
#include <string>
using namespace AirNotePolicy;
struct FakeFS {
  std::map<std::string, std::string> files;
  int renameCount = 0, failRename = 0;
  bool failCleanup = false;
  bool exists(const char* p) { return files.count(p); }
  bool remove(const char* p) { if (failCleanup) return false; return files.erase(p); }
  bool rename(const char* from, const char* to) {
    if (++renameCount == failRename || !exists(from) || exists(to)) return false;
    files[to] = files[from]; files.erase(from); return true;
  }
};
int main() {
  std::string_view title, body;
  const auto content = noteContent("中文", "尾端保留\n\n");
  assert(splitNote(content, title, body));
  assert(title == "中文" && body == "尾端保留\n\n");
  assert(!splitNote("broken", title, body));
  assert(!splitNote("title\n\n", title, body));
  assert(validFileName("中文-99.txt"));
  assert(validFileName(std::string(80, 'a') + "-99.txt"));
  assert(!validFileName(std::string(81, 'a') + "-99.txt"));
  for (const auto name : {"../x.txt", ".x.txt", "x.txt.bak", "/x.txt", "x\\a.txt", "x.txt/", "x.TXT"})
    assert(!validFileName(name));
  assert(!validFileName(std::string("a\0.txt", 6)));
  for (int failure = 0; failure <= 3; ++failure) {
    FakeFS fs; fs.files = {{"note", "old"}, {"stage", "new"}};
    fs.failRename = failure;
    bool invalidated = false;
    const bool saved = AirNoteStore::replace(fs, "note", "stage", "backup", [&](const std::string&) {
      invalidated = true; return true;
    });
    assert(invalidated); // includes equal-length edits, before renaming the original
    if (failure == 1 || failure == 2) {
      assert(!saved); assert(AirNoteStore::recover(fs, "note", "backup"));
      assert(fs.files["note"] == "old");
    } else { assert(saved); assert(fs.files["note"] == "new"); }
  }
  FakeFS fs; fs.files = {{"note", "old"}, {"stage", "new"}};
  assert(!AirNoteStore::replace(fs, "note", "stage", "backup", [](const auto&) { return false; }));
  assert(fs.files["note"] == "old" && fs.renameCount == 0);
  // Power loss before and after the final rename.
  fs.files = {{"backup", "old"}, {"stage", "new"}};
  assert(AirNoteStore::recover(fs, "note", "backup")); assert(fs.files["note"] == "old");
  fs.files = {{"backup", "old"}, {"note", "new"}};
  assert(AirNoteStore::recover(fs, "note", "backup")); assert(fs.files["note"] == "new");
  fs.files = {{"note", "old"}, {"stage", "new"}}; fs.failCleanup = true;
  assert(AirNoteStore::replace(fs, "note", "stage", "backup", [](const auto&) { return true; }));
  assert(fs.files["note"] == "new" && fs.files["backup"] == "old");

  assert(validTitle("會議筆記"));
  assert(validText("第一行\n第二行"));
  assert(noteContent("會議筆記", "第一行\n第二行") ==
         "會議筆記\n\n第一行\n第二行\n");
  assert(fileName("會議筆記", 1) == "會議筆記.txt");
  assert(fileName("會議筆記", 2) == "會議筆記-2.txt");
  assert(!validTitle(""));
  assert(!validTitle("  \t"));
  assert(!validTitle("../etc"));
  assert(!validTitle(".hidden"));
  assert(!validTitle("bad\\name"));
  assert(!validTitle("bad:name"));
  assert(!validTitle("trailing."));
  assert(!validTitle("bad\nname"));
  assert(!validTitle(std::string(kMaxTitleBytes + 1, 'x')));
  assert(!validTitle(std::string("\xED\xA0\x80", 3))); // surrogate
  assert(!validTitle(std::string("\xC0\xAF", 2))); // overlong
  assert(!validText("\n \t"));
  assert(!validText(std::string("a\0b", 3)));
  assert(!validText(std::string(kMaxBodyBytes + 1, 'x')));
  assert(!validText(std::string("\xF4\x90\x80\x80", 4)));
  assert(validText(std::string(kMaxBodyBytes, 'x')));
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            cpp = pathlib.Path(tmp) / 'test.cpp'
            exe = pathlib.Path(tmp) / 'test'
            cpp.write_text(source)
            subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', '-I' + str(ROOT),
                            str(cpp), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)

    def test_settings_page_and_server_route(self):
        server = (ROOT / 'src/network/CrossPointWebServer.cpp').read_text()
        self.assertIn('"/api/airnote", HTTP_POST', server)
        self.assertIn('handlePostAirNote()', server)
        for lang in ('en', 'zh-CN'):
            html = (ROOT / f'src/network/html/{lang}/SettingsPage.html').read_text()
            self.assertIn('id="navpane-airnote"', html)
            self.assertIn('id="pane-airnote"', html)
            self.assertIn("'/api/airnote'", html)
            self.assertIn('textarea', html)

    def test_change_history_records_airnote_in_three_languages(self):
        history = (ROOT / 'src/activities/settings/ChangeHistoryData.h').read_text()
        self.assertIn('2026-09-23", StrId::STR_CHANGE_AIRNOTE_TITLE', history)
        for lang in ('english', 'chinese', 'chinese-traditional'):
            translations = (ROOT / f'lib/I18n/translations/{lang}.yaml').read_text()
            for field in ('TITLE', 'WHAT', 'HOW', 'NOTE'):
                self.assertIn('STR_CHANGE_AIRNOTE_' + field + ':', translations)

    def test_device_app_uses_existing_txt_reader(self):
        app = (ROOT / 'src/activities/apps/AppsMenuActivity.cpp').read_text()
        manager = (ROOT / 'src/activities/ActivityManager.cpp').read_text()
        self.assertIn('AirNote = 20', app)
        self.assertIn('StrId::STR_AIRNOTE_TITLE', app)
        self.assertIn('goToAirNote()', manager)
        self.assertIn('goToFileBrowser("/AirNote")', manager)
        self.assertIn('FsHelpers::hasTxtExtension(path)',
                      (ROOT / 'src/activities/reader/ReaderActivity.cpp').read_text())


if __name__ == '__main__':
    unittest.main()
