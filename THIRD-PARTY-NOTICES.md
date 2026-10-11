# Third-party notices and license boundaries

HanMo original application remains MIT; the matching copyright grant is LICENSE and hanmo/LICENSE.
This candidate removes the Arduino-wolfSSL dependency and optional WolfsslCrypto backend.
mbedTLS 3.6.5 is used under its Apache-2.0 option, with original license texts retained.
Arduino core 3.3.7 and WebSockets remain LGPL-2.1-or-later. Full modified sources,
build scripts and relinking materials are included; modification and reverse engineering
for debugging library modifications are permitted. See LGPL-RELINK.md.

KanjiVG SVGs and KanaStrokeData.generated.h remain CC-BY-SA-3.0, Ulrich Apel and contributors.
Their source, conversion and attribution are in hanmo/third_party/kanjivg/SOURCE.md.
Controller/type declarations are MIT; independent artwork is not relicensed.
Noto / Maruko / HanMoKana fonts remain OFL-1.1 with their source notices.
Lucide/Feather and Tabler retain ISC/MIT notices.
MiniBidi: Ahmad Khalifa; Mintty changes Thomas Wolff, MIT in original source headers.
Michi-c2: Denis Blumstein, based on Petr Baudis michi.py, MIT in UPSTREAM-README.md.
No external commercial Michi pattern database is included.

Ten Espressif radio binaries retain their Apache-2.0 notices; libxt_hal.a retains
Tensilica MIT in LICENSES/Xtensa-libhal-MIT.txt. Binary files are not described as source.
Standard toolchain runtime notices and GCC Runtime Library Exception are retained.
SDK tools/tests/examples can have their own licenses and are independently included source;
the firmware link map determines which code participates in the device image.

See notice-index.json for notice paths and hashes, DEPENDENCIES.lock.json for fixed source
inputs, and SOURCE-COVERAGE.md for exact build boundaries. Donations grant no additional rights.

Maruko Gothic CJK JP Bold: SIL OFL 1.1, upstream max32002/maruko-gothic commit 97e9dd4a2fdde58084dde8d022de253f8d8415e9. Original font and Maruko-Bold-OFL.txt are included under hanmo/lib/EpdFont/builtinFonts/source/HanMoKana/.
