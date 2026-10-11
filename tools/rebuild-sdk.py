#!/usr/bin/env python3
"""Compile the linked open ESP32-S3 SDK libraries; preserve identified vendor binaries."""
import argparse,hashlib,json,os,re,shutil,subprocess,sys
from pathlib import Path

def macros(path):
    return dict(re.findall(r'^#define (CONFIG_\w+)\s+(.*)$',path.read_text(),re.M))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--package',type=Path,default=Path(__file__).resolve().parents[1]);ap.add_argument('--work-dir',type=Path,required=True);ap.add_argument('--core-dir',type=Path,required=True);ap.add_argument('--jobs',type=int,default=4);args=ap.parse_args()
    package=args.package.resolve();work=args.work_dir.resolve();core=args.core_dir.resolve()
    if work.exists():raise SystemExit('Use a new empty SDK work directory.')
    if work==package or package.is_relative_to(work):raise SystemExit('Work directory must not contain source package.')
    compiler=core/'packages/toolchain-xtensa-esp-elf/bin';sdk=core/'packages/framework-arduinoespressif32-libs/esp32s3'
    if not sdk.is_dir() or not compiler.is_dir():raise SystemExit('First bootstrap PlatformIO packages using BUILDING.md.')
    work.mkdir(parents=True);project=work/'project';build=work/'build'
    shutil.copytree(package/'sdk-build',project,symlinks=True)
    (project/'components/arduino/CMakeLists.txt').write_text('idf_component_register(INCLUDE_DIRS "'+str(package/'sdk-source/arduino-sdk/cores/esp32')+'")\n')
    env=os.environ.copy();env.update(IDF_PATH=str(package/'sdk-source/esp-idf'),IDF_COMPONENT_MANAGER='0',PATH=str(compiler)+os.pathsep+str(Path(sys.executable).parent)+os.pathsep+env.get('PATH',''))
    log=work/'build.log'
    def run(cmd):
        with log.open('a') as stream:subprocess.run(cmd,env=env,stdout=stream,stderr=subprocess.STDOUT,check=True)
    run(['cmake','-S',str(project),'-B',str(build),'-G','Ninja','-DIDF_TARGET=esp32s3','-DPYTHON='+sys.executable,'-DPYTHON_DEPS_CHECKED=1'])
    expected=macros(package/'build-config/esp32s3/dio_opi/include/sdkconfig.h');actual=macros(build/'config/sdkconfig.h')
    if expected!=actual:raise SystemExit('Generated SDK configuration differs from frozen X4 Pro configuration; see '+str(log))
    targets=json.loads((package/'sdk-build/archive-targets.json').read_text())
    run(['ninja','-C',str(build),'-j',str(args.jobs)]+[r['target'] for r in targets])
    names={r['target']:r['archive'] for r in targets}
    for f in (build/'esp-idf').rglob('*.a'):names.setdefault(f.relative_to(build).as_posix(),f.name)
    records=[]
    for rel,name in names.items():
        source=build/rel
        for dest in sdk.rglob(name):
            if not (dest.is_relative_to(sdk/'lib') or dest.is_relative_to(sdk/'dio_opi')):continue
            shutil.copy2(source,dest)
            records.append({'archive':name,'buildTarget':rel,'installed':dest.relative_to(core).as_posix(),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
    if not {r['archive'] for r in targets}<={r['archive'] for r in records}:raise SystemExit('Some rebuilt SDK archives were not installed.')
    shutil.copy2(build/'config/sdkconfig.h',sdk/'dio_opi/include/sdkconfig.h')
    result={'configurationMatches':True,'requiredOpenArchives':len(targets),'installed':records,'binaryExceptions':'binary-system-libraries/manifest.json','notFlashed':True}
    (work/'sdk-result.json').write_text(json.dumps(result,indent=2))
    print('Rebuilt SDK installed:',len(records),'archive paths. Result:',work/'sdk-result.json')

if __name__=='__main__':main()
