"""Read back the immutable previous unified package, not the next live build.

The dated package remains protected as history. The words candidate has its
own exact live-build package gate; never compare an old archive to new source.
"""
from pathlib import Path
import hashlib, json, tarfile, unittest, zipfile

ROOT=Path(__file__).resolve().parents[2]
PKG=Path('/mnt/c/Users/angus/OneDrive/文件/ChatGPT/XTEINK UI/migration/hanmo-games-kana-unified-test-20261007')
APP='hanmo-games-kana-unified-test-20261007-app-only.bin'
ZIP='hanmo-games-kana-unified-test-20261007-app-only.zip'
SRC='hanmo-games-kana-unified-test-20261007-source.tar.gz'
VERSION=b'1.5.8-hanmo-games-kana-unified-20261007'


def sha(blob):return hashlib.sha256(blob).hexdigest()


class GamesKanaUnifiedPackageTests(unittest.TestCase):
    def test_only_one_real_app_image_in_zip_and_binary_has_new_identity(self):
        manifest=json.loads((PKG/'manifest.json').read_text())
        blob=(PKG/APP).read_bytes()
        self.assertEqual(sha(blob),'36a6595c976d782d3d684a407723bfbdbc261a868dec46c2385ce55ea9f42d21')
        self.assertEqual(blob[0],0xe9)
        self.assertIn(VERSION,blob)
        self.assertLess(len(blob),0x7f0000)
        self.assertEqual(manifest['app']['sha256'],sha(blob))
        self.assertEqual(manifest['app']['size'],len(blob))
        self.assertFalse(manifest['hardwareFlashPerformed'])
        with zipfile.ZipFile(PKG/ZIP) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(z.namelist(),[APP,'README.txt'])
            self.assertEqual(z.read(APP),blob)
            self.assertIn(b'app-only',z.read('README.txt').lower())

    def test_full_combined_source_matches_worktree_and_has_license(self):
        manifest=json.loads((PKG/'manifest.json').read_text())
        index=json.loads((PKG/'source-files.json').read_text())
        self.assertEqual(len(index),manifest['source']['fileCount'])
        required=('src/apps_local/memory/MemoryActivity.cpp',
                  'src/apps_local/reversi/ReversiCore.h',
                  'src/apps_local/slidepuzzle/SlidePuzzleActivity.cpp',
                  'src/apps_local/mahjong/MahjongActivity.cpp',
                  'src/apps_local/backgammon/BackgammonActivity.cpp',
                  'src/apps_local/tilerummy/TileRummyActivity.cpp',
                  'src/activities/apps/japanese/JapaneseLearningActivity.cpp',
                  'src/activities/apps/japanese/KanaStrokeActivity.cpp',
                  'src/activities/apps/japanese/KanaSoundReading.h',
                  'src/activities/apps/japanese/KanaStroke.generated.h',
                  'data/japanese/kana-basic.json',
                  'third_party/kanjivg/LICENSE','third_party/kanjivg/SOURCE.md',
                  'scripts/generate_kana_strokes.py',
                  'lib/I18n/translations/english.yaml',
                  'lib/I18n/translations/chinese.yaml',
                  'lib/I18n/translations/chinese-traditional.yaml')
        with tarfile.open(PKG/SRC,'r:gz') as t:
            names=set(t.getnames())
            for path in required:
                self.assertIn(path,index)
                name='crossmux-games-kana-unified-source/'+path
                self.assertIn(name,names)
                data=t.extractfile(name).read()
                self.assertEqual(sha(data),index[path]['sha256'],path)
                self.assertEqual(index[path]['sha256'],sha(data))
        self.assertEqual(manifest['source']['sha256'],sha((PKG/SRC).read_bytes()))

    def test_checksums_host_and_simulator_evidence_are_for_this_build(self):
        manifest=json.loads((PKG/'manifest.json').read_text())
        sums=dict((line.split('  ',1)[1],line.split('  ',1)[0]) for line in (PKG/'SHA256SUMS').read_text().splitlines())
        for filename,digest in sums.items():self.assertEqual(sha((PKG/filename).read_bytes()),digest,filename)
        self.assertEqual(manifest['host']['newErrors'],[])
        self.assertEqual(manifest['host']['skipped'],2)
        self.assertEqual(len(manifest['host']['baselineErrors']),3)
        self.assertEqual(len(manifest['simulator']['gameCases']),18)
        self.assertEqual(len(manifest['simulator']['kanaCases']),9)
        self.assertTrue(manifest['build']['simulatorSuccess'])
        self.assertTrue(manifest['build']['hardwareSuccess'])

if __name__=='__main__':unittest.main()
