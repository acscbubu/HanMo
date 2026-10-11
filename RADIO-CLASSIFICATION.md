# SDK binary boundary in the mbedTLS candidate

The former candidate combined wolfSSL under GPLv3 and required analysis of eleven SDK
binaries under GPL System Libraries rules. That candidate remains separate and unchanged.
This candidate removes wolfSSL/wolfCrypt and uses Apache-2.0 mbedTLS with the existing MIT
application and LGPL libraries. It does not select GPLv3 for the whole linked application.
The wolfSSL-specific question is therefore not a prerequisite for this new TLS backend.

Ten radio archives are delivered under their recorded Espressif Apache-2.0 notices;
libxt_hal.a has its Tensilica MIT notice. They remain precompiled vendor inputs, with hashes
and provenance in binary-system-libraries/manifest.json. Standard runtime libraries retain
their own terms. LGPL source, build and relinking obligations are still addressed separately.
This change does not retroactively clear any earlier wolfSSL image or previously published binary.
