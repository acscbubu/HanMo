# LGPL source and relinking materials

Arduino core 3.3.7 and WebSockets retain LGPL-2.1-or-later. Complete delivered sources are editable
under dependencies/. LGPL text, original notices, build scripts, application sources and linker inputs
are provided. This full-source build route lets recipients modify the libraries and relink the application;
it does not impose a proprietary restriction on modification or reverse engineering.
This mbedTLS candidate uses the LGPL section 6 full-source/relinking route, without
converting the whole application to GPL. Original notices and terms remain.
The package retains the prior two-library relink probe result for the same SDK/backend. It was not rerun for the Bold/status UI change.
The probe binary is never an installable release; clean artifacts are retained separately.

```sh
# First complete BUILDING.md, then run against that disposable work directory:
/tmp/hanmo-tools/bin/python tools/verify-lgpl-relink.py --package "$PWD" --work-dir /tmp/hanmo-final --core-dir /tmp/hanmo-pio --pio /tmp/hanmo-tools/bin/pio --evidence /tmp/hanmo-lgpl-evidence
```

The verifier temporarily modifies two delivered sources; run on your own extracted copy and do not
interrupt it. Its finally block restores sources. The output work directory still contains a PROBE BIN;
never flash it. After verification use a fresh work directory for any ordinary build.
Source restoration is checked again against DEPENDENCIES.lock.json before packaging.

Complete BUILDING.md before running the verifier. The probe is build/relink evidence,
not device validation or a substitute for the independent vendor component license notices.

The fresh probe was performed on the first mbedTLS build (which still displayed the old
Maruko version suffix). The later Bold/status build additionally changes UI font data, reader status placement,
translations and change history. SDK and LGPL library source hashes are unchanged; the
final linked archives match the prior source-built SDK and the dependency lock. This
retained result demonstrates relinkability of that dependency setup, not a fresh probe
on every UI revision.
Both retained markers reached the probe BIN/ELF. Probe SHA256: bf0b64da545430c532fe31d9781401bdbd7e09a8c298f5ffb63db291f94239d7.
