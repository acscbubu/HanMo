#pragma once

#include <array>
#include <cstdio>
#include <cstring>
#include "KanaData.generated.h"

namespace kana {
// Match the existing 50-sound card reading; a parenthesized sound hint
// attaches directly to the romaji. This is a phonetic hint, not a translation.
template <size_t N>
void formatSoundReading(const Card& card, std::array<char, N>& out) {
  static_assert(N >= 64, "room for authored card sound hints");
  const bool parenthesized = std::strncmp(card.soundHint, "（", 3) == 0;
  std::snprintf(out.data(), out.size(), "%s%s%s", card.romaji,
                parenthesized ? "" : " ", card.soundHint);
}
}  // namespace kana
