"""Keep the pinned simulator String API compatible with Arduino reserve()."""
from pathlib import Path
import re
Import("env")
# GCC 15 defaults to C23; pinned QRCode 0.0.1 expects the C17 bool rules.
env.Append(CFLAGS=["-std=gnu17"])
header = Path(env.subst("$PROJECT_LIBDEPS_DIR")) / env.subst("$PIOENV") / "simulator/src/WString.h"
if header.exists():
    source = header.read_text()
    if not re.search(r"\breserve\s*\(", source):
        anchor = "  std::string s;"
        if anchor not in source:
            raise RuntimeError("Simulator String layout changed; inspect before patching")
        header.write_text(source.replace(anchor, anchor + "\n  bool reserve(size_t size) { s.reserve(size); return true; }", 1))

# The simulator has no OTA banks; keep boot switching safely unavailable.
slot = header.with_name("HalOtaSlot.h")
if slot.exists():
    source = slot.read_text()
    anchor = "  static HalOtaSlot inactive();"
    for method in ("inactiveHoldsApplication", "bootInactiveSlot"):
        if method + "(" not in source:
            if anchor not in source:
                raise RuntimeError("Simulator OTA layout changed")
            source = source.replace(anchor, anchor + "\n  static bool " + method + "() { return false; }", 1)
    slot.write_text(source)
