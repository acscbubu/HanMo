#pragma once
#include <cstdint>

namespace imported_minesweeper {
// Only the Biscuit rules are supported.
enum class Variant : uint8_t { Biscuit };
struct Profile { uint8_t cols; uint8_t rows; uint8_t mines; };
Profile profile(Variant variant, int difficulty);
int defaultDifficulty(Variant variant);

struct Rect { int x, y, width, height; };
struct BoardGeometry {
  int x = 0, y = 0, pitch = 0, cell = 0, rows = 0, cols = 0;
  int width() const { return cols * pitch; }
  int height() const { return rows * pitch; }
  bool cellAt(int x, int y, int& row, int& col) const;
};
BoardGeometry fitBoard(Rect content, int rows, int cols);

enum class CellState : uint8_t { Hidden, Flagged, Revealed };
enum class Phase : uint8_t { Playing, Won, Lost };
enum class Direction : uint8_t { Up, Down, Left, Right };
struct ActionResult { bool changed = false; bool minesPlaced = false; };

// Source-derived rules, bounded to the largest original grid (10x16).
// No saves, renderer, SDK, or heap.
class Board {
 public:
  static constexpr int kMaxCells = 160;
  void reset(Variant variant, int difficulty, uint32_t seed);
  Profile settings() const { return settings_; }
  Variant variant() const { return variant_; }
  Phase phase() const { return phase_; }
  bool minesPlaced() const { return minesPlaced_; }
  int flagCount() const { return flags_; }
  int mineCount() const { return placedMines_; }
  int revealedCount() const { return revealed_; }
  int cursorRow() const { return cursorRow_; }
  int cursorCol() const { return cursorCol_; }
  bool setCursor(int row, int col);
  bool move(Direction direction);
  ActionResult confirm(unsigned long heldMs);
  bool isMine(int row, int col) const;
  bool isFlagged(int row, int col) const { return state(row, col) == CellState::Flagged; }
  CellState state(int row, int col) const;
  int adjacent(int row, int col) const;

 private:
  int index(int row, int col) const;
  uint32_t nextRandom();
  void placeMines(int safeRow, int safeCol);
  void open(int row, int col);
  void revealAll();
  bool won() const;

  Variant variant_ = Variant::Biscuit;
  Profile settings_{10, 16, 25};
  Phase phase_ = Phase::Playing;
  uint32_t random_ = 1;
  uint8_t values_[kMaxCells]{};   // 0..8 adjacent, 9 = mine
  CellState states_[kMaxCells]{};
  uint8_t queue_[kMaxCells]{};    // BFS: enqueue only once, so never overflows
  int cursorRow_ = 0;
  int cursorCol_ = 0;
  int flags_ = 0;
  int revealed_ = 0;
  int placedMines_ = 0;
  bool minesPlaced_ = false;
};
}  // namespace imported_minesweeper
