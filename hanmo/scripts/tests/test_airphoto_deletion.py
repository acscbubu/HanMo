"""The viewer must confirm before deleting a selected original photo."""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
PHOTO = ROOT / 'src/activities/apps/airphoto'
HARNESS = r'''
#include <string>
#include <vector>
#include "AirPhotoDeletion.h"
int main() {
  using airphoto::deletionPlan;
  std::vector<std::string> images{"A.jpg", "B.png", "A.png"};
  auto shared = deletionPlan(images, 0);
  if (shared.original != "/AirPhoto/A.jpg" || !shared.removeCaches) return 1;
  auto unique = deletionPlan(images, 1);
  if (unique.original != "/AirPhoto/B.png" || !unique.removeCaches) return 2;
  if (unique.view != "/AirPhoto/.view/B.png.bmp") return 3;
  if (unique.landscapeView != "/AirPhoto/.view/B.png.land.bmp") return 4;
  if (unique.thumb != "/AirPhoto/.thumb/B.png.bmp") return 5;
  if (deletionPlan(images, 3).valid) return 6;
  if (deletionPlan(images, -1).valid) return 7;
  if (deletionPlan({"../bad.jpg"}, 0).valid) return 8;
  if (!deletionPlan({"C.JPG", "c.png"}, 0).removeCaches) return 9;
  if (!deletionPlan({"x.jpg", "x.jpeg"}, 0).removeCaches) return 10;
  if (shared.view != "/AirPhoto/.view/A.jpg.bmp" ||
      shared.landscapeView != "/AirPhoto/.view/A.jpg.land.bmp" ||
      shared.thumb != "/AirPhoto/.thumb/A.jpg.bmp") return 11;
  if (deletionPlan({"A.jpg", "A.png"}, 0).view ==
      deletionPlan({"A.jpg", "A.png"}, 1).view) return 12;
  return 0;
}
'''

class DeletionTest(unittest.TestCase):
    def test_confirmation_uses_a_separate_popup_after_photo_menu_callback(self):
        # OptionPopup::handleInput invokes onSelectCallback in place. Calling
        # show() on that same popup destroys the executing std::function.
        source = (PHOTO / 'AirPhotoActivity.cpp').read_text(encoding='utf-8')
        header = (PHOTO / 'AirPhotoActivity.h').read_text(encoding='utf-8')
        self.assertIn('OptionPopup confirmationPopup_;', header)
        menu = source.split('void AirPhotoActivity::showPhotoMenu()', 1)[1].split(
            'void AirPhotoActivity::deletePhoto()', 1)[0]
        for method in ('showCoverPrompt', 'confirmDeletePhoto'):
            body = menu.split(f'void AirPhotoActivity::{method}()', 1)[1].split('\n}', 1)[0]
            self.assertIn('confirmationPopup_.show(', body)
            self.assertNotIn('photoMenuPopup_.show(', body)
            self.assertLess(body.index('drawOpenPhoto();'), body.index('confirmationPopup_.show('))
        self.assertIn('confirmationPopup_.handleInput(mappedInput,', source)
        self.assertIn('confirmationPopup_.processRender(renderer, mappedInput)', source)

    def test_only_unshared_cache_files_are_eligible(self):
        with tempfile.TemporaryDirectory() as td:
            source = pathlib.Path(td) / 'check.cpp'
            binary = pathlib.Path(td) / 'check'
            source.write_text(HARNESS, encoding='utf-8')
            build = subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-I', str(PHOTO), str(source), '-o', str(binary)], text=True, capture_output=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(binary)], text=True, capture_output=True)
            self.assertEqual(run.returncode, 0, run.stderr)

    def test_viewer_asks_again_and_deletes_original_before_cache_cleanup(self):
        source = (PHOTO / 'AirPhotoActivity.cpp').read_text(encoding='utf-8')
        self.assertIn('void AirPhotoActivity::showCoverPrompt()', source)
        self.assertIn('if (index == 1) showCoverPrompt();', source)
        self.assertIn('airphoto::Cover::Startup', source)
        self.assertIn('airphoto::Cover::Sleep', source)
        self.assertIn('airphoto::Cover::Shutdown', source)
        self.assertIn('StrId::STR_DELETE', source)
        self.assertIn('void AirPhotoActivity::confirmDeletePhoto()', source)
        self.assertIn('const char* confirmOptions[] = {tr(STR_CANCEL), tr(STR_DELETE)};', source)
        self.assertIn('confirmationPopup_.show(title.c_str(), confirmOptions, 2, 0,', source)
        self.assertIn('if (index == 1) deletePhoto();', source)
        self.assertIn('const auto plan = airphoto::deletionPlan(photos_, openIndex_);', source)
        self.assertIn('if (!Storage.remove(plan.original.c_str()))', source)
        self.assertIn('if (plan.removeCaches)', source)
        self.assertLess(source.index('if (!Storage.remove(plan.original.c_str()))'),
                        source.index('if (plan.removeCaches)', source.index('void AirPhotoActivity::deletePhoto()')),
                        'a failed original delete must not discard previews')
        self.assertIn('loadPhotos();', source)
        self.assertIn('drawGrid();', source)

    def test_dismissing_menu_restores_photo(self):
        source = (PHOTO / 'AirPhotoActivity.cpp').read_text(encoding='utf-8')
        handler = source.split('if (photoMenuPopup_.handleInput(', 1)[1].split('if (openIndex_ >= 0) {\n    int longPressX', 1)[0]
        self.assertIn('if (!photoMenuPopup_.isActive())', handler)
        self.assertIn('drawOpenPhoto();', handler)
        self.assertIn('drawGrid();', handler)

    def test_cover_helper_uses_original_and_recoverable_sleep_transaction(self):
        source = (PHOTO / 'AirPhotoActivity.cpp').read_text(encoding='utf-8')
        helper = (PHOTO / 'AirPhotoActions.cpp').read_text(encoding='utf-8')
        method = source.split('void AirPhotoActivity::applyCover() {', 1)[1].split(
            'void AirPhotoActivity::onExit()', 1)[0]
        self.assertIn('photoPath(openIndex_)', method)
        self.assertIn('airphoto::setCover(original.c_str(), coverToSet_)', method)
        self.assertIn('writeBmp(original, kSleepPart)', helper)
        self.assertIn('airpage::AirPageWallpaper::install(selected, /*cropToFill=*/true)', helper)
        self.assertIn('clearPart(kSleepPart)', helper)

if __name__ == '__main__':
    unittest.main()
