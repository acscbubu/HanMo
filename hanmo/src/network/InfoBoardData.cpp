#include "InfoBoardData.h"

#include <ArduinoJson.h>

#include <atomic>
#include <cmath>
#include <utility>

#include "InfoBoardPolicy.h"
#if defined(ARDUINO_ARCH_ESP32)
#include <Arduino.h>
#include <esp_crt_bundle.h>
#include <esp_http_client.h>
#endif
namespace info_board {
namespace {
std::atomic<int> state{0};  // idle / working / ready; acquire-release publishes result
Request request;
Data result;
std::string number(float n, const char* unit) {
  char out[40];
  snprintf(out, sizeof(out), "%.1f%s", double(n), unit);
  return out;
}
bool numeric(JsonVariantConst v, float lo, float hi) {
  return v.is<float>() && std::isfinite(v.as<float>()) && v.as<float>() >= lo && v.as<float>() <= hi;
}
std::string bounded(const char* p, size_t n = 80) {
  std::string s = p ? p : "";
  if (s.size() > n) {
    size_t cut = n;
    while (cut && (static_cast<unsigned char>(s[cut]) & 0xc0) == 0x80) --cut;
    s.resize(cut);
  }
  return s;
}
#if defined(ARDUINO_ARCH_ESP32)
int get(const std::string& url, std::string& body) {
  esp_http_client_config_t cfg{};
  cfg.url = url.c_str();
  cfg.crt_bundle_attach = esp_crt_bundle_attach;
  cfg.disable_auto_redirect = true;
  cfg.timeout_ms = 4000;
  cfg.buffer_size = 512;
  auto client = esp_http_client_init(&cfg);
  if (!client) return -1;
  const uint32_t started = millis();
  int status = -1;
  if (esp_http_client_open(client, 0) == ESP_OK) {
    const auto length = esp_http_client_fetch_headers(client);
    status = esp_http_client_get_status_code(client);
    if (status == 200 && length >= 0 && length <= 8192) {
      char chunk[256];
      bool ok = true;
      while (true) {
        if (millis() - started > 12000) {
          ok = false;
          break;
        }
        int n = esp_http_client_read(client, chunk, sizeof(chunk));
        if (n < 0 || body.size() + size_t(n) > 8192) {
          ok = false;
          break;
        }
        if (!n) break;
        body.append(chunk, n);
      }
      if (!ok || !esp_http_client_is_complete_data_received(client)) status = -1;
    } else if (status == 200)
      status = -2;
  }
  esp_http_client_cleanup(client);
  return status;
}
void worker(void*) {
  Data next;
  std::string body;
  int status = -1;
  if (request.scene == 1) {
    const char* coordinates = request.city == 1   ? "-33.8688&longitude=151.2093"
                              : request.city == 2 ? "-27.4698&longitude=153.0251"
                                                  : "-37.8136&longitude=144.9631";
    std::string url = std::string("https://api.open-meteo.com/v1/forecast?latitude=") + coordinates +
                      "&current=temperature_2m,relative_humidity_2m,wind_speed_10m&timezone=auto&forecast_days=1";
    status = get(url, body);
  } else if (request.scene == 2) {
    status = localPcUrl(request.url) ? get(request.url, body) : -3;

  }
  if (status != 200 || !parse(request.scene, body, next)) next.error = status == 200 ? -2 : status;
  next.generation = request.generation;
  result = std::move(next);
  request.url.clear();
  state.store(2, std::memory_order_release);
  vTaskDelete(nullptr);
}
#endif
}  // namespace
bool parse(uint8_t scene, const std::string& body, Data& out) {
  if (body.empty() || body.size() > 32768) return false;
  JsonDocument doc;
  if (deserializeJson(doc, body) != DeserializationError::Ok) return false;
  Data next;
  if (scene == 1) {
    auto c = doc["current"];
    if (!numeric(c["temperature_2m"], -100, 80) || !numeric(c["relative_humidity_2m"], 0, 100) ||
        !numeric(c["wind_speed_10m"], 0, 500))
      return false;
    next.rows = {Row{"Temperature", number(c["temperature_2m"], " C")},
                 Row{"Humidity", number(c["relative_humidity_2m"], " %")},
                 Row{"Wind", number(c["wind_speed_10m"], " km/h")}};
    next.updated = bounded(c["time"] | "", 32);
  } else if (scene == 2) {
    if (!numeric(doc["cpu_percent"], 0, 100) || !numeric(doc["memory_percent"], 0, 100) ||
        !numeric(doc["disk_percent"], 0, 100))
      return false;
    next.rows = {Row{"CPU", number(doc["cpu_percent"], " %")}, Row{"RAM", number(doc["memory_percent"], " %")},
                 Row{"Disk", number(doc["disk_percent"], " %")}};
    next.updated = bounded(doc["updated"] | "", 32);
  } else
    return false;
  next.valid = true;
  out = std::move(next);
  return true;
}
bool busy() { return state.load(std::memory_order_acquire) != 0; }
bool start(Request next) {
  int idle = 0;
  if (!state.compare_exchange_strong(idle, 1)) return false;
  request = std::move(next);
  result = Data{};
#if defined(ARDUINO_ARCH_ESP32)
  if (xTaskCreate(worker, "InfoBoardFetch", 12288, nullptr, 1, nullptr) != pdPASS) {
    request = Request{};
    state.store(0);
    return false;
  }
#else
  result.error = -1;
  result.generation = request.generation;
  state.store(2, std::memory_order_release);
#endif
  return true;
}
bool take(uint8_t& scene, Data& data) {
  if (state.load(std::memory_order_acquire) != 2) return false;
  scene = request.scene;
  data = std::move(result);
  request = Request{};
  state.store(0, std::memory_order_release);
  return true;
}
}  // namespace info_board
