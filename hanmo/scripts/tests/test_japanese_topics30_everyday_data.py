"""Agent D's authored additions: independent literal oracle, no generator dependency."""
import copy
import hashlib
import json
from pathlib import Path
import re
import unicodedata
import unittest

ROOT = Path(__file__).resolve().parents[2]
ORACLE = Path(__file__).parent / 'fixtures/japanese_topics30_everyday_oracle.tsv'
CATEGORY_IDS = {'daily': 1, 'restaurant': 2, 'shopping': 3, 'transport': 4}


def expected_cards(category):
    result = []
    for row in ORACLE.read_text(encoding='utf-8').splitlines():
        if not row or row.startswith('#'):
            continue
        ident, aj, ar, am, bj, br, bm, n1, n2 = row.split('|')
        if not ident.startswith(category + '-'):
            continue
        result.append({'id': ident, 'category': CATEGORY_IDS[category],
                       'a': {'japanese': aj, 'kanaReading': aj, 'romaji': ar, 'meaning': am},
                       'b': {'japanese': bj, 'kanaReading': bj, 'romaji': br, 'meaning': bm},
                       'grammarNotes': [n1, n2], 'vocabularyCardId': -1})
    return result


def validate_cards(cards, category):
    """Test-only contract checker; no production generator or sibling imports."""
    if type(cards) is not list or len(cards) != 24:
        raise ValueError('additions must be a list of exactly 24 cards')
    card_keys = {'id', 'category', 'a', 'b', 'grammarNotes', 'vocabularyCardId'}
    line_keys = {'japanese', 'kanaReading', 'romaji', 'meaning'}
    for index, card in enumerate(cards, 7):
        if type(card) is not dict or set(card) != card_keys:
            raise ValueError('card schema drift')
        if (category not in CATEGORY_IDS or card['id'] != f'{category}-{index:02d}'
                or type(card['category']) is not int or card['category'] != CATEGORY_IDS[category]
                or type(card['vocabularyCardId']) is not int or card['vocabularyCardId'] != -1):
            raise ValueError('card identity, category, order or vocabulary ID invalid')
        for side in ['a', 'b']:
            line = card[side]
            if type(line) is not dict or set(line) != line_keys:
                raise ValueError('line schema drift')
            for value in line.values():
                if (type(value) is not str or not value.strip()
                        or any(unicodedata.category(ch)[0] == 'C' or ch in '\u2028\u2029' for ch in value)):
                    raise ValueError('unsafe, empty or non-string lesson text')
            if (len(line['japanese']) > 20
                    or not re.fullmatch(r'[ぁ-ゖァ-ヺー。、！？]+', line['japanese'])
                    or line['kanaReading'] != line['japanese']):
                raise ValueError('kana-only text, equal reading and <=20 required')
            if not re.fullmatch(r"[a-zāēīōū ,.?!'\-]+", line['romaji']):
                raise ValueError('lower-case Hepburn text required')
        notes = card['grammarNotes']
        if (type(notes) is not list or len(notes) != 2
                or any(type(note) is not str or not note.strip() or len(note) > 22
                       or any(unicodedata.category(ch)[0] == 'C' for ch in note) for note in notes)):
            raise ValueError('exactly 2 safe string notes of <=22 characters required')
    originals = json.loads((ROOT / 'data/japanese/sentences-dialogues-v1.json').read_text(encoding='utf-8'))
    seen = {(c['a']['japanese'], c['b']['japanese']) for c in originals['cards']
            if c['category'] == CATEGORY_IDS[category]}
    for card in cards:
        pair = (card['a']['japanese'], card['b']['japanese'])
        if pair in seen:
            raise ValueError('duplicate scene pair: ' + card['id'])
        seen.add(pair)
    return cards


def validate_language_oracle(cards, category):
    expected = expected_cards(category)
    if len(cards) != len(expected):
        raise ValueError('oracle card count mismatch')
    for actual, wanted in zip(cards, expected):
        for side in ['a', 'b']:
            for field in ['japanese', 'kanaReading', 'romaji', 'meaning']:
                if actual[side][field] != wanted[side][field]:
                    raise ValueError(f"{wanted['id']}.{side}.{field}: language oracle mismatch")
        for field in ['id', 'category', 'grammarNotes', 'vocabularyCardId']:
            if actual[field] != wanted[field]:
                raise ValueError(f"{wanted['id']}.{field}: language oracle mismatch")
    return cards


def parse_strict_json(raw):
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result

    def nonfinite(value):
        raise ValueError('non-finite JSON number: ' + value)

    return json.loads(raw.decode('utf-8', errors='strict'),
                      object_pairs_hook=object_pairs, parse_constant=nonfinite)


def validate_original_bytes(raw):
    baseline = '33176928d6f8a48b92cfd39ac731d832f46487f37291869f7c16a85108ef8402'
    if hashlib.sha256(raw).hexdigest() != baseline:
        raise ValueError('original54 immutable byte snapshot changed')
    return raw


class EverydayDataTests(unittest.TestCase):
    def test_all_authored_fields_have_exact_utf8_oracle_parity(self):
        # The literal TSV and production JSON are separate inputs, not generator outputs.
        for category in CATEGORY_IDS:
            actual = parse_strict_json((ROOT / 'data/japanese/topics30' / (category + '.json')).read_bytes())
            expected = expected_cards(category)
            self.assertEqual(len(actual), 24)
            for card, wanted in zip(actual, expected):
                self.assertEqual(card['id'].encode('utf-8'), wanted['id'].encode('utf-8'))
                self.assertIs(type(card['category']), int)
                self.assertEqual(card['category'], wanted['category'])
                self.assertIs(type(card['vocabularyCardId']), int)
                self.assertEqual(card['vocabularyCardId'], wanted['vocabularyCardId'])
                self.assertEqual(len(card['grammarNotes']), 2)
                for side in ['a', 'b']:
                    for field in ['japanese', 'kanaReading', 'romaji', 'meaning']:
                        with self.subTest(id=card['id'], side=side, field=field):
                            self.assertEqual(card[side][field].encode('utf-8'),
                                             wanted[side][field].encode('utf-8'))
                for note, wanted_note in zip(card['grammarNotes'], wanted['grammarNotes']):
                    self.assertEqual(note.encode('utf-8'), wanted_note.encode('utf-8'))

    def test_rejects_ambiguous_or_invalid_utf8_json(self):
        for raw in [b'{"id": 1, "id": 2}', b'[NaN]', b'[Infinity]', b'[]\xff', b'\xef\xbb\xbf[]', b'[', b'"\x00"']:
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    parse_strict_json(raw)

    def test_rejects_any_original54_byte_drift(self):
        raw = (ROOT / 'data/japanese/sentences-dialogues-v1.json').read_bytes()
        validate_original_bytes(raw)
        for invalid in [raw + b' ', raw.replace(b'"edition": 1', b'"edition": 2'), raw[:-1]]:
            with self.assertRaisesRegex(ValueError, 'original54'):
                validate_original_bytes(invalid)

    def test_rejects_hepburn_particle_apostrophe_or_reading_drift(self):
        cases = [('daily', 6, 'a', 'eakon ha samukunai desu ka?'),
                 ('daily', 1, 'a', 'asagohan wo tabemasu ka?'),
                 ('restaurant', 2, 'b', 'hai, kochira he dōzo.'),
                 ('restaurant', 3, 'a', 'koko wa kinen desu ka?'),
                 ('daily', 0, 'a', 'mo okimashita ka?'),
                 ('daily', 21, 'a', 'kite o kudasai.'),
                 ('transport', 11, 'b', 'hai, jūpun okurete imasu.')]
        for category, index, side, bad_romaji in cases:
            payload = expected_cards(category)
            payload[index][side]['romaji'] = bad_romaji
            with self.subTest(category=category, id=payload[index]['id'], side=side):
                with self.assertRaisesRegex(ValueError, 'romaji'):
                    validate_language_oracle(payload, category)

    def test_rejects_duplicate_pairs_in_new_and_original_scenes(self):
        original = json.loads((ROOT / 'data/japanese/sentences-dialogues-v1.json').read_text(encoding='utf-8'))
        for category, number in CATEGORY_IDS.items():
            valid = expected_cards(category)
            sources = [valid[0]] + [c for c in original['cards'] if c['category'] == number]
            for source in sources:
                payload = copy.deepcopy(valid)
                for side in ['a', 'b']:
                    payload[-1][side] = copy.deepcopy(source[side])
                with self.subTest(category=category, duplicate=source['id']):
                    with self.assertRaisesRegex(ValueError, 'duplicate scene pair'):
                        validate_cards(payload, category)
            payload = copy.deepcopy(valid)
            payload[1]['b'] = copy.deepcopy(payload[0]['b'])
            validate_cards(payload, category)  # Natural conventional B repeats are allowed.

    def test_rejects_unsafe_or_unreadable_lesson_text(self):
        valid = expected_cards('daily')
        changes = []
        for side in ['a', 'b']:
            for field in ['japanese', 'kanaReading', 'romaji', 'meaning']:
                for value in [None, 0, '', ' ', valid[0][side][field] + '\x00',
                              valid[0][side][field] + '\n', valid[0][side][field] + '\u200b', '\ud800']:
                    changes.append((side, field, value))
            changes += [(side, 'japanese', 'あ' * 21), (side, 'japanese', '漢字。'),
                        (side, 'japanese', 'hello'), (side, 'kanaReading', 'ちがいます。'),
                        (side, 'romaji', 'HAI.'), (side, 'romaji', 'はい。')]
        for side, field, value in changes:
            payload = copy.deepcopy(valid)
            payload[0][side][field] = value
            with self.subTest(side=side, field=field, value=repr(value)):
                with self.assertRaisesRegex(ValueError, 'text'):
                    validate_cards(payload, 'daily')
        for notes in [None, '提示', [], ['提示'], ['提示'] * 3, [1, '提示'],
                      ['', '提示'], ['あ' * 23, '提示'], ['提示\t', '提示']]:
            payload = copy.deepcopy(valid)
            payload[0]['grammarNotes'] = notes
            with self.subTest(notes=notes):
                with self.assertRaisesRegex(ValueError, 'notes'):
                    validate_cards(payload, 'daily')

    def test_rejects_wrong_identity_order_or_numeric_types(self):
        for category in CATEGORY_IDS:
            valid = expected_cards(category)
            mutations = [('id', category + '-06'), ('id', category + '-31'),
                         ('id', category + '-7'), ('id', 'daily-07 '), ('id', None),
                         ('category', -1), ('category', 9), ('category', True),
                         ('category', float(CATEGORY_IDS[category])),
                         ('vocabularyCardId', 0), ('vocabularyCardId', -1.0),
                         ('vocabularyCardId', False)]
            for field, value in mutations:
                payload = copy.deepcopy(valid)
                payload[0][field] = value
                with self.subTest(category=category, field=field, value=value):
                    with self.assertRaisesRegex(ValueError, 'identity'):
                        validate_cards(payload, category)
            payload = copy.deepcopy(valid)
            payload[0], payload[1] = payload[1], payload[0]
            with self.assertRaisesRegex(ValueError, 'identity'):
                validate_cards(payload, category)

    def test_rejects_card_or_line_schema_drift(self):
        valid = expected_cards('daily')
        bad_cards = [None, [], {**valid[0], 'extra': 1}]
        bad_cards += [{k: v for k, v in valid[0].items() if k != key} for key in valid[0]]
        for bad in bad_cards:
            payload = copy.deepcopy(valid)
            payload[0] = bad
            with self.subTest(card=bad):
                with self.assertRaisesRegex(ValueError, 'card schema'):
                    validate_cards(payload, 'daily')
        for side in ['a', 'b']:
            bad_lines = [None, [], {**valid[0][side], 'extra': ''}]
            bad_lines += [{k: v for k, v in valid[0][side].items() if k != key} for key in valid[0][side]]
            for bad in bad_lines:
                payload = copy.deepcopy(valid)
                payload[0][side] = bad
                with self.subTest(side=side, line=bad):
                    with self.assertRaisesRegex(ValueError, 'line schema'):
                        validate_cards(payload, 'daily')

    def test_rejects_non_list_or_non_24_additions(self):
        valid = expected_cards('daily')
        for invalid in [None, {}, tuple(valid), [], valid[:-1], valid + [valid[0]]]:
            with self.subTest(payload_type=type(invalid).__name__):
                with self.assertRaisesRegex(ValueError, 'exactly 24'):
                    validate_cards(invalid, 'daily')

    def assert_category(self, category):
        path = ROOT / 'data/japanese/topics30' / (category + '.json')
        self.assertTrue(path.is_file(), 'missing authored category: ' + category)
        actual = parse_strict_json(path.read_bytes())
        expected = expected_cards(category)
        self.assertEqual(len(expected), 24)
        validate_cards(actual, category)
        validate_language_oracle(actual, category)
        self.assertEqual(actual, expected)

    def test_daily_all_fields_match_independent_language_oracle(self):
        self.assert_category('daily')

    def test_restaurant_all_fields_match_independent_language_oracle(self):
        self.assert_category('restaurant')

    def test_shopping_all_fields_match_independent_language_oracle(self):
        self.assert_category('shopping')

    def test_transport_all_fields_match_independent_language_oracle(self):
        self.assert_category('transport')


if __name__ == '__main__':
    unittest.main()
