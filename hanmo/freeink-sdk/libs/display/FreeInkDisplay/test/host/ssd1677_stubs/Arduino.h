#pragma once
#include <cstdint>
#include <cstring>
#define PROGMEM
inline uint8_t pgm_read_byte(const unsigned char* p) { return *p; }
inline uint32_t ticks = 0;
inline uint32_t millis() { return ticks; }
inline void delay(uint32_t n) { ticks += n; }
inline void esp_rom_printf(const char*, ...) {}
