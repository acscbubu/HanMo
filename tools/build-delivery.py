#!/usr/bin/env python3
"""Build this source delivery in a disposable work directory; never flash."""
from pathlib import Path
import argparse, os, shutil, subprocess, configparser, json

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--package',type=Path,default=Path(__file__).resolve().parents[1])
    ap.add_argument('--work-dir',type=Path,required=True)
    ap.add_argument('--core-dir',type=Path,required=True)
    ap.add_argument('--pio',default='pio'); ap.add_argument('--jobs',type=int,default=4)
    ap.add_argument("--install-only",action="store_true")
    args=ap.parse_args(); package=args.package.resolve(); work=args.work_dir.resolve(); core=args.core_dir.resolve()
    assert (package/'hanmo/platformio.ini').is_file()
    assert work!=package and not package.is_relative_to(work), 'Work directory must not contain package'
    project=work/'hanmo'; work.mkdir(parents=True,exist_ok=True)
    marker=work/'hanmo-delivery-work.json'
    if project.exists():
        assert marker.is_file() and json.loads(marker.read_text())['package']==str(package), 'Unowned existing work directory'
    else:
        shutil.copytree(package/'hanmo',project,symlinks=True,ignore=shutil.ignore_patterns('.pio','.cache','.git','__pycache__','build','platformio.local.ini'))
        marker.write_text(json.dumps({'package':str(package)}))
    # Always use the delivered (editable) libraries, not registry downloads.
    config=configparser.ConfigParser(interpolation=None); config.read(project/'platformio.ini')
    libs=[f'{p.name}=symlink://{p.as_posix()}' for p in sorted((package/'dependencies').iterdir()) if p.is_dir() and p.name!='arduino-core-3.3.7']
    libs += [s.strip() for s in config['base']['lib_deps'].splitlines() if 'symlink://' in s]
    text='[env:x4pro_custom]\nplatform = file://'+(package/'build-platform').as_posix()+'\n'
    text+='lib_deps =\n'+''.join('  '+s+'\n' for s in libs)
    text+='platform_packages =\n  framework-arduinoespressif32@file://'+(package/'dependencies/arduino-core-3.3.7').as_posix()+'\n'
    (project/'platformio.local.ini').write_text(text)
    # Refresh editable Arduino source if the same version was previously installed.
    target=core/'packages/framework-arduinoespressif32'
    if target.is_dir():
        shutil.copytree(package/'dependencies/arduino-core-3.3.7',target,dirs_exist_ok=True,symlinks=True,
                        ignore=shutil.ignore_patterns('.piopm','.git','__pycache__'))
    env=os.environ.copy(); env.update(PLATFORMIO_CORE_DIR=str(core),PLATFORMIO_BUILD_CACHE_DIR=str(work/'build-cache'),IDF_COMPONENT_CACHE_PATH=str(work/'idf-cache'))
    cmd=[args.pio,'pkg','install','-e','x4pro_custom'] if args.install_only else [args.pio,'run','-e','x4pro_custom','-j',str(args.jobs)]
    subprocess.run(cmd,cwd=project,env=env,check=True)
    if args.install_only:return
    expected=(package/'VERSION').read_text().strip().encode()
    image=(project/'.pio/build/x4pro_custom/firmware.bin').read_bytes()
    if expected not in image:raise SystemExit('Built image does not contain package VERSION; do not package/flash.')
    print('Built application:',project/'.pio/build/x4pro_custom/firmware.bin')

if __name__=='__main__': main()
