"""Exercise the AirPhoto orientation probe against real PNG headers."""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
HEADER = ROOT / 'src/activities/apps/airphoto/AirPhotoOrientation.h'
HARNESS = r'''
#include <cstdint>
#include <cstdio>
#include "AirPhotoOrientation.h"
int main() {
  const uint8_t landscape[] = {137,80,78,71,13,10,26,10,0,0,0,13,73,72,68,82,0,0,3,32,0,0,1,224};
  const uint8_t portrait[]  = {137,80,78,71,13,10,26,10,0,0,0,13,73,72,68,82,0,0,1,224,0,0,3,32};
  if (!airphoto::isLandscapePng(landscape, sizeof landscape)) return 1;
  if (airphoto::isLandscapePng(portrait, sizeof portrait)) return 2;
  if (airphoto::isLandscapePng(landscape, 23)) return 3;
  uint8_t invalid[sizeof landscape];
  for (unsigned i=0; i<sizeof landscape; ++i) invalid[i] = landscape[i];
  invalid[0] = 0;
  if (airphoto::isLandscapePng(invalid, sizeof invalid)) return 4;
  invalid[0] = 137;
  invalid[18] = invalid[19] = 0;
  if (airphoto::isLandscapePng(invalid, sizeof invalid)) return 5;
  std::puts("PNG landscape/portrait/truncated/signature/zero: OK");
  return 0;
}
'''

class OrientationTest(unittest.TestCase):
    def test_home_navigation_restores_portrait_on_exit(self):
        header = (ROOT / 'src/activities/apps/airphoto/AirPhotoActivity.h').read_text()
        source = (ROOT / 'src/activities/apps/airphoto/AirPhotoActivity.cpp').read_text()
        self.assertIn('void onExit() override;', header)
        self.assertIn('void AirPhotoActivity::onExit() {', source)
        exit_body = source.split('void AirPhotoActivity::onExit() {', 1)[1].split('\n}', 1)[0]
        self.assertIn('GfxRenderer::Orientation::Portrait', exit_body)

    def test_turning_rebuilds_invalid_view_cache(self):
        source = (ROOT / 'src/activities/apps/airphoto/AirPhotoActivity.cpp').read_text()
        toggle = source.split('void AirPhotoActivity::toggleRotation() {', 1)[1].split('void AirPhotoActivity::applyWallpaper() {', 1)[0]
        self.assertIn('AirPageImageStore::inspectImage(viewPath(openIndex_).c_str(), cached)', toggle)
        self.assertNotIn('Storage.exists(viewPath(openIndex_).c_str())', toggle)

    def test_truncated_derived_files_are_rebuilt_from_original(self):
        source = (ROOT / 'src/activities/apps/airphoto/AirPhotoActivity.cpp').read_text()
        derived = source.split('bool AirPhotoActivity::ensureDerivedAt(', 1)[1].split('void AirPhotoActivity::ensurePageDerived()', 1)[0]
        self.assertIn('AirPageImageStore::inspectImage(target.c_str(), cached)', derived)
        self.assertIn('AirPageImageStore::inspectImage(part.c_str(), generated)', derived)
        self.assertIn('Storage.rename(target.c_str(), backup.c_str())', derived)
        self.assertIn('Storage.rename(part.c_str(), target.c_str())', derived)
        self.assertLess(derived.index('Storage.openFileForWrite("APHO", part.c_str(), out)'),
                        derived.index('Storage.rename(target.c_str(), backup.c_str())'),
                        'do not discard existing cache unless the replacement succeeded')

    def test_converter_rejects_extreme_crop_dimensions_before_writing_bmp(self):
        # Filling a 480x800 display from a 1x3072 PNG would otherwise produce
        # a 480x1474560 BMP (~177 MiB) before the reader rejects it.
        png = (ROOT / 'lib' / 'PngToBmpConverter' / 'PngToBmpConverter.cpp').read_text()
        jpeg = (ROOT / 'lib' / 'JpegToBmpConverter' / 'JpegToBmpConverter.cpp').read_text()
        self.assertIn('outWidth > MAX_IMAGE_WIDTH || outHeight > MAX_IMAGE_HEIGHT', png)
        self.assertIn('outWidth > MAX_IMAGE_WIDTH || outHeight > MAX_IMAGE_HEIGHT', jpeg)
        self.assertLess(png.index('outWidth > MAX_IMAGE_WIDTH || outHeight > MAX_IMAGE_HEIGHT'), png.index('// Write BMP header'))
        self.assertLess(jpeg.index('outWidth > MAX_IMAGE_WIDTH || outHeight > MAX_IMAGE_HEIGHT'), jpeg.index('// Write BMP header with output dimensions'))

    def test_device_cache_uses_uncropped_fit(self):
        source = (ROOT / 'src/activities/apps/airphoto/AirPhotoActivity.cpp').read_text()
        self.assertIn('maxWidth, maxHeight, /*crop=*/false)', source)
        jpeg = (ROOT / 'lib/JpegToBmpConverter/JpegToBmpConverter.cpp').read_text()
        png = (ROOT / 'lib/PngToBmpConverter/PngToBmpConverter.cpp').read_text()
        self.assertIn('targetMaxHeight, false, crop)', jpeg)
        self.assertIn('targetMaxHeight, false, crop)', png)

    def test_png_probe_is_wired_to_photo_viewer(self):
        source = (ROOT / 'src/activities/apps/airphoto/AirPhotoActivity.cpp').read_text()
        self.assertIn('airphoto::isLandscapePng(header, sizeof(header))', source)
        self.assertIn('if (FsHelpers::hasPngExtension(photos_[openIndex_]))', source)

    def test_png_dimensions_determine_rotation(self):
        with tempfile.TemporaryDirectory() as td:
            source = pathlib.Path(td) / 'probe.cpp'
            binary = pathlib.Path(td) / 'probe'
            source.write_text(HARNESS)
            build = subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-I', str(HEADER.parent), str(source), '-o', str(binary)], text=True, capture_output=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(binary)], text=True, capture_output=True)
            self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
            self.assertIn('OK', run.stdout)

if __name__ == '__main__':
    unittest.main()
