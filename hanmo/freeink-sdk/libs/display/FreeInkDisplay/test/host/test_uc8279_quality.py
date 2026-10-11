"""Check the production LUT generator against the reviewed upstream waveforms."""

from pathlib import Path
import hashlib
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
source = (root / "src/driver/Uc8279X4Driver.cpp").read_text()
function = source[source.index("const uint8_t (*scaledQualityBank()"):
                  source.index("// Register order for the quality bank")]
# Byte-for-byte output of upstream 14028b17 before packing Phase's bounded fields.
expected = {
    1: "59701a2b7e6e3bc769f6166cd560a7ced04740f63a9272931356df730b4f08a8",
    40: "69f878f37aeb4535fa616092c41bf555147940ae984d08242e7713ace660c0b7",
    60: "9dad4b1b7c89b1e0941b02adc09e4667441d979e4bf84216dbe36207bf2748ae",
    100: "c3389a040de40e8d80b231a2b01f9d00bec26df9cf75ecffb7126c68db223e3e",
    150: "b4d122fef1a6db93d858ca6796495dc39d0d8993561d026f17e9167bc44afd3a",
}
harness = """
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <cassert>
#include "Uc8279X3Luts.h"
using namespace freeink;
constexpr uint8_t GRAY_LUT_LEN = 49;
""" + function + """
int main() {
  const auto* bank = scaledQualityBank();
  assert(bank == scaledQualityBank());
  std::fwrite(bank, 1, 5 * GRAY_LUT_LEN, stdout);
}
"""
with tempfile.TemporaryDirectory(prefix="freeink-quality-lut-") as directory:
    temporary = Path(directory)
    cpp = temporary / "test.cpp"
    cpp.write_text(harness)
    binary = temporary / "test"
    for speed, digest in expected.items():
        subprocess.run(["c++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
                        f"-DFREEINK_UC8279X4_GRAY_SPEED={speed}", "-I" + str(root / "src/lut"),
                        str(cpp), "-o", str(binary)], check=True)
        actual = subprocess.check_output([str(binary)])
        assert len(actual) == 245
        assert hashlib.sha256(actual).hexdigest() == digest, f"waveform changed at {speed}%"
print("UC8279 quality LUT: five speed settings match reviewed upstream bytes")
