#pragma once
#include <Arduino.h>

#include <cassert>
#include <vector>
namespace freeink {
enum class BusyPolarity { ActiveHigh };
class EpdBus {
 public:
  struct Event {
    int cmd;
    std::vector<uint8_t> bytes;
  };
  std::vector<Event> events;
  bool busy = false, stuck = false;
  int activation = 0, failAt = 0;
  void reset() { busy = false; }
  void cmd(uint8_t c) {
    assert(!busy);
    events.push_back({c, {}});
    if (c == 0x20) {
      busy = true;
      ++activation;
    }
  }
  void data(uint8_t b) { events.back().bytes.push_back(b); }
  void data(const uint8_t* p, uint16_t n) { events.back().bytes.insert(events.back().bytes.end(), p, p + n); }
  void waitBusy(const char*) {
    busy = stuck || (failAt != 0 && activation == failAt);
    events.push_back({-1, {}});
  }
  void waitRefreshComplete(const char* s) { waitBusy(s); }
  bool isBusy() const { return busy; }
  void fillPlane(uint8_t c, uint8_t v, uint16_t h, uint16_t wb) {
    cmd(c);
    events.back().bytes.assign(h * wb, v);
  }
  void clear() {
    assert(!busy);
    events.clear();
  }
  std::vector<uint8_t> sequences() const {
    std::vector<uint8_t> result;
    for (auto& e : events)
      if (e.cmd == 0x22) result.push_back(e.bytes.at(0));
    return result;
  }
  std::vector<uint8_t> last(int c) const {
    for (auto i = events.rbegin(); i != events.rend(); ++i)
      if (i->cmd == c) return i->bytes;
    return {};
  }
};
}  // namespace freeink
