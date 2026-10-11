#include <cassert>

#include "InfoBoardPolicy.h"
#include "network/InfoBoardData.cpp"
int main() {
  using namespace info_board;
  assert(rotationMs(0) == 15000 && rotationMs(255) == 30000);
  assert(due(20, 0xfffffff0, 30) && !due(20, 0xfffffff0, 40));
  assert(refreshMs(1) == 900000 && refreshMs(2) == 30000 && refreshMs(3) == 120000);
  for (const char* s : {"http://192.168.88.20:4342/metrics.json", "http://10.2.3.4/metrics.json",
                        "http://172.16.0.2:65535/metrics.json"})
    assert(localPcUrl(s));
  for (const char* s :
       {"http://8.8.8.8/metrics.json", "http://192.168.1.1@evil.test/metrics.json", "https://192.168.1.1/metrics.json",
        "http://192.168.1.1:99999/metrics.json", "http://192.168.1.1:0/metrics.json", "http://127.0.0.1/metrics.json",
        "http://172.32.1.1/metrics.json", "http://192.168.1.256/metrics.json", "http://192.168.1.1/metrics.json?x=y"})
    assert(!localPcUrl(s));
  Data weather;
  assert(parse(
      1,
      R"({"current":{"temperature_2m":18.5,"relative_humidity_2m":63,"wind_speed_10m":12,"time":"2026-10-04T10:00"}})",
      weather));
  assert(weather.valid && weather.rows[0].value == "18.5 C");
  const auto old = weather.rows[0].value;
  assert(!parse(1, R"({"current":{"temperature_2m":null,"relative_humidity_2m":63,"wind_speed_10m":12}})", weather));
  assert(weather.rows[0].value == old);  // invalid input must not destroy last data
  Data pc;
  assert(
      parse(2, R"({"cpu_percent":25,"memory_percent":50.5,"disk_percent":99,"updated":"2026-10-04T00:00:00Z"})", pc));
  assert(!parse(2, R"({"cpu_percent":-1,"memory_percent":50,"disk_percent":99})", pc));
  assert(!parse(2, R"({"cpu_percent":"25","memory_percent":50,"disk_percent":99})", pc));
  assert(!parse(2, R"({"cpu_percent":25,"memory_percent":101,"disk_percent":99})", pc));
  Data rejected;
  assert(!parse(3, R"({"panels":[{"metrics":[{"label":"A","value":12}]}]})", rejected));
  assert(!rejected.valid);
  assert(!parse(1, std::string(32769, 'x'), rejected));
  Request r;
  r.scene = 1;
  r.generation = 42;
  assert(start(r) && busy() && !start(r));
  uint8_t scene = 0;
  Data result;
  assert(take(scene, result) && scene == 1 && result.generation == 42 && !busy());
  assert(!take(scene, result));
}
