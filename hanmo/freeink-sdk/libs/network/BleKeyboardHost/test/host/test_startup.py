"""Compile the actual begin() task-creation tail with a failing FreeRTOS allocator."""

import os
from pathlib import Path
import shlex
import subprocess
import tempfile


source = (Path(__file__).resolve().parents[2] / "src/BleKeyboardHost.cpp").read_text()
begin = source.split("bool BleKeyboardHost::begin(const char* hostName) {", 1)[1]
begin = begin.split("\nvoid BleKeyboardHost::end()", 1)[0]
# Keep the branch around xTaskCreate as well as every subsequent statement.
tail = begin[begin.rfind("\n", 0, begin.index("xTaskCreate(")) + 1:]
harness = r'''
#include <cassert>
constexpr int pdPASS = 1;
int client, worker, deletes = 0, deinits = 0, attempts = 0;
int* g_client = &client;
void* g_connTask = nullptr;
void connTaskFn(void*) {}
struct { void println(const char*) {} } Serial;
struct NimBLEDevice {
  static void deleteClient(int* p) { assert(p == &client); ++deletes; }
  static void deinit(bool clear) {
    assert(clear && g_client == nullptr && g_connTask == nullptr);
    ++deinits;
  }
};
int xTaskCreate(void (*)(void*), const char*, int stack, void*, int priority, void** out) {
  assert(stack == 4096 && priority == 3);
  if (++attempts == 1) return 0;
  *out = &worker;
  return pdPASS;
}
struct Host {
  bool begun_ = false;
  bool start() {
''' + tail + r'''
};
int main() {
  Host host;
  assert(!host.start());
  assert(!host.begun_ && !g_client && !g_connTask);
  assert(deletes == 1 && deinits == 1);
  g_client = &client; // The next begin() creates a fresh client.
  assert(host.start());
  assert(host.begun_ && g_client == &client && g_connTask == &worker);
  assert(deletes == 1 && deinits == 1);
}
'''
with tempfile.TemporaryDirectory() as directory:
    cpp = Path(directory) / "startup.cpp"
    binary = Path(directory) / "startup"
    cpp.write_text(harness)
    subprocess.run(shlex.split(os.environ.get("CXX", "c++")) +
                   ["-std=c++17", "-Wall", "-Wextra", "-Werror", str(cpp), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)

# The callback-only scanner releases advertisements after onResult. Exercise
# the real SDK ingestion with temporary buffers, including later name updates.
ingest = source[source.index('void BleKeyboardHost::onScanResultIngest('):source.index('\nvoid BleKeyboardHost::onLinkUp(')]
scan = r'''
#include <cassert>
#include <cstring>
#include <cstdio>
#define private public
#include "BleKeyboardHost.h"
#undef private
#define portENTER_CRITICAL(x) ((void)0)
#define portEXIT_CRITICAL(x) ((void)0)
namespace freeink {
''' + ingest + r'''
}
int main() {
  freeink::BleKeyboardHost host;
  {
    char addr[] = "11:22:33:44:55:66";
    char name[] = "Remote";
    host.onScanResultIngest(addr, name, -30, 1, true, true);
    memset(addr, 0, sizeof(addr));
    memset(name, 0, sizeof(name));
  }
  assert(host.deviceCount_ == 1);
  assert(strcmp(host.devices_[0].name, "Remote") == 0);
  assert(strcmp(host.devices_[0].addr, "11:22:33:44:55:66") == 0);
  assert(host.devices_[0].addrType == 1);
  host.onScanResultIngest("11:22:33:44:55:66", "11:22:33:44:55:66", -29, 1, true, true);
  assert(strcmp(host.devices_[0].name, "Remote") == 0);
  host.onScanResultIngest("11:22:33:44:55:66", "Remote response", -28, 1, true, true);
  assert(strcmp(host.devices_[0].name, "Remote response") == 0);
  for (int i = 0; i < 100; ++i) {
    char addr[18];
    snprintf(addr, sizeof(addr), "11:22:33:44:55:%02x", i);
    host.onScanResultIngest(addr, "Nearby", -40, 0, true, true);
  }
  assert(host.deviceCount_ == host.kMaxDiscovered);
  assert(strcmp(host.devices_[0].name, "Remote response") == 0);
}
'''
with tempfile.TemporaryDirectory() as directory:
    cpp = Path(directory) / 'scan.cpp'
    binary = Path(directory) / 'scan'
    (Path(directory) / 'Arduino.h').write_text('#pragma once\n#include <cstdint>\n')
    cpp.write_text(scan)
    sdk_include = Path(__file__).resolve().parents[2] / 'include'
    subprocess.run(shlex.split(os.environ.get('CXX', 'c++')) +
                   ['-std=c++17', '-Wall', '-Wextra', '-Werror', '-I', directory,
                    '-I', str(sdk_include), str(cpp), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
