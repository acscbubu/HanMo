"""Generate only the licensed Japanese word-card font; basic kana fonts stay untouched."""
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
cards = json.loads((ROOT / 'data/japanese/kana-basic.json').read_text(encoding='utf-8'))['cards']
assert len(cards) == 46
# Card44 is a sentence, not vocabulary. Never duplicate or invent a word reading.
characters = ''.join(card[3] for index, card in enumerate(cards) if index != 44) + ' �'
font = ROOT / 'lib/EpdFont/builtinFonts/source/HanMoKana/MarukoGothicCJKjp-Medium.ttf'
out = ROOT / 'lib/EpdFont/builtinFonts/hanmo_words_44.h'
temporary = out.with_suffix('.tmp')
with temporary.open('w', encoding='utf-8') as stream:
    subprocess.run([sys.executable, str(ROOT / 'lib/EpdFont/scripts/fontconvert.py'),
                    'hanmo_words_44', '44', str(font), '--mono', '--characters', characters],
                   check=True, stdout=stream)
temporary.replace(out)
