"""The device web UI offers three independent browser languages."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ThreeWayWebLanguageTest(unittest.TestCase):
    def test_server_selects_exact_html_locale_without_changing_device(self):
        source = r'''
#include <cstring>
#include "I18n.h"
#include "WebUiLanguage.h"
int main() {
    using webui::PageLanguage;
    I18N.setLanguage(Language::ZH_TW);
    if (webui::pageLanguage(Language::EN, "zh-Hant") != PageLanguage::ZH_HANT) return 1;
    if (webui::pageLanguage(Language::ZH_CN, "zh-Hant") != PageLanguage::ZH_HANT) return 2;
    if (webui::pageLanguage(Language::ZH_TW, "zh-CN") != PageLanguage::ZH_CN) return 3;
    if (webui::pageLanguage(Language::ZH_TW, "en") != PageLanguage::EN) return 4;
    if (webui::pageLanguage(Language::EN, "en") != PageLanguage::EN) return 5;
    if (webui::pageLanguage(Language::ZH_CN, nullptr) != PageLanguage::ZH_CN) return 6;
    if (webui::pageLanguage(Language::ZH_TW, nullptr) != PageLanguage::ZH_HANT) return 7;
    if (webui::pageLanguage(Language::EN, nullptr) != PageLanguage::EN) return 8;
    if (webui::pageLanguage(Language::ZH_TW, "") != PageLanguage::ZH_HANT) return 9;
    if (webui::pageLanguage(Language::ZH_TW, "invalid") != PageLanguage::ZH_HANT) return 10;
    if (webui::settingsLanguage(I18N.getLanguage(), "zh-Hant") != Language::ZH_TW) return 11;
    if (webui::settingsLanguage(I18N.getLanguage(), "zh-CN") != Language::ZH_CN) return 12;
    if (webui::settingsLanguage(I18N.getLanguage(), "en") != Language::EN) return 13;
    if (I18N.getLanguage() != Language::ZH_TW) return 14;
    if (std::strcmp(webui::settingsDynamicOption("fontFamily", 0, "old", Language::EN), "Noto Serif") != 0) return 15;
    if (std::strcmp(webui::settingsDynamicOption("fontFamily", 1, "old", Language::EN), "Noto Sans") != 0) return 16;
    if (std::strcmp(webui::settingsDynamicOption("fontFamily", 2, "Family on SD", Language::ZH_TW), "Family on SD") != 0) return 17;
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as td:
            probe, binary = Path(td) / 'probe.cpp', Path(td) / 'probe'
            probe.write_text(source)
            lib = ROOT / 'lib/I18n'
            result = subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                                     '-I', str(lib), '-I', str(ROOT / 'src/network'), str(probe),
                                     str(lib / 'I18n.cpp'), str(lib / 'I18nStrings.cpp'),
                                     '-o', str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, f'probe returned {run.returncode}: {run.stderr}')

    def test_every_route_has_a_traditional_bundle(self):
        source = (ROOT / 'src/network/CrossPointWebServer.cpp').read_text()
        for name in ['HomePageHtml', 'FilesPageHtml', 'FontsPageHtml', 'SettingsPageHtml']:
            self.assertIn('web_zh_hant::' + name, source)
        for page in ['HomePage', 'FilesPage', 'FontsPage', 'SettingsPage']:
            template = ROOT / 'src/network/html/zh-Hant' / (page + '.html')
            self.assertTrue(template.is_file(), str(template))
            self.assertIn('<html lang="zh-Hant">', template.read_text())


if __name__ == '__main__':
    unittest.main()
