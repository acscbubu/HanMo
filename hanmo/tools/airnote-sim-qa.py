"""Capture the isolated AirNote multiline editor in the 480x800 simulator."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/airnote-multiline-sim-qa'
OUT.mkdir(parents=True, exist_ok=True)
subprocess.run([sys.executable, str(ROOT / 'tools/video_simulator/seed.py'), 'zh'], check=True)
sd = ROOT / 'build/video/zh/sd'
# The public video seed stores raw TXT; device-created notes use title+blank+body.
(sd / 'AirNote/閱讀筆記.txt').write_text('閱讀筆記\n\n第一行：今天的想法\n第二行：可以換行記錄\n第三行：之後還能編輯\n', encoding='utf-8')
events = [(3000, 'TAP:120,770'), (6500, 'TAP:130,245'), (12500, 'QUIT')]
shots = [(5200, 'list'), (10000, 'multiline-editor')]
env = os.environ.copy()
env.update(CROSSPOINT_SIM_SD=str(sd), SDL_AUDIODRIVER='dummy', SDL_RENDER_DRIVER='software',
           SDL_VIDEO_WINDOW_POS='0,0', CROSSPOINT_SIM_INPUT_SCRIPT=';'.join(f'{t}:{action}' for t, action in events),
           CROSSPOINT_SIM_SCREENSHOTS=';'.join(f'{t}:{OUT}/{name}.bmp' for t, name in shots))
with (OUT / 'simulator.log').open('w') as log:
    result = subprocess.run(['xvfb-run', '-a', str(ROOT / '.pio/build/simulator_x4pro_video/program')],
                            cwd=OUT, env=env, stdout=log, stderr=log, timeout=40)
if result.returncode:
    raise RuntimeError(f'Simulator failed ({result.returncode}); see {OUT / "simulator.log"}')
for _, name in shots:
    original = OUT / f'{name}.bmp'
    if not original.is_file():
        raise RuntimeError(f'No simulator screenshot: {original}')
    target = OUT / f'{name}.png'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(original), str(target)], check=True)
    print(target, 'bytes', target.stat().st_size)

# Drive the complete new-note path through real simulator touch coordinates.
# Title "a"; body "q", newline, "w". Inspect the SD bytes after Save.
created = sd / 'AirNote/a.txt'
if created.exists():
    created.unlink()
new_events = [(3000, 'TAP:120,770'), (6200, 'TAP:130,130'),
              (9000, 'TAP:240,392'), (11200, 'TAP:68,655'),
              (13700, 'TAP:422,753'), (15600, 'TAP:35,607'),
              (17400, 'TAP:327,755'), (19400, 'TAP:82,607'),
              (22000, 'TAP:421,755'), (25500, 'QUIT')]
new_shots = [(14800, 'new-note-body'), (23700, 'created-note-list')]
env['CROSSPOINT_SIM_INPUT_SCRIPT'] = ';'.join(f'{t}:{action}' for t, action in new_events)
env['CROSSPOINT_SIM_SCREENSHOTS'] = ';'.join(f'{t}:{OUT}/{name}.bmp' for t, name in new_shots)
with (OUT / 'create-simulator.log').open('w') as log:
    result = subprocess.run(['xvfb-run', '-a', str(ROOT / '.pio/build/simulator_x4pro_video/program')],
                            cwd=OUT, env=env, stdout=log, stderr=log, timeout=45)
if result.returncode or not created.is_file() or created.read_bytes() != b'a\n\nq\nw\n':
    raise RuntimeError(f'Simulator new-note save failed: code={result.returncode}; '
                       f'file={created}; bytes={created.read_bytes() if created.exists() else None!r}')
for _, name in new_shots:
    original = OUT / f'{name}.bmp'
    if not original.is_file():
        raise RuntimeError(f'No simulator screenshot: {original}')
    target = OUT / f'{name}.png'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(original), str(target)], check=True)
    print(target, 'bytes', target.stat().st_size)
print('new note saved', repr(created.read_bytes()))
