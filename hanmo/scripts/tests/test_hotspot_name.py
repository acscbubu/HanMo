import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


class HotspotNameTest(unittest.TestCase):
    def test_utf8_limits_and_saved_json(self):
        source = r"""
#include "src/network/HotspotName.h"
#include <cassert>
#include <string>
int main() {
  char name[HotspotName::BUFFER_SIZE] = "XTEINK-X4-PRO";
  assert(HotspotName::isValid(name));
  assert(HotspotName::assign(name, "Angus Reader"));
  assert(std::string(name) == "Angus Reader");
  assert(HotspotName::assign(name, std::string(32, 'x')));
  assert(!HotspotName::assign(name, std::string(33, 'x')));
  assert(std::string(name) == std::string(32, 'x'));
  assert(HotspotName::assign(name, "我的閱讀器"));
  assert(!HotspotName::assign(name, "   "));
  assert(!HotspotName::assign(name, "bad\nname"));
  assert(!HotspotName::assign(name, std::string("a\0b", 3)));
  assert(!HotspotName::assign(name, "\xc0\xaf"));
  assert(!HotspotName::assign(name, "\xed\xa0\x80"));
  assert(!HotspotName::assign(name, "\xf4\x90\x80\x80"));
  assert(!HotspotName::assign(name, "\xe7\x86"));
  assert(!HotspotName::assign(name, "\x80"));
  assert(!HotspotName::assign(name, "\xc2\x85"));
  const std::string tenChinese = "熱熱熱熱熱熱熱熱熱熱";
  assert(HotspotName::assign(name, tenChinese + "ab"));
  assert(!HotspotName::assign(name, tenChinese + "abc"));
  assert(HotspotName::assign(name, "quoted\"name\\ok"));
  assert(HotspotName::wifiQrPayload("XTEINK-X4-PRO") == "WIFI:T:nopass;S:XTEINK-X4-PRO;;");
  assert(HotspotName::wifiQrPayload("a;b:c,d\\e\"f") == "WIFI:T:nopass;S:a\\;b\\:c\\,d\\\\e\\\"f;;");
  assert(HotspotName::wifiQrPayload("中文") == "WIFI:T:nopass;S:中文;;");
  JsonDocument stored;
  stored["hotspotName"] = name;
  std::string json;
  serializeJson(stored, json);
  JsonDocument loaded;
  assert(!deserializeJson(loaded, json));
  char restored[33] = "XTEINK-X4-PRO";
  assert(!HotspotName::load(restored, loaded["hotspotName"]));
  assert(std::string(restored) == name);
  JsonDocument old;
  assert(!HotspotName::load(restored, old["hotspotName"]));
  assert(std::string(restored) == name);
  old["hotspotName"] = std::string(33, 'x');
  assert(HotspotName::load(restored, old["hotspotName"]));
  assert(std::string(restored) == HotspotName::DEFAULT_NAME);
  old["hotspotName"] = 42;
  assert(HotspotName::load(restored, old["hotspotName"]));
  old["hotspotName"] = nullptr;
  assert(HotspotName::load(restored, old["hotspotName"]));
  old["hotspotName"] = "";
  assert(HotspotName::load(restored, old["hotspotName"]));
  assert(std::string(restored) == HotspotName::DEFAULT_NAME);
  assert(HotspotName::assign(restored, {}));
  assert(std::string(restored) == "XTEINK-X4-PRO");
  assert(!deserializeJson(old, R"({"hotspotName":"a\u0000b"})"));
  assert(HotspotName::load(restored, old["hotspotName"]));
  assert(std::string(restored) == HotspotName::DEFAULT_NAME);
}
"""
        arduinojson = ROOT / '.pio/libdeps/x4pro_custom/ArduinoJson/src'
        with tempfile.TemporaryDirectory() as tmp:
            cpp = pathlib.Path(tmp) / 'hotspot.cpp'
            exe = pathlib.Path(tmp) / 'hotspot'
            cpp.write_text(source)
            subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror',
                            '-I' + str(ROOT), '-I' + str(arduinojson), str(cpp), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    unittest.main()
