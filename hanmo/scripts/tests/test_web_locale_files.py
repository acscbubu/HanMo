"""Files-page locale parity against the shipped English markup and behavior.

Run in WSL: python3 -m unittest scripts.tests.test_web_locale_files -v
"""

import re
import shutil
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "src/network/html"
NODE = shutil.which("node") or shutil.which("node.exe")
if not NODE and Path("/mnt/c/Program Files/nodejs/node.exe").exists():
    NODE = "/mnt/c/Program Files/nodejs/node.exe"


def page(locale):
    return (ROOT / locale / "FilesPage.html").read_text(encoding="utf-8")


def css(html):
    return re.search(r"<style>(.*?)</style>", html, re.S).group(1)


def markup(html):
    return html.split("<body>", 1)[1].split("<script>", 1)[0]


class Markup(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__()
        self.elements = []
        self.paths = []
        self.stack = []
        self.unbalanced = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))
        self.paths.append(tuple(self.stack + [tag]))
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        else:
            self.unbalanced.append(tag)

    def handle_data(self, data):
        self.text.append(data)


def elements(html):
    parser = Markup()
    parser.feed(markup(html))
    return parser


class FilesLocaleTests(unittest.TestCase):
    def test_chinese_files_use_english_layout_styles(self):
        reference = css(page("en"))
        for locale in ("zh-CN", "zh-Hant"):
            with self.subTest(locale=locale):
                self.assertEqual(css(page(locale)), reference)

    def test_chinese_files_match_english_dom_and_keep_controls(self):
        def signature(html):
            return [
                (tag, tuple(sorted((k, v) for k, v in attrs.items()
                                    if k not in ("title", "placeholder", "aria-label"))))
                for tag, attrs in elements(html).elements
            ]

        english = elements(page("en"))
        self.assertEqual(english.unbalanced, [])
        self.assertEqual(english.stack, [])
        reference = signature(page("en"))
        for locale in ("zh-CN", "zh-Hant"):
            with self.subTest(locale=locale):
                html = page(locale)
                parsed = elements(html)
                self.assertEqual(signature(html), reference)
                self.assertEqual(parsed.paths, english.paths)
                self.assertEqual(parsed.unbalanced, [])
                self.assertEqual(parsed.stack, [])
                attrs = [a for _, a in parsed.elements]
                ids = [a["id"] for a in attrs if "id" in a]
                handlers = [(k, v) for a in attrs for k, v in a.items()
                            if k.startswith("on")]
                self.assertEqual(len(ids), 71)  # plus selectAllCheckbox in dynamic table markup
                self.assertEqual(len(set(ids)), 71)
                self.assertEqual(len(handlers), 53)
                self.assertEqual(len(set(handlers)), 47)
                self.assertIn('id="selectAllCheckbox"', html)

    def test_locale_labels_are_distinct_in_markup_and_dynamic_messages(self):
        simplified = page("zh-CN")
        traditional = page("zh-Hant")
        self.assertIn('<html lang="zh-CN">', simplified)
        self.assertIn('<html lang="zh-Hant">', traditional)
        for text in ("文件管理", "上传", "新建文件夹", "删除所选"):
            self.assertIn(text, markup(simplified))
        for text in ("檔案管理", "上傳", "新增資料夾", "刪除所選"):
            self.assertIn(text, markup(traditional))
        for text in ("刪除選取項目", "下載為 ZIP", "連線失敗", "讀取檔案失敗", "轉換完成"):
            self.assertTrue(text in traditional, f"Traditional message missing: {text}")
        for unwanted in ("上传", "新建文件夹", "删除所选", "网络连接", "转换完成", "專案"):
            self.assertFalse(unwanted in traditional, f"Unexpected Hant wording: {unwanted}")
        self.assertIn("function localizeError(error)", simplified)
        self.assertIn("function localizeError(error)", traditional)

    @unittest.skipUnless(NODE, "Node.js required to parse the inline JavaScript")
    def test_scripts_parse_and_preserve_cn_function_and_bulk_behavior(self):
        def script(html):
            return html.rsplit("<script>", 1)[1].split("</script>", 1)[0]

        cn = script(page("zh-CN"))
        hant = script(page("zh-Hant"))
        names = lambda s: set(re.findall(r"(?:async\s+)?function\s+(\w+)\s*\(", s))
        self.assertEqual(names(cn), names(hant))
        for function in ("localizeError", "confirmDelete", "confirmMove",
                         "bulkDeleteSelected", "bulkMoveSelected", "bulkDownloadSelected",
                         "uploadFile", "convertEpubFile"):
            self.assertIn(function, names(cn))
        for locale, source in (("zh-CN", cn), ("zh-Hant", hant)):
            with self.subTest(locale=locale):
                parsed = subprocess.run([NODE, "--check", "-"], input=source,
                                        text=True, capture_output=True, check=False)
                self.assertEqual(parsed.returncode, 0, parsed.stderr)
                self.assertIn("// ---- Bulk selection ----", source)
                self.assertIn("// ---- End bulk selection ----", source)
                self.assertIn("fetch('/delete'", source)
                self.assertIn("xhr.open('POST', '/move', true)", source)

    def test_epub_font_cleanup_matches_english_behavior(self):
        for locale in ("zh-CN", "zh-Hant"):
            with self.subTest(locale=locale):
                html = page(locale)
                for needle in ("function collectFontPaths(", "function stripFontFaceRules(",
                               "function stripFontEncryptionEntries(",
                               "const fontPaths = collectFontPaths(zip, opfContent, opfPath);",
                               "if (fontPaths.has(path))", "const enc = stripFontEncryptionEntries(t, fontPaths);",
                               "stripFontFaceRules(css)", "stripFontFaceRules(t)",
                               "fixOPF(t, opfContent, opfDir, splitImages, fontPaths)"):
                    self.assertTrue(needle in html, f"{locale} missing {needle}")

    @unittest.skipUnless(NODE, "Node.js required for the bulk-action harness")
    def test_existing_bulk_actions_also_work_in_traditional(self):
        source = (ROOT.parents[2] / "scripts/tests/test_files_bulk.mjs").read_text()
        self.assertIn("const root = fileURLToPath(new URL('../..', import.meta.url));", source)
        source = source.replace("const root = fileURLToPath(new URL('../..', import.meta.url));",
                                "const root = process.cwd();", 1)
        source = source.replace("'zh-CN'", "'zh-Hant'")
        source = source.replace("for (const locale of ['en', 'zh-Hant'])",
                                "for (const locale of ['zh-Hant'])", 1)
        result = subprocess.run([NODE, "--input-type=module", "-"],
                                input=source, text=True, capture_output=True,
                                cwd=ROOT.parents[2], check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('"ok":true', result.stdout)


if __name__ == "__main__":
    unittest.main()
