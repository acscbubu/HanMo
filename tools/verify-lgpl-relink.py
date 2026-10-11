#!/usr/bin/env python3
"""Temporary modified-library link probe. Never flash its output."""
from pathlib import Path
import argparse, subprocess, hashlib, json, shutil

def main():
    p=argparse.ArgumentParser(); p.add_argument('--package',type=Path,required=True); p.add_argument('--work-dir',type=Path,required=True); p.add_argument('--core-dir',type=Path,required=True); p.add_argument('--pio',default='pio'); p.add_argument('--evidence',type=Path,required=True)
    a=p.parse_args(); P=a.package.resolve(); E=a.evidence.resolve(); E.mkdir(parents=True,exist_ok=True)
    build=a.work_dir/'hanmo/.pio/build/x4pro_custom'; before=(build/'firmware.bin').read_bytes()
    probes=[(P/'dependencies/arduino-core-3.3.7/cores/esp32/esp32-hal-misc.c','unsigned long ARDUINO_ISR_ATTR millis() {','HANMO_LGPL_CORE_RELINK_PROBE_20261009'),
            (P/'dependencies/WebSockets/src/WebSockets.cpp','uint8_t WebSockets::createHeader(uint8_t * headerPtr, WSopcode_t opcode, size_t length, bool mask, uint8_t maskKey[4], bool fin) {','HANMO_LGPL_WS_RELINK_PROBE_20261009')]
    originals={str(f):f.read_bytes() for f,_,_ in probes}
    for _,_,m in probes: assert m.encode() not in before
    result={'baselineAppSha256':hashlib.sha256(before).hexdigest(),'changes':[]}
    baseline=E/'baseline'; baseline.mkdir(exist_ok=True)
    for n in ['firmware.bin','firmware.elf','firmware.map']: shutil.copy2(build/n,baseline/n)
    try:
        for f,needle,marker in probes:
            s=f.read_text(); assert s.count(needle)==1
            s=s.replace(needle,needle+'\n    __asm__ __volatile__("" : : "r"("'+marker+'") : "memory");',1)
            f.write_text(s); result['changes'].append({'file':str(f.relative_to(P)),'marker':marker})
        cmd=['python3',str(P/'tools/build-delivery.py'),'--package',str(P),'--work-dir',str(a.work_dir),'--core-dir',str(a.core_dir),'--pio',a.pio,'--jobs','8']
        with (E/'relink-build.log').open('w') as log: subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
        binary=(build/'firmware.bin').read_bytes(); elf=(build/'firmware.elf').read_bytes()
        for _,_,m in probes: assert m.encode() in binary and m.encode() in elf, 'Modified library marker did not reach app'
        assert binary!=before
        result.update(success=True,probeAppSha256=hashlib.sha256(binary).hexdigest(),probeBytes=len(binary),markersInAppAndElf=True)
        shutil.copy2(build/'firmware.bin',E/'DO-NOT-FLASH-lgpl-probe.bin')
    finally:
        for f,b in originals.items(): Path(f).write_bytes(b)
        # Restore the isolated installed core source too; never touch global packages.
        for f,_,_ in probes:
            if 'arduino-core-3.3.7' in f.parts:
                rel=f.relative_to(P/'dependencies/arduino-core-3.3.7'); target=a.core_dir/'packages/framework-arduinoespressif32'/rel
                if target.exists(): target.write_bytes(originals[str(f)])
        result['sourcesRestored']=all(Path(f).read_bytes()==b for f,b in originals.items())
        result['notFlashed']=True
        (E/'relink-result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
