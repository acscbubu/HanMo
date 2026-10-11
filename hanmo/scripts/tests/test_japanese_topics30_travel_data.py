"""Agent E's authored travel additions, independent language oracle, no generation.

The reviewed PSV fixtures predate their category JSONs. They are fixed authored
expectations, never populated by loading production data. This is an authored
language check, not external linguistic certification or production C++ parity.
"""
import copy
import hashlib
import json
from pathlib import Path
import re
import unicodedata
import unittest

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'data/japanese/topics30'
FIXTURES = Path(__file__).resolve().parent / 'fixtures/japanese_topics30_travel'
ORIGINAL = ROOT / 'data/japanese/sentences-dialogues-v1.json'
ORIGINAL_SHA = '33176928d6f8a48b92cfd39ac731d832f46487f37291869f7c16a85108ef8402'
CATEGORIES = {'hotel': 5, 'directions': 6, 'social': 7, 'emergency': 8}
CARD_FIELDS = {'id', 'category', 'a', 'b', 'grammarNotes', 'vocabularyCardId'}
LINE_FIELDS = {'japanese', 'kanaReading', 'romaji', 'meaning'}
KANA = re.compile(r'[ぁ-ゖァ-ヺー。、！？]+')
HEPBURN = re.compile(r"[a-zāīūēō ,.'?!-]+")
SIMPLIFIED_ONLY = set('这说请谢问间门开关车国学语见后里时点电话联络紧医药伤压绷带')


def decode_json(data):
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'duplicate JSON key: {key}')
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError(f'nonfinite JSON value: {value}')

    return json.loads(data.decode('utf-8', errors='strict'),
                      object_pairs_hook=unique_keys, parse_constant=reject_constant)


def safe_text(value, label):
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f'{label}: nonempty trimmed string required')
    if any(unicodedata.category(c).startswith('C') or (c.isspace() and c != ' ') for c in value):
        raise ValueError(f'{label}: control, invisible or separator character')
    if unicodedata.normalize('NFC', value) != value:
        raise ValueError(f'{label}: NFC required')
    value.encode('utf-8', errors='strict')


def validate_category(cards, name, original):
    """Strict independently scoped schema and pair guards for the four lists."""
    if type(cards) is not list or len(cards) != 24:
        raise ValueError('exactly 24 cards in a list required')
    category = CATEGORIES[name]
    pairs = {(c['a']['japanese'], c['b']['japanese']) for c in original['cards'] if c['category'] == category}
    for number, card in enumerate(cards, 7):
        label = f'{name}-{number:02}'
        if type(card) is not dict or set(card) != CARD_FIELDS:
            raise ValueError(f'{label}: exact card fields required')
        if card['id'] != label:
            raise ValueError(f'{label}: id or order')
        if type(card['category']) is not int or card['category'] != category:
            raise ValueError(f'{label}: category')
        if type(card['vocabularyCardId']) is not int or card['vocabularyCardId'] != -1:
            raise ValueError(f'{label}: vocabularyCardId')
        for side in ('a', 'b'):
            line = card[side]
            if type(line) is not dict or set(line) != LINE_FIELDS:
                raise ValueError(f'{label}.{side}: exact line fields required')
            for key, value in line.items():
                safe_text(value, f'{label}.{side}.{key}')
            if name == 'emergency':
                # Narrow fail-closed tripwires plus the full authored oracle;
                # this is not a general-purpose medical-content classifier.
                prohibited = ('くすり', 'ちりょう', 'ほうたい', 'あっぱく', 'こきゅう',
                              'きずをおさ', 'やけどをひや', 'しんぞうマッサージ',
                              'ひゃくじゅう', 'いちいちきゅう', 'いちいちゼロ',
                              'ゼロゼロゼロ', '服藥', '按住傷口', '心肺復甦', '胸外按壓')
                all_text = ' '.join(line.values())
                if any(token in all_text for token in prohibited) or re.search(r'[0-9０-９]', all_text):
                    raise ValueError(f'{label}.{side}: emergency policy: requests/contact only; no treatment or phone number assertions')
            if not KANA.fullmatch(line['japanese']) or len(line['japanese']) > 20:
                raise ValueError(f'{label}.{side}: kana-only at most 20 characters')
            if line['kanaReading'] != line['japanese']:
                raise ValueError(f'{label}.{side}: kanaReading')
            if not HEPBURN.fullmatch(line['romaji']) or not line['romaji'].endswith(('.', '?', '!')):
                raise ValueError(f'{label}.{side}: lower-case Hepburn')
            if not re.search(r'[\u3400-\u9fff]', line['meaning']) or SIMPLIFIED_ONLY.intersection(line['meaning']):
                raise ValueError(f'{label}.{side}: Taiwan Traditional Chinese meaning')
        notes = card['grammarNotes']
        if type(notes) is not list or len(notes) != 2:
            raise ValueError(f'{label}: exactly two notes')
        for note in notes:
            safe_text(note, f'{label}.note')
            if len(note) > 22 or not re.search(r'[\u3400-\u9fff]', note) or SIMPLIFIED_ONLY.intersection(note):
                raise ValueError(f'{label}: Traditional Chinese note at most 22 characters')
        pair = (card['a']['japanese'], card['b']['japanese'])
        if pair in pairs:
            raise ValueError(f'{label}: repeated scene pair including legacy')
        pairs.add(pair)


def read_oracle(name):
    rows = (FIXTURES / f'{name}.psv').read_text(encoding='utf-8').splitlines()
    expected, intents = [], []
    for number, row in enumerate(rows, 7):
        intent, aj, ar, am, bj, br, bm, note1, note2 = row.split('|')
        intents.append(intent)
        expected.append({'id': f'{name}-{number:02}', 'category': CATEGORIES[name],
                         'a': {'japanese': aj, 'kanaReading': aj, 'romaji': ar, 'meaning': am},
                         'b': {'japanese': bj, 'kanaReading': bj, 'romaji': br, 'meaning': bm},
                         'grammarNotes': [note1, note2], 'vocabularyCardId': -1})
    if len(expected) != 24 or len(set(intents)) != 24:
        raise ValueError('oracle requires 24 individually specified intents')
    return expected, intents


def audit_cards(cards, name, original):
    validate_category(cards, name, original)
    expected, _ = read_oracle(name)
    if cards != expected:
        raise ValueError(f'{name}: all-field authored language oracle mismatch')


class TravelDataTests(unittest.TestCase):
    def check_category(self, name):
        path = DATA / f'{name}.json'
        self.assertTrue(path.is_file(), f'missing authored category array: {path}')
        original = decode_json(ORIGINAL.read_bytes())
        try:
            cards = decode_json(path.read_bytes())
            audit_cards(cards, name, original)
        except (ValueError, UnicodeError) as error:
            self.fail(f'{name}: rejected source data: {error}')
        _, intents = read_oracle(name)
        self.assertEqual(len(intents), 24)
        return cards

    def test_hotel_24_new_scenes_schema_language_and_legacy_pair_parity(self):
        self.check_category('hotel')

    def test_directions_24_new_scenes_schema_language_and_legacy_pair_parity(self):
        self.check_category('directions')

    def test_social_24_new_scenes_schema_language_and_legacy_pair_parity(self):
        self.check_category('social')

    def test_emergency_24_new_scenes_schema_language_and_legacy_pair_parity(self):
        self.check_category('emergency')

    def test_emergency_rejects_treatment_and_unscoped_phone_numbers(self):
        original = json.loads(ORIGINAL.read_text(encoding='utf-8'))
        cards = self.check_category('emergency')
        for japanese, meaning in [('くすりをのんでください。', '請服藥。'),
                                  ('きずをおさえてください。', '請按住傷口。'),
                                  ('こきゅうをかくにんしてください。', '請確認呼吸。'),
                                  ('ひゃくじゅうばんにでんわします。', '我打110。'),
                                  ('いちいちきゅうばんによびます。', '我打119。')]:
            bad = copy.deepcopy(cards)
            bad[0]['b'].update(japanese=japanese, kanaReading=japanese, meaning=meaning)
            with self.subTest(japanese=japanese), self.assertRaisesRegex(ValueError, 'emergency policy'):
                validate_category(bad, 'emergency', original)

    def test_json_decoder_rejects_duplicate_keys_and_nonfinite_values(self):
        for payload in (b'{"id":"hotel-07","id":"hotel-08"}', b'{"a":{"meaning":"a","meaning":"b"}}', b'[NaN]', b'[Infinity]', b'[-Infinity]'):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                decode_json(payload)

    def test_original54_bytes_identifiers_and_categories_unchanged(self):
        raw = ORIGINAL.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), ORIGINAL_SHA)
        old = decode_json(raw)
        self.assertEqual(old['edition'], 1)
        names = ['basic', 'daily', 'restaurant', 'shopping', 'transport', 'hotel', 'directions', 'social', 'emergency']
        self.assertEqual(old['categories'], [{'id': n, 'first': c * 6, 'count': 6} for c, n in enumerate(names)])
        self.assertEqual(len(old['cards']), 54)
        for c, name in enumerate(names):
            prefix = 'sentence' if c == 0 else name
            for n in range(1, 7):
                card = old['cards'][c * 6 + n - 1]
                self.assertEqual(card['id'], f'{prefix}-{n:02}')
                self.assertEqual(card['category'], c)

    def test_scoped_four_categories_each30_without_touching_aggregate(self):
        old = decode_json(ORIGINAL.read_bytes())
        scenes, utterances, all_ids = 0, 0, []
        for name, category in CATEGORIES.items():
            legacy = [c for c in old['cards'] if c['category'] == category]
            additions = self.check_category(name)
            merged = legacy + additions
            self.assertEqual(len(merged), 30)
            self.assertEqual([c['id'] for c in merged], [f'{name}-{n:02}' for n in range(1, 31)])
            self.assertEqual(merged[:6], legacy)
            self.assertEqual(len({(c['a']['japanese'], c['b']['japanese']) for c in merged}), 30)
            scenes += len(merged)
            utterances += sum(bool(c[s]['japanese']) for c in merged for s in ('a', 'b'))
            all_ids.extend(c['id'] for c in merged)
        self.assertEqual(scenes, 120)  # Scoped travel four, not all 270 categories.
        self.assertEqual(utterances, 240)
        self.assertEqual(len(set(all_ids)), 120)

    def test_rejects_wrong_list_shape_and_count(self):
        original = decode_json(ORIGINAL.read_bytes())
        cards = self.check_category('hotel')
        for bad in ({'cards': cards}, tuple(cards), None, cards[:-1], cards + [cards[0]], []):
            with self.subTest(shape=type(bad).__name__), self.assertRaisesRegex(ValueError, '24 cards'):
                validate_category(bad, 'hotel', original)

    def test_rejects_wrong_card_keys_and_card_types(self):
        original = decode_json(ORIGINAL.read_bytes())
        cards = self.check_category('hotel')
        edits = []
        for key in sorted(CARD_FIELDS):
            bad = copy.deepcopy(cards); del bad[0][key]; edits.append(bad)
        bad = copy.deepcopy(cards); bad[0]['extra'] = 1; edits.append(bad)
        for value in (None, [], 'hotel-07'):
            bad = copy.deepcopy(cards); bad[0] = value; edits.append(bad)
        for i, bad in enumerate(edits):
            with self.subTest(edit=i), self.assertRaisesRegex(ValueError, 'card fields'):
                validate_category(bad, 'hotel', original)

    def test_rejects_wrong_line_keys_and_line_types(self):
        original = decode_json(ORIGINAL.read_bytes())
        cards = self.check_category('hotel')
        for side in ('a', 'b'):
            edits = []
            for key in sorted(LINE_FIELDS):
                bad = copy.deepcopy(cards); del bad[0][side][key]; edits.append(bad)
            bad = copy.deepcopy(cards); bad[0][side]['extra'] = ''; edits.append(bad)
            for value in (None, [], 'kana'):
                bad = copy.deepcopy(cards); bad[0][side] = value; edits.append(bad)
            for i, bad in enumerate(edits):
                with self.subTest(side=side, edit=i), self.assertRaisesRegex(ValueError, 'line fields'):
                    validate_category(bad, 'hotel', original)

    def test_rejects_id_range_prefix_order_and_duplicates(self):
        original = decode_json(ORIGINAL.read_bytes())
        cards = self.check_category('hotel')
        for value in ('hotel-06', 'hotel-31', 'hotel-7', 'social-07', 'hotel-07 ', '', 7, None):
            bad = copy.deepcopy(cards); bad[0]['id'] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'id or order'):
                validate_category(bad, 'hotel', original)
        for i in (1, 23):
            bad = copy.deepcopy(cards); bad[i]['id'] = cards[0]['id']
            with self.subTest(duplicate_at=i), self.assertRaises(ValueError):
                validate_category(bad, 'hotel', original)
        bad = copy.deepcopy(cards); bad[0], bad[-1] = bad[-1], bad[0]
        with self.assertRaises(ValueError):
            validate_category(bad, 'hotel', original)

    def test_rejects_category_and_vocabulary_wrong_types_or_bounds(self):
        original = decode_json(ORIGINAL.read_bytes())
        cards = self.check_category('hotel')
        for key, values in [('category', [False, True, 5.0, '5', None, -1, 4, 9]),
                            ('vocabularyCardId', [False, True, -1.0, '-1', None, -2, 0, 45])]:
            for value in values:
                bad = copy.deepcopy(cards); bad[0][key] = value
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, key):
                    validate_category(bad, 'hotel', original)

    def test_rejects_kanji_ascii_symbols_and_overlength_japanese(self):
        original = decode_json(ORIGINAL.read_bytes())
        cards = self.check_category('hotel')
        for side in ('a', 'b'):
            for value in ('ホテルは駅です。', 'hotel', 'あ' * 21, 'ありがとう🙂。', 'あ り。'):
                bad = copy.deepcopy(cards); bad[0][side].update(japanese=value, kanaReading=value)
                with self.subTest(side=side, value=value), self.assertRaisesRegex(ValueError, 'kana-only'):
                    validate_category(bad, 'hotel', original)

    def test_rejects_reading_mismatch_and_all_empty_or_nonstring_lines(self):
        original = decode_json(ORIGINAL.read_bytes())
        cards = self.check_category('hotel')
        for side in ('a', 'b'):
            bad = copy.deepcopy(cards); bad[0][side]['kanaReading'] = 'ちがいます。'
            with self.subTest(side=side), self.assertRaisesRegex(ValueError, 'kanaReading'):
                validate_category(bad, 'hotel', original)
            for key in sorted(LINE_FIELDS):
                for value in ('', None, 0, False, []):
                    bad = copy.deepcopy(cards); bad[0][side][key] = value
                    with self.subTest(side=side, key=key, value=value), self.assertRaisesRegex(ValueError, 'string'):
                        validate_category(bad, 'hotel', original)

    def test_rejects_non_hepburn_format(self):
        original = decode_json(ORIGINAL.read_bytes())
        cards = self.check_category('hotel')
        for value in ('HAI.', 'hai1.', 'はい。', 'hai', 'hai; desu.', 'hai_ desu.'):
            bad = copy.deepcopy(cards); bad[0]['b']['romaji'] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'Hepburn'):
                validate_category(bad, 'hotel', original)

    def test_language_oracle_rejects_particle_wo_ha_he_and_missing_apostrophe(self):
        original = decode_json(ORIGINAL.read_bytes())
        cases = [('hotel', 0, 'a', ' o ', ' wo '),
                 ('hotel', 1, 'a', ' wa?', ' ha?'),
                 ('directions', 13, 'b', ' e ', ' he '),
                 ('hotel', 3, 'a', "kin'en", 'kinen'),
                 ('hotel', 5, 'a', "kon'ya", 'konya')]
        for name, position, side, before, after in cases:
            bad = self.check_category(name)
            self.assertIn(before, bad[position][side]['romaji'])
            bad[position][side]['romaji'] = bad[position][side]['romaji'].replace(before, after)
            validate_category(bad, name, original)  # Otherwise schema-valid.
            with self.subTest(name=name, position=position), self.assertRaisesRegex(ValueError, 'language oracle'):
                audit_cards(bad, name, original)

    def test_rejects_nontraditional_or_nonchinese_meanings(self):
        original = decode_json(ORIGINAL.read_bytes())
        cards = self.check_category('hotel')
        for value in ('hello.', '请给我房间。', '这是什么？', '電話在这里。'):
            bad = copy.deepcopy(cards); bad[0]['a']['meaning'] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'Traditional Chinese'):
                validate_category(bad, 'hotel', original)

    def test_rejects_note_count_type_length_and_language(self):
        original = decode_json(ORIGINAL.read_bytes())
        cards = self.check_category('hotel')
        for value in (None, {}, tuple(cards[0]['grammarNotes']), [], ['表示請求。'], ['表示請求。'] * 3,
                      ['說' * 23, '表示請求。'], ['note.', '表示請求。'], ['请表示请求。', '表示請求。'],
                      [None, '表示請求。'], ['', '表示請求。']):
            bad = copy.deepcopy(cards); bad[0]['grammarNotes'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_category(bad, 'hotel', original)

    def test_rejects_controls_in_every_utterance_field_and_both_notes(self):
        original = decode_json(ORIGINAL.read_bytes())
        cards = self.check_category('hotel')
        controls = ('\x00', '\n', '\r', '\t', '\u200b', '\u202e', '\ufeff', '\u2028', '\u2029')
        for control in controls:
            for side in ('a', 'b'):
                for key in sorted(LINE_FIELDS):
                    bad = copy.deepcopy(cards)
                    value = bad[0][side][key]
                    bad[0][side][key] = value[:1] + control + value[1:]
                    with self.subTest(control=repr(control), side=side, key=key), self.assertRaises(ValueError):
                        validate_category(bad, 'hotel', original)
            for i in (0, 1):
                bad = copy.deepcopy(cards); bad[0]['grammarNotes'][i] = '表示' + control + '請求。'
                with self.subTest(control=repr(control), note=i), self.assertRaises(ValueError):
                    validate_category(bad, 'hotel', original)

    def test_rejects_non_nfc_romaji_and_invalid_utf8(self):
        original = decode_json(ORIGINAL.read_bytes())
        bad = self.check_category('hotel')
        bad[0]['b']['romaji'] = 'do\u0304zo.'
        with self.assertRaisesRegex(ValueError, 'NFC'):
            validate_category(bad, 'hotel', original)
        for value in (b'\xff', b'["\xed\xa0\x80"]', b'["\xc0\xaf"]'):
            with self.subTest(value=value), self.assertRaises(UnicodeError):
                decode_json(value)

    def test_rejects_repeated_scene_pairs_new_and_legacy(self):
        original = decode_json(ORIGINAL.read_bytes())
        for name, category in CATEGORIES.items():
            cards = self.check_category(name)
            old_card = next(c for c in original['cards'] if c['category'] == category)
            for source, target in ((cards[0], 1), (old_card, 0)):
                bad = copy.deepcopy(cards)
                for side in ('a', 'b'):
                    bad[target][side] = copy.deepcopy(source[side])
                with self.subTest(name=name, target=target), self.assertRaisesRegex(ValueError, 'repeated scene pair'):
                    validate_category(bad, name, original)

    def test_allows_natural_repeated_b_acknowledgments(self):
        original = decode_json(ORIGINAL.read_bytes())
        cards = self.check_category('social')
        for key in ('japanese', 'kanaReading', 'romaji'):
            self.assertEqual(cards[11]['b'][key], cards[18]['b'][key])  # Contextual gloss may differ.
        bad = copy.deepcopy(cards); bad[0]['b'] = copy.deepcopy(cards[11]['b'])
        validate_category(bad, 'social', original)

    def test_authored_allfield_oracle_detects_schema_valid_language_edits(self):
        original = decode_json(ORIGINAL.read_bytes())
        for name in CATEGORIES:
            cards = self.check_category(name)
            for index in range(24):
                for side in ('a', 'b'):
                    for key, value in [('japanese', 'そうです。'), ('romaji', 'sō desu.'), ('meaning', '內容不同。')]:
                        bad = copy.deepcopy(cards); bad[index][side][key] = value
                        if key == 'japanese':
                            bad[index][side]['kanaReading'] = value
                        with self.subTest(name=name, index=index, side=side, key=key), self.assertRaises(ValueError):
                            audit_cards(bad, name, original)
                for note_index in (0, 1):
                    bad = copy.deepcopy(cards); bad[index]['grammarNotes'][note_index] = '說明不同。'
                    with self.subTest(name=name, index=index, note=note_index), self.assertRaisesRegex(ValueError, 'language oracle'):
                        audit_cards(bad, name, original)

    def test_oracle_has_exactly24_distinct_reviewed_intents_per_category(self):
        for name in CATEGORIES:
            expected, intents = read_oracle(name)
            self.assertEqual(len(expected), 24)
            self.assertEqual(len(set(intents)), 24)
            self.assertTrue(all(re.fullmatch(r'[a-z]+(?:-[a-z]+)*', intent) for intent in intents))

    def test_rejects_internal_unicode_line_separators(self):
        original = json.loads(ORIGINAL.read_text(encoding='utf-8'))
        cards = self.check_category('hotel')
        for separator in ('\u2028', '\u2029'):
            bad = copy.deepcopy(cards)
            bad[0]['a']['meaning'] = '我' + separator + '想寄放行李。'
            with self.subTest(separator=repr(separator)), self.assertRaisesRegex(ValueError, 'control|invisible|separator'):
                validate_category(bad, 'hotel', original)


if __name__ == '__main__':
    unittest.main()
