"""Exact NEW private lessons package, not a historical image or public pin."""
from pathlib import Path
import hashlib
import json
import tarfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUTER = Path('/mnt/c/Users/angus/OneDrive/文件/ChatGPT/XTEINK UI')
ID = 'hanmo-japanese-lessons-test-20261008'
PKG = OUTER / 'XTEINK-Firmware' / ('build-' + ID)
ZIP = OUTER / 'XTEINK-Firmware/releases' / (ID + '-update.zip')
VERSION = b'1.5.8-hanmo-japanese-lessons-20261008'


def sha(data):
    return hashlib.sha256(data).hexdigest()


class JapaneseLessonsPackageTests(unittest.TestCase):
    def manifest(self):
        self.assertTrue((PKG / 'manifest.json').is_file(), 'the NEW lessons candidate has not been packaged')
        return json.loads((PKG / 'manifest.json').read_text())

    def test_exact_single_new_app_has_both_lessons_and_private_identity(self):
        manifest = self.manifest()
        self.assertEqual(manifest['id'], ID)
        self.assertEqual(manifest['version'].encode(), VERSION)
        self.assertFalse(manifest['hardwareFlashed'])
        self.assertFalse(manifest['published'])
        blob = (PKG / 'crossmux-app0.bin').read_bytes()
        self.assertEqual(blob, (ROOT / '.pio/build/x4pro_custom/firmware.bin').read_bytes())
        self.assertEqual(blob[0], 0xe9)
        self.assertIn(VERSION, blob)
        self.assertEqual(manifest['app']['sha256'], sha(blob))
        self.assertEqual(manifest['app']['size'], len(blob))
        self.assertLess(len(blob), 0x7f0000)
        for title in ('單字卡', '短句閱讀', 'Words', 'Short sentences'):
            self.assertIn(title.encode(), blob)
        with zipfile.ZipFile(ZIP) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(z.namelist(), ['crossmux-app0.bin', 'README.txt',
                                          'HanMoKana/LICENSE.txt', 'HanMoKana/COPYRIGHT.txt',
                                          'HanMoKana/UPSTREAM-README.md'])
            self.assertEqual(z.read('crossmux-app0.bin'), blob)
            self.assertIn(b'app-only', z.read('README.txt').lower())
            for filename in ('LICENSE.txt', 'COPYRIGHT.txt', 'UPSTREAM-README.md'):
                self.assertEqual(z.read('HanMoKana/' + filename),
                                 (ROOT / 'lib/EpdFont/builtinFonts/source/HanMoKana' / filename).read_bytes())
        self.assertFalse(any('FULL' in p.name.upper() or 'factory' in p.name.lower() for p in PKG.rglob('*.bin')))
        for folder in ('build-x4pro-custom', 'flasher/firmware'):
            mirror = OUTER / 'XTEINK-Firmware' / folder / 'prototypes' / ID
            self.assertEqual((mirror / 'crossmux-app0.bin').read_bytes(), blob)

    def test_curated_complete_source_matches_index_and_actual_new_lesson_files(self):
        manifest = self.manifest()
        source = OUTER / manifest['source']['path']
        self.assertEqual(sha(source.read_bytes()), manifest['source']['sha256'])
        index = json.loads((PKG / 'source-index.json').read_text())
        self.assertEqual(len(index), manifest['source']['fileCount'])
        required = [
            'src/activities/apps/japanese/JapaneseWords.h',
            'src/activities/apps/japanese/JapaneseWordsActivity.cpp',
            'src/activities/apps/japanese/JapaneseSentences.h',
            'src/activities/apps/japanese/JapaneseSentencesActivity.cpp',
            'src/activities/apps/japanese/JapaneseSentences.generated.h',
            'data/japanese/sentences-basic.json',
            'scripts/generate_japanese_sentences.py',
            'scripts/build_japanese_sentences_font.py',
            'lib/EpdFont/builtinFonts/hanmo_words_44.h',
            'lib/EpdFont/builtinFonts/hanmo_sentences_28.h',
            'lib/EpdFont/builtinFonts/hanmo_sentence_notes_12.h',
            'docs/japanese-lessons.md',
            'lib/EpdFont/builtinFonts/source/HanMoKana/LICENSE.txt',
            'lib/EpdFont/builtinFonts/source/HanMoKana/COPYRIGHT.txt',
        ]
        with tarfile.open(source, 'r:gz') as archive:
            members = {p.name: p for p in archive.getmembers()}
            self.assertEqual(len(members), len(index))
            for rel in required:
                self.assertIn(rel, index)
                data = archive.extractfile(members['hanmo-japanese-lessons-source/' + rel]).read()
                self.assertEqual(sha(data), index[rel]['sha256'])
                self.assertEqual(data, (ROOT / rel).read_bytes())
            forbidden = {'.pio', '.git', '.cache', 'build', '.font-tools', 'sdk', '__pycache__'}
            for member in members.values():
                self.assertFalse(set(Path(member.name).parts) & forbidden, member.name)

    def test_build_test_image_and_capacity_evidence_are_real_and_for_this_candidate(self):
        manifest = self.manifest()
        self.assertTrue(manifest['build']['simulatorSuccess'])
        self.assertTrue(manifest['build']['hardwareSuccess'])
        for path in manifest['build']['logs']:
            log = (OUTER / path).read_text()
            self.assertIn('SUCCESS', log)
            self.assertNotIn('[FAILED]', log)
        self.assertEqual(manifest['tests']['failures'], 0)
        self.assertEqual(manifest['tests']['errors'], 0)
        self.assertGreaterEqual(manifest['tests']['testsRun'], 20)
        self.assertEqual(manifest['images']['kind'], 'app')
        self.assertEqual(manifest['images']['sha256'], manifest['app']['sha256'])
        self.assertGreater(manifest['capacity']['spareBytes'], 0)
        self.assertEqual(manifest['historyCount'], 63)
        self.assertEqual(manifest['simulator']['locales'], ['ZH_TW', 'ZH_CN', 'EN'])
        self.assertEqual(manifest['simulator']['newLessonFlows'], 6)


if __name__ == '__main__':
    unittest.main()
