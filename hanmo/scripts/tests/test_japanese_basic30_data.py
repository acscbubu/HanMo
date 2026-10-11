"""Topics edition 3: Basic editorial oracle, original54, assembly and real outputs."""
from pathlib import Path
import copy
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from scripts.tests import test_japanese_dialogues_data as legacy

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data/japanese/sentences-dialogues.json'
ORIGINAL = ROOT / 'data/japanese/sentences-dialogues-v1.json'
TOPICS = ROOT / 'data/japanese/topics30'
BUILD = ROOT / 'build/japanese-basic30-data'
FIXTURE = ROOT / 'scripts/tests/fixtures/japanese_basic30_original54.json'
FIELDS = ('japanese', 'kanaReading', 'romaji', 'meaning')
COUNTS = (30, 30, 30, 30, 30, 30, 30, 30, 30)
FIRSTS = (0, 30, 60, 90, 120, 150, 180, 210, 240)

# Independent editorial oracle, NOT loaded from authored JSON or transliterated
# by the generator. Each row was reviewed for kana, natural polite beginner
# Japanese, Hepburn (particles wa/e/o), Taiwan meaning and both teaching notes.
# Conventional Hepburn keeps ei in gakusei/eiga; long ou/oo use macrons.
REVIEWED_ADDITIONS = (
    ('sentence-07', 'わたしはがくせいです。', 'watashi wa gakusei desu.', '我是學生。', ('は表示主題，讀 wa。', 'です讓名詞句更客氣。')),
    ('sentence-08', 'おしごとはなんですか。', 'oshigoto wa nan desu ka?', '您從事什麼工作？', ('おしごとは工作的客氣說法。', 'なんですか用來問是什麼。')),
    ('sentence-09', 'これはわたしのかばんです。', 'kore wa watashi no kaban desu.', '這是我的包包。', ('の表示所屬關係。', 'これは用來介紹眼前物品。')),
    ('sentence-10', 'あれはわたしのじてんしゃです。', 'are wa watashi no jitensha desu.', '那是我的腳踏車。', ('あれ指離雙方較遠的物品。', 'わたしの表示我的。')),
    ('sentence-11', 'にほんごはむずかしいです。', 'nihongo wa muzukashii desu.', '日語很難。', ('むずかしい表示困難。', 'い形容詞後加です更客氣。')),
    ('sentence-12', 'きょうはさむくないです。', 'kyō wa samukunai desu.', '今天不冷。', ('さむい的否定是さむくない。', 'きょう表示今天。')),
    ('sentence-13', 'わたしはコーヒーがすきです。', 'watashi wa kōhī ga suki desu.', '我喜歡咖啡。', ('が標示喜歡的對象。', 'すきです表示喜歡。')),
    ('sentence-14', 'あまいものはすきではありません。', 'amai mono wa suki de wa arimasen.', '我不喜歡甜食。', ('あまいもの指甜的東西。', 'ではありません表示客氣否定。')),
    ('sentence-15', 'ねこがへやにいます。', 'neko ga heya ni imasu.', '房間裡有貓。', ('います用於人或動物的存在。', 'に標示存在的地點。')),
    ('sentence-16', 'つくえのうえにペンがあります。', 'tsukue no ue ni pen ga arimasu.', '桌上有筆。', ('のうえ表示在上面。', 'あります用於物品的存在。')),
    ('sentence-17', 'がっこうはえきのちかくです。', 'gakkō wa eki no chikaku desu.', '學校在車站附近。', ('のちかく表示在附近。', 'は提示要說明位置的地方。')),
    ('sentence-18', 'いまはひまではありません。', 'ima wa hima de wa arimasen.', '現在沒空。', ('ひま表示有空。', 'ではありません表示客氣否定。')),
    ('sentence-19', 'まいあさろくじにおきます。', 'maiasa rokuji ni okimasu.', '每天早上六點起床。', ('に標示具體的時間。', 'おきます表示起床。')),
    ('sentence-20', 'あしたはちちとでかけます。', 'ashita wa chichi to dekakemasu.', '明天要和爸爸出門。', ('と表示與誰一起行動。', 'ちち用來對外說自己的父親。')),
    ('sentence-21', 'きのうははやくねました。', 'kinō wa hayaku nemashita.', '昨天很早就睡了。', ('ました表示過去的動作。', 'はやく在此表示時間早。')),
    ('sentence-22', 'きょうはテレビをみません。', 'kyō wa terebi o mimasen.', '今天不看電視。', ('ません是ます的否定形式。', 'を標示動作對象，讀 o。')),
    ('sentence-23', 'どようびにえいがをみます。', 'doyōbi ni eiga o mimasu.', '星期六要看電影。', ('に可標示星期等時間。', 'えいがをみます表示看電影。')),
    ('sentence-24', 'にちようびはなにをしますか。', 'nichiyōbi wa nani o shimasu ka?', '星期日要做什麼？', ('なに用來問什麼。', 'か放在句尾表示疑問。')),
    ('sentence-25', 'まいにちバスでがっこうへいきます。', 'mainichi basu de gakkō e ikimasu.', '每天搭公車去學校。', ('で標示交通工具。', 'へ表示方向，讀 e。')),
    ('sentence-26', 'ここにすわってもいいですか。', 'koko ni suwatte mo ii desu ka?', '可以坐在這裡嗎？', ('に標示坐下的位置。', 'てもいいですか用來徵求同意。')),
    ('sentence-27', 'ゆっくりはなしてください。', 'yukkuri hanashite kudasai.', '請說慢一點。', ('ゆっくり表示慢慢地。', 'てください用來客氣地請求。')),
    ('sentence-28', 'もういちどいってください。', 'mō ichido itte kudasai.', '請再說一次。', ('もういちど表示再一次。', 'いって是いう的て形。')),
    ('sentence-29', 'しおをとってください。', 'shio o totte kudasai.', '請把鹽拿給我。', ('を標示動作對象，讀 o。', 'とって是とる的て形。')),
    ('sentence-30', 'いっしょにさんぽしませんか。', 'issho ni sanpo shimasen ka?', '要不要一起散步？', ('いっしょに表示一起。', 'ませんか用來客氣地邀請。')),
)


def reviewed_inputs(test):
    paths = {cid:TOPICS/(cid+'.json') for cid in legacy.CATEGORY_IDS}
    missing = [cid for cid,path in paths.items() if not path.is_file()]
    test.assertFalse(missing, 'Parent integration dependency: missing authored arrays ' + ', '.join(missing))
    return {cid:json.loads(path.read_bytes()) for cid,path in paths.items()}


def source():
    return legacy.DialoguesDataTests().source()


def raw_cards(payload):
    # Frozen raw UTF-8 card blocks: root card indentation is distinct from lines.
    return {match.group(1).decode('ascii'): match.group(0) for match in re.finditer(
        rb'    \{\n      "id": "([a-z]+-\d+)".*?\n    \}', payload, re.S)}


class Basic30AuthoredTests(unittest.TestCase):
    def test_basic24_array_matches_independent_reviewed_oracle(self):
        path = TOPICS / 'basic.json'
        self.assertTrue(path.is_file(), 'Reviewed Basic07..30 addition array required')
        additions = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(len(additions), 24)
        self.assertEqual(len(REVIEWED_ADDITIONS), 24)
        for card, (sid, japanese, romaji, meaning, notes) in zip(additions, REVIEWED_ADDITIONS):
            with self.subTest(id=sid):
                self.assertEqual(card, dict(id=sid, category=0,
                    a=dict(zip(FIELDS, (japanese, japanese, romaji, meaning))),
                    b=dict.fromkeys(FIELDS, ''), grammarNotes=list(notes), vocabularyCardId=-1))
                self.assertLessEqual(len(japanese), 20)
                self.assertRegex(japanese, r'^[\u3041-\u3096\u30a1-\u30faー、。]+。$')
                for note in notes:
                    self.assertLessEqual(len(note), 22)
        original = json.loads(ORIGINAL.read_bytes())
        japanese = [card['a']['japanese'] for card in original['cards'][:6] + additions]
        self.assertEqual(len(japanese), 30)
        self.assertEqual(len(set(japanese)), 30)
        self.assertEqual(sum(card['a']['japanese'].startswith('これ') for card in additions), 1)

    def test_immutable_original54_is_frozen_byte_exact(self):
        baseline = FIXTURE.read_bytes()
        self.assertEqual(hashlib.sha256(baseline).hexdigest(), '33176928d6f8a48b92cfd39ac731d832f46487f37291869f7c16a85108ef8402')
        self.assertEqual(ORIGINAL.read_bytes(), baseline)
        old = json.loads(baseline)
        old_blocks = raw_cards(baseline)
        self.assertEqual(len(old_blocks), 54)
        self.assertEqual(len(old['cards']), 54)


class Basic30GeneratorTests(unittest.TestCase):
    def generator(self):
        return legacy.DialoguesGeneratorTests().generator()

    def test_assemble_requires_exact_nine_reviewed_addition_arrays(self):
        generator = self.generator()
        self.assertTrue(callable(getattr(generator, 'assemble', None)), 'Pure reviewed-source assembler is missing')
        original = json.loads(ORIGINAL.read_bytes())
        basic = json.loads((TOPICS/'basic.json').read_bytes())
        for additions in (None, [], {}, {'basic':basic},
                          dict.fromkeys(legacy.CATEGORY_IDS, []),
                          dict.fromkeys(legacy.CATEGORY_IDS, None)):
            with self.subTest(additions=type(additions).__name__):
                with self.assertRaises(ValueError):
                    generator.assemble(original, additions)

    def test_actual_assembled_270_preserves_old54_and_does_not_mutate_inputs(self):
        generator = self.generator()
        self.assertTrue(callable(getattr(generator, 'assemble', None)), 'Pure reviewed-source assembler is missing')
        original = json.loads(ORIGINAL.read_bytes())
        additions = reviewed_inputs(self)
        before = copy.deepcopy((original, additions))
        data = generator.assemble(original, additions)
        self.assertEqual((original, additions), before)
        self.assertEqual(data['edition'], 3)
        self.assertEqual(data['categories'], [dict(id=cid, first=first, count=count)
                         for cid, first, count in zip(legacy.CATEGORY_IDS, FIRSTS, COUNTS)])
        self.assertEqual(len(data['cards']), 270)
        self.assertEqual(sum(bool(line['japanese']) for card in data['cards'] for line in (card['a'],card['b'])), 510)
        old_blocks = raw_cards(ORIGINAL.read_bytes())
        new_blocks = raw_cards((json.dumps(data, ensure_ascii=False, indent=2)+'\n').encode('utf-8'))
        for index, card in enumerate(original['cards']):
            self.assertEqual(data['cards'][(index//6)*30+index%6], card)
            self.assertEqual(new_blocks[card['id']], old_blocks[card['id']])
        self.assertEqual(data['provenance'], original['provenance'])
        self.assertEqual(data['basicProvenance'], original['basicProvenance'])
        self.assertEqual(generator.assemble(original, additions), data)
        data['cards'][0]['a']['meaning'] = 'not an alias'
        data['cards'][6]['a']['meaning'] = 'not an alias'
        self.assertEqual((original, additions), before)

    def test_assembly_cli_exposes_explicit_safe_modes(self):
        script = ROOT/'scripts/generate_japanese_dialogues.py'
        help_result = subprocess.run([sys.executable,str(script),'--help'],capture_output=True,text=True)
        self.assertEqual(help_result.returncode,0,help_result.stderr)
        self.assertIn('--assemble',help_result.stdout)
        self.assertIn('--original',help_result.stdout)
        self.assertIn('--additions-dir',help_result.stdout)
        BUILD.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=BUILD) as directory:
            out = Path(directory)/'untouched.json'
            out.write_bytes(b'never overwritten on missing inputs')
            # A negative empty-input directory is intentionally invalid, not a course fixture.
            empty = Path(directory)/'empty'; empty.mkdir()
            result = subprocess.run([sys.executable,str(script),'--assemble','--additions-dir',str(empty),
                                     '--output',str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,2,result.stderr)
            self.assertNotIn('unrecognized arguments',result.stderr)
            self.assertNotIn('Traceback',result.stderr)
            self.assertEqual(out.read_bytes(),b'never overwritten on missing inputs')

    def test_actual_cpp_declarations_use_uint16_ranges_and_270_count(self):
        generator = self.generator()
        self.assertTrue(callable(getattr(generator,'cpp_declarations',None)), 'Data-free C++ schema declaration emitter is missing')
        BUILD.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=BUILD) as directory:
            root = Path(directory)
            declarations = '\n'.join(generator.cpp_declarations() + ['}']) + '\n'
            (root/'schema.h').write_text(declarations,encoding='utf-8')
            (root/'schema.cpp').write_text('''#include "schema.h"
#include <type_traits>
using namespace japanese::dialogues;
static_assert(kCategoryCount==9 && kCardCount==270 && kMaxCardsPerCategory==30);
static_assert(std::is_same_v<decltype(Category::first),uint16_t>);
static_assert(std::is_same_v<decltype(Category::count),uint8_t>);
static_assert(std::is_same_v<decltype(Card::category),uint8_t>);
constexpr Category range{"type-boundary-only",269,30};
static_assert(range.first==269 && range.count==30);
int main(){return 0;}
''',encoding='utf-8')
            command = ['c++','-std=c++17','-Wall','-Wextra','-Werror',str(root/'schema.cpp'),'-o',str(root/'schema')]
            compiled = subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(compiled.returncode,0,compiled.stderr)
            self.assertEqual(subprocess.run([str(root/'schema')],capture_output=True).returncode,0)

    def test_actual_assembly_cli_deterministic_check_and_no_production_write(self):
        reviewed_inputs(self)
        generator = self.generator()
        expected = generator.assemble(json.loads(ORIGINAL.read_bytes()), reviewed_inputs(self))
        BUILD.mkdir(parents=True,exist_ok=True)
        before = SOURCE.read_bytes()
        production_header = ROOT/'src/activities/apps/japanese/JapaneseDialogues.generated.h'
        header_before = production_header.read_bytes()
        with tempfile.TemporaryDirectory(dir=BUILD) as directory:
            output = Path(directory)/'assembled.json'
            command = [sys.executable,str(ROOT/'scripts/generate_japanese_dialogues.py'),'--assemble','--output',str(output)]
            run = subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertIn('9 categories, 270 scenes, 510 utterances',run.stdout)
            self.assertEqual(json.loads(output.read_bytes()),expected)
            first = output.read_bytes()
            self.assertEqual(subprocess.run(command,capture_output=True).returncode,0)
            self.assertEqual(output.read_bytes(),first)
            self.assertEqual(subprocess.run(command+['--check'],capture_output=True).returncode,0)
            output.write_bytes(b'stale assembly')
            self.assertEqual(subprocess.run(command+['--check'],capture_output=True).returncode,1)
            self.assertEqual(output.read_bytes(),b'stale assembly')
            output.unlink()
            self.assertEqual(subprocess.run(command+['--check'],capture_output=True).returncode,1)
            self.assertFalse(output.exists())
        self.assertEqual(SOURCE.read_bytes(),before)
        self.assertEqual(production_header.read_bytes(),header_before)

    def test_actual_edition3_cpp_constants_include_uint16_category_first(self):
        generator = self.generator()
        data = generator.assemble(json.loads(ORIGINAL.read_bytes()), reviewed_inputs(self))
        header = generator.generate(data)
        self.assertIn('inline constexpr int kCategoryCount = 9;', header)
        self.assertIn('inline constexpr int kCardCount = 270;', header)
        self.assertIn('inline constexpr int kMaxCardsPerCategory = 30;', header)
        self.assertIn('uint16_t first;', header)
        self.assertNotIn('kCardsPerCategory', header)
        self.assertEqual(header.count('"sentence-'), 30)
        self.assertEqual(header.encode('utf-8'), generator.generate(data).encode('utf-8'))


    def test_topics30_schema_rejects_numeric_bounds_ids_and_duplicates(self):
        generator, data = self.generator(), source()
        generator.validate(data)
        cases = []
        def changed(path, value):
            candidate = copy.deepcopy(data)
            owner = candidate
            for key in path[:-1]:
                owner = owner[key]
            owner[path[-1]] = value
            cases.append((repr(path) + ':' + repr(value), candidate))
        for category in range(9):
            for key in ('first', 'count'):
                for value in (True, False, None, '6', 6.0, -1, 0, 256):
                    if type(value) is not int or value != data['categories'][category][key]:
                        changed(['categories', category, key], value)
            changed(['categories', category, 'first'], FIRSTS[category] + 1)
            changed(['categories', category, 'count'], COUNTS[category] - 1)
        for index in (6, 29, 30, 59, 60, 239, 240, 255, 269):
            for value in (True, 0.0, '0', -1, 9):
                changed(['cards', index, 'category'], value)
            changed(['cards', index, 'id'], 'sentence-30' if index != 29 else 'sentence-29')
        for index in (6, 29):
            for key in FIELDS:
                changed(['cards', index, 'b', key], 'はい。')
            for value in (True, False, -1.0, None, 0, 45):
                changed(['cards', index, 'vocabularyCardId'], value)
        changed(['cards'], data['cards'][:54])
        changed(['cards', 29, 'a', 'extra'], 'ignored')
        changed(['cards', 29, 'a', 'japanese'], 'あ' * 20 + '。')
        changed(['cards', 29, 'grammarNotes'], ['あ' * 23, '二'])
        changed(['cards',29,'a'],data['cards'][28]['a'])
        for index, other in ((36,37),(269,268)):
            candidate = copy.deepcopy(data)
            candidate['cards'][index]['a'] = copy.deepcopy(data['cards'][other]['a'])
            candidate['cards'][index]['b'] = copy.deepcopy(data['cards'][other]['b'])
            cases.append(('duplicate A/B pair '+str(index),candidate))
        for label, candidate in cases:
            with self.subTest(case=label):
                with self.assertRaises(ValueError):
                    generator.validate(candidate)
                with self.assertRaises(ValueError):
                    generator.generate(candidate)

    def test_scene_pair_rule_allows_repeated_natural_acknowledgments(self):
        generator = self.generator()
        data = generator.assemble(json.loads(ORIGINAL.read_bytes()), reviewed_inputs(self))
        candidate = copy.deepcopy(data)
        # Existing natural acknowledgment, re-used only in an invalid/valid
        # schema test candidate, never published as new authored course text.
        acknowledgment = data['cards'][32]['b']
        for index in (36,37):
            candidate['cards'][index]['b'] = copy.deepcopy(acknowledgment)
        pairs = [(c['a']['japanese'],c['b']['japanese']) for c in candidate['cards'][30:60]]
        self.assertEqual(len(set(pairs)),30,'Test must exercise repeated B without accidentally duplicating A/B')
        generator.validate(candidate)
        candidate['cards'][37]['a'] = copy.deepcopy(candidate['cards'][36]['a'])
        with self.assertRaisesRegex(ValueError,'scene pairs'):
            generator.validate(candidate)

    def test_assembly_is_pure_without_filesystem_reads(self):
        from unittest.mock import patch
        generator = self.generator()
        original = json.loads(ORIGINAL.read_bytes())
        additions = reviewed_inputs(self)
        expected = generator.assemble(original, additions)
        with patch.object(Path,'read_text',side_effect=AssertionError('Assembler must not read filesystem')), \
             patch.object(Path,'read_bytes',side_effect=AssertionError('Assembler must not read filesystem')):
            self.assertEqual(generator.assemble(original,additions),expected)

    def test_all54_original_objects_reject_field_changes_by_id(self):
        generator, data = self.generator(), source()
        original = json.loads(ORIGINAL.read_bytes())
        positions = {card['id']:index for index,card in enumerate(data['cards'])}
        for old in original['cards']:
            index = positions[old['id']]
            for field in ('meaning','romaji','grammarNotes'):
                with self.subTest(id=old['id'],field=field):
                    changed = copy.deepcopy(data)
                    if field == 'grammarNotes':
                        changed['cards'][index][field][0] = '舊教材提示已改。'
                    else:
                        changed['cards'][index]['a'][field] = '舊翻譯已更改。' if field=='meaning' else 'changed text.'
                    with self.assertRaisesRegex(ValueError,'original'):
                        generator.validate(changed)

    def test_assemble_rejects_changed_original_types_or_objects(self):
        generator = self.generator()
        self.assertTrue(callable(getattr(generator,'assemble',None)))
        original = json.loads(ORIGINAL.read_bytes())
        cases = (None, [], {'edition':1})
        for wrong in cases:
            with self.assertRaises(ValueError):
                generator.assemble(wrong,{})
        for path,value in ((('edition',),True),(('edition',),1.0),
                           (('cards',53,'a','meaning'),'改過的翻譯。'),
                           (('categories',1,'first'),6.0),
                           (('cards',0,'grammarNotes'),['改過的提示。','二'])):
            changed = copy.deepcopy(original)
            owner = changed
            for key in path[:-1]: owner = owner[key]
            owner[path[-1]] = value
            with self.assertRaisesRegex(ValueError,'unchanged original'):
                generator.assemble(changed,{})

    def test_bad_basic30_cli_never_creates_or_overwrites_output(self):
        BUILD.mkdir(parents=True, exist_ok=True)
        data = source()
        candidates = []
        wrong_range = copy.deepcopy(data)
        wrong_range['categories'][1]['first'] = 6
        candidates.append(wrong_range)
        wrong_id = copy.deepcopy(data)
        wrong_id['cards'][29]['id'] = 'sentence-31'
        candidates.append(wrong_id)
        duplicate = copy.deepcopy(data)
        duplicate['cards'][29]['a'] = copy.deepcopy(data['cards'][28]['a'])
        candidates.append(duplicate)
        with tempfile.TemporaryDirectory(dir=BUILD) as directory:
            input_path, output = Path(directory)/'bad.json', Path(directory)/'untouched.h'
            command = [sys.executable, str(ROOT/'scripts/generate_japanese_dialogues.py'),
                       '--source', str(input_path), '--output', str(output)]
            for candidate in candidates:
                input_path.write_text(json.dumps(candidate, ensure_ascii=False), encoding='utf-8')
                for destination_exists in (False, True):
                    if destination_exists:
                        output.write_bytes(b'preserve existing bytes')
                    else:
                        output.unlink(missing_ok=True)
                    result = subprocess.run(command, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertNotIn('Traceback', result.stderr)
                    if destination_exists:
                        self.assertEqual(output.read_bytes(), b'preserve existing bytes')
                    else:
                        self.assertFalse(output.exists())


class Basic30FontTests(unittest.TestCase):
    def test_font_input_builder_rejects_legacy54_in_new_topics30_model(self):
        font = legacy.DialoguesFontTests().font_script()
        BUILD.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=BUILD) as directory:
            root = Path(directory)
            target = root/'data/japanese'; target.mkdir(parents=True)
            (target/'sentences-dialogues.json').write_bytes(ORIGINAL.read_bytes())
            for name in ('sentences-basic.json','kana-basic.json'):
                (target/name).write_bytes((ROOT/'data/japanese'/name).read_bytes())
            with self.assertRaises(ValueError):
                font.font_specs(root)

    def test_real_topics30_font_inputs_include_all_new_kana_and_taiwan_notes(self):
        font = legacy.DialoguesFontTests().font_script()
        try:
            specs = {name:(size, chars) for name,size,chars in font.font_specs()}
        except ValueError as error:
            self.fail(f'Parent integration dependency: final Topics30 must supply the real font converter: {error}')
        self.assertEqual({name:size for name,(size,chars) in specs.items()},
                         {'hanmo_sentences_28':28, 'hanmo_dialogues_20':20, 'hanmo_sentence_notes_12':12})
        old = json.loads(FIXTURE.read_bytes())
        new = source()
        old_primary = set(''.join(line['japanese'] for card in old['cards'] for line in (card['a'],card['b'])))
        new_primary = set(''.join(line['japanese'] for card in new['cards'] for line in (card['a'],card['b'])))
        additions = new_primary - old_primary
        self.assertTrue(additions, 'This fixture must actually introduce new kana glyphs')
        self.assertFalse(additions - set(specs['hanmo_dialogues_20'][1]))
        for card in new['cards']:
            for speaker in ('a','b'):
                for field in FIELDS:
                    name = 'hanmo_dialogues_20' if field in ('japanese','kanaReading') else 'hanmo_sentence_notes_12'
                    self.assertFalse(set(card[speaker][field]) - set(specs[name][1]), (card['id'],speaker,field))
            self.assertFalse(set(''.join(card['grammarNotes'])) - set(specs['hanmo_sentence_notes_12'][1]))
        self.assertEqual(font.font_specs(), font.font_specs())


if __name__ == '__main__':
    unittest.main()
