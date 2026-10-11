#pragma once
#include <array>
#include <cstdint>
#include <string>

namespace info_board {
struct Row {
  std::string label, value;
};
struct Data {
  std::array<Row, 3> rows;
  std::string updated;
  bool valid = false;
  int error = 0;
  uint32_t generation = 0;
};
struct Request {
  uint32_t generation = 0;
  uint8_t scene = 0, city = 0;
  std::string url;
};
bool start(Request request);  // one worker only; never holds an Activity pointer
bool take(uint8_t& scene, Data& data);
bool busy();
bool parse(uint8_t scene, const std::string& json, Data& data);
}  // namespace info_board
