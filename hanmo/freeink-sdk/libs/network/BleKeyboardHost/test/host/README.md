# BLE host regression checks

Run `python3 test/host/test_startup.py` from the BleKeyboardHost library directory.
It compiles production code with small host doubles and checks:

- Connection-worker allocation failure returns false, releases the client and
  initialized stack, and permits a subsequent successful start.
- Discovery owns copied addresses and names after callback buffers expire,
  retains scan-response name updates, and respects the fixed device capacity.

ESP32-C3 uses NimBLE callback-only scan results (`setMaxResults(0)`); the SDK
device list remains the connection source. Other targets retain their existing
scan mode. These checks do not establish controller or radio behavior on hardware.
