"""Real 480x800 simulator touch QA for long 50-sound card readings."""
from pathlib import Path
import json, os, subprocess, sys
from PIL import Image, ImageChops

root = Path(__file__).resolve().parents[1]
program = root / '.pio/build/simulator_x4pro_video/program'
assert program.is_file(), program
locale = sys.argv[1] if len(sys.argv) > 1 else 'ZH_TW'
assert locale in ('ZH_TW', 'ZH_CN', 'EN')
run = root / 'build/kana-sound-hint-qa' / locale
sd = run / 'sd'
(sd / '.crosspoint').mkdir(parents=True, exist_ok=True)
settings = {'language': locale, 'onboardingVersion': 1, 'uiTheme': 4,
            'homeLabel': 'HanMo', 'homeShortcut1': 4,
            'homeShortcut2': 9, 'homeShortcut3': 9, 'homeShortcut4': 9,
            'homeShortcut5': 9, 'homeShortcut6': 9, 'sleepTimeout': 0,
            'hiddenAppsMask': 0, 'infoBoardDemo': 1, 'infoBoardRotate': 0,
            'infoBoardInterval': 0, 'clockUtcOffsetQ': 92, 'wifiStatusPosition': 0}
(sd / '.crosspoint/settings.json').write_text(json.dumps(settings, ensure_ascii=False))
(sd / '.crosspoint/state.json').write_text(json.dumps({'showBootScreen': False}))
events = [(2600, 'TAP:240,765'), (5300, 'TAP:100,140'), (8500, 'TAP:100,247')]
events += [(12000 + 1800 * i, 'TAP:390,765') for i in range(36)]
events += [(78000, 'TAP:350,125'), (80500, 'QUIT')]
shots = [(10500, 'a-sound'), (16800, 'e-parenthesized'),
         (76300, 'yu-parenthesized'), (79600, 'yu-katakana')]
env = os.environ.copy()
env.update(CROSSPOINT_SIM_SD=str(sd), SDL_AUDIODRIVER='dummy', SDL_RENDER_DRIVER='software',
           CROSSPOINT_SIM_INPUT_SCRIPT=';'.join(f'{t}:{action}' for t, action in events),
           CROSSPOINT_SIM_SCREENSHOTS=';'.join(f'{t}:{run}/{name}.bmp' for t, name in shots))
with (run / 'run.log').open('w') as log:
    subprocess.run(['xvfb-run', '-a', str(program.resolve())], cwd=run,
                   env=env, stdout=log, stderr=log, timeout=110, check=True)
images = []
for _, name in shots:
    pic = Image.open(run / (name + '.bmp'))
    assert pic.size == (480, 800), (name, pic.size)
    pic.save(run / (name + '.png'))
    images.append(pic.convert('L'))
assert all(ImageChops.difference(a, b).getbbox() for a, b in zip(images, images[1:]))
assert not (sd / '.crosspoint/kana-practice-v1.bin').exists()
print(json.dumps({'locale': locale, 'out': str(run), 'shots': [name for _, name in shots],
                  'practice_file_created': False}, ensure_ascii=False))
