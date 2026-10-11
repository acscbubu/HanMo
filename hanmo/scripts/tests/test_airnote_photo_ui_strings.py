"""Validate the new device labels and their real built-in CJK glyphs."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).parents[2]
KEYS = (
    "STR_AIRPHOTO_LIST_VIEW", "STR_AIRPHOTO_GRID_VIEW",
    "STR_AIRNOTE_MULTI_SELECT", "STR_AIRNOTE_MULTI_ACTIONS", "STR_AIRNOTE_MULTI_REORDER",
    "STR_AIRNOTE_MULTI_MOVE", "STR_AIRNOTE_MULTI_DELETE", "STR_AIRNOTE_MULTI_LIMIT",
    "STR_AIRNOTE_MULTI_END", "STR_AIRNOTE_MULTI_DELETE_CONFIRM",
    "STR_AIRNOTE_MULTI_MOVE_RESULT", "STR_AIRNOTE_MULTI_DELETE_RESULT",
)

class DeviceUiStringsTest(unittest.TestCase):
    def test_tr_calls_do_not_pass_conditional_expressions(self):
        # tr(id) token-pastes StrId::id; a ternary must wrap two tr() calls.
        for relative in ("activities/apps/airphoto/AirPhotoActivity.cpp",
                         "activities/home/FileBrowserActivity.cpp"):
            source = (ROOT / "src" / relative).read_text(encoding="utf-8")
            self.assertNotRegex(source, r'tr\([^)]*\?[^)]*\)', relative)

    def test_all_new_labels_exist_in_each_locale(self):
        for language in ("english", "chinese", "chinese-traditional"):
            text = (ROOT / f"lib/I18n/translations/{language}.yaml").read_text(encoding="utf-8")
            for key in KEYS:
                self.assertRegex(text, rf'(?m)^{key}: "[^"\n]+"$', f"{language}: {key}")

    def test_delete_result_names_all_three_counts(self):
        for language in ("english", "chinese", "chinese-traditional"):
            text = (ROOT / f"lib/I18n/translations/{language}.yaml").read_text(encoding="utf-8")
            value = re.search(r'(?m)^STR_AIRNOTE_MULTI_DELETE_RESULT: "([^"\n]+)"$', text)
            self.assertIsNotNone(value)
            self.assertEqual(value.group(1).count("%u"), 3, language)

    def test_chinese_labels_fit_all_six_device_fonts(self):
        texts = []
        for language in ("chinese", "chinese-traditional"):
            text = (ROOT / f"lib/I18n/translations/{language}.yaml").read_text(encoding="utf-8")
            for key in KEYS:
                value = re.search(rf'(?m)^{key}: "([^"\n]+)"$', text)
                self.assertIsNotNone(value, f"{language}: {key}")
                texts.append(value.group(1))
        needed = {ord(c) for text in texts for c in text if "一" <= c <= "鿿"}
        fontdir = ROOT / "lib/EpdFont/builtinFonts"
        common = (fontdir / "notosans_cjk_common_intervals.h").read_text()
        for size in (8, 10, 12, 14, 16, 18):
            font = (fontdir / f"notosans_cjk_{size}.h").read_text()
            intervals = common if "notosans_cjk_commonIntervals," in font else font
            ranges = [(int(a, 16), int(b, 16)) for a, b in re.findall(
                r'\{\s*(0x[0-9A-Fa-f]+),\s*(0x[0-9A-Fa-f]+),\s*0x[0-9A-Fa-f]+\s*\}', intervals)]
            self.assertTrue(ranges)
            missing = sorted(c for c in needed if not any(a <= c <= b for a, b in ranges))
            self.assertEqual(missing, [], f"{size}pt missing: {''.join(map(chr, missing))}")

if __name__ == "__main__":
    unittest.main()
