"""Focused, source-level web locale parity checks for Home and Fonts."""

from html.parser import HTMLParser
from pathlib import Path
import re
import unittest
import json
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[2] / "src/network/html"
LOCALES = ("zh-CN", "zh-Hant")


def source(locale, page):
    return (ROOT / locale / f"{page}Page.html").read_text(encoding="utf-8")


def css(html):
    return re.search(r"<style>(.*?)</style>", html, re.S).group(1)


class Structure(HTMLParser):
    """Compare actual markup, including nav hooks, without comparing translations."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(("start", tag, tuple(sorted(attrs))))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        self.tags.append(("end", tag))


def structure(html):
    parser = Structure()
    # The language attribute is the only attribute allowed to differ from EN.
    parser.feed(re.sub(r'<html lang="[^"]+">', '<html lang="en">', html, count=1))
    return parser.tags


def inline_script(html):
    scripts = re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', html, re.S)
    if len(scripts) != 1:
        raise AssertionError("expected exactly one inline script")
    return scripts[0]


NODE_HOME_PROBE = r"""
const vm = require('node:vm');
const fs = require('node:fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const nodes = Object.fromEntries(['serial', 'version', 'ip-address', 'free-heap']
  .map(id => [id, {textContent: '', attrs: {}, setAttribute(k, v) {this.attrs[k] = v;}}]));
const wifi = {textContent: '', className: 'status', style: {}};
const requests = [];
let refreshes = 0;
const context = {
  document: {getElementById(id) { return nodes[id]; }, querySelector(selector) {
    if (selector !== '.status') throw Error('unexpected selector ' + selector);
    return wifi;
  }},
  window: input.nav ? {crossmuxNav: {refreshBranding() { refreshes++; }}} : {},
  fetch: async url => {
    requests.push(url);
    return input.failure ? {ok: false, status: 503, statusText: 'Offline'} : {
      ok: true, json: async () => ({serial:'X4-12', version:'v2', ip:'192.0.2.1', freeHeap:12345})
    };
  },
  console: {error() {}}
};
vm.createContext(context);
vm.runInContext(input.script, context);
(async () => {
  await context.fetchStatus();
  console.log(JSON.stringify({requests, refreshes, nodes, wifi}));
})().catch(err => {console.error(err); process.exitCode = 1;});
"""


def home_result(html, failure, nav=True):
    node = shutil.which('node') or shutil.which('node.exe')
    if not node:
        raise AssertionError('Node.js required to exercise embedded page JavaScript')
    proc = subprocess.run(
        [node, '-e', NODE_HOME_PROBE],
        input=json.dumps({'script': inline_script(html), 'failure': failure, 'nav': nav}),
        text=True, capture_output=True,
    )
    if proc.returncode:
        raise AssertionError(f'Home JS failed: {proc.stderr}')
    return json.loads(proc.stdout)


NODE_FONT_PROBE = r"""
const vm = require('node:vm');
const fs = require('node:fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
class Element {
  constructor(tag) {
    this.tag = tag; this.children = []; this.listeners = {};
    this.textContent = ''; this.className = ''; this.style = {};
  }
  appendChild(child) {this.children.push(child); return child;}
  replaceChildren(...children) {this.children = children;}
  addEventListener(event, fn) {(this.listeners[event] ||= []).push(fn);}
}
const ids = Object.fromEntries(['families', 'fontFiles', 'pickedInfo', 'uploadForm', 'status']
  .map(id => [id, new Element(id)]));
ids.fontFiles.files = input.files || [];
const requests = [], prompts = [];
const context = {
  document: {getElementById(id) {if (!ids[id]) throw Error('unknown id ' + id); return ids[id];},
    createElement(tag) {return new Element(tag);}},
  FormData: class {constructor() {this.parts = [];}
    append(k, value, filename) {this.parts.push([k, value, filename]);}},
  confirm(msg) {prompts.push(msg); return input.confirm !== false;},
  fetch: async (url, opts = {}) => {
    requests.push({url, method: opts.method || 'GET', body: opts.body?.parts || opts.body || null});
    if (url === '/api/fonts') {
      if (input.mode === 'list-error') throw Error('Offline');
      return {json: async () => ({families: input.families || []})};
    }
    if (url === '/api/fonts/delete') {
      if (input.mode === 'delete-error') throw Error('Offline');
      return {ok: input.mode !== 'delete-refused'};
    }
    if (url === '/api/fonts/upload') {
      if (input.mode === 'upload-error') throw Error('Offline');
      return {json: async () => input.mode === 'upload-refused'
        ? {ok:false, error:'storage full'} : {ok:true}};
    }
    throw Error('unexpected route ' + url);
  }
};
vm.createContext(context);
vm.runInContext(input.script, context);
(async () => {
  await context.loadFonts();
  if (input.mode.startsWith('upload')) {
    ids.fontFiles.listeners.change[0].call(ids.fontFiles);
    await ids.uploadForm.listeners.submit[0]({preventDefault() {}});
  }
  if (input.mode.startsWith('delete')) await context.deleteFamily(input.family);
  function snapshot(el) {
    return {tag:el.tag, text:el.textContent, className:el.className,
      children:el.children.map(snapshot)};
  }
  console.log(JSON.stringify({requests, prompts, families:snapshot(ids.families),
    pickedInfo:ids.pickedInfo.textContent, status:snapshot(ids.status)}));
})().catch(err => {console.error(err); process.exitCode = 1;});
"""


def font_result(html, mode, **kwargs):
    node = shutil.which('node') or shutil.which('node.exe')
    if not node:
        raise AssertionError('Node.js required to exercise embedded page JavaScript')
    proc = subprocess.run(
        [node, '-e', NODE_FONT_PROBE],
        input=json.dumps({'script': inline_script(html), 'mode': mode, **kwargs}),
        text=True, capture_output=True,
    )
    if proc.returncode:
        raise AssertionError(f'Fonts JS failed: {proc.stderr}')
    return json.loads(proc.stdout)


class WebLocaleHomeFontsTest(unittest.TestCase):
    def test_home_uses_english_css_and_dom(self):
        english = source("en", "Home")
        for locale in LOCALES:
            with self.subTest(locale=locale):
                localized = source(locale, "Home")
                self.assertIn(f'<html lang="{locale}">', localized)
                self.assertEqual(css(english), css(localized), "Home CSS must match English byte for byte")
                self.assertEqual(structure(english), structure(localized), "Home DOM and nav hooks must match English")
                self.assertIn("/api/status", localized)
                self.assertIn('data-brand="version"', localized)


    def test_home_status_updates_brand_and_shows_localized_errors(self):
        for locale, fallback, unit, error in (
            ("zh-CN", "不可用", "字节", "暂时无法读取设备状态"),
            ("zh-Hant", "無法取得", "位元組", "暫時無法讀取裝置狀態"),
        ):
            with self.subTest(locale=locale):
                html = source(locale, "Home")
                success = home_result(html, failure=False)
                self.assertEqual(set(success["requests"]), {"/api/status"})
                self.assertEqual(success["nodes"]["version"]["attrs"]["data-brand-default"], "v2")
                self.assertEqual(home_result(html, failure=False, nav=False)["nodes"]["version"]["textContent"], "v2")
                self.assertEqual(success["nodes"]["serial"]["textContent"], "X4-12")
                self.assertEqual(success["nodes"]["free-heap"]["textContent"], f"12,345 {unit}")
                self.assertGreater(success["refreshes"], 0)
                failed = home_result(html, failure=True, nav=False)
                self.assertEqual(failed["nodes"]["serial"]["textContent"], fallback)
                self.assertEqual(failed["nodes"]["version"]["textContent"], fallback)
                self.assertIn(error, failed["wifi"]["textContent"])
                self.assertIn("503", failed["wifi"]["textContent"])
                self.assertNotEqual(failed["wifi"]["style"].get("backgroundColor"), None)
                self.assertEqual(failed["wifi"]["style"].get("maxWidth"), "65%")
                self.assertEqual(failed["wifi"]["style"].get("overflowWrap"), "anywhere")


    def test_fonts_uses_english_css_and_dom(self):
        english = source("en", "Fonts")
        for locale in LOCALES:
            with self.subTest(locale=locale):
                localized = source(locale, "Fonts")
                self.assertIn(f'<html lang="{locale}">', localized)
                self.assertEqual(css(english), css(localized), "Fonts CSS must match English byte for byte")
                self.assertEqual(structure(english), structure(localized), "Fonts DOM and hooks must match English")
                for endpoint in ("/api/fonts", "/api/fonts/delete", "/api/fonts/upload"):
                    self.assertIn(endpoint, localized)

    def test_fonts_list_is_localized_and_untrusted_family_is_dom_text(self):
        for locale, empty, list_error, delete_label in (
            ("zh-CN", "尚未安装自定义字体", "无法读取字体列表", "删除"),
            ("zh-Hant", "尚未安裝自訂字體", "無法讀取字體列表", "刪除"),
        ):
            with self.subTest(locale=locale):
                html = source(locale, "Fonts")
                self.assertEqual(font_result(html, "empty")["families"]["children"][0]["text"], empty)
                self.assertEqual(font_result(html, "list-error")["families"]["children"][0]["text"], list_error)
                name = '<img src=x onerror=alert(1)>'
                result = font_result(html, "list", families=[{
                    "name": name, "sizes": [12], "files": [{"size": 1024}]
                }])
                row = result["families"]["children"][0]
                self.assertEqual(row["children"][0]["children"][0]["text"], name)
                self.assertEqual(row["children"][1]["text"], delete_label)
                self.assertIn("12pt · 1 KB", row["children"][0]["children"][1]["text"])

    def test_fonts_upload_rejects_mixed_families_and_keeps_api_payload(self):
        for locale, mixed_text, success_text in (
            ("zh-CN", "请只选择同一个字体家族的文件", "已将 2 个文件上传到字体家族"),
            ("zh-Hant", "請只選取同一個字體家族的檔案", "已將 2 個檔案上傳至字體家族"),
        ):
            with self.subTest(locale=locale):
                html = source(locale, "Fonts")
                mixed = font_result(html, "upload-ok", files=[
                    {"name": "A_12.cpfont"}, {"name": "B_14.cpfont"}
                ])
                self.assertIn(mixed_text, mixed["status"]["text"])
                self.assertNotIn("/api/fonts/upload", [r["url"] for r in mixed["requests"]])
                good = font_result(html, "upload-ok", files=[
                    {"name": "Bookerly_12.cpfont"}, {"name": "Bookerly_14.cpfont"}, {"name": "ignore.txt"}
                ])
                uploads = [r for r in good["requests"] if r["url"] == "/api/fonts/upload"]
                self.assertEqual(len(uploads), 2)
                self.assertEqual([r["method"] for r in uploads], ["POST", "POST"])
                self.assertEqual([r["body"][0][:2] for r in uploads],
                                 [["family", "Bookerly"], ["family", "Bookerly"]])
                self.assertEqual([r["body"][1][2] for r in uploads],
                                 ["Bookerly_12.cpfont", "Bookerly_14.cpfont"])
                self.assertIn(success_text, good["status"]["text"])

    def test_fonts_delete_keeps_confirmation_and_localized_failure(self):
        for locale, question, failure in (
            ("zh-CN", "确定删除字体家族", "删除“Custom”失败"),
            ("zh-Hant", "確定刪除字體家族", "刪除「Custom」失敗"),
        ):
            with self.subTest(locale=locale):
                html = source(locale, "Fonts")
                result = font_result(html, "delete-refused", family="Custom")
                self.assertIn(question, result["prompts"][0])
                delete = [r for r in result["requests"] if r["url"] == "/api/fonts/delete"]
                self.assertEqual(len(delete), 1)
                self.assertEqual(json.loads(delete[0]["body"]), {"family": "Custom"})
                self.assertIn(failure, result["status"]["text"])
                cancelled = font_result(html, "delete-refused", family="Custom", confirm=False)
                self.assertNotIn("/api/fonts/delete", [r["url"] for r in cancelled["requests"]])


if __name__ == "__main__":
    unittest.main()
