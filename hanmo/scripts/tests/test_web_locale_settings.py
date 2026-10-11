"""Contract tests for the Chinese Settings and Device page templates.

Run: python scripts/tests/test_web_locale_settings.py
"""

from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2] / "src/network/html"
NODE = shutil.which("node") or shutil.which("node.exe")
if not NODE and Path("/mnt/c/Program Files/nodejs/node.exe").exists():
    NODE = "/mnt/c/Program Files/nodejs/node.exe"


def page(locale):
    return (ROOT / locale / "SettingsPage.html").read_text(encoding="utf-8")


def style(html):
    return re.search(r"<style>(.*?)</style>", html, re.S).group(1)


class BodyShape(HTMLParser):
    """Compare visible element topology and event wiring, not translated prose."""

    def __init__(self):
        super().__init__()
        self.nodes = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        self.nodes.append((
            "start", "div" if tag == "nav" else tag,
            *(data.get(key) for key in (
                "id", "class", "href", "data-nav-key", "onclick", "onchange", "oninput",
            )),
        ))

    def handle_endtag(self, tag):
        self.nodes.append(("end", "div" if tag == "nav" else tag))


def body_shape(html):
    body = html.split("<body>", 1)[1].split("<script>", 1)[0]
    parser = BodyShape()
    parser.feed(body)
    return parser.nodes


class SettingsPageLocaleTests(unittest.TestCase):
    def test_simplified_page_has_english_layout_and_hooks(self):
        english = page("en")
        simplified = page("zh-CN")
        self.assertEqual(style(simplified), style(english))
        self.assertEqual(body_shape(simplified), body_shape(english))
        self.assertIn('<html lang="zh-CN">', simplified)
        self.assertIn('保存设置', simplified)

    def test_simplified_page_forwards_traditional_api_choice(self):
        simplified = page("zh-CN")
        self.assertEqual(simplified.count("ui === 'zh-Hant'"), 2)
        self.assertIn("body: JSON.stringify(changes)", simplified)
        self.assertNotIn("changes.ui", simplified)

    def test_traditional_passwords_stay_masked_with_either_chinese_api_label(self):
        traditional = page("zh-Hant")
        code = traditional.split("  function escapeHtml(unsafe) {", 1)[1].split("  function getValue(setting) {", 1)[0]
        code = "  function escapeHtml(unsafe) {" + code
        harness = r"""
const vm = require('node:vm');
const assert = require('node:assert/strict');
const code = require('node:fs').readFileSync(0, 'utf8');
const ctx = vm.createContext({});
vm.runInContext(code, ctx);
for (const [key, name, expected] of [
  ['credential', '登入密碼', true], ['credential', '登录密码', true],
  ['wifiSecret', 'Wi-Fi 憑證', true], ['ordinary', '一般欄位', false],
]) {
  const html = ctx.renderControl({key, name, type:'string', value:'safe'});
  assert.equal(html.includes('type="password"'), expected, name);
}
"""
        result = subprocess.run([NODE, "-e", harness], input=code, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_traditional_page_matches_english_layout_and_localizes_both_routes(self):
        english = page("en")
        self.assertTrue((ROOT / "zh-Hant" / "SettingsPage.html").is_file(), "missing zh-Hant SettingsPage")
        traditional = page("zh-Hant")
        self.assertEqual(style(traditional), style(english))
        self.assertEqual(body_shape(traditional), body_shape(english))
        self.assertIn('<html lang="zh-Hant">', traditional)
        self.assertIn('<title>設定 - 翰墨</title>', traditional)
        self.assertIn('document.title = "設備 - 翰墨"', traditional)
        body = traditional.split("<body>", 1)[1].split("<script>", 1)[0]
        for label in ("首頁", "檔案管理", "設備", "字型", "設定", "儲存設定",
                      "已儲存筆記", "待辦清單", "傳送到 X4 Pro"):
            self.assertIn(label, body)
        for simplified in ("主页", "文件管理", "设备", "字体", "设置", "保存", "删除", "图片"):
            self.assertNotIn(simplified, body)
        for label in ("讀取設定失敗", "首頁捷徑選單", "輕觸與手勢", "螢幕輕觸區域",
                      "Wi-Fi 網路", "OPDS 伺服器", "AirPage 圖片", "刪除所選", "上傳照片作為桌布"):
            self.assertIn(label, traditional)
        for simplified in ("读取设置失败", "Wi-Fi 网络", "OPDS 服务器", "AirPage 图片",
                           "删除所选", "上传照片作为壁纸", "正在保存", "确定删除这个"):
            self.assertNotIn(simplified, traditional)
        # The two API calls (GET and POST) must carry the explicit UI choice.
        self.assertEqual(traditional.count("ui === 'zh-Hant'"), 2)
        self.assertIn(r"const IS_DEVICE_PAGE = /^\/device\/?$/.test(location.pathname)", traditional)
        self.assertIn("const DEVICE_PANES = ['wifi', 'opds', 'airpage', 'airnote', 'airphoto']", traditional)
        self.assertIn("if (wanted === 'airnote' && !airnoteListed) loadAirnotes()", traditional)
        self.assertIn("if (wanted === 'airphoto' && !airphotoReady) initAirphoto()", traditional)
        # Do not regress the Chinese-key/password detection to the English-only check.
        self.assertIn("/password|passwd|secret/i.test(setting.key)", traditional)
        self.assertIn("setting.name.includes('密碼')", traditional)
        self.assertIn("setting.name.includes('密码')", traditional)
        simplified = page("zh-CN")
        # The already-localized AirNote/AirPhoto markup and engine must survive unchanged.
        for start, end in (("id=\"pane-airnote\"", "id=\"pane-airphoto\""),
                           ("id=\"pane-airphoto\"", "CrossPoint")):
            self.assertEqual(traditional.split(start, 1)[1].split(end, 1)[0],
                             simplified.split(start, 1)[1].split(end, 1)[0])
        self.assertEqual(traditional.split("// ---- AirPhoto photos", 1)[1],
                         simplified.split("// ---- AirPhoto photos", 1)[1])
        for locale in ("zh-CN", "zh-Hant"):
            raw = (ROOT / locale / "SettingsPage.html").read_bytes()
            self.assertEqual(raw.count(b"\r\n"), raw.count(b"\n"), locale)

    def test_traditional_api_choice_is_forwarded_without_changing_device_language(self):
        harness = r"""
const vm = require('node:vm');
const assert = require('node:assert/strict');
const script = require('node:fs').readFileSync(0, 'utf8');
(async () => {
  const requests = [];
  const setting = {key:'nickname',name:'名稱',category:'外觀',type:'string',value:'old'};
  const saveBtn = {disabled:false,textContent:''};
  const ctx = vm.createContext({
    URLSearchParams, TextEncoder, location:{search:'?ui=zh-Hant'},
    console:{error(e){throw e}},
    document:{getElementById(id){assert.equal(id,'saveBtn');return saveBtn}},
    fetch:async (url, options) => {
      requests.push({url, options});
      return options ? {ok:true} : {ok:true,json:async()=>[setting]};
    },
    escapeHtml:s=>s, renderControl:s=>'',
    installSettingsPanes:()=>{}, updateSettingsVisibility:()=>{},
    getControlValue:()=>undefined, syncQuickResumeTimeoutForSleepScreen:()=>false,
    getValue:()=> 'new', showMessage:()=>{}, findSetting:()=>setting,
  });
  vm.runInContext('let allSettings=[];let originalValues={};let settingsReady=false;let preserveQuickResumeTimeoutOn=false;let quickResumeTimeoutAutoEnabled=false;\n'+script,ctx);
  await vm.runInContext('loadSettings()',ctx);
  await vm.runInContext('saveSettings()',ctx);
  assert.deepEqual(requests.map(r=>r.url), ['/api/settings?ui=zh-Hant','/api/settings?ui=zh-Hant']);
  assert.equal(requests[1].options.method,'POST');
  assert.deepEqual(JSON.parse(requests[1].options.body),{nickname:'new'});
})().catch(e=>{console.error(e);process.exitCode=1});
"""
        for locale in ("zh-CN", "zh-Hant"):
            html = page(locale)
            code = html.split("  async function loadSettings() {", 1)[1].split("  // --- Wi-Fi Network Management ---", 1)[0]
            code = "  async function loadSettings() {" + code
            result = subprocess.run([NODE, "-e", harness], input=code, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, f"{locale}: {result.stderr}")


if __name__ == "__main__":
    unittest.main()
