from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];DEP=ROOT/'.pio/libdeps/simulator_x4pro_video/simulator/src'
assert DEP.is_dir()
p=DEP/'HalGPIO.h';t=p.read_text()
if 'gestureContacts()' not in t:
 t=t.replace('  HalGPIO() = default;','  HalGPIO() = default;\n  struct DemoContacts {uint8_t count=0,reportedCount=0;float x[2]{},y[2]{};};\n  bool supportsMultiTouch() const {return hasTouch();}\n  DemoContacts gestureContacts() const {return {};}\n  bool twoFingerSwipe(float&,float&,float&,float&) const {return false;}\n  bool twoFingerRotation(float&) const {return false;}\n');p.write_text(t)
p=DEP/'IPAddress.h';t=p.read_text()
if 'operator uint32_t()' not in t:
 t=t.replace('  IPAddress() = default;','  IPAddress() = default;\n  operator uint32_t() const {return uint32_t(bytes_[0]) | uint32_t(bytes_[1])<<8 | uint32_t(bytes_[2])<<16 | uint32_t(bytes_[3])<<24;}\n');p.write_text(t)
p=DEP/'WiFi.h';t=p.read_text()
if 'broadcastIP()' not in t:
 t=t.replace('  IPAddress localIP() {','  IPAddress broadcastIP(){return IPAddress(127,255,255,255);}\n  IPAddress subnetMask(){return IPAddress(255,0,0,0);}\n  IPAddress localIP() {');p.write_text(t)
print('Prepared simulator-only video adapters')

p=DEP/"WString.h";t=p.read_text()
if "bool reserve(" not in t:
 t=t.replace("  String() {}", "  String() {}\n  bool reserve(size_t n){s.reserve(n);return true;}");p.write_text(t)

p=DEP/"HalOtaSlot.h";t=p.read_text()
if "bootInactiveSlot()" not in t:
 t=t.replace("  static HalOtaSlot inactive();", "  static HalOtaSlot inactive();\n  static bool inactiveHoldsApplication(){return false;}\n  static bool bootInactiveSlot(){return false;}");p.write_text(t)

p=DEP/"HalStorage.h";t=p.read_text()
if "bool freeBytes(" not in t:
 t=t.replace("class HalStorage {", "class HalStorage {\n public: bool freeBytes(uint64_t& bytes){bytes=uint64_t(1024)*1024*1024;return true;}\n private:");p.write_text(t)

# Native GCC C23 defines bool/true/false; use the standard header for this dependency.
p=ROOT/".pio/libdeps/simulator_x4pro_video/QRCode/src/qrcode.h"
t=p.read_text(encoding="utf-8")
t=t.replace("typedef unsigned char bool;\nstatic const bool false = 0;\nstatic const bool true = 1;", "#include <stdbool.h>")
p.write_text(t,encoding="utf-8")
