#include "ImportedMinesweeperRules.h"

namespace imported_minesweeper {
Profile profile(Variant, int difficulty) {
  const int tier = difficulty < 0 ? 0 : (difficulty > 2 ? 2 : difficulty);
  if (tier == 0) return {8, 12, 10};
  return {10, 16, static_cast<uint8_t>(tier == 1 ? 25 : 40)};
}
int defaultDifficulty(Variant) { return 1; }

BoardGeometry fitBoard(Rect content, int rows, int cols) {
  BoardGeometry result{};
  if (rows < 1 || cols < 1 || content.width < cols * 12 || content.height < rows * 12) return result;
  int pitch = content.width / cols;
  if (content.height / rows < pitch) pitch = content.height / rows;
  if (pitch > 48) pitch = 48;
  result.pitch = pitch;
  result.cell = pitch - 6;
  result.rows = rows;
  result.cols = cols;
  result.x = content.x + (content.width - result.width()) / 2;
  result.y = content.y + (content.height - result.height()) / 2;
  return result;
}

bool BoardGeometry::cellAt(int touchX, int touchY, int& row, int& col) const {
  if (pitch == 0 || touchX < x || touchY < y || touchX >= x + width() || touchY >= y + height()) return false;
  col = (touchX - x) / pitch;
  row = (touchY - y) / pitch;
  return (touchX - x) % pitch < cell && (touchY - y) % pitch < cell;
}

int Board::index(int row, int col) const {
  if (row < 0 || col < 0 || row >= settings_.rows || col >= settings_.cols) return -1;
  return row * settings_.cols + col;
}

void Board::reset(Variant variant, int difficulty, uint32_t seed) {
  variant_ = variant;
  settings_ = profile(variant, difficulty);
  phase_ = Phase::Playing;
  random_ = seed == 0 ? 0x9E3779B9u : seed;
  for (int i = 0; i < kMaxCells; ++i) {
    values_[i] = 0;
    states_[i] = CellState::Hidden;
  }
  cursorRow_ = settings_.rows / 2;
  cursorCol_ = settings_.cols / 2;
  flags_ = 0;
  revealed_ = 0;
  placedMines_ = 0;
  minesPlaced_ = false;
}

bool Board::setCursor(int row, int col) {
  if (index(row, col) < 0) return false;
  const bool changed = row != cursorRow_ || col != cursorCol_;
  cursorRow_ = row;
  cursorCol_ = col;
  return changed;
}

bool Board::move(Direction direction) {
  int row = cursorRow_;
  int col = cursorCol_;
  switch (direction) {
    case Direction::Up: --row; break;
    case Direction::Down: ++row; break;
    case Direction::Left: --col; break;
    case Direction::Right: ++col; break;
  }
  return setCursor(row, col);
}

uint32_t Board::nextRandom() {
  random_ ^= random_ << 13;
  random_ ^= random_ >> 17;
  random_ ^= random_ << 5;
  return random_;
}

void Board::placeMines(int safeRow, int safeCol) {
  // Fixed pool, at most 160 bytes on stack; no rejection loop or unbounded RNG.
  uint8_t choices[kMaxCells];
  int count = 0;
  for (int row = 0; row < settings_.rows; ++row) {
    for (int col = 0; col < settings_.cols; ++col) {
      if (row >= safeRow - 1 && row <= safeRow + 1 &&
          col >= safeCol - 1 && col <= safeCol + 1) continue;
      const int candidate = index(row, col);
      // The upstream Biscuit implementation can overwrite a pre-flagged cell.
      // Preserve the user's marker and reduce the bounded mine target only if
      // they flagged so many cells that no legal candidate remains.
      if (states_[candidate] == CellState::Flagged) continue;
      choices[count++] = static_cast<uint8_t>(candidate);
    }
  }
  const int target = count < settings_.mines ? count : settings_.mines;
  placedMines_ = target;
  for (int i = 0; i < target; ++i) {
    const int picked = i + static_cast<int>(nextRandom() % static_cast<uint32_t>(count - i));
    const uint8_t swap = choices[i];
    choices[i] = choices[picked];
    choices[picked] = swap;
    values_[choices[i]] = 9;
  }
  for (int row = 0; row < settings_.rows; ++row) {
    for (int col = 0; col < settings_.cols; ++col) {
      const int target = index(row, col);
      if (values_[target] == 9) continue;
      int adjacent = 0;
      for (int dr = -1; dr <= 1; ++dr) {
        for (int dc = -1; dc <= 1; ++dc) {
          const int near = index(row + dr, col + dc);
          if (near >= 0 && values_[near] == 9) ++adjacent;
        }
      }
      values_[target] = static_cast<uint8_t>(adjacent);
    }
  }
  minesPlaced_ = true;
}

void Board::open(int row, int col) {
  const int first = index(row, col);
  if (first < 0 || states_[first] != CellState::Hidden) return;
  // An empty cell's neighbours are enqueued as soon as marked revealed:
  // no duplicate ever enters the queue, and the 160-byte member bounds work.
  int head = 0;
  int tail = 0;
  states_[first] = CellState::Revealed;
  ++revealed_;
  queue_[tail++] = static_cast<uint8_t>(first);
  while (head < tail) {
    const int at = queue_[head++];
    if (values_[at] != 0) continue;
    const int curRow = at / settings_.cols;
    const int curCol = at % settings_.cols;
    for (int dr = -1; dr <= 1; ++dr) {
      for (int dc = -1; dc <= 1; ++dc) {
        const int near = index(curRow + dr, curCol + dc);
        if (near < 0 || states_[near] != CellState::Hidden || values_[near] == 9) continue;
        states_[near] = CellState::Revealed;
        ++revealed_;
        queue_[tail++] = static_cast<uint8_t>(near);
      }
    }
  }
}

bool Board::won() const { return revealed_ == settings_.rows * settings_.cols - placedMines_; }
void Board::revealAll() {
  for (int i = 0; i < settings_.rows * settings_.cols; ++i) states_[i] = CellState::Revealed;
}

ActionResult Board::confirm(const unsigned long heldMs) {
  if (phase_ != Phase::Playing) return {};
  const int at = index(cursorRow_, cursorCol_);
  if (at < 0) return {};
  if (heldMs >= 500) {
    if (states_[at] == CellState::Hidden) {
      states_[at] = CellState::Flagged;
      ++flags_;
      return {true, false};
    }
    if (states_[at] == CellState::Flagged) {
      states_[at] = CellState::Hidden;
      --flags_;
      return {true, false};
    }
    return {};
  }
  if (states_[at] != CellState::Hidden) return {};
  const bool fresh = !minesPlaced_;
  if (fresh) placeMines(cursorRow_, cursorCol_);
  if (values_[at] == 9) {
    phase_ = Phase::Lost;
    revealAll();
  } else {
    open(cursorRow_, cursorCol_);
    if (won()) { phase_ = Phase::Won; revealAll(); }
  }
  return {true, fresh};
}

bool Board::isMine(int row, int col) const {
  const int at = index(row, col);
  return at >= 0 && values_[at] == 9;
}
CellState Board::state(int row, int col) const {
  const int at = index(row, col);
  return at >= 0 ? states_[at] : CellState::Hidden;
}
int Board::adjacent(int row, int col) const {
  const int at = index(row, col);
  return at < 0 ? -1 : values_[at];
}

}  // namespace imported_minesweeper
