"""Verify the per-browser web UI language choice, independently of device language."""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
HEADER = ROOT / 'src/network/WebUiLanguage.h'
SERVER = ROOT / 'src/network/CrossPointWebServer.cpp'
I18N = ROOT / 'lib/I18n'
NAV = ROOT / 'src/network/html/js/nav.js'
HARNESS = r'''
#include "WebUiLanguage.h"
int main() {
  if (webui::pageLanguage(Language::EN, "zh-Hant") != webui::PageLanguage::ZH_HANT) return 1;
  if (webui::pageLanguage(Language::ZH_CN, "en") != webui::PageLanguage::EN) return 2;
  if (webui::pageLanguage(Language::ZH_CN, nullptr) != webui::PageLanguage::ZH_CN) return 3;
  if (webui::pageLanguage(Language::EN, nullptr) != webui::PageLanguage::EN) return 4;
  if (webui::pageLanguage(Language::EN, "other") != webui::PageLanguage::EN) return 5;
  return 0;
}
'''

class WebUiLanguageTest(unittest.TestCase):
    def test_browser_choice_overrides_device_only_for_web_pages(self):
        with tempfile.TemporaryDirectory() as td:
            source = pathlib.Path(td) / 'probe.cpp'
            binary = pathlib.Path(td) / 'probe'
            source.write_text(HARNESS)
            compiled = subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-I', str(HEADER.parent), '-I', str(I18N), str(source), '-o', str(binary)], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_pages_are_wired_to_web_selector(self):
        server = SERVER.read_text()
        self.assertIn('webui::pageLanguage(I18N.getLanguage()', server)
        self.assertIn('server->hasArg("ui")', server)
        self.assertIn('localizedPage(server.get(),', server)
        for name in ('HomePageHtml', 'FilesPageHtml', 'SettingsPageHtml', 'FontsPageHtml'):
            self.assertIn('web_zh_hant::' + name, server)
        nav = NAV.read_text()
        self.assertIn("hanmo.web-ui", nav)
        self.assertIn("value=\"zh-CN\"", nav)
        self.assertIn("value=\"zh-Hant\"", nav)
        self.assertIn('new URL(window.location.href)', nav)

    def test_labels_match_servable_html_bundles(self):
        html_root = ROOT / 'src/network/html'
        for page in ('SettingsPage', 'HomePage', 'FilesPage', 'FontsPage'):
            english = (html_root / 'en' / f'{page}.html').read_text()
            chinese = (html_root / 'zh-CN' / f'{page}.html').read_text()
            traditional = (html_root / 'zh-Hant' / f'{page}.html').read_text()
            self.assertIn('<html lang="en">', english)
            self.assertIn('<html lang="zh-CN">', chinese)
            self.assertNotIn('<html lang="zh-Hant">', chinese)
            self.assertIn('<html lang="zh-Hant">', traditional)
        self.assertIn('简体中文', NAV.read_text().replace(r'\u7b80\u4f53\u4e2d\u6587', '简体中文'))
        self.assertIn('繁體中文</option>', NAV.read_text().replace(r'\u7e41\u9ad4\u4e2d\u6587', '繁體中文'))

    def test_settings_api_uses_requested_language_without_mutating_device_language(self):
        source = r'''
#include <cstring>
#include "I18n.h"
#include "WebUiLanguage.h"
int main() {
  I18N.setLanguage(Language::ZH_TW);  // Device remains Traditional Chinese.
  if (webui::settingsLanguage(I18N.getLanguage(), nullptr) != Language::ZH_TW) return 1;
  if (webui::settingsLanguage(I18N.getLanguage(), "invalid") != Language::ZH_TW) return 2;
  const auto en = webui::settingsLanguage(I18N.getLanguage(), "en");
  const auto cn = webui::settingsLanguage(I18N.getLanguage(), "zh-CN");
  if (en != Language::EN || cn != Language::ZH_CN) return 3;
  if (webui::settingsLanguage(I18N.getLanguage(), "zh-Hant") != Language::ZH_TW) return 4;
  if (std::strcmp(webui::settingsText(StrId::STR_CAT_DISPLAY, en), "Display") != 0) return 5;
  if (std::strcmp(webui::settingsText(StrId::STR_CAT_DISPLAY, cn), "显示") != 0) return 6;
  if (std::strcmp(webui::settingsText(StrId::STR_CAT_DISPLAY, I18N.getLanguage()), "顯示") != 0) return 7;
  if (std::strcmp(webui::settingsDynamicOption("dictionaryName", 0, "无", en), "None") != 0) return 8;
  if (std::strcmp(webui::settingsDynamicOption("dictionaryName", 1, "Personal", en), "Personal") != 0) return 9;
  if (std::strcmp(webui::settingsDynamicOption("fontSize", 0, "12 pt", cn), "12 pt") != 0) return 10;
  if (I18N.getLanguage() != Language::ZH_TW) return 11;
  return 0;
}
'''
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td)
            source_path = path / 'probe.cpp'
            executable = path / 'probe'
            source_path.write_text(source)
            compiled = subprocess.run([
                'g++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                '-I', str(HEADER.parent), '-I', str(I18N),
                str(source_path), str(I18N / 'I18n.cpp'), str(I18N / 'I18nStrings.cpp'),
                '-o', str(executable),
            ], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, f'API language probe returned {result.returncode}: {result.stderr}')

    def test_settings_api_uses_selected_language_only_for_responses(self):
        server = SERVER.read_text()
        get = server.split('void CrossPointWebServer::handleGetSettings() const {', 1)[1].split(
            'void CrossPointWebServer::handlePostSettings()', 1)[0]
        post = server.split('void CrossPointWebServer::handlePostSettings() {', 1)[1].split(
            '// ---- OPDS Server API ----', 1)[0]
        self.assertIn('webui::settingsLanguage(I18N.getLanguage()', get)
        self.assertIn('webui::settingsText(s.nameId, settingsLanguage)', get)
        self.assertIn('webui::settingsText(s.category, settingsLanguage)', get)
        self.assertIn('webui::settingsText(opt, settingsLanguage)', get)
        self.assertIn('webui::settingsDynamicOption(s.key,', get)
        self.assertIn('webui::settingsLanguage(I18N.getLanguage()', post)
        self.assertIn('webui::settingsText(StrId::STR_HOTSPOT_NAME_INVALID, settingsLanguage)', post)
        self.assertIn('webui::settingsText(StrId::STR_SETTINGS_SAVE_FAILED, settingsLanguage)', post)
        self.assertNotIn('I18N.setLanguage(', get)
        self.assertNotIn('I18N.setLanguage(', post)

    def test_simplified_settings_groups_do_not_claim_traditional_spelling(self):
        html = (ROOT / 'src/network/html/zh-CN/SettingsPage.html').read_text()
        for text in ('首页快捷菜单', '主页文字菜单', '轻触与手势', '画面快捷栏', '下拉快捷栏', '屏幕轻触区域'):
            self.assertTrue(text in html, f'missing simplified label: {text}')
        for text in ('首頁捷徑選單', '主頁文字選單', '輕觸與手勢', '畫面快捷列'):
            self.assertTrue(text not in html, f'stale Traditional label: {text}')

    def test_settings_line_endings_are_preserved(self):
        for lang in ('en', 'zh-CN', 'zh-Hant'):
            data = (ROOT / 'src/network/html' / lang / 'SettingsPage.html').read_bytes()
            self.assertEqual(data.count(b'\n'), data.count(b'\r\n'))

if __name__ == '__main__':
    unittest.main()
