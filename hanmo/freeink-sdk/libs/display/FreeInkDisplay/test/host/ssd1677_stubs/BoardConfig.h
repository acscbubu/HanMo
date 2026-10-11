#pragma once
#include <MurphyM4Batch.h>
namespace BoardConfig {
enum class Board { XteinkX4, XteinkX4Pro, Sticky, WaveshareEpaper397, MetalioEink4 };
struct Profile {
  Board board = Board::MetalioEink4;
  unsigned displayWidth = 32, displayHeight = 8, displaySpiHz = 10000000;
  struct {
    bool mirrorX = false, mirrorY = false;
  } orientation;
};
inline Profile ACTIVE;
}  // namespace BoardConfig
