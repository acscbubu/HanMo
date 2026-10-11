"""Host checks for the Memory Match icon and Games shelf row.

This test reads the authoritative source and compiles a small registry-facing
harness against the real icon header; it does not invoke PlatformIO or firmware.
"""
import pathlib
import re
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SHELF = ROOT / "src/apps_local/Shelf.cpp"
ICONS = ROOT / "src/apps_local/ui/ToyboxIcons.h"
TITLE = "MEMORY MATCH"


def _bitmap(icons, name, size):
    match = re.search(
        rf"static const uint8_t {name}_{size}_bits\[\]\s*=\s*\{{(.*?)\}};",
        icons,
        re.S,
    )
    if not match:
        raise AssertionError(f"missing {name}_{size}_bits")
    tokens = [token.strip() for token in match.group(1).split(",") if token.strip()]
    if not all(re.fullmatch(r"0x[0-9A-Fa-f]{2}", token) for token in tokens):
        raise AssertionError(f"{name}_{size}_bits contains a non-byte token")
    return bytes(int(token, 16) for token in tokens)


class MemoryShelfTest(unittest.TestCase):
    def test_memory_match_icon_and_shelf_row(self):
        shelf = SHELF.read_text(encoding="utf-8")
        icons = ICONS.read_text(encoding="utf-8")
        registry = re.search(
            r"constexpr shelf::Item kGames\[\] = \{(.*?)\n\};", shelf, re.S
        )
        self.assertIsNotNone(registry, "the real Games registry must be present")
        rows = re.findall(
            r'\{"([^"\n]+)",\s*(&[^,]+),\s*(&[^}]+)\}',
            registry.group(1),
        )
        memory_rows = [row for row in rows if row[0] == TITLE]
        self.assertEqual(memory_rows, [(TITLE, "&icon_memory_32", "&MemoryActivity::create")])
        self.assertEqual(shelf.count('#include "memory/MemoryActivity.h"'), 1)
        self.assertEqual(shelf.count('\"MEMORY MATCH\"'), 1)
        self.assertNotIn("MURDLE", registry.group(1))
        self.assertNotIn("TRIVIA", registry.group(1))

        for size in (24, 32):
            with self.subTest(size=size):
                data = _bitmap(icons, "icon_memory", size)
                stride = (size + 7) // 8
                self.assertEqual(len(data), stride * size)
                definition = re.search(
                    rf"static const freeink::Icon icon_memory_{size}\s*=\s*"
                    rf"\{{\s*{size},\s*{size},\s*(-?\d+),\s*icon_memory_{size}_bits\s*\}};",
                    icons,
                )
                self.assertIsNotNone(definition)
                optical_y = int(definition.group(1))
                self.assertGreaterEqual(optical_y, 0)
                self.assertLess(optical_y, size)
                black = [(x, y) for y in range(size) for x in range(size)
                         if not (data[y * stride + x // 8] & (0x80 >> (x % 8)))]
                self.assertTrue(black, "the Memory icon cannot be blank")
                self.assertTrue(all(0 < x < size - 1 and 0 < y < size - 1 for x, y in black))
                self.assertLessEqual(abs(optical_y - sum(y for _, y in black) / len(black)), 1)

        row = re.search(r'\{"MEMORY MATCH",[^\n]+\}', registry.group(1))
        self.assertIsNotNone(row)
        harness = """
#include \"ToyboxIcons.h\"
#include <cassert>
#include <cstring>
#include <memory>
#include <type_traits>
class Activity {};
class GfxRenderer {};
class MappedInputManager {};
class MemoryActivity {
 public:
  static std::unique_ptr<Activity> create(GfxRenderer&, MappedInputManager&) { return {}; }
};
struct Item {
  const char* title;
  const freeink::Icon* icon;
  std::unique_ptr<Activity> (*create)(GfxRenderer&, MappedInputManager&);
};
constexpr Item memoryRow = MEMORY_ROW;
static_assert(std::is_same<decltype(memoryRow.create),
                           std::unique_ptr<Activity> (*)(GfxRenderer&, MappedInputManager&)>::value,
              "Memory factory must match shelf callback shape");
static_assert(sizeof(icon_memory_24_bits) == 24 * 3, "24px packed bitmap size");
static_assert(sizeof(icon_memory_32_bits) == 32 * 4, "32px packed bitmap size");
int main() {
  assert(std::strcmp(memoryRow.title, "MEMORY MATCH") == 0);
  assert(memoryRow.icon == &icon_memory_32);
}
"""
        harness = harness.replace("MEMORY_ROW", row.group(0))
        with tempfile.TemporaryDirectory(prefix="memory-shelf-") as directory:
            source = pathlib.Path(directory) / "memory_shelf_host.cpp"
            source.write_text(harness, encoding="utf-8")
            executable = pathlib.Path(directory) / "memory_shelf_host"
            compiled = subprocess.run(
                [
                    "g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                    "-I", str(ROOT / "freeink-sdk/libs/assets/Icons/include"),
                    "-I", str(ROOT / "src/apps_local/ui"),
                    str(source), "-o", str(executable),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)


if __name__ == "__main__":
    unittest.main()
