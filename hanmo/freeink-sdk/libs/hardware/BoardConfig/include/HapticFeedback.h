#pragma once

#include <BoardConfig.h>

#if FREEINK_CAP_HAPTIC
#if !FREEINK_DEVICE_METALIO_EINK4
#error "FREEINK_CAP_HAPTIC requires a board motor pin and pulse calibration"
#endif

#include <driver/gpio.h>
#include <esp_rom_sys.h>
#include <esp_timer.h>
#include <freertos/FreeRTOS.h>

namespace freeink::haptic {
constexpr gpio_num_t MOTOR_PIN = GPIO_NUM_44;
// Board calibration: reference firmware uses 35 ms. Tune against the real motor.
constexpr uint16_t PULSE_MS[] = {0, 20, 35, 60};
constexpr uint16_t pulseDuration(uint8_t level) { return PULSE_MS[level < 4 ? level : 2]; }

inline esp_timer_handle_t timer = nullptr;
inline portMUX_TYPE mux = portMUX_INITIALIZER_UNLOCKED;
inline int64_t deadline = 0;

inline void timerExpired(void*) {
  portENTER_CRITICAL(&mux);
  // A callback already dispatched before stop() may arrive during a new pulse.
  if (deadline != 0 && esp_timer_get_time() >= deadline) {
    gpio_set_level(MOTOR_PIN, 0);
    deadline = 0;
  }
  portEXIT_CRITICAL(&mux);
}

// begin/pulse/stop are owned by the application loop; only timerExpired races them.
inline void stop() {
  portENTER_CRITICAL(&mux);
  deadline = 0;
  gpio_set_level(MOTOR_PIN, 0);
  portEXIT_CRITICAL(&mux);
  if (timer) esp_timer_stop(timer);  // An already expired timer is harmless.
}

inline void prepareForSleep() {
  stop();
  gpio_hold_en(MOTOR_PIN);  // Keep LOW through the SDK's deep-sleep GPIO isolation.
}

inline bool begin() {
  if (timer) return true;
  gpio_set_level(MOTOR_PIN, 0);
  if (gpio_set_direction(MOTOR_PIN, GPIO_MODE_OUTPUT) != ESP_OK) {
    esp_rom_printf("[haptic] motor GPIO initialization failed\r\n");
    return false;
  }
  gpio_sleep_sel_dis(MOTOR_PIN);  // Light sleep must not replace the output configuration.
  esp_timer_create_args_t args = {};
  args.callback = timerExpired;
  args.dispatch_method = ESP_TIMER_TASK;
  args.name = "haptic";
  // One SDK timer allocation for device lifetime; the platform API has no static
  // allocation variant (local S3 IDF payload: 32 bytes plus allocator overhead).
  // No new task or per-pulse allocation is needed.
  if (esp_timer_create(&args, &timer) != ESP_OK) {
    esp_rom_printf("[haptic] timer allocation failed\r\n");
    return false;
  }
  return true;
}

inline void pulse(uint16_t durationMs) {
  if (!timer || durationMs == 0) return;
  portENTER_CRITICAL(&mux);
  const bool busy = deadline != 0;
  portEXIT_CRITICAL(&mux);
  if (busy) return;  // Never queue or extend a pulse while the motor is running.
  esp_timer_stop(timer);
  portENTER_CRITICAL(&mux);
  deadline = esp_timer_get_time() + static_cast<int64_t>(durationMs) * 1000;
  gpio_set_level(MOTOR_PIN, 1);
  portEXIT_CRITICAL(&mux);
  if (esp_timer_start_once(timer, static_cast<uint64_t>(durationMs) * 1000) != ESP_OK) {
    stop();
    esp_rom_printf("[haptic] timer start failed\r\n");
  }
}
}  // namespace freeink::haptic
#endif
