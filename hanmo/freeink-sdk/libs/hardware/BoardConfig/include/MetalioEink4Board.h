#pragma once

#include <Arduino.h>
#include <Wire.h>
#include <driver/gpio.h>
#include <esp_rom_sys.h>

// Shared Wire owns transaction serialization (endTransmission(false) + requestFrom).
// Only the input/setup/shutdown task writes the expander's output shadow.
namespace freeink::metalio {
constexpr uint8_t EXPANDER = 0x20;
constexpr uint8_t CHARGER = 0x6B;
constexpr uint16_t MAIN_POWER = 1u << 6;
constexpr uint16_t SCREEN_POWER = 1u << 5;
constexpr uint16_t PA_POWER = 1u << 4;
constexpr uint16_t TOUCH_RESET = 1u << 9;
constexpr uint16_t POWER_PULSE = 1u << 11;
constexpr uint16_t USB_MUX_SEL = 1u << 0;  // High selects USB flash/debug, low selects the camera.
constexpr uint16_t OUTPUTS = USB_MUX_SEL | MAIN_POWER | SCREEN_POWER | TOUCH_RESET | POWER_PULSE | PA_POWER | (1u << 1);
constexpr uint16_t BOOT_OUTPUT = MAIN_POWER | POWER_PULSE | USB_MUX_SEL;
inline uint16_t output = BOOT_OUTPUT;
inline bool ready = false;
inline bool bootPowerPending = true;

inline bool powerButtonPressed(bool pressed) {
  if (!bootPowerPending) return pressed;
  if (!pressed) bootPowerPending = false;
  return false;  // Consume the initial held gesture and its release on every boot.
}

inline bool read(uint8_t addr, uint8_t reg, uint8_t* bytes, uint8_t count) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(addr, count, static_cast<uint8_t>(true)) != count) {
    while (Wire.available()) Wire.read();
    return false;
  }
  for (uint8_t i = 0; i < count; ++i) bytes[i] = Wire.read();
  return true;
}

inline bool sleepTouch() {
  Wire.beginTransmission(0x15);
  Wire.write(0xA5);
  Wire.write(0x03);
  return Wire.endTransmission() == 0;
}

inline bool write16(uint8_t reg, uint16_t value) {
  Wire.beginTransmission(EXPANDER);
  Wire.write(reg);
  Wire.write(static_cast<uint8_t>(value));
  Wire.write(static_cast<uint8_t>(value >> 8));
  return Wire.endTransmission() == 0;
}

inline bool setOutput(uint16_t value) {
  if (!write16(2, value)) return false;
  output = value;
  return true;
}

inline bool begin() {
  if (ready) return true;
  pinMode(44, OUTPUT);
  digitalWrite(44, LOW);       // Keep the motor off until the HAL initializes feedback.
  gpio_hold_dis(GPIO_NUM_44);  // Release the previous deep sleep's LOW hold, including capability-off builds.
  pinMode(46, INPUT_PULLUP);   // SD DAT3/CD: input-only, never part of the 1-bit data bus.
  pinMode(2, INPUT_PULLUP);
  if (!Wire.begin(41, 42, 400000)) return false;
  Wire.setTimeOut(10);
  // Set idle output levels BEFORE enabling the drivers: no low shutdown pulse.
  if (!setOutput(BOOT_OUTPUT) || !write16(6, static_cast<uint16_t>(~OUTPUTS)) || !setOutput(output | SCREEN_POWER))
    return false;
  delay(10);
  if (!setOutput(output | TOUCH_RESET)) return false;
  delay(120);
  ready = true;
  return true;
}

inline uint8_t buttons() {
  static uint32_t nextRead = 0;
  static uint8_t state = 0;
  const uint32_t now = millis();
  if (!ready || static_cast<int32_t>(now - nextRead) < 0) return state;
  uint8_t data[2];
  if (!read(EXPANDER, 0, data, sizeof(data))) {
    nextRead = now + 2000;
    state = 0;  // A failed read must never retain a held key.
    esp_rom_printf("[metalio] TCA9555 input read failed\r\n");
    return state;
  }
  nextRead = now + 20;
  state = ((data[0] & 0x80) ? 0 : (1u << 5)) | ((data[1] & 0x01) ? 0 : (1u << 4));
  return state;
}

inline bool externalPowerConnected(bool& connected) {
  // Read-only CX25601N status. Never run the reference charger's voltage/current init.
  static uint32_t nextRead = 0;
  static bool valid = false;
  static bool cached = false;
  const uint32_t now = millis();
  if (!ready) return false;
  if (static_cast<int32_t>(now - nextRead) >= 0) {
    uint8_t status;
    valid = read(CHARGER, 0x1E, &status, 1);
    if (valid) {
      const uint8_t source = status & 7;
      valid = source != 6;                  // Reserved encoding: leave fallback to the consumer.
      cached = source >= 1 && source <= 5;  // 0 = absent, 7 = OTG output.
    }
    nextRead = now + (valid ? 1000 : 2000);
  }
  if (valid) connected = cached;
  return valid;
}

// Caller has saved state, parked the display and waited for its BUSY completion.
[[noreturn]] inline void shutdown() {
  while (!begin()) {
    esp_rom_printf("[metalio] Power-off initialization failed; retrying\r\n");
    delay(1000);
  }
  esp_rom_printf("[metalio] Power-off pulses until hardware cuts power\r\n");
  constexpr uint32_t PULSE_HALF_MS = 100;
  uint32_t lastError = millis() - 1000;
  for (;;) {
    // Match the reference board: keep MAIN/SCREEN powered, PA off, and pulse forever.
    const uint16_t rails = (output | MAIN_POWER | SCREEN_POWER) & ~PA_POWER;
    const bool highOk = setOutput(rails | POWER_PULSE);
    delay(PULSE_HALF_MS);
    const bool lowOk = setOutput(rails & ~POWER_PULSE);
    delay(PULSE_HALF_MS);
    if ((!highOk || !lowOk) && static_cast<uint32_t>(millis() - lastError) >= 1000) {
      lastError = millis();
      esp_rom_printf("[metalio] Power-off pulse I2C failed; retrying\r\n");
    }
  }
}
}  // namespace freeink::metalio
