import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]

class FirmwareIdentityTest(unittest.TestCase):
    def test_display_persistence_and_validation(self):
        source = r"""
#include "src/FirmwareIdentity.h"
#include <cassert>
#include <string>
int main() {
  char name[FirmwareIdentity::BUFFER_SIZE] = "";
  char text[128];
  uint8_t visible = 1;
  auto check = [&](const char* expected) {
    FirmwareIdentity::format(text, sizeof(text), name, FirmwareIdentity::DEFAULT_NAME, visible, "1.2.3");
    assert(std::string(text) == expected);
  };
  check("HanMo 1.2.3");
  visible = 0; check("HanMo");
  assert(FirmwareIdentity::assign(name, "Angus 專用版"));
  check("Angus 專用版");
  visible = 1; check("Angus 專用版 1.2.3");
  assert(!FirmwareIdentity::assign(name, "  "));
  assert(!FirmwareIdentity::assign(name, "bad\nname"));
  assert(!FirmwareIdentity::assign(name, std::string("a\0b", 3)));
  assert(!FirmwareIdentity::assign(name, "\xc0\xaf"));
  assert(!FirmwareIdentity::assign(name, "\xed\xa0\x80"));
  assert(!FirmwareIdentity::assign(name, "\xf4\x90\x80\x80"));
  assert(!FirmwareIdentity::assign(name, "\xc2\x85"));
  assert(!FirmwareIdentity::assign(name, std::string(33, 'x')));
  check("Angus 專用版 1.2.3");
  assert(FirmwareIdentity::assign(name, std::string(32, 'x')));
  assert(FirmwareIdentity::assign(name, "名名名名名名名名名名ab"));
  assert(!FirmwareIdentity::assign(name, "名名名名名名名名名名abc"));
  JsonDocument saved;
  saved["versionDisplayName"] = name;
  saved["showVersionNumber"] = 0;
  std::string json;
  serializeJson(saved, json);
  JsonDocument loaded;
  assert(!deserializeJson(loaded, json));
  char restored[33] = "";
  assert(!FirmwareIdentity::load(restored, loaded["versionDisplayName"]));
  assert(std::string(restored) == name);
  assert(!FirmwareIdentity::loadVisibility(visible, loaded["showVersionNumber"]));
  assert(visible == 0);
  JsonDocument old;
  assert(!FirmwareIdentity::load(restored, old["versionDisplayName"]));
  assert(!FirmwareIdentity::loadVisibility(visible, old["showVersionNumber"]));
  assert(visible == 0);
  old["versionDisplayName"] = nullptr;
  assert(FirmwareIdentity::load(restored, old["versionDisplayName"]));
  assert(restored[0] == '\0');
  for (const char* invalid : {R"({"versionDisplayName":"a\u0000b"})",
                             R"({"versionDisplayName":42})", R"({"versionDisplayName":"   "})"}) {
    assert(!deserializeJson(old, invalid));
    assert(FirmwareIdentity::load(restored, old["versionDisplayName"]));
    assert(restored[0] == '\0');
  }
  for (const char* value : {"true", "false", "0", "1"}) {
    assert(!deserializeJson(old, value));
    assert(FirmwareIdentity::validVisibility(old.as<JsonVariantConst>()));
    assert(!FirmwareIdentity::loadVisibility(visible, old.as<JsonVariantConst>()));
    assert(visible == (std::string(value) == "true" || std::string(value) == "1"));
  }
  for (const char* value : {"null", "2", "-1", "0.5", "\"false\"", "[]", "{}"}) {
    assert(!deserializeJson(old, value));
    assert(!FirmwareIdentity::validVisibility(old.as<JsonVariantConst>()));
    assert(FirmwareIdentity::loadVisibility(visible, old.as<JsonVariantConst>()));
    assert(visible == 1);
  }
  assert(FirmwareIdentity::assign(name, {}));
  check("HanMo 1.2.3");
  assert(std::string(FirmwareIdentity::name("", "")) == "HanMo");
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            cpp = pathlib.Path(tmp) / 'identity.cpp'
            exe = pathlib.Path(tmp) / 'identity'
            cpp.write_text(source)
            subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror',
                            '-I' + str(ROOT), '-I' + str(ROOT / '.pio/libdeps/x4pro_custom/ArduinoJson/src'),
                            str(cpp), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)

if __name__ == '__main__':
    unittest.main()
