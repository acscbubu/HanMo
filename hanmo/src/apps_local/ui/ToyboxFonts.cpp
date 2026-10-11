#include "ToyboxFonts.h"

#include <EpdFont.h>
#include <EpdFontFamily.h>
#include <Logging.h>

#include "ToyboxTokens.h"
#include "fonts/public_noto_serif_9.h"
#include "fonts/public_noto_serif_12.h"
#include "fonts/public_noto_serif_22.h"
#include "fonts/reading_serif_11.h"
#include "fonts/reading_serif_14.h"
#include "fonts/reading_serif_bold_12.h"
#include "fonts/reading_serif_bold_16.h"
#include "fonts/public_noto_sans_7.h"
#include "fonts/public_noto_sans_10.h"
#include "fonts/public_noto_sans_15.h"
#include "fonts/public_noto_sans_22.h"
#include "fonts/public_noto_sans_32.h"
#include "fonts/public_noto_sans_47.h"

namespace toybox {
namespace {

// Public-edition Noto cuts; exact source TTF/OFL and generation recipe are retained.
// Monochrome glyphs preserve the renderer bitmap format.
EpdFont display30(&public_noto_sans_22);
EpdFont large44(&public_noto_sans_32);
EpdFont huge64(&public_noto_sans_47);
EpdFont ui20(&public_noto_sans_15);
EpdFont tile10(&public_noto_sans_7);
// Noto Serif, converted at 1 bit by us rather than taken from builtinFonts/.
// The builtin cuts are --2bit, and GfxRenderer's BW path paints a pixel for ANY
// coverage above zero, so they flood to mush -- which is why Toybox has its own
// face at all. Converting the same TTF at 1 bit sidesteps the flooding entirely
// and gives a real text face: The display face has larger cuts,
// and a screenful of it reads as permanently bold.
//
// Noto Serif specifically because it is what the EPUB reader sets books in. An
// app whose surface is a page of prose should look like the rest of this
// device's reading, not like its games.
EpdFont button14(&public_noto_sans_10);
EpdFont reading11(&reading_serif_11);
EpdFont reading14(&reading_serif_14);
EpdFont readingBold12(&reading_serif_bold_12);
EpdFont readingBold16(&reading_serif_bold_16);
EpdFont instrument10(&public_noto_serif_9);
EpdFont instrument13(&public_noto_serif_12);
EpdFont instrument24(&public_noto_serif_22);
EpdFontFamily displayFamily(&display30);
EpdFontFamily largeFamily(&large44);
EpdFontFamily hugeFamily(&huge64);
EpdFontFamily uiFamily(&ui20);
EpdFontFamily tileFamily(&tile10);
EpdFontFamily buttonFamily(&button14);
EpdFontFamily readingSmallFamily(&reading11);
EpdFontFamily readingFamily(&reading14);
EpdFontFamily readingBoldSmallFamily(&readingBold12);
EpdFontFamily readingBoldFamily(&readingBold16);
EpdFontFamily serifTileFamily(&instrument13);
EpdFontFamily serifSmallFamily(&instrument10);
EpdFontFamily serifTitleFamily(&instrument24);

bool registered = false;

}  // namespace

FontMetrics metricsFor(const int fontId) {
  const EpdFontFamily& family = fontId == kHugeFontId               ? hugeFamily
                                : fontId == kLargeFontId            ? largeFamily
                                : fontId == kDisplayFontId          ? displayFamily
                                : fontId == kTileFontId             ? tileFamily
                                : fontId == kButtonFontId           ? buttonFamily
                                : fontId == kReadingBoldFontId      ? readingBoldFamily
                                : fontId == kReadingFontId          ? readingFamily
                                : fontId == kReadingSmallFontId     ? readingSmallFamily
                                : fontId == kReadingBoldSmallFontId ? readingBoldSmallFamily
                                                                    : uiFamily;
  const EpdFontData* data = fontId == kHugeFontId               ? &public_noto_sans_47
                            : fontId == kLargeFontId            ? &public_noto_sans_32
                            : fontId == kDisplayFontId          ? &public_noto_sans_22
                            : fontId == kTileFontId             ? &public_noto_sans_7
                            : fontId == kButtonFontId           ? &public_noto_sans_10
                            : fontId == kReadingBoldFontId      ? &reading_serif_bold_16
                            : fontId == kReadingFontId          ? &reading_serif_14
                            : fontId == kReadingSmallFontId     ? &reading_serif_11
                            : fontId == kReadingBoldSmallFontId ? &reading_serif_bold_12
                                                                : &public_noto_sans_15;
  FontMetrics metrics;
  metrics.ascender = data->ascender;
  // 'H' stands in for cap height: a flat-topped capital with no overshoot, so it
  // measures the band the eye actually aligns to.
  if (const EpdGlyph* glyph = family.getGlyph('H'); glyph != nullptr) {
    metrics.capTop = glyph->top;
    metrics.capHeight = glyph->height;
  }
  return metrics;
}

int drawCapsCentered(const GfxRenderer& renderer, const int fontId, const int x, const int boxY, const int boxH,
                     const char* text, const bool black) {
  const FontMetrics metrics = metricsFor(fontId);
  // Ink top on screen is (y + ascender) - capTop. Solve for the y that puts ink
  // top at the box's centred position.
  const int y = boxY + (boxH - metrics.capHeight) / 2 - metrics.ascender + metrics.capTop;
  renderer.drawText(fontId, x, y, text, black);
  return x;
}

// The cuts, paired with the constants ToyboxTokens.h carries for them.
// Screens are freestanding and cannot see a font, so those constants are the
// only thing standing between a regenerated cut and every centred label in the
// fork drifting at once. Checked here, where the real data is in scope.
void verifyCutMetrics() {
  struct Pair {
    const char* name;
    const EpdFontData* data;
    const EpdFontFamily* family;
    const toybox::CutMetrics* cut;
  };
  const Pair pairs[] = {
      {"public_noto_sans_7", &public_noto_sans_7, &tileFamily, &toybox::kTileCut},
      {"public_noto_sans_10", &public_noto_sans_10, &buttonFamily, &toybox::kButtonCut},
      {"public_noto_sans_15", &public_noto_sans_15, &uiFamily, &toybox::kUiCut},
      {"public_noto_sans_22", &public_noto_sans_22, &displayFamily, &toybox::kDisplayCut},
      {"public_noto_sans_32", &public_noto_sans_32, &largeFamily, &toybox::kLargeCut},
      {"public_noto_sans_47", &public_noto_sans_47, &hugeFamily, &toybox::kHugeCut},
      {"public_noto_serif_9", &public_noto_serif_9, &serifSmallFamily, &toybox::kSerifSmallCut},
      {"public_noto_serif_12", &public_noto_serif_12, &serifTileFamily, &toybox::kSerifTileCut},
      {"public_noto_serif_22", &public_noto_serif_22, &serifTitleFamily, &toybox::kSerifTitleCut},
      {"reading_serif_11", &reading_serif_11, &readingSmallFamily, &toybox::kReadingSmallCut},
      {"reading_serif_14", &reading_serif_14, &readingFamily, &toybox::kReadingCut},
      {"reading_serif_bold_12", &reading_serif_bold_12, &readingBoldSmallFamily, &toybox::kReadingBoldSmallCut},
      {"reading_serif_bold_16", &reading_serif_bold_16, &readingBoldFamily, &toybox::kReadingBoldCut},
  };
  for (const Pair& pair : pairs) {
    const EpdGlyph* glyph = pair.family->getGlyph('H');
    const int ink = glyph != nullptr ? glyph->height : 0;
    if (pair.data->advanceY == pair.cut->lineHeight && pair.data->ascender == pair.cut->ascender &&
        ink == pair.cut->inkHeight) {
      continue;
    }
    LOG_ERR("TOYBOX", "%s moved: advanceY %d/%d ascender %d/%d ink %d/%d -- update CutMetrics in ToyboxTokens.h",
            pair.name, pair.data->advanceY, pair.cut->lineHeight, pair.data->ascender, pair.cut->ascender, ink,
            pair.cut->inkHeight);
  }
}

void ensureFonts(GfxRenderer& renderer) {
  if (registered) return;
  verifyCutMetrics();
  // Registered from here rather than main.cpp so the design language costs zero
  // upstream surface. insertFont is idempotent per id, but the guard keeps this
  // free to call from every activity's onEnter().
  renderer.insertFont(kDisplayFontId, displayFamily);
  renderer.insertFont(kLargeFontId, largeFamily);
  renderer.insertFont(kHugeFontId, hugeFamily);
  renderer.insertFont(kUiFontId, uiFamily);
  renderer.insertFont(kTileFontId, tileFamily);
  renderer.insertFont(kButtonFontId, buttonFamily);
  renderer.insertFont(kReadingFontId, readingFamily);
  renderer.insertFont(kReadingSmallFontId, readingSmallFamily);
  renderer.insertFont(kReadingBoldSmallFontId, readingBoldSmallFamily);
  renderer.insertFont(kReadingBoldFontId, readingBoldFamily);
  renderer.insertFont(kSerifTileFontId, serifTileFamily);
  renderer.insertFont(kSerifSmallFontId, serifSmallFamily);
  renderer.insertFont(kSerifTitleFontId, serifTitleFamily);
  registered = true;
}

}  // namespace toybox
