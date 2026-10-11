"""Every Home menu action must resolve a 32px glyph on every theme that draws one.

AirNote and AirPage regressed here: HomeActivity named icons (Text, Image) that
exist only in the legacy 24px table, so the Home row rendered with no icon at
all -- and on the carousel, which is an icon-only tile bar, with nothing at all.
Two icon sets are in play and they are NOT interchangeable: the legacy
LyraTheme::iconForName bitmaps are stored pre-rotated for GfxRenderer::drawIcon,
while the modern listIcons/InxAppIcons rows are stored upright for
InxAppIcons::draw. A glyph is only reachable if some set has it AND the theme
consults that set.
"""
import pathlib
import re
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]

# The three themes that paint Home icons, and the function that does it.
HOME_DRAWERS = {
    "InxTheme": ("src/components/themes/inx/InxTheme.cpp", "void InxTheme::drawButtonMenu"),
    "LyraTheme": ("src/components/themes/lyra/LyraTheme.cpp", "void LyraTheme::drawButtonMenu"),
    "LyraCarouselTheme": (
        "src/components/themes/lyra/LyraCarouselTheme.cpp",
        "void LyraCarouselTheme::drawHomeMenu",
    ),
}


def _body(path, signature):
    src = (ROOT / path).read_text()
    start = src.index(signature)
    return src[start : src.index("\n}\n", start)]


def _legacy_tables():
    """LyraTheme::iconForName, split into its 24px and 32px halves."""
    src = (ROOT / "src/components/themes/lyra/LyraTheme.cpp").read_text()
    fn = _body(src and "src/components/themes/lyra/LyraTheme.cpp", "const uint8_t* LyraTheme::iconForName")
    cut = fn.index("} else if (size == 32)")
    cases = lambda block: set(re.findall(r"case UIIcon::(\w+):", block))
    return cases(fn[fn.index("if (size == 24)") : cut]), cases(fn[cut:])


def _modern_table():
    src = (ROOT / "src/components/icons/inx_apps.h").read_text()
    get = src[src.index("constexpr const uint8_t* get(") :]
    return set(re.findall(r"case UIIcon::(\w+):", get[: get.index("\n}\n")]))


def _home_entries():
    """(HomeMenuItem, UIIcon) for every row in HomeActivity's kEntries table."""
    src = (ROOT / "src/activities/home/HomeActivity.cpp").read_text()
    table = src[src.index("constexpr HomeMenuEntry kEntries[]") :]
    table = table[: table.index("};")]
    return re.findall(r"\{HomeMenuItem::(\w+),\s*StrId::\w+,\s*(\w+)\}", table)


class HomeMenuIconsTest(unittest.TestCase):
    def test_every_home_action_resolves_a_32px_glyph(self):
        _, legacy32 = _legacy_tables()
        modern = _modern_table()
        reachable = legacy32 | modern
        entries = _home_entries()
        self.assertGreater(len(entries), 10, "kEntries table did not parse")

        missing = sorted(
            {f"{item} -> UIIcon::{icon}" for item, icon in entries if item != "NONE" and icon not in reachable}
        )
        self.assertEqual(
            [],
            missing,
            "Home actions with no 32px glyph in either icon set (they render blank): " + ", ".join(missing),
        )

    def test_home_drawing_themes_consult_both_icon_sets(self):
        """A glyph present in only one set still needs the theme to look there."""
        for theme, (path, signature) in HOME_DRAWERS.items():
            with self.subTest(theme=theme):
                body = _body(path, signature)
                self.assertIn("iconForName", body, f"{theme} stopped consulting the legacy icon table")
                self.assertIn(
                    "InxAppIcons::get", body, f"{theme} does not consult the modern icon set, so its glyphs draw blank"
                )

    def test_airnote_and_airpage_specifically(self):
        """The two that regressed, pinned against silent re-breakage."""
        legacy24, legacy32 = _legacy_tables()
        modern = _modern_table()
        icons = dict((item, icon) for item, icon in _home_entries())

        self.assertEqual(icons.get("AIRNOTE"), "Text")
        self.assertIn("Text", modern, "AirNote's glyph vanished from the modern set")
        self.assertNotIn("Text", legacy32, "Text gained a 32px legacy bitmap; simplify the fallback")

        self.assertEqual(icons.get("AIRPAGE"), "AirPage", "AirPage must not reuse the generic Image icon (24px only)")
        self.assertIn("AirPage", legacy32)
        self.assertIn("AirPage", modern)
        self.assertIn("Image", legacy24)
        self.assertNotIn("Image", legacy32)

    def test_fallback_glyphs_actually_have_ink(self):
        """Render through the real InxAppIcons::draw, not just the lookup table."""
        icons = ["Text", "AirPage"]
        names = sorted(set(re.findall(r"UIIcon::(\w+)", (ROOT / "src/components/icons/inx_apps.h").read_text())))
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            (tmp / "components/themes").mkdir(parents=True)
            (tmp / "components/themes/BaseTheme.h").write_text(
                "#pragma once\nenum class UIIcon {" + ",".join(names) + "};\n"
            )
            (tmp / "Icon.h").write_text(
                "#pragma once\n#include <cstdint>\nnamespace freeink {struct Icon {int w,h,advance; const uint8_t* bits;};}\n"
            )
            (tmp / "GfxRenderer.h").write_text(
                "#pragma once\nstruct GfxRenderer {mutable int ink=0; void fillRect(int,int,int,int,bool) const {++ink;}};\n"
            )
            code = ['#include "components/icons/inx_apps.h"', "#include <cassert>", "int main(){GfxRenderer r;"]
            for icon in icons:
                code.append(
                    f"assert(InxAppIcons::get(UIIcon::{icon})); r.ink=0;"
                    f" InxAppIcons::draw(r,UIIcon::{icon},0,0,1,false); assert(r.ink>10);"
                )
            code.append("}")
            (tmp / "t.cpp").write_text("\n".join(code) + "\n")
            subprocess.run(
                ["g++", "-std=c++20", "-DENABLE_CHINESE_VERSION=1", f"-I{tmp}", f"-I{ROOT / 'src'}",
                 str(tmp / "t.cpp"), "-o", str(tmp / "t")],
                check=True,
            )
            subprocess.run([str(tmp / "t")], check=True)


if __name__ == "__main__":
    unittest.main()
