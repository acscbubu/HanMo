"""Package the private kana sound-hint candidate; never publish or flash it."""
from pathlib import Path
import hashlib
import json
import shutil
import tarfile
import zipfile

root = Path(__file__).resolve().parents[1]
windows = Path('/mnt/c/Users/angus/OneDrive/文件/ChatGPT/XTEINK UI/migration/hanmo-kana-sound-test-20261006')
source_archive = windows / 'crossmux-hanmo-kana-sound-test-20261006-source.tar.gz'
zip_path = windows / 'hanmo-kana-sound-test-20261006-update.zip'
app = root / '.pio/build/x4pro_custom/firmware.bin'
boot = root / '.pio/build/x4pro_custom/bootloader.bin'
part = root / '.pio/build/x4pro_custom/partitions.bin'
pinned = Path('/mnt/c/Users/angus/OneDrive/文件/ChatGPT/XTEINK UI/XTEINK-Firmware/build-hanmo-panel-save-fix-20261005')
boot_app0 = pinned / 'boot_app0.bin'
pinned_part = pinned / 'partitions.bin'
version = '1.5.8-hanmo-kana-sound-20261006'
release = 'hanmo-kana-sound-test-20261006'
for p in (app, boot, part, boot_app0, pinned_part):
    assert p.is_file(), p
assert version.encode() in app.read_bytes()
assert part.read_bytes() == pinned_part.read_bytes()
assert not source_archive.exists() and not zip_path.exists(), 'refusing to overwrite an existing candidate package'

exclude = {'.pio', '.cache', 'build', '__pycache__', '.git', '.venv-fonts'}
with tarfile.open(source_archive, 'w:gz') as archive:
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root)
        if any(part in exclude or (part == 'docs' and i + 1 < len(rel.parts) and rel.parts[i+1] == 'images')
               for i, part in enumerate(rel.parts)):
            continue
        if path.is_symlink():
            target = path.readlink()
            resolved = path.parent.joinpath(target).resolve(strict=False)
            assert resolved == root or root in resolved.parents, (path, target)
            info = tarfile.TarInfo(str(Path('crossmux-kana-sound-20261006') / rel))
            info.type = tarfile.SYMTYPE
            info.linkname = str(target)
            info.mtime = 0
            archive.addfile(info)
        elif path.is_file():
            archive.add(path, arcname=str(Path('crossmux-kana-sound-20261006') / rel), recursive=False)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def copy_to(source, relative):
    target = windows / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target

app_out = copy_to(app, 'update/hanmo-x4pro-1.5.8-hanmo-kana-sound-20261006-update.bin')
boot_out = copy_to(boot, 'recovery-only/bootloader.bin')
part_out = copy_to(part, 'recovery-only/partitions.bin')
boot_app_out = copy_to(boot_app0, 'recovery-only/boot_app0.bin')
full = bytearray(b'\xff' * 0xff0000)
full[0:len(boot.read_bytes())] = boot.read_bytes()
full[0x8000:0x8000 + len(part.read_bytes())] = part.read_bytes()
full[0xe000:0xe000 + len(boot_app0.read_bytes())] = boot_app0.read_bytes()
app_bytes = app.read_bytes()
assert len(app_bytes) <= 0x7f0000
full[0x10000:0x10000 + len(app_bytes)] = app_bytes
full_out = windows / 'recovery-only/x4pro-single-FULL.bin'
full_out.write_bytes(full)
assert full_out.stat().st_size == 0xff0000

assert (windows / 'README.md').is_file()
copy_to(root / 'docs/kana-sound-hints.md', 'evidence/kana-sound-hints.md')
for image in sorted((root / 'build/kana-practice-qa/final-ui').glob('*.png')):
    copy_to(image, 'evidence/simulator/' + image.name)

manifest = {
    'id': release,
    'version': version,
    'date': '2026-10-06',
    'privateFlashTest': True,
    'published': False,
    'hardwareFlashed': False,
    'hardwareValidated': False,
    'publicPin': 'hanmo-panel-save-fix-20261005',
    'sourceArchive': source_archive.relative_to(windows).as_posix(),
    'sourceArchiveSha256': digest(source_archive),
    'images': {
        app_out.relative_to(windows).as_posix(): {'bytes': app_out.stat().st_size, 'sha256': digest(app_out)},
        boot_out.relative_to(windows).as_posix(): {'bytes': boot_out.stat().st_size, 'sha256': digest(boot_out)},
        part_out.relative_to(windows).as_posix(): {'bytes': part_out.stat().st_size, 'sha256': digest(part_out)},
        boot_app_out.relative_to(windows).as_posix(): {'bytes': boot_app_out.stat().st_size, 'sha256': digest(boot_app_out)},
        full_out.relative_to(windows).as_posix(): {'bytes': full_out.stat().st_size, 'sha256': digest(full_out)},
    },
    'updateFile': app_out.relative_to(windows).as_posix(),
    'flashing': {
        'preferred': 'local flasher > application-only update',
        'overwritePartitions': False,
        'preserveNvsAndSd': True,
        'fullImageForRecoveryOnly': True,
    },
    'verification': {
        'targetedKanaTests': 24,
        'airnoteRegressionTests': 24,
        'fullHostTests': 269,
        'fullHostPreexistingErrors': 3,
        'fullHostSkipped': 2,
        'simulatorBuild': 'SUCCESS: simulator_x4pro_video',
        'hardwareBuild': 'SUCCESS: x4pro_custom',
        'simulatorQa': 'ki（起）, hidden/restored romaji, saved card flags 0x47, group counts 1/46 and 1/5',
    },
}
manifest_path = windows / 'manifest.json'
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
sha_lines = [f'{digest(path)}  {path.relative_to(windows).as_posix()}' for path in (app_out, full_out, source_archive)]
(windows / 'SHA256SUMS').write_text('\n'.join(sha_lines) + '\n', encoding='utf-8')
with zipfile.ZipFile(zip_path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for path in (windows / 'README.md', manifest_path, app_out):
        z.write(path, path.relative_to(windows).as_posix())
assert zipfile.ZipFile(zip_path).testzip() is None
print(json.dumps({**manifest, 'sourceArchiveSha256': digest(source_archive),
                  'zip': str(zip_path), 'zipSha256': digest(zip_path),
                  'fullRecoveryOnly': str(full_out)}, ensure_ascii=False, indent=2))
