"""Real Home -> Apps -> NEW lessons touch QA, synthetic SD only."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import json
import os
import subprocess
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('tag')
parser.add_argument('--locales', nargs='+', default=['ZH_TW', 'ZH_CN', 'EN'], choices=['ZH_TW', 'ZH_CN', 'EN'])
parser.add_argument('--modes', nargs='+', default=['words', 'sentences'], choices=['words', 'sentences'])
args = parser.parse_args()
program = ROOT / '.pio/build/simulator_x4pro_video/program'
assert program.is_file()
out = ROOT / 'build/japanese-lessons-sim-qa' / args.tag
assert not out.exists(), 'Keep previous screenshots and logs'
out.mkdir(parents=True)


def run(case):
    mode, locale = case
    folder = out / (mode + '-' + locale)
    sd = folder / 'sd'
    (sd / '.crosspoint').mkdir(parents=True)
    settings = {'language': locale, 'onboardingVersion': 1, 'uiTheme': 4, 'homeLabel': 'HanMo',
                'homeShortcut1': 4, 'homeShortcut2': 9, 'homeShortcut3': 9, 'homeShortcut4': 9,
                'homeShortcut5': 9, 'homeShortcut6': 9, 'sleepTimeout': 0, 'hiddenAppsMask': 0,
                'infoBoardDemo': 1, 'infoBoardRotate': 0, 'infoBoardInterval': 0,
                'clockUtcOffsetQ': 44, 'wifiStatusPosition': 0}
    (sd / '.crosspoint/settings.json').write_text(json.dumps(settings, ensure_ascii=False))
    (sd / '.crosspoint/state.json').write_text(json.dumps({'showBootScreen': False}))
    events = [(2600, 'TAP:240,765'), (5300, 'TAP:100,140')]
    shots = [(7000, 'categories')]
    if mode == 'words':
        events += [(8500, 'TAP:100,414'), (11500, 'TAP:350,765'), (14500, 'TAP:240,765'),
                   (17500, 'TAP:350,765'), (20500, 'TAP:390,765')]
        shots += [(10200, 'front-01'), (13000, 'reveal-01'), (16000, 'front-02'),
                  (19000, 'reveal-02'), (22000, 'front-03')]
        at = 23500
        if locale == 'ZH_TW':
            for _ in range(43):
                events += [(at, 'TAP:350,765'), (at + 850, 'TAP:390,765')]
                at += 1900
            shots.append((at + 100, 'retry-round'))
            events += [(at + 1800, 'TAP:350,765'), (at + 4500, 'TAP:390,765'),
                       (at + 7500, 'TAP:350,765')]
            shots += [(at + 3200, 'retry-reveal'), (at + 6000, 'complete'), (at + 9000, 'restart')]
            at += 10500
        events += [(at, 'TAP:80,765'), (at + 4000, 'QUIT')]
        shots.append((at + 2000, 'returned'))
    else:
        events += [(8500, 'TAP:100,472'), (11500, 'TAP:350,646'), (14500, 'TAP:350,646')]
        shots += [(10200, 'front-01'), (13000, 'reveal-01'), (16000, 'hidden-again')]
        at = 17500
        for i in range(2, 7):
            events += [(at, 'TAP:350,715'), (at + 3000, 'TAP:350,646')]
            shots += [(at + 1400, 'front-%02d' % i), (at + 4400, 'reveal-%02d' % i)]
            at += 6000
        events += [(at, 'TAP:350,715'), (at + 3000, 'TAP:80,715'),
                   (at + 6000, 'TAP:80,646'), (at + 10000, 'QUIT')]
        shots += [(at + 1400, 'last-boundary'), (at + 4400, 'previous-hidden'), (at + 8000, 'returned')]
    environment = os.environ.copy()
    environment.update(CROSSPOINT_SIM_SD=str(sd), SDL_AUDIODRIVER='dummy', SDL_RENDER_DRIVER='software',
                       CROSSPOINT_SIM_INPUT_SCRIPT=';'.join(f'{t}:{a}' for t, a in events),
                       CROSSPOINT_SIM_SCREENSHOTS=';'.join(f'{t}:{folder}/{name}.bmp' for t, name in shots))
    with (folder / 'run.log').open('x') as log:
        subprocess.run(['xvfb-run', '-a', str(program)], cwd=folder, env=environment, stdout=log,
                       stderr=log, timeout=(events[-1][0] / 1000 + 25), check=True)
    record = []
    for _, name in shots:
        image = Image.open(folder / (name + '.bmp'))
        assert image.size == (480, 800)
        path = folder / (name + '.png')
        image.save(path)
        record.append({'name': name, 'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    log = (folder / 'run.log').read_text()
    activity = 'JapaneseWords' if mode == 'words' else 'JapaneseSentences'
    assert activity in log, (mode, locale, 'factory did not launch real activity')
    assert not (sd / '.crosspoint/kana-practice-v1.bin').exists()
    front = Image.open(folder / 'front-01.png').convert('L')
    reveal = Image.open(folder / 'reveal-01.png').convert('L')
    assert ImageChops.difference(front.crop((0, 160, 480, 730)), reveal.crop((0, 160, 480, 730))).getbbox()
    if mode == 'sentences':
        def content(name):
            return Image.open(folder / (name + '.png')).convert('L').crop((0, 130, 480, 580))
        assert content('front-01').tobytes() == content('hidden-again').tobytes()
        assert content('reveal-06').tobytes() == content('last-boundary').tobytes()
        assert len({content('front-%02d' % i).tobytes() for i in range(1, 7)}) == 6
        for i in range(1, 7):
            assert content('front-%02d' % i).tobytes() != content('reveal-%02d' % i).tobytes()
    contact = Image.new('RGB', (960, 1600), 'white')
    selected = ['front-01', 'reveal-01', 'complete' if mode == 'words' and locale == 'ZH_TW' else
                'front-02' if mode == 'words' else 'reveal-05', 'returned']
    for index, name in enumerate(selected):
        contact.paste(Image.open(folder / (name + '.png')).convert('RGB'), ((index % 2) * 480, (index // 2) * 800))
    contact.save(folder / 'contact.png')
    result = {'mode': mode, 'locale': locale, 'shots': record, 'directory': str(folder),
              'actualActivityLaunched': True, 'practiceFileCreated': False}
    (folder / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({'mode': mode, 'locale': locale, 'frames': len(record), 'contact': str(folder / 'contact.png')}), flush=True)
    return result


cases = [(mode, locale) for locale in args.locales for mode in args.modes]
with ThreadPoolExecutor(max_workers=3) as pool:
    results = list(pool.map(run, cases))
assert len(results) == len(cases)
summary = {'locales': args.locales, 'newLessonFlows': len(results), 'frameCount': sum(len(r['shots']) for r in results),
           'results': results, 'hardwareValidated': False}
(out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
print(json.dumps({k: v for k, v in summary.items() if k != 'results'}), flush=True)
