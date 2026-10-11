#!/usr/bin/env python3
"""Emit authored HanMo categorized dialogues as deterministic UTF-8 C++17."""
import json
import copy
import hashlib
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATEGORY_IDS = ('basic', 'daily', 'restaurant', 'shopping', 'transport', 'hotel', 'directions', 'social', 'emergency')
CATEGORY_COUNTS = (30, 30, 30, 30, 30, 30, 30, 30, 30)
FIELDS = ('japanese', 'kanaReading', 'romaji', 'meaning')
# Canonical, sorted-key UTF-8 SHA256 of the immutable edition-1 source.
ORIGINAL_CANONICAL_SHA256 = '513cf8667745a998832dc96718cd67b17aa21c6ffb151fe294c8ee734cc22687'


def object_fields(value, fields, label):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError(f'{label}: exact object fields required')


def string(value, label, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f'{label}: nonempty bounded string required')
    if value != value.strip() or any(unicodedata.category(c).startswith('C') for c in value):
        raise ValueError(f'{label}: controls, surrogates or edge whitespace forbidden')


def validate(data):
    original = json.loads((ROOT / 'data/japanese/sentences-basic.json').read_text(encoding='utf-8'))
    frozen = json.loads((ROOT / 'data/japanese/sentences-dialogues-v1.json').read_text(encoding='utf-8'))
    _validate(data, original, frozen)


def _validate(data, original, frozen):
    object_fields(data, ('edition', 'provenance', 'basicProvenance', 'categories', 'cards'), 'source')
    if type(data['edition']) is not int or data['edition'] != 3:
        raise ValueError('Expected edition 3')
    provenance = data['provenance']
    object_fields(provenance, ('authoredForHanMo', 'isOriginalJpfText', 'claim', 'referenceUrls'), 'provenance')
    if provenance['authoredForHanMo'] is not True or provenance['isOriginalJpfText'] is not False:
        raise ValueError('Explicit HanMo authorship / not original JPF text required')
    string(provenance['claim'], 'provenance.claim', 512)
    if 'not copied' not in provenance['claim'].lower() or provenance['referenceUrls'] != []:
        raise ValueError('New dialogues must be authored, not copied course passages')
    old_by_id = {card['id']: card for card in frozen['cards']}
    if data['provenance'] != frozen['provenance']:
        raise ValueError('Original HanMo provenance must remain unchanged')
    if data['basicProvenance'] != original['provenance']:
        raise ValueError('Basic provenance must remain unchanged')
    categories = data['categories']
    if not isinstance(categories, list) or len(categories) != 9:
        raise ValueError('Exactly nine categories required')
    first = 0
    for index, category in enumerate(categories):
        object_fields(category, ('id', 'first', 'count'), 'category')
        if (category['id'] != CATEGORY_IDS[index] or type(category['first']) is not int or
                type(category['count']) is not int or category['first'] != first or
                category['count'] != CATEGORY_COUNTS[index]):
            raise ValueError('Stable ordered category IDs and cumulative nine 30-card ranges required')
        first += category['count']
    cards = data['cards']
    if not isinstance(cards, list) or len(cards) != first:
        raise ValueError('Exactly 270 cards covering all category ranges required')
    mappings = [(category, local) for category, entry in enumerate(categories) for local in range(entry['count'])]
    seen = [set() for _ in categories]
    kana = re.compile(r'[\u3041-\u3096\u30a1-\u30faー、。]+。')
    word = r"[a-zāīūēō]+(?:'[a-zāīūēō]+)?"
    romaji = re.compile(word + r'(?:[,?.]? ' + word + r')*[.?]')
    for index, card in enumerate(cards):
        object_fields(card, ('id', 'category', 'a', 'b', 'grammarNotes', 'vocabularyCardId'), 'card')
        category, local = mappings[index]
        prefix = 'sentence' if category == 0 else CATEGORY_IDS[category]
        if card['id'] != f'{prefix}-{local + 1:02d}' or type(card['category']) is not int or card['category'] != category:
            raise ValueError('Stable unique ordered card IDs/category mappings required')
        for key in ('a', 'b'):
            line = card[key]
            object_fields(line, FIELDS, 'line')
            if category == 0 and key == 'b':
                if line != dict.fromkeys(FIELDS, ''):
                    raise ValueError('Basic B must be completely empty')
                continue
            for field in FIELDS:
                string(line[field], field, 20 if field in ('japanese', 'kanaReading') else 96)
            if not kana.fullmatch(line['japanese']) or line['kanaReading'] != line['japanese']:
                raise ValueError('Kana-only Japanese and matching kanaReading required')
            if not romaji.fullmatch(line['romaji']) or re.search(r"(?<!n)'|'(?![aeiouyāīūēō])", line['romaji']):
                raise ValueError('Lower-case Hepburn words/punctuation and n apostrophe required')
            if re.search(r'\bwo\b', line['romaji']):
                raise ValueError('Object を must be read o')
        scene = (card['a']['japanese'], card['b']['japanese'])
        if scene in seen[category]:
            raise ValueError('Basic sentences and A/B scene pairs must be unique within each category')
        seen[category].add(scene)
        notes = card['grammarNotes']
        if not isinstance(notes, list) or len(notes) != 2:
            raise ValueError('Exactly two grammar notes required')
        for note in notes:
            string(note, 'grammarNotes', 22)
        expected_vocabulary = original['cards'][local]['vocabularyCardId'] if category == 0 and local < 6 else -1
        if type(card['vocabularyCardId']) is not int or card['vocabularyCardId'] != expected_vocabulary:
            raise ValueError('Reviewed vocabulary mapping required; new scenes use -1')
        if category == 0 and local < 6:
            old = original['cards'][local]
            if (card['a'] != {field: old[field] for field in FIELDS} or card['grammarNotes'] != old['grammarNotes']):
                raise ValueError('All original six fields/notes must remain unchanged')
        if card['id'] in old_by_id and card != old_by_id[card['id']]:
            raise ValueError('All original 54 scene objects must remain unchanged by stable ID')


def assemble(original, additions):
    """Combine immutable 54 originals with nine genuinely authored 24-card arrays."""
    object_fields(original, ('edition', 'provenance', 'basicProvenance', 'categories', 'cards'), 'original')
    canonical = json.dumps(original, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    if (type(original['edition']) is not int or not isinstance(original['cards'], list) or
            not isinstance(original['categories'], list) or
            hashlib.sha256(canonical).hexdigest() != ORIGINAL_CANONICAL_SHA256):
        raise ValueError('Assembly requires the unchanged original edition 1 / 54 scenes')
    object_fields(additions, CATEGORY_IDS, 'additions')
    for cid in CATEGORY_IDS:
        if not isinstance(additions[cid], list) or len(additions[cid]) != 24:
            raise ValueError(f'{cid}: exactly 24 authored additions required')
    data = copy.deepcopy(original)
    data['edition'] = 3
    data['categories'] = []
    data['cards'] = []
    first = 0
    for category, cid in enumerate(CATEGORY_IDS):
        data['categories'].append(dict(id=cid, first=first, count=30))
        data['cards'].extend(copy.deepcopy(original['cards'][category * 6:category * 6 + 6]))
        data['cards'].extend(copy.deepcopy(additions[cid]))
        first += 30
    basic = dict(provenance=original['basicProvenance'], cards=[
        dict(card['a'], grammarNotes=card['grammarNotes'], vocabularyCardId=card['vocabularyCardId'])
        for card in original['cards'][:6]])
    _validate(data, basic, original)
    return data


def cpp_declarations():
    """Emit the actual C++ type contract without requiring any lesson fixtures."""
    return [
        '// Generated by scripts/generate_japanese_dialogues.py; do not edit.',
        '// Original HanMo dialogue text; Basic retains its original source/provenance.',
        '#pragma once', '#include <array>', '#include <cstdint>',
        'namespace japanese::dialogues {',
        'struct Line { const char *japanese, *kanaReading, *romaji, *meaning; };',
        'struct Card {', '  const char *id;', '  uint8_t category;', '  Line a, b;',
        '  std::array<const char*, 2> grammarNotes;', '  int vocabularyCardId;', '};',
        'struct Category { const char* id; uint16_t first; uint8_t count; };',
        'inline constexpr int kCategoryCount = 9;',
        'inline constexpr int kCardCount = 270;',
        'inline constexpr int kMaxCardsPerCategory = 30;',
    ]


def generate(data):
    validate(data)
    quote = lambda value: json.dumps(value, ensure_ascii=False)
    lines = cpp_declarations() + ['inline constexpr std::array<Category, kCategoryCount> categories = {{']
    for category in data['categories']:
        lines.append('  {' + quote(category['id']) + ', ' + str(category['first']) + ', ' + str(category['count']) + '},')
    lines += ['}};', 'inline constexpr std::array<Card, kCardCount> cards = {{']
    for card in data['cards']:
        a = '{' + ', '.join(quote(card['a'][k]) for k in FIELDS) + '}'
        b = '{' + ', '.join(quote(card['b'][k]) for k in FIELDS) + '}'
        notes = '{{' + ', '.join(quote(note) for note in card['grammarNotes']) + '}}'
        lines.append('  {' + ', '.join((quote(card['id']), str(card['category']), a, b, notes, str(card['vocabularyCardId']))) + '},')
    return '\n'.join(lines + ['}};', '}  // namespace japanese::dialogues', ''])


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'data/japanese/sentences-dialogues.json')
    parser.add_argument('--output', type=Path, help='Explicit output; default header, or aggregate source with --assemble')
    parser.add_argument('--assemble', action='store_true', help='Assemble original 54 plus all nine authored addition arrays; no C++ or fonts')
    parser.add_argument('--original', type=Path, default=ROOT / 'data/japanese/sentences-dialogues-v1.json')
    parser.add_argument('--additions-dir', type=Path, default=ROOT / 'data/japanese/topics30')
    parser.add_argument('--check', action='store_true', help='Fail if missing/stale; never write')
    args = parser.parse_args()
    try:
        if args.assemble:
            original = json.loads(args.original.read_text(encoding='utf-8'))
            additions = {cid: json.loads((args.additions_dir / (cid + '.json')).read_text(encoding='utf-8')) for cid in CATEGORY_IDS}
            data = assemble(original, additions)
            payload = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
            output = args.output or args.source
        else:
            payload = generate(json.loads(args.source.read_text(encoding='utf-8'))).encode('utf-8')
            output = args.output or ROOT / 'src/activities/apps/japanese/JapaneseDialogues.generated.h'
        if args.check:
            if not output.is_file() or output.read_bytes() != payload:
                parser.exit(1, 'Dialogue output is missing or stale\n')
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(payload)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print('Checked' if args.check else ('Assembled' if args.assemble else 'Generated'), '9 categories, 270 scenes, 510 utterances')


if __name__ == '__main__':
    main()
