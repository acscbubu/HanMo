"""Parse the browser-generated AirPhoto bitmaps with the device's real BMP reader.

The web page encodes 2bpp grayscale BMPs itself so the panel can blit them with
no decoding. That only works if the bytes match what lib/GfxRenderer/Bitmap.cpp
actually accepts, so this compiles that exact source -- no transcription, no
reimplementation -- and runs it over the sample files the page test emits.
"""

import os
import pathlib
import subprocess
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
BITMAP_CPP = REPO / "lib" / "GfxRenderer" / "Bitmap.cpp"
# adjustPixel()/quantize() live here; using the real ones keeps the decoded
# levels honest instead of stubbing the pixel maths the test is checking.
BITMAP_HELPERS_CPP = REPO / "lib" / "GfxRenderer" / "BitmapHelpers.cpp"

SAMPLE_DIRS = [
    "/mnt/c/Users/angus/AppData/Local/Temp/airphoto-samples",
    "/mnt/c/Users/angus/AppData/Local/hermes/cache/scratch/airphoto-samples",
]

STUB_HAL_STORAGE = """
#pragma once
#include <cstddef>
#include <cstdint>
// The memory-source constructor is the one under test, so HalFile only has to
// exist as a type here.
class HalFile {
 public:
  int read(void*, size_t) { return -1; }
  bool seek(size_t) { return false; }
  bool seekCur(int64_t) { return false; }
  int64_t position() { return 0; }
  uint64_t fileSize64() { return 0; }
  explicit operator bool() const { return false; }
};
"""

STUB_LOGGING = """
#pragma once
#define LOG_ERR(...) do { } while (0)
#define LOG_WRN(...) do { } while (0)
#define LOG_INF(...) do { } while (0)
#define LOG_DBG(...) do { } while (0)
"""

STUB_MEMORY = """
#pragma once
#include <cstdlib>
namespace Memory {
inline void* alloc(size_t size) { return std::malloc(size); }
inline void* allocPreferPsram(size_t size) { return std::malloc(size); }
inline void release(void* p) { std::free(p); }
}  // namespace Memory
"""

HARNESS = """
#include <cstdio>
#include <vector>
#include "Bitmap.h"

// Reports what the device's own parser makes of the file, one field per line,
// so the Python side never has to guess.
int main(int argc, char** argv) {
  if (argc < 2) return 2;
  FILE* f = std::fopen(argv[1], "rb");
  if (!f) { std::printf("ERROR open\\n"); return 1; }
  std::fseek(f, 0, SEEK_END);
  const long size = std::ftell(f);
  std::fseek(f, 0, SEEK_SET);
  std::vector<unsigned char> data(static_cast<size_t>(size));
  if (std::fread(data.data(), 1, data.size(), f) != data.size()) {
    std::fclose(f);
    std::printf("ERROR read\\n");
    return 1;
  }
  std::fclose(f);

  Bitmap bitmap(data.data(), data.size(), false);
  const BmpReaderError err = bitmap.parseHeaders();
  if (err != BmpReaderError::Ok) {
    std::printf("ERROR %s\\n", Bitmap::errorToString(err));
    return 1;
  }
  std::printf("width %d\\n", bitmap.getWidth());
  std::printf("height %d\\n", bitmap.getHeight());
  std::printf("bpp %u\\n", static_cast<unsigned>(bitmap.getBpp()));
  std::printf("topDown %d\\n", bitmap.isTopDown() ? 1 : 0);
  std::printf("rowBytes %d\\n", bitmap.getRowBytes());
  std::printf("transparency %d\\n", bitmap.hasTransparency() ? 1 : 0);

  // Walk every row through the real reader and collect the distinct levels it
  // produces, which is what the renderer would draw.
  std::vector<unsigned char> row(static_cast<size_t>(bitmap.getWidth()) / 4 + 8);
  std::vector<unsigned char> scratch(static_cast<size_t>(bitmap.getRowBytes()) + 8);
  bool seen[256] = {false};
  for (int y = 0; y < bitmap.getHeight(); y++) {
    const BmpReaderError rowErr = bitmap.readNextRow(row.data(), scratch.data());
    if (rowErr != BmpReaderError::Ok) {
      std::printf("ERROR row %d %s\\n", y, Bitmap::errorToString(rowErr));
      return 1;
    }
    // readNextRow emits the panel's native packed 2bpp, not one byte per
    // pixel, so unpack with the parser's own expression before counting.
    for (int x = 0; x < bitmap.getWidth(); x++) {
      seen[(row[x >> 2] >> (6 - ((x & 3) * 2))) & 0x03] = true;
    }
  }
  std::printf("levels");
  for (int i = 0; i < 256; i++) {
    if (seen[i]) std::printf(" %d", i);
  }
  std::printf("\\n");
  std::printf("OK\\n");
  return 0;
}
"""


def find_samples():
    for candidate in SAMPLE_DIRS:
        path = pathlib.Path(candidate)
        if path.is_dir():
            files = sorted(path.glob("*.bmp"))
            if files:
                return files
    return []


class AirPhotoBmpTest(unittest.TestCase):
    """The page's bitmaps must satisfy the firmware's own parser, not a copy of it."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = pathlib.Path(cls._tmp.name)
        shadow = tmp / "shadow"
        shadow.mkdir(parents=True)
        (shadow / "HalStorage.h").write_text(STUB_HAL_STORAGE)
        (shadow / "Logging.h").write_text(STUB_LOGGING)

        harness = tmp / "harness.cpp"
        harness.write_text(HARNESS)
        cls.binary = tmp / "parse_bmp"

        result = subprocess.run(
            ["g++", "-std=c++20", "-O1", "-DCROSSPOINT_EMULATED",
             "-I", str(shadow), "-I", str(BITMAP_CPP.parent),
             str(harness), str(BITMAP_CPP), str(BITMAP_HELPERS_CPP), "-o", str(cls.binary)],
            capture_output=True, text=True)
        if result.returncode != 0:
            raise AssertionError("could not build the device BMP reader:\n" + result.stderr[-3000:])

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def parse(self, path):
        result = subprocess.run([str(self.binary), str(path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, "%s: %s%s" % (path.name, result.stdout, result.stderr))
        fields = {}
        for line in result.stdout.splitlines():
            key, _, value = line.partition(" ")
            fields[key] = value
        self.assertIn("OK", fields, "%s: parser did not finish" % path.name)
        return fields

    def test_every_generated_bitmap_is_readable_by_the_device_parser(self):
        samples = find_samples()
        if not samples:
            self.skipTest("no samples; run: node scripts/tests/test_airphoto_settings.mjs")

        for path in samples:
            with self.subTest(sample=path.name):
                fields = self.parse(path)
                self.assertEqual(fields["bpp"], "2", "the panel's native depth")
                self.assertEqual(fields["topDown"], "1", "rows must be top-down")
                self.assertEqual(fields["transparency"], "0",
                                 "the transparent-overlay marker must not be tripped")
                width = int(fields["width"])
                height = int(fields["height"])
                self.assertGreater(width, 0)
                self.assertGreater(height, 0)
                self.assertLessEqual(width, 2048)
                self.assertLessEqual(height, 3072)
                self.assertEqual(int(fields["rowBytes"]), ((width * 2 + 31) // 32) * 4)

    def test_four_gray_levels_survive_the_round_trip(self):
        samples = find_samples()
        if not samples:
            self.skipTest("no samples; run: node scripts/tests/test_airphoto_settings.mjs")

        for path in samples:
            with self.subTest(sample=path.name):
                fields = self.parse(path)
                levels = [int(v) for v in fields["levels"].split()]
                self.assertTrue(levels, "%s: no pixels decoded" % path.name)
                # 2bpp takes the parser's native-palette path, so the palette
                # entries come back as levels 0..3 rather than luminances.
                self.assertTrue(set(levels).issubset({0, 1, 2, 3}),
                                "%s: unexpected levels %s" % (path.name, levels))
                if int(fields["width"]) >= 16:
                    self.assertGreater(len(levels), 1,
                                       "%s: collapsed to a single level" % path.name)


if __name__ == "__main__":
    unittest.main()
