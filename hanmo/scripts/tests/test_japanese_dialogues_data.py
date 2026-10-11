"""Authored independent language oracle plus real generated C++/font checks."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data/japanese/sentences-dialogues.json'
BUILD = ROOT / 'build/japanese-basic30-data'
CATEGORY_IDS = ('basic', 'daily', 'restaurant', 'shopping', 'transport', 'hotel', 'directions', 'social', 'emergency')
CATEGORY_COUNTS = (30, 30, 30, 30, 30, 30, 30, 30, 30)
CATEGORY_FIRSTS = (0, 30, 60, 90, 120, 150, 180, 210, 240)
FIELDS = ('japanese', 'kanaReading', 'romaji', 'meaning')
EMPTY = dict.fromkeys(FIELDS, '')
REVIEWED_BASIC = [
    ('sentence-01','これはほんです。','kore wa hon desu.','這是書。',45),
    ('sentence-02','これはかさです。','kore wa kasa desu.','這是傘。',5),
    ('sentence-03','これはちずです。','kore wa chizu desu.','這是地圖。',16),
    ('sentence-04','みずをのみます。','mizu o nomimasu.','喝水。',-1),
    ('sentence-05','すしをたべます。','sushi o tabemasu.','吃壽司。',12),
    ('sentence-06','ほんをよみます。','hon o yomimasu.','讀書。',45),
]

# Reviewed independently of the JSON loader/generator: (A Japanese, Hepburn,
# Taiwan meaning, B Japanese, Hepburn, Taiwan meaning), six scenes/category.
# Long vowels use macrons; unchanged Basic keeps its original spelling.
REVIEWED_SCENES = [
    ('おはようございます。', 'ohayō gozaimasu.', '早安。', 'きょうもいいてんきですね。', 'kyō mo ii tenki desu ne.', '今天也是好天氣呢。'),
    ('いま、なんじですか。', 'ima, nanji desu ka?', '現在幾點？', 'くじです。', 'kuji desu.', '九點。'),
    ('まどをあけてもいいですか。', 'mado o akete mo ii desu ka?', '可以開窗嗎？', 'はい、どうぞ。', 'hai, dōzo.', '可以，請。'),
    ('せんたくはおわりましたか。', 'sentaku wa owarimashita ka?', '衣服洗好了嗎？', 'はい、いまおわりました。', 'hai, ima owarimashita.', '是的，剛洗好。'),
    ('ゴミはどこにだしますか。', 'gomi wa doko ni dashimasu ka?', '垃圾要放在哪裡？', 'あそこにおねがいします。', 'asoko ni onegai shimasu.', '請放在那裡。'),
    ('あしたはやすみですか。', 'ashita wa yasumi desu ka?', '明天休息嗎？', 'はい、やすみです。', 'hai, yasumi desu.', '是的，休息。'),
    ('ふたりです。', 'futari desu.', '我們兩位。', 'こちらへどうぞ。', 'kochira e dōzo.', '請往這邊。'),
    ('メニューをおねがいします。', 'menyū o onegai shimasu.', '請給我菜單。', 'はい、こちらです。', 'hai, kochira desu.', '好的，這是菜單。'),
    ('おすすめはなんですか。', 'osusume wa nan desu ka?', '有什麼推薦的？', 'このスープがおすすめです。', 'kono sūpu ga osusume desu.', '推薦這道湯。'),
    ('コーヒーをひとつください。', 'kōhī o hitotsu kudasai.', '請給我一杯咖啡。', 'ホットでよろしいですか。', 'hotto de yoroshii desu ka?', '熱的可以嗎？'),
    ('おみずをいただけますか。', 'omizu o itadakemasu ka?', '可以給我水嗎？', 'はい、おもちします。', 'hai, omochi shimasu.', '好的，我拿過來。'),
    ('おかいけいをおねがいします。', 'okaikei o onegai shimasu.', '麻煩結帳。', 'レジでおねがいします。', 'reji de onegai shimasu.', '請到收銀台結帳。'),
    ('これはいくらですか。', 'kore wa ikura desu ka?', '這個多少錢？', 'せんえんです。', "sen'en desu.", '一千日圓。'),
    ('これをみてもいいですか。', 'kore o mite mo ii desu ka?', '可以看看這個嗎？', 'はい、おてにとってどうぞ。', 'hai, ote ni totte dōzo.', '可以，請拿起來看。'),
    ('ほかのいろはありますか。', 'hoka no iro wa arimasu ka?', '有其他顏色嗎？', 'あおもあります。', 'ao mo arimasu.', '也有藍色。'),
    ('もうすこしおおきいのはありますか。', 'mō sukoshi ōkii no wa arimasu ka?', '有再大一點的嗎？', 'はい、こちらはいかがですか。', 'hai, kochira wa ikaga desu ka?', '有，這個如何？'),
    ('カードはつかえますか。', 'kādo wa tsukaemasu ka?', '可以刷卡嗎？', 'はい、つかえます。', 'hai, tsukaemasu.', '可以。'),
    ('ふくろをひとつください。', 'fukuro o hitotsu kudasai.', '請給我一個袋子。', 'こちらをどうぞ。', 'kochira o dōzo.', '這個給您。'),
    ('このバスはえきにいきますか。', 'kono basu wa eki ni ikimasu ka?', '這班公車到車站嗎？', 'はい、えきにとまります。', 'hai, eki ni tomarimasu.', '是的，會停靠車站。'),
    ('きっぷはどこでかいますか。', 'kippu wa doko de kaimasu ka?', '車票在哪裡買？', 'あのきかいでかえます。', 'ano kikai de kaemasu.', '可以在那台機器買。'),
    ('つぎのでんしゃはなんじですか。', 'tsugi no densha wa nanji desu ka?', '下一班電車是幾點？', 'じゅうじにきます。', 'jūji ni kimasu.', '十點會來。'),
    ('ここでおりてもいいですか。', 'koko de orite mo ii desu ka?', '可以在這裡下車嗎？', 'はい、ここでだいじょうぶです。', 'hai, koko de daijōbu desu.', '可以，在這裡沒問題。'),
    ('くうこうまでおねがいします。', 'kūkō made onegai shimasu.', '麻煩到機場。', 'はい、わかりました。', 'hai, wakarimashita.', '好的，知道了。'),
    ('ここはあいていますか。', 'koko wa aite imasu ka?', '這個位子是空的嗎？', 'はい、どうぞおすわりください。', 'hai, dōzo osuwari kudasai.', '是的，請坐。'),
    ('よやくしているたなかです。', 'yoyaku shite iru tanaka desu.', '我是有預約的田中。', 'おなまえをかくにんします。', 'onamae o kakunin shimasu.', '我確認一下您的姓名。'),
    ('チェックインをおねがいします。', 'chekkuin o onegai shimasu.', '我要辦理入住。', 'パスポートをみせてください。', 'pasupōto o misete kudasai.', '請出示護照。'),
    ('へやはなんかいですか。', 'heya wa nankai desu ka?', '房間在幾樓？', 'さんかいです。', 'sankai desu.', '三樓。'),
    ('あさごはんはなんじからですか。', 'asagohan wa nanji kara desu ka?', '早餐從幾點開始？', 'しちじからです。', 'shichiji kara desu.', '從七點開始。'),
    ('タオルをもういちまいください。', 'taoru o mō ichimai kudasai.', '請再給我一條毛巾。', 'はい、おへやにおもちします。', 'hai, oheya ni omochi shimasu.', '好的，我拿到您的房間。'),
    ('チェックアウトはなんじですか。', 'chekkuauto wa nanji desu ka?', '退房時間是幾點？', 'じゅういちじです。', 'jūichiji desu.', '十一點。'),
    ('すみません、えきはどこですか。', 'sumimasen, eki wa doko desu ka?', '不好意思，車站在哪裡？', 'このみちをまっすぐです。', 'kono michi o massugu desu.', '沿這條路直走。'),
    ('トイレはどこですか。', 'toire wa doko desu ka?', '洗手間在哪裡？', 'あのドアのむこうです。', 'ano doa no mukō desu.', '在那扇門的另一邊。'),
    ('ここからあるいていけますか。', 'koko kara aruite ikemasu ka?', '可以從這裡走過去嗎？', 'はい、あるいてごふんです。', 'hai, aruite gofun desu.', '可以，走路五分鐘。'),
    ('ここをみぎにまがりますか。', 'koko o migi ni magarimasu ka?', '在這裡右轉嗎？', 'いいえ、ひだりです。', 'iie, hidari desu.', '不是，是左邊。'),
    ('ホテルはこのちかくですか。', 'hoteru wa kono chikaku desu ka?', '飯店在這附近嗎？', 'はい、すぐそこです。', 'hai, sugu soko desu.', '是的，就在那裡。'),
    ('ちずでおしえていただけますか。', 'chizu de oshiete itadakemasu ka?', '可以用地圖告訴我嗎？', 'はい、ここです。', 'hai, koko desu.', '可以，在這裡。'),
    ('はじめまして、たなかです。', 'hajimemashite, tanaka desu.', '初次見面，我是田中。', 'どうぞよろしくおねがいします。', 'dōzo yoroshiku onegai shimasu.', '請多多指教。'),
    ('おなまえをおしえてください。', 'onamae o oshiete kudasai.', '請告訴我您的名字。', 'さとうです。', 'satō desu.', '我姓佐藤。'),
    ('どちらからいらっしゃいましたか。', 'dochira kara irasshaimashita ka?', '請問您從哪裡來？', 'たいわんからきました。', 'taiwan kara kimashita.', '我從臺灣來。'),
    ('にほんごがおじょうずですね。', 'nihongo ga ojōzu desu ne.', '您的日語說得真好。', 'ありがとうございます。', 'arigatō gozaimasu.', '謝謝您。'),
    ('いっしょにおちゃをのみませんか。', 'issho ni ocha o nomimasen ka?', '要不要一起喝茶？', 'いいですね。', 'ii desu ne.', '好啊。'),
    ('またおあいしましょう。', 'mata oai shimashō.', '下次再見吧。', 'はい、またこんど。', 'hai, mata kondo.', '好，下次見。'),
    ('たすけてください。', 'tasukete kudasai.', '請幫幫我。', 'どうしましたか。', 'dō shimashita ka?', '怎麼了？'),
    ('さいふをなくしました。', 'saifu o nakushimashita.', '我的錢包不見了。', 'こうばんにいきましょう。', 'kōban ni ikimashō.', '我們去派出所吧。'),
    ('けいさつをよんでください。', 'keisatsu o yonde kudasai.', '請幫我叫警察。', 'はい、すぐにれんらくします。', 'hai, sugu ni renraku shimasu.', '好的，我馬上聯絡。'),
    ('ひじょうぐちはどこですか。', 'hijōguchi wa doko desu ka?', '逃生出口在哪裡？', 'こちらです。いそいでください。', 'kochira desu. isoide kudasai.', '在這裡。請快一點。'),
    ('ここはあぶないですか。', 'koko wa abunai desu ka?', '這裡危險嗎？', 'はい、はなれてください。', 'hai, hanarete kudasai.', '是的，請離開這裡。'),
    ('まいごになりました。', 'maigo ni narimashita.', '我迷路了。', 'ここでいっしょにまちましょう。', 'koko de issho ni machimashō.', '我們一起在這裡等吧。'),
]

class DialoguesDataTests(unittest.TestCase):
    def source(self):
        self.assertTrue(SOURCE.is_file(), 'Authored categorized dialogue source is missing')
        data = json.loads(SOURCE.read_text(encoding='utf-8'))
        self.assertEqual(data['edition'],3,'Parent integration dependency: final nine-category source assembly is required')
        return data

    def test_basic_six_fields_and_provenance_preserved(self):
        data = self.source()
        original = json.loads((ROOT / 'data/japanese/sentences-basic.json').read_text(encoding='utf-8'))
        self.assertEqual(data['basicProvenance'], original['provenance'])
        self.assertEqual(data['categories'], [dict(id=cid, first=first, count=count)
                         for cid,first,count in zip(CATEGORY_IDS,CATEGORY_FIRSTS,CATEGORY_COUNTS)])
        for index, (card, old) in enumerate(zip(data['cards'][:6], original['cards'])):
            self.assertEqual(card['id'], old['id'])
            self.assertEqual(card['category'], 0)
            self.assertEqual(card['a'], {key:old[key] for key in FIELDS})
            self.assertEqual(card['b'], EMPTY)
            self.assertEqual(card['grammarNotes'], old['grammarNotes'])
            self.assertEqual(card['vocabularyCardId'], old['vocabularyCardId'])
            sid,jp,romaji,meaning,vocabulary=REVIEWED_BASIC[index]
            self.assertEqual((card['id'],card['a'],card['vocabularyCardId']),
                             (sid,dict(zip(FIELDS,(jp,jp,romaji,meaning))),vocabulary))
            notes=['は表示主題，此時讀 wa。','です是客氣的說法。'] if index<3 else ['を表示動作對象，讀 o。','ます是客氣的說法。']
            self.assertEqual(card['grammarNotes'],notes)
        self.assertEqual(len(data['cards'][:6]), 6)

    def test_independent_legacy102_line_oracle_in_270_scenes(self):
        data = self.source()
        self.assertEqual(len(data['cards']), 270)
        self.assertEqual(len(REVIEWED_SCENES), 48)
        self.assertEqual(data['edition'], 3)
        self.assertEqual(data['provenance']['referenceUrls'], [])
        self.assertIs(data['provenance']['authoredForHanMo'], True)
        self.assertIs(data['provenance']['isOriginalJpfText'], False)
        self.assertIn('not copied', data['provenance']['claim'])
        ids, utterances = [], []
        for index, card in enumerate(data['cards']):
            category = next(c for c,(first,count) in enumerate(zip(CATEGORY_FIRSTS,CATEGORY_COUNTS)) if first <= index < first+count)
            local = index-CATEGORY_FIRSTS[category]
            expected_id = f"{'sentence' if category == 0 else CATEGORY_IDS[category]}-{local+1:02d}"
            self.assertEqual((card['id'],card['category']), (expected_id,category))
            ids.append(card['id'])
            if category and local < 6:
                aj, ar, am, bj, br, bm = REVIEWED_SCENES[(category-1)*6+local]
                self.assertEqual(card['a'], dict(zip(FIELDS,(aj,aj,ar,am))))
                self.assertEqual(card['b'], dict(zip(FIELDS,(bj,bj,br,bm))))
                self.assertEqual(card['vocabularyCardId'], -1)
            for line in (card['a'],card['b']):
                if not line['japanese']:
                    continue
                utterances.append(line['japanese'])
                self.assertLessEqual(len(line['japanese']),20)
                self.assertRegex(line['japanese'], r'^[\u3041-\u3096\u30a1-\u30faー、。]+。$')
            self.assertEqual(len(card['grammarNotes']),2)
            for note in card['grammarNotes']:
                self.assertTrue(note.strip())
                self.assertLessEqual(len(note),22)
        self.assertEqual(len(set(ids)),270)
        self.assertEqual(len(utterances),510)
        for category,first in enumerate(CATEGORY_FIRSTS):
            pairs = [(c['a']['japanese'],c['b']['japanese']) for c in data['cards'][first:first+30]]
            self.assertEqual(len(set(pairs)),30,category)

class DialoguesGeneratorTests(unittest.TestCase):
    source = DialoguesDataTests.source

    def generator(self):
        path = ROOT / 'scripts/generate_japanese_dialogues.py'
        self.assertTrue(path.is_file(), 'Dialogue generator is missing')
        spec = importlib.util.spec_from_file_location('dialogue_generator',path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_schema_rejects_malformed_inputs_without_partial_output(self):
        generator, data = self.generator(), self.source()
        self.assertTrue(callable(getattr(generator,'validate',None)), 'Explicit schema validator is missing')
        generator.validate(data)
        cases = [('not-object',None),('not-object',[])]
        def changed(path,value):
            candidate=copy.deepcopy(data); owner=candidate
            for key in path[:-1]: owner=owner[key]
            owner[path[-1]]=value
            cases.append((repr(path)+repr(value),candidate))
        changed(['edition'],True); changed(['edition'],1); changed(['edition'],2); changed(['edition'],4)
        changed(['extra'],1)
        for value in [None,[],data['cards'][:-1],data['cards']+[data['cards'][0]]]: changed(['cards'],value)
        for value in [None,[],data['categories'][:-1]]: changed(['categories'],value)
        changed(['categories',1,'id'],'shopping'); changed(['categories',1,'first'],5)
        changed(['categories',1,'count'],True); changed(['categories',1,'extra'],1)
        changed(['cards',7,'id'],'daily-01'); changed(['cards',6,'id'],'daily-99')
        changed(['cards',6,'category'],2); changed(['cards',6,'category'],True)
        changed(['cards',6,'extra'],1); changed(['cards',6,'a','extra'],'ignored')
        for value in [None, [], 'line']: changed(['cards',6,'a'],value)
        changed(['cards',0,'a','meaning'],'這是一本書。')
        changed(['cards',0,'b','japanese'],'はい。')
        changed(['basicProvenance','claim'],'changed')
        changed(['provenance','authoredForHanMo'],False)
        changed(['provenance','isOriginalJpfText'],True)
        changed(['provenance','claim'],'Copied course passage')
        changed(['provenance','referenceUrls'],['https://example.com/course'])
        for field in FIELDS:
            for value in ['',None,17,[], 'bad\x00text','\ud800','x\x7fy']:
                changed(['cards',6,'a',field],value)
        for value in ['今日は晴れです。','ハロー', 'a。','あ'*20+'。','あ\u3099。']:
            changed(['cards',6,'a','japanese'],value)
        changed(['cards',6,'a','kanaReading'],'おはよう。')
        for value in ['Ohayō gozaimasu.','ohayō  gozaimasu.','ohayō gozaimasu','ohayō2 gozaimasu.',"se'en desu.",'mado wo akemasu.']:
            changed(['cards',6,'a','romaji'],value)
        for value in [None,[],['一個'],['一','二','三'],['','二'],[22,'二'],['長'*23,'二']]: changed(['cards',6,'grammarNotes'],value)
        for value in [True,'-1',None,-2,0,44,46]: changed(['cards',6,'vocabularyCardId'],value)
        for label,candidate in cases:
            with self.subTest(case=label):
                with self.assertRaises(ValueError): generator.validate(candidate)
                with self.assertRaises(ValueError): generator.generate(candidate)

    def test_deterministic_cli_check_and_invalid_input_no_write(self):
        generator = self.generator()
        BUILD.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=BUILD) as directory:
            output = Path(directory)/'generated.h'
            command = [sys.executable,str(ROOT/'scripts/generate_japanese_dialogues.py'),'--source',str(SOURCE),'--output',str(output)]
            first = subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(first.returncode,0,first.stderr)
            self.assertTrue(output.is_file(),'Generator CLI did not write the requested temp output')
            before = output.read_bytes()
            self.assertEqual(before,generator.generate(self.source()).encode('utf-8'))
            subprocess.run(command,check=True,capture_output=True)
            self.assertEqual(output.read_bytes(),before)
            self.assertEqual(subprocess.run(command+['--check'],capture_output=True).returncode,0)
            output.write_bytes(b'stale')
            self.assertNotEqual(subprocess.run(command+['--check'],capture_output=True).returncode,0)
            self.assertEqual(output.read_bytes(),b'stale')
            output.unlink()
            self.assertNotEqual(subprocess.run(command+['--check'],capture_output=True).returncode,0)
            self.assertFalse(output.exists())
            invalid = Path(directory)/'invalid.json'
            invalid.write_text('{"edition":true}',encoding='utf-8')
            output.write_bytes(b'preserve invalid destination')
            command[command.index('--source')+1]=str(invalid)
            failed = subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(failed.returncode,2)
            self.assertEqual(output.read_bytes(),b'preserve invalid destination')
            self.assertNotIn('Traceback',failed.stderr)

    def test_actual_generated_cpp_full_byte_parity(self):
        generator, data = self.generator(), self.source()
        BUILD.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=BUILD) as directory:
            build = Path(directory)
            (build/'JapaneseDialogues.generated.h').write_text(generator.generate(data),encoding='utf-8')
            header_sha256 = hashlib.sha256((build/'JapaneseDialogues.generated.h').read_bytes()).hexdigest()
            (build/'parity.cpp').write_text(r'''
#include "JapaneseDialogues.generated.h"
#include <cstring>
#include <iostream>
#include <string>
#include <type_traits>
void emit(const char* s) { auto n=std::strlen(s); std::cout<<n<<':'; std::cout.write(s,n); }
void number(int n) { emit(std::to_string(n).c_str()); }
int main() {
  using namespace japanese::dialogues;
  static_assert(kCategoryCount==9 && kCardCount==270 && kMaxCardsPerCategory==30);
  static_assert(categories.size()==9 && cards.size()==270);
  static_assert(std::is_same_v<decltype(Category::first),uint16_t>);
  static_assert(categories[0].first==0 && categories[0].count==30);
  static_assert(categories[1].first==30 && categories[8].first==240 && categories[8].count==30);
  for (const auto& c:categories) { emit(c.id); number(c.first); number(c.count); }
  for (const auto& c:cards) {
    emit(c.id); number(c.category);
    for (const auto* line:{&c.a,&c.b}) {
      emit(line->japanese); emit(line->kanaReading); emit(line->romaji); emit(line->meaning);
    }
    for (const auto* note:c.grammarNotes) emit(note);
    number(c.vocabularyCardId);
  }
}
''',encoding='utf-8')
            compiled = subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror','-I',str(build),str(build/'parity.cpp'),'-o',str(build/'parity')],capture_output=True,text=True)
            self.assertEqual(compiled.returncode,0,compiled.stderr)
            result = subprocess.run([str(build/'parity')],check=True,capture_output=True).stdout
        expected=[]
        for c in data['categories']:
            expected += [c['id'],str(c['first']),str(c['count'])]
        for c in data['cards']:
            expected += [c['id'],str(c['category'])]
            for line in (c['a'],c['b']):
                expected += [line[k] for k in FIELDS]
            expected += c['grammarNotes']+[str(c['vocabularyCardId'])]
        actual, offset = [],0
        while offset<len(result):
            colon=result.index(b':',offset); length=int(result[offset:colon]); offset=colon+1
            actual.append(result[offset:offset+length]); offset+=length
        self.assertEqual(offset,len(result))
        self.assertEqual(actual,[s.encode('utf-8') for s in expected])
        report = {'categoryCount':len(data['categories']), 'cardCount':len(data['cards']),
                  'lengthPrefixedFieldsCompared':len(actual), 'streamBytes':len(result),
                  'streamSha256':hashlib.sha256(result).hexdigest(), 'temporaryHeaderSha256':header_sha256,
                  'utf8ByteExact':True, 'categoryFirstType':'uint16_t',
                  'compilerFlags':['-std=c++17','-Wall','-Wextra','-Werror']}
        (BUILD/'cpp-parity.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')

class DialoguesFontTests(unittest.TestCase):
    source = DialoguesDataTests.source

    def font_script(self):
        path=ROOT/'scripts/build_japanese_sentences_font.py'
        self.assertIn('hanmo_dialogues_20',path.read_text(encoding='utf-8'), 'Font script still uses only the six legacy sentences')
        spec=importlib.util.spec_from_file_location('dialogue_font',path)
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        return module

    def test_font_inputs_cover_both_speakers_and_preserve_legacy_28(self):
        font=self.font_script(); specs={name:(size,chars) for name,size,chars in font.font_specs()}
        self.assertEqual(set(specs),{'hanmo_sentences_28','hanmo_dialogues_20','hanmo_sentence_notes_12'})
        self.assertEqual([specs[n][0] for n in ('hanmo_sentences_28','hanmo_dialogues_20','hanmo_sentence_notes_12')],[28,20,12])
        basic=json.loads((ROOT/'data/japanese/sentences-basic.json').read_text(encoding='utf-8'))
        legacy=' �'+''.join(c['japanese']+c['kanaReading'] for c in basic['cards'])
        self.assertEqual(set(specs['hanmo_sentences_28'][1]),set(legacy))
        for card in self.source()['cards']:
            for line in (card['a'],card['b']):
                for field in FIELDS:
                    name='hanmo_dialogues_20' if field in ('japanese','kanaReading') else 'hanmo_sentence_notes_12'
                    self.assertFalse(set(line[field])-set(specs[name][1]),(card['id'],field))
                self.assertFalse(set(''.join(line.values()))-set(specs['hanmo_sentence_notes_12'][1]))
            self.assertFalse(set(''.join(card['grammarNotes']))-set(specs['hanmo_sentence_notes_12'][1]))
        for size,characters in specs.values():
            self.assertEqual(characters,''.join(sorted(set(characters))))

    def test_actual_generated_glyph_intervals_cover_all_510_lines(self):
        self.font_script()
        script=ROOT/'scripts/build_japanese_sentences_font.py'
        self.assertIn('--output-dir',script.read_text(encoding='utf-8'),'Safe temporary font output option is missing')
        configured=os.environ.get('HANMO_FONT_PYTHON')
        candidates=[configured, sys.executable]
        python=None
        for candidate in candidates:
            if candidate and Path(candidate).is_file() and subprocess.run([candidate,'-c','import freetype, fontTools'],capture_output=True).returncode==0:
                python=candidate; break
        self.assertIsNotNone(python,'No available FreeType/fontTools Python; actual font coverage cannot be skipped')
        BUILD.mkdir(parents=True,exist_ok=True)
        names=('hanmo_sentences_28','hanmo_dialogues_20','hanmo_sentence_notes_12')
        production={name:ROOT/'lib/EpdFont/builtinFonts'/f'{name}.h' for name in names}
        before={n:p.read_bytes() if p.exists() else None for n,p in production.items()}
        with tempfile.TemporaryDirectory(dir=BUILD) as directory:
            out=Path(directory)
            command=[python,str(script),'--output-dir',str(out)]
            run=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertEqual(set(p.name for p in out.iterdir()),{n+'.h' for n in names})
            first={n:(out/(n+'.h')).read_bytes() for n in names}
            covered={}; metrics={}; report={}
            for name in names:
                header=first[name].decode('utf-8')
                intervals=re.search(r'EpdUnicodeInterval '+name+r'Intervals\[\] = \{(.*?)\n\};',header,re.S)
                self.assertIsNotNone(intervals,name)
                tuples=re.findall(r'\{\s*(0x[0-9A-Fa-f]+),\s*(0x[0-9A-Fa-f]+),\s*(0x[0-9A-Fa-f]+)\s*\}',intervals.group(1))
                codepoints={}; previous=-1
                for lo,hi,base in tuples:
                    lo,hi,base=(int(s,16) for s in (lo,hi,base))
                    self.assertGreater(lo,previous); self.assertGreaterEqual(hi,lo); previous=hi
                    for cp in range(lo,hi+1): codepoints[cp]=base+cp-lo
                glyphs=re.findall(r'\{\s*(\d+),\s*(\d+),\s*(\d+),\s*(-?\d+),\s*(-?\d+),\s*(\d+),\s*(\d+)\s*\}, // ([^\n]+)',header)
                def codepoint(comment):
                    return int(comment[2:],16) if comment.startswith('U+') else ord(comment)
                actual={codepoint(row[-1]):tuple(int(x) for x in row[:-1]) for row in glyphs}
                self.assertEqual(set(actual),set(codepoints))
                for cp,index in codepoints.items():
                    self.assertLess(index,len(glyphs)); self.assertEqual(codepoint(glyphs[index][-1]),cp)
                    self.assertGreater(actual[cp][2],0)
                    if cp!=32: self.assertGreater(actual[cp][5],0)
                covered[name]=set(chr(cp) for cp in codepoints)
                metrics[name]=actual
                report[name]={'sha256':hashlib.sha256(first[name]).hexdigest(),'actualGlyphs':len(actual),'actualIntervals':len(tuples)}
            data=self.source()
            for card in data['cards']:
                for line in (card['a'],card['b']):
                    for field in FIELDS:
                        name='hanmo_dialogues_20' if field in ('japanese','kanaReading') else 'hanmo_sentence_notes_12'
                        self.assertFalse(set(line[field])-covered[name],(card['id'],field,'actual intervals'))
                    self.assertFalse(set(''.join(line.values()))-covered['hanmo_sentence_notes_12'],card['id'])
                self.assertFalse(set(''.join(card['grammarNotes']))-covered['hanmo_sentence_notes_12'],card['id'])
            self.assertFalse(set('AB:：0123456789/- ')-covered['hanmo_dialogues_20'])
            jp=[line['japanese'] for c in data['cards'] for line in (c['a'],c['b']) if line['japanese']]
            report['maxJapaneseWidthPx']=max(sum(metrics['hanmo_dialogues_20'][ord(ch)][2] for ch in text)/16 for text in jp)
            report['utterancesChecked']=len(jp)
            self.assertEqual(len(jp),510)
            # Second actual conversion must emit identical bytes, not just equal requested sets.
            repeat=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(repeat.returncode,0,repeat.stderr)
            self.assertEqual({n:(out/(n+'.h')).read_bytes() for n in names},first)
            (BUILD/'font-coverage.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        self.assertEqual({n:p.read_bytes() if p.exists() else None for n,p in production.items()},before,'Temporary tests touched production fonts')

if __name__ == '__main__':
    unittest.main()
