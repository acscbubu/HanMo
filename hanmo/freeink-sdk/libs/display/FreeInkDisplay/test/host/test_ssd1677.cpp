#include <algorithm>
#include <array>

#include "driver/Ssd1677Driver.cpp"
using namespace freeink;
using Mode = RefreshMode;
using Policy = Ssd1677CleanPolicy;
void expect(EpdBus& b, std::initializer_list<uint8_t> seq) { assert(b.sequences() == std::vector<uint8_t>(seq)); }
void parameters(EpdBus& b) {
  for (auto& e : b.events)
    if (e.cmd == 0x21) assert(e.bytes.size() == 2);
  assert(b.last(0x18) == std::vector<uint8_t>{0x80});
}
// External drivers implementing only the original interface remain compatible.
struct LegacyDriver : PanelDriver {
  int calls = 0;
  uint32_t spiHz() const override { return 10000000; }
  BusyPolarity busyPolarity() const override { return BusyPolarity::ActiveHigh; }
  PanelGeometry geometry() const override { return {32, 8, 4, 32}; }
  void begin(EpdBus&) override {}
  void deepSleep(EpdBus&) override {}
  void display(EpdBus&, const uint8_t*, const uint8_t*, RefreshMode mode, bool off) override {
    assert(mode == Mode::Fast && off);
    calls |= 1;
  }
  bool displayStart(EpdBus&, const uint8_t*, const uint8_t*, RefreshMode mode, bool off) override {
    assert(mode == Mode::Half && !off);
    calls |= 2;
    return true;
  }
  void displayGrayscaleBase(EpdBus&, const uint8_t*, RefreshMode mode, bool off) override {
    assert(mode == Mode::Full && off);
    calls |= 4;
  }
};

void testDriverSequences() {
  LegacyDriver legacy;
  PanelDriver& compat = legacy;
  EpdBus compatBus;
  compat.displayWithContext(compatBus, nullptr, nullptr, Mode::Fast, true, RefreshContext::ContinuousReading);
  assert(compat.displayStartWithContext(compatBus, nullptr, nullptr, Mode::Half, false,
                                        RefreshContext::ContinuousReading));
  compat.displayGrayscaleBaseWithContext(compatBus, nullptr, Mode::Full, true, RefreshContext::ContinuousReading);
  assert(legacy.calls == 7);

  std::array<uint8_t, 32> fb;
  fb.fill(0xA5);
  const auto original = fb;
  {
    auto cfg = ssd1677MetalioConfig();
    assert(cfg.cleanPolicy == Policy::BlackPulse);
    Ssd1677Driver d(cfg);
    EpdBus b;
    d.begin(b);
    b.clear();
    d.display(b, fb.data(), nullptr, Mode::Full, false);
    expect(b, {0xF7});  // Explicit FULL must survive first-paint promotion.
    parameters(b);
    b.clear();
    d.displayGray(b, fb.data(), false, nullptr, false);
    expect(b, {0xCC});
    b.clear();
    d.cleanupGrayscaleBuffers(b, fb.data());
    assert(b.sequences().empty());
    b.clear();
    d.display(b, fb.data(), nullptr, Mode::Fast, false);
    expect(b, {0xFC, 0xFC});
    assert(b.last(0x24) == std::vector<uint8_t>(fb.begin(), fb.end()));
    assert(b.last(0x26) == b.last(0x24));
    parameters(b);
    b.clear();
    d.display(b, fb.data(), nullptr, Mode::Fast, false);
    expect(b, {0xFC});
    b.clear();  // one-shot clean was consumed
    d.displayGray(b, fb.data(), false, nullptr, false);
    d.cleanupGrayscaleBuffers(b, fb.data());
    b.clear();
    d.displayWindow(b, fb.data(), nullptr, 0, 0, 8, 1, false);
    expect(b, {0xFC, 0xFC});
    assert(b.last(0x24).size() == fb.size());
    b.clear();
    d.displayGray(b, fb.data(), false, nullptr, false);
    d.cleanupGrayscaleBuffers(b, fb.data());
    b.clear();
    d.displayGrayscaleBase(b, fb.data(), Mode::Fast, false);
    expect(b, {0xFC, 0xFC});
    b.clear();
    d.displayGray(b, fb.data(), false, nullptr, false);
    b.clear();
    d.deepSleep(b);
    expect(b, {0x83});
    assert(b.last(0x3c) == std::vector<uint8_t>{0x80});
    assert(b.events.back().cmd == 0x10 && b.events.back().bytes == std::vector<uint8_t>{3});
    d.begin(b);
    b.clear();
    d.display(b, fb.data(), nullptr, Mode::Full, true);
    b.clear();
    d.displayGray(b, fb.data(), true, nullptr, false);
    expect(b, {0xCF});
    b.clear();
    d.deepSleep(b);
    expect(b, {});  // already powered down
    d.begin(b);
    b.clear();
    // Leaving the reader does not inherit its one-frame baseline permission.
    d.display(b, fb.data(), nullptr, Mode::Fast, false);
    expect(b, {0xFC, 0xFC});
    b.clear();
    d.displayGray(b, fb.data(), false, nullptr, false);
    b.clear();
    // Reading context cannot reuse an unsynchronized grayscale baseline.
    d.displayWithContext(b, fb.data(), nullptr, Mode::Fast, false, RefreshContext::ContinuousReading);
    expect(b, {0xFC, 0xFC});
    assert(fb == original);
  }
  auto cfg = ssd1677MetalioConfig();
  assert(cfg.cleanPolicy == Policy::BlackPulse);
  Ssd1677Driver d(cfg);
  EpdBus b;
  d.begin(b);
  b.clear();
  assert(!d.displayStart(b, fb.data(), nullptr, Mode::Fast, true));
  expect(b, {0xFC, 0xFC, 0x83});
  std::vector<EpdBus::Event> planes;
  for (auto& e : b.events)
    if (e.cmd == 0x24 || e.cmd == 0x26) planes.push_back(e);
  assert(planes.size() == 7);
  assert(planes[0].cmd == 0x26 && planes[0].bytes == std::vector<uint8_t>(32, 0xff));
  assert(planes[1].cmd == 0x24 && planes[1].bytes == std::vector<uint8_t>(32, 0));
  assert(planes[2].bytes == planes[1].bytes && planes[3].bytes == planes[1].bytes);
  assert(planes[4].bytes == std::vector<uint8_t>(fb.begin(), fb.end()));
  assert(planes[5].bytes == planes[4].bytes && planes[6].bytes == planes[4].bytes);
  b.clear();
  assert(d.displayStart(b, fb.data(), nullptr, Mode::Fast, true));
  expect(b, {0xFC});
  assert(b.busy);
  d.displayFinish(b, fb.data());
  expect(b, {0xFC, 0x83});
  assert(!b.busy);
  b.clear();
  d.display(b, fb.data(), nullptr, Mode::Half, false);
  expect(b, {0xFC, 0xFC});
  b.clear();
  b.stuck = true;
  d.display(b, fb.data(), nullptr, Mode::Half, false);
  expect(b, {0xFC});
  assert(b.events.back().cmd == -1);  // no writes after a timed-out first phase
  b.stuck = false;
  b.busy = false;
  b.clear();
  d.display(b, fb.data(), nullptr, Mode::Fast, false);
  expect(b, {0xFC, 0xFC});
  // A fast reading page does not physically erase residual gray; leaving the
  // reader still cleans even if this last page did not need a new AA overlay.
  b.clear();
  d.displayGray(b, fb.data(), false, nullptr, false);
  d.cleanupGrayscaleBuffers(b, fb.data());
  b.clear();
  d.displayWithContext(b, fb.data(), nullptr, Mode::Fast, false, RefreshContext::ContinuousReading);
  expect(b, {0xFC});
  b.clear();
  d.display(b, fb.data(), nullptr, Mode::Fast, false);
  expect(b, {0xFC, 0xFC});
  // Failure in the restore phase: no baseline writes, next request cleans.
  b.clear();
  b.failAt = b.activation + 2;
  d.display(b, fb.data(), nullptr, Mode::Half, false);
  expect(b, {0xFC, 0xFC});
  assert(b.events.back().cmd == -1);
  b.failAt = 0;
  b.busy = false;
  b.clear();
  d.display(b, fb.data(), nullptr, Mode::Fast, false);
  expect(b, {0xFC, 0xFC});
  // Failed analog power-off must not proceed to deep sleep or be marked off.
  b.clear();
  b.failAt = b.activation + 1;
  d.deepSleep(b);
  expect(b, {0x83});
  assert(b.last(0x10).empty());
  b.failAt = 0;
  b.busy = false;
  b.clear();
  d.deepSleep(b);
  expect(b, {0x83});
  assert(!b.last(0x10).empty());
  d.begin(b);
  b.clear();
  d.display(b, fb.data(), nullptr, Mode::Full, false);
  b.clear();
  d.displayGray(b, fb.data(), false, nullptr, false);
  d.cleanupGrayscaleBuffers(b, fb.data());
  b.clear();
  d.displayWithContext(b, fb.data(), nullptr, Mode::Full, false, RefreshContext::ContinuousReading);
  expect(b, {0xF7});  // Explicit FULL cannot be weakened by reading context.
  b.clear();
  assert(d.displayStart(b, fb.data(), nullptr, Mode::Fast, true));
  b.stuck = true;
  d.displayFinish(b, fb.data());
  expect(b, {0xFC});  // No park while the display is still busy.
  b.stuck = false;
  b.busy = false;
  b.clear();
  d.display(b, fb.data(), nullptr, Mode::Fast, false);
  expect(b, {0xFC, 0xFC});
  // Legacy devices retain their wire behavior and RED-only gray cleanup.
  for (const auto* legacy : {&ssd1677DefaultConfig(), &ssd1677Waveshare397Config()}) {
    Ssd1677Driver old(*legacy);
    EpdBus bus;
    old.begin(bus);
    bus.clear();
    old.display(bus, fb.data(), nullptr, Mode::Fast, false);
    expect(bus, {0xD7});
    bus.clear();
    old.displayGray(bus, fb.data(), false, nullptr, false);
    old.cleanupGrayscaleBuffers(bus, fb.data());
    bus.clear();
    old.display(bus, fb.data(), nullptr, Mode::Fast, false);
    expect(bus, {legacy->fastSeqOverride});
    for (auto& e : bus.events)
      if (e.cmd == 0x21) assert(e.bytes.size() == 1);
  }
  assert(fb == original);
}

#ifndef CROSSMUX_READER_REFRESH_TEST
int main() { testDriverSequences(); }
#endif
