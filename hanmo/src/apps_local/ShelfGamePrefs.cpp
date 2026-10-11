#include "ShelfGamePrefs.h"

#include <cstdio>
#include <cstring>

#include "ShelfState.h"

namespace shelf {
namespace {
constexpr char kMagic[] = "SGP1\n";
constexpr uint32_t kOffset = 2166136261u;
constexpr uint32_t kPrime = 16777619u;

uint32_t checksum(const char* text, size_t size) {
  uint32_t value = kOffset;
  for (size_t i = 0; i < size; ++i) value = (value ^ static_cast<uint8_t>(text[i])) * kPrime;
  return value;
}

int hexValue(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  return -1;
}
}  // namespace

GamePrefs::GamePrefs(const char* const* titles, int count) : titles_(titles), count_(count) {
  if (titles == nullptr || count < 0) count_ = 0;
  if (count_ > kMaxGames) count_ = kMaxGames;
  for (int i = 0; i < count_; ++i) order_[i] = static_cast<uint8_t>(i);
}

int GamePrefs::position(int item) const {
  if (!valid(item)) return -1;
  for (int i = 0; i < count_; ++i)
    if (order_[i] == item) return i;
  return -1;
}

bool GamePrefs::isFavorite(int item) const { return valid(item) && favorites_[item]; }

bool GamePrefs::setFavorite(int item, bool on) {
  if (!valid(item) || favorites_[item] == on) return false;
  favorites_[item] = on;
  return true;
}

bool GamePrefs::moveUp(int item) {
  const int at = position(item);
  if (at < 0) return false;
  for (int i = at - 1; i >= 0; --i) {
    if (favorites_[order_[i]] != favorites_[item]) continue;
    const uint8_t temp = order_[i];
    order_[i] = order_[at];
    order_[at] = temp;
    return true;
  }
  return false;
}

bool GamePrefs::moveDown(int item) {
  const int at = position(item);
  if (at < 0) return false;
  for (int i = at + 1; i < count_; ++i) {
    if (favorites_[order_[i]] != favorites_[item]) continue;
    const uint8_t temp = order_[i];
    order_[i] = order_[at];
    order_[at] = temp;
    return true;
  }
  return false;
}

bool GamePrefs::moveToTop(int item) {
  const int at = position(item);
  if (at < 0) return false;
  int first = at;
  for (int i = at - 1; i >= 0; --i)
    if (favorites_[order_[i]] == favorites_[item]) first = i;
  if (at == first) return false;
  const uint8_t held = order_[at];
  for (int i = at; i > first; --i) order_[i] = order_[i - 1];
  order_[first] = held;
  return true;
}

bool GamePrefs::moveAheadOf(int item, int neighbor) {
  if (!valid(item) || !valid(neighbor)) return false;
  const int from = position(item);
  const int to = position(neighbor);
  if (from <= to || favorites_[item] != favorites_[neighbor]) return false;
  const uint8_t held = order_[from];
  for (int i = from; i > to; --i) order_[i] = order_[i - 1];
  order_[to] = held;
  return true;
}

bool GamePrefs::moveBehind(int item, int neighbor) {
  if (!valid(item) || !valid(neighbor)) return false;
  const int from = position(item);
  const int to = position(neighbor);
  if (to <= from || favorites_[item] != favorites_[neighbor]) return false;
  const uint8_t held = order_[from];
  for (int i = from; i < to; ++i) order_[i] = order_[i + 1];
  order_[to] = held;
  return true;
}

std::string GamePrefs::format() const {
  std::string out(kMagic);
  out.reserve(sizeof(kMagic) + static_cast<size_t>(count_) * 30 + 16);
  for (int pos = 0; pos < count_; ++pos) {
    const int item = order_[pos];
    out += favorites_[item] ? "F\t" : "N\t";
    out += titles_[item];
    out += '\n';
  }
  char footer[16];
  std::snprintf(footer, sizeof(footer), "END\t%08X\n", checksum(out.data(), out.size()));
  out += footer;
  return out;
}

bool GamePrefs::parse(const char* text, size_t size) {
  if (!text || size < sizeof(kMagic) + 12 || size > kMaxFileBytes || std::memcmp(text, kMagic, sizeof(kMagic) - 1) != 0)
    return false;
  constexpr size_t kFooterSize = sizeof("END\t00000000\n") - 1;
  if (size < sizeof(kMagic) - 1 + kFooterSize) return false;
  const size_t footer = size - kFooterSize;
  if (std::memcmp(text + footer, "END\t", 4) != 0 || text[size - 1] != '\n') return false;
  uint32_t expected = 0;
  for (size_t i = footer + 4; i < size - 1; ++i) {
    const int digit = hexValue(text[i]);
    if (digit < 0) return false;
    expected = (expected << 4) | static_cast<uint32_t>(digit);
  }
  if (expected != checksum(text, footer)) return false;

  uint8_t nextOrder[kMaxGames] = {};
  bool nextFavorites[kMaxGames] = {};
  bool seen[kMaxGames] = {};
  int taken = 0;
  size_t start = sizeof(kMagic) - 1;
  while (start < footer) {
    size_t end = start;
    while (end < footer && text[end] != '\n') ++end;
    if (end == footer || end - start < 3 || (text[start] != 'F' && text[start] != 'N') || text[start + 1] != '\t' ||
        end - start - 2 > MAX_ITEM_TITLE)
      return false;
    const char* title = text + start + 2;
    const size_t len = end - start - 2;
    if (len == 0) return false;
    for (size_t i = 0; i < len; ++i)
      if (title[i] < ' ' || title[i] == '\t' || title[i] > '~') return false;
    for (int i = 0; i < count_; ++i) {
      if (std::strlen(titles_[i]) != len || std::memcmp(title, titles_[i], len) != 0) continue;
      if (seen[i]) return false;
      seen[i] = true;
      nextFavorites[i] = text[start] == 'F';
      nextOrder[taken++] = static_cast<uint8_t>(i);
      break;
    }
    start = end + 1;
  }
  // Unknown titles disappear from the active ordering, but don't leave holes:
  // append all newly added games in the registry's order.
  for (int i = 0; i < count_; ++i)
    if (!seen[i]) nextOrder[taken++] = static_cast<uint8_t>(i);
  for (int i = 0; i < count_; ++i) {
    order_[i] = nextOrder[i];
    favorites_[i] = nextFavorites[i];
  }
  return true;
}
}  // namespace shelf
