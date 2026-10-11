"""Independent first-lesson oracle, not expectations derived from its JSON."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data/japanese/sentences-basic.json'
ORACLE = [
    ('sentence-01', 'これはほんです。', 'kore wa hon desu.', '這是書。', 45),
    ('sentence-02', 'これはかさです。', 'kore wa kasa desu.', '這是傘。', 5),
    ('sentence-03', 'これはちずです。', 'kore wa chizu desu.', '這是地圖。', 16),
    ('sentence-04', 'みずをのみます。', 'mizu o nomimasu.', '喝水。', -1),
    ('sentence-05', 'すしをたべます。', 'sushi o tabemasu.', '吃壽司。', 12),
    ('sentence-06', 'ほんをよみます。', 'hon o yomimasu.', '讀書。', 45),
]

class JapaneseSentencesDataTests(unittest.TestCase):
    def source(self):
        self.assertTrue(SOURCE.is_file(), 'Authored six-sentence lesson is missing')
        return json.loads(SOURCE.read_text(encoding='utf-8'))

    def test_independent_six_entry_oracle_and_particles(self):
        data = self.source()
        self.assertEqual(data['edition'], 1)
        self.assertEqual(len(data['cards']), 6)
        for row, (sid, japanese, romaji, meaning, vocabulary_id) in zip(data['cards'], ORACLE):
            with self.subTest(id=sid):
                self.assertEqual((row['id'], row['japanese'], row['kanaReading'], row['romaji'],
                                  row['meaning'], row['vocabularyCardId']),
                                 (sid, japanese, japanese, romaji, meaning, vocabulary_id))
                notes = ['は表示主題，此時讀 wa。', 'です是客氣的說法。'] if vocabulary_id != -1 and japanese.startswith('これ') else [
                    'を表示動作對象，讀 o。', 'ます是客氣的說法。']
                self.assertEqual(row['grammarNotes'], notes)
                self.assertNotIn(' ha ', romaji)
                self.assertNotIn(' wo ', romaji)
                self.assertTrue(all('\u3041' <= c <= '\u3096' or c == '。' for c in japanese))

    def test_authored_provenance_is_not_jpf_original_text(self):
        provenance = self.source()['provenance']
        self.assertIs(provenance['authoredForHanMo'], True)
        self.assertIs(provenance['isOriginalJpfText'], False)
        self.assertIn('not', provenance['claim'].lower())
        self.assertEqual(provenance['referenceUrls'], [
            'https://www.irodori.jpf.go.jp/assets/data/starter/pdf/X_L03.pdf',
            'https://www.irodori.jpf.go.jp/assets/data/starter/pdf/X_L05.pdf',
        ])

class JapaneseSentencesGeneratorTests(unittest.TestCase):
    source = JapaneseSentencesDataTests.source
    def generator(self):
        path = ROOT / 'scripts/generate_japanese_sentences.py'
        self.assertTrue(path.is_file(), 'Sentence generator is missing')
        spec = importlib.util.spec_from_file_location('sentence_generator', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_schema_rejects_malformed_inputs(self):
        generator, data = self.generator(), self.source()
        generator.validate(data)
        cases = []
        def changed(path, value):
            candidate = copy.deepcopy(data)
            owner = candidate
            for key in path[:-1]:
                owner = owner[key]
            owner[path[-1]] = value
            cases.append((path, value, candidate))
        changed(['edition'], 2)
        changed(['edition'], True)
        changed(['cards'], data['cards'][:-1])
        changed(['cards'], data['cards'] + [data['cards'][0]])
        changed(['cards', 1, 'id'], 'sentence-01')
        changed(['cards', 0, 'id'], 'sentence-99')
        changed(['provenance', 'authoredForHanMo'], False)
        changed(['provenance', 'isOriginalJpfText'], True)
        changed(['provenance', 'referenceUrls'], ['https://example.com/lesson.pdf'])
        for field in ['id', 'japanese', 'kanaReading', 'romaji', 'meaning']:
            for value in ['', None, 17, [], 'bad\x00text', '\ud800']:
                changed(['cards', 0, field], value)
        for value in ['Kore wa hon desu.', 'kore  wa hon desu.', 'kore wa hon 2.', 'kore wa hon desu', 'kore ha hon desu.']:
            changed(['cards', 0, 'romaji'], value)
        for value in [None, [], ['one'], ['one', 'two', 'three'], ['', 'two'], [22, 'two'], ['長' * 29, 'two']]:
            changed(['cards', 0, 'grammarNotes'], value)
        for value in [44, 46, -2, True, '45', None]:
            changed(['cards', 0, 'vocabularyCardId'], value)
        changed(['cards', 3, 'vocabularyCardId'], 44)
        for path, value, candidate in cases:
            with self.subTest(path=path, value=repr(value)):
                with self.assertRaises(ValueError):
                    generator.validate(candidate)

    def test_deterministic_cli_and_check_mode(self):
        generator = self.generator()
        header = ROOT / 'src/activities/apps/japanese/JapaneseSentences.generated.h'
        with tempfile.TemporaryDirectory(dir=ROOT / 'build/japanese-sentences-child') as directory:
            output = Path(directory) / 'sentences.h'
            command = [sys.executable, str(ROOT / 'scripts/generate_japanese_sentences.py'),
                       '--source', str(SOURCE), '--output', str(output)]
            subprocess.run(command, check=True, capture_output=True)
            before = hashlib.sha256(output.read_bytes()).hexdigest()
            subprocess.run(command, check=True, capture_output=True)
            self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(), before)
            self.assertEqual(output.read_text(encoding='utf-8'), generator.generate(self.source()))
            self.assertEqual(output.read_bytes(), header.read_bytes())
            self.assertEqual(subprocess.run(command + ['--check'], capture_output=True).returncode, 0)
            output.write_text('stale', encoding='utf-8')
            self.assertNotEqual(subprocess.run(command + ['--check'], capture_output=True).returncode, 0)
            self.assertEqual(output.read_text(), 'stale')

    def test_actual_generated_cpp_all_fields_utf8_byte_parity(self):
        self.generator()
        build = ROOT / 'build/japanese-sentences-child/parity'
        build.mkdir(parents=True, exist_ok=True)
        cpp, binary = build / 'parity.cpp', build / 'parity'
        cpp.write_text(r'''
#include "JapaneseSentences.generated.h"
#include <cstring>
#include <iostream>
#include <string>
void emit(const char* s) { std::cout << std::strlen(s) << ':'; std::cout.write(s,std::strlen(s)); }
int main() {
  static_assert(japanese::sentences::kCardCount == 6);
  for (const auto& c : japanese::sentences::cards) {
    emit(c.id); emit(c.japanese); emit(c.kanaReading); emit(c.romaji); emit(c.meaning);
    for (const auto* note : c.grammarNotes) emit(note);
    emit(std::to_string(c.vocabularyCardId).c_str());
  }
}
''', encoding='utf-8')
        compiled = subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-I',
                                   str(ROOT / 'src/activities/apps/japanese'), str(cpp), '-o', str(binary)],
                                  capture_output=True, text=True)
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        result = subprocess.run([str(binary)], check=True, capture_output=True).stdout
        expected = []
        for c in self.source()['cards']:
            expected += [c[k].encode('utf-8') for k in ['id','japanese','kanaReading','romaji','meaning']]
            expected += [s.encode('utf-8') for s in c['grammarNotes']]
            expected += [str(c['vocabularyCardId']).encode('ascii')]
        actual, offset = [], 0
        while offset < len(result):
            colon = result.index(b':', offset)
            length = int(result[offset:colon])
            offset = colon + 1
            actual.append(result[offset:offset+length])
            offset += length
        self.assertEqual(offset, len(result))
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
