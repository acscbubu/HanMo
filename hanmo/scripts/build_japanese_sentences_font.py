#!/usr/bin/env python3
"""Build licensed Maruko subsets for authored categorized HanMo dialogues.

Keep the original six-sentence 28pt subset; new dialogue text uses 20pt.
Mixed kana / Taiwan meanings / Hepburn / grammar notes share the 12pt subset.
Never regenerate word, kana, stroke or reader fonts here.
"""
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def font_specs(root=ROOT):
    basic = json.loads((root / 'data/japanese/sentences-basic.json').read_text(encoding='utf-8'))['cards']
    dialogues = json.loads((root / 'data/japanese/sentences-dialogues.json').read_text(encoding='utf-8'))['cards']
    kana = json.loads((root / 'data/japanese/kana-basic.json').read_text(encoding='utf-8'))['cards']
    if len(basic) != 6 or len(dialogues) != 270:
        raise ValueError('Expected original six sentences and 270 authored scenes / nine categories of 30')
    legacy = ' �' + ''.join(card['japanese'] + card['kanaReading'] for card in basic)
    primary = ' AB:：0123456789/- �'
    notes = "0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:.,!?/'()- �："
    for card in dialogues:
        for key in ('a', 'b'):
            line = card[key]
            primary += line['japanese'] + line['kanaReading']
            notes += ''.join(line[field] for field in ('japanese', 'kanaReading', 'romaji', 'meaning'))
        notes += ''.join(card['grammarNotes'])
        index = card['vocabularyCardId']
        if index >= 0:
            notes += ''.join(kana[index][3:6])
    return [(name, size, ''.join(sorted(set(characters)))) for name, size, characters in (
        ('hanmo_sentences_28', 28, legacy),
        ('hanmo_dialogues_20', 20, primary),
        ('hanmo_sentence_notes_12', 12, notes),
    )]


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'lib/EpdFont/builtinFonts',
                        help='Use a build/test directory to avoid touching production outputs')
    args = parser.parse_args()
    font = ROOT / 'lib/EpdFont/builtinFonts/source/HanMoKana/MarukoGothicCJKjp-Medium.ttf'
    specs = font_specs()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, size, characters in specs:
        out = args.output_dir / (name + '.h')
        temporary = out.with_suffix('.tmp')
        try:
            with temporary.open('w', encoding='utf-8') as stream:
                subprocess.run([sys.executable, str(ROOT / 'lib/EpdFont/scripts/fontconvert.py'),
                                name, str(size), str(font), '--mono', '--characters', characters],
                               check=True, stdout=stream)
            temporary.replace(out)
        finally:
            temporary.unlink(missing_ok=True)
        print('Generated', name, 'requested characters', len(characters))


if __name__ == '__main__':
    main()
