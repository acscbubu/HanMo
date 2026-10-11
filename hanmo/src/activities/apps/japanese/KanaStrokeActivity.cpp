#include "KanaStrokeActivity.h"
#include "KanaStroke.h"
#include "KanaStrokeLayout.h"
#include "KanaData.generated.h"
#include "KanaSoundReading.h"

#include <EpdFontFamily.h>
#include <I18n.h>
#include <builtinFonts/hanmo_kana_52.h>
#include <builtinFonts/hanmo_kana_20.h>
#include <algorithm>
#include <cmath>
#include <cstdio>

#include "components/UITheme.h"
#include "fontIds.h"

namespace fui = freeink::ui;
namespace {
const char* text(StrId id) { return I18N.get(id); }
constexpr int kBigFontId = 0x4A510035;
constexpr int kReadingFontId = 0x4A510014;
const EpdFont kBigFont(&hanmo_kana_52);
const EpdFontFamily kBigFamily(&kBigFont);
const EpdFont kReadingFont(&hanmo_kana_20);
const EpdFontFamily kReadingFamily(&kReadingFont);
static_assert(kana::cards.size() == kana::kStrokeCardCount);

int plot(int start, int side, uint16_t coord) { return start + int(coord) * side / 1024; }
}  // namespace

void KanaStrokeActivity::onEnter() {
  Activity::onEnter();
  orientation_ = renderer.getOrientation();
  renderer.setOrientation(GfxRenderer::Orientation::Portrait);
  if (!renderer.getFontMap().count(kBigFontId)) renderer.insertFont(kBigFontId, kBigFamily);
  if (!renderer.getFontMap().count(kReadingFontId)) renderer.insertFont(kReadingFontId, kReadingFamily);
  resetUi();
  app.on(1, &KanaStrokeActivity::event, this);
  app.setScreen(&KanaStrokeActivity::screen, this);
  requestUpdate();
}

void KanaStrokeActivity::onExit() {
  renderer.setOrientation(orientation_);
  Activity::onExit();
}

void KanaStrokeActivity::screen(UiScreen& s, void* p) { static_cast<KanaStrokeActivity*>(p)->build(s); }
void KanaStrokeActivity::event(const fui::ActionEvent& e, void* p) { static_cast<KanaStrokeActivity*>(p)->action(e.value); }

void KanaStrokeActivity::action(int value) {
  if (value == 0) {
    app.clearTapFlash();
    finish();
    return;
  }
  bool changed = false;
  {
    RenderLock lock(*this);
    if (value == 1) changed = lesson_.previousStroke();
    if (value == 2) changed = lesson_.nextStroke();
    if (value == 3) { lesson_.restart(); changed = true; }
    if (value == 4) changed = lesson_.previousCard();
    if (value == 5) changed = lesson_.nextCard();
    if (value == 6) changed = kana_ui::selectScript(lesson_, kana::Script::Hiragana);
    if (value == 7) changed = kana_ui::selectScript(lesson_, kana::Script::Katakana);
  }
  if (changed) requestUpdate();
}

void KanaStrokeActivity::loop() {
  if (mappedInput.wasReleased(MappedInputManager::Button::Back)) { action(0); return; }
  if (routeTouch(mappedInput)) return;
  if (mappedInput.wasReleased(MappedInputManager::Button::Confirm)) { action(2); return; }
  if (mappedInput.wasReleased(MappedInputManager::Button::Left)) { action(1); return; }
  if (mappedInput.wasReleased(MappedInputManager::Button::Right)) { action(2); return; }
  if (mappedInput.wasReleased(MappedInputManager::Button::Up)) { action(4); return; }
  if (mappedInput.wasReleased(MappedInputManager::Button::Down)) action(5);
}

void KanaStrokeActivity::drawGlyph(const kana::GlyphStrokes& glyph, int x, int y, int side) {
  // Trace sampled from the source SVG centerlines. Earlier strokes remain
  // thin; the current stroke is bold. No font outline is interpreted as order.
  for (int si = 0; si < lesson_.visibleStrokes(); ++si) {
    const auto& stroke = glyph.strokes[si];
    const int thickness = si + 1 == lesson_.visibleStrokes() ? 11 : 5;
    for (int part = 0; part < stroke.partCount; ++part) {
      const auto& path = stroke.parts[part];
      for (int point = 1; point < path.pointCount; ++point) {
        const auto a = path.points[point - 1];
        const auto b = path.points[point];
        renderer.drawLine(plot(x, side, a.x), plot(y, side, a.y),
                          plot(x, side, b.x), plot(y, side, b.y), thickness, true);
      }
    }
  }
  const auto& current = glyph.strokes[lesson_.visibleStrokes() - 1];
  const auto& centerline = current.parts[0];
  const auto tip = centerline.points[centerline.pointCount - 1];
  // Draw an end-of-stroke tangent arrow displaced from the outline to avoid
  // hiding its finishing shape, including short curved strokes.
  int i = centerline.pointCount - 2;
  while (i > 0) {
    const auto prev = centerline.points[i];
    const int dx = int(tip.x) - int(prev.x), dy = int(tip.y) - int(prev.y);
    if (dx * dx + dy * dy > 50 * 50) break;
    --i;
  }
  const auto prev = centerline.points[i];
  const float dx = float(int(tip.x) - int(prev.x)), dy = float(int(tip.y) - int(prev.y));
  const float len = std::sqrt(dx * dx + dy * dy);
  if (len < 1) return;
  const float ux = dx / len, uy = dy / len;
  const int tx = plot(x, side, tip.x) + int(-uy * 16);
  const int ty = plot(y, side, tip.y) + int(ux * 16);
  // Clamp arrows to the lesson's image rectangle. The centerline SVG can
  // overhang its viewBox for self-intersections; never draw into controls.
  const int tipX = std::clamp(tx, x + 12, x + side - 12);
  const int tipY = std::clamp(ty, y + 12, y + side - 12);
  const int tailX = tipX - int(ux * 29), tailY = tipY - int(uy * 29);
  const int leftX = tipX - int(ux * 10) + int(uy * 8);
  const int leftY = tipY - int(uy * 10) - int(ux * 8);
  const int rightX = tipX - int(ux * 10) - int(uy * 8);
  const int rightY = tipY - int(uy * 10) + int(ux * 8);
  renderer.drawLine(tailX, tailY, tipX, tipY, 2, true);
  renderer.drawLine(tipX, tipY, leftX, leftY, 2, true);
  renderer.drawLine(tipX, tipY, rightX, rightY, 2, true);
}

void KanaStrokeActivity::build(UiScreen& s) {
  const auto& metrics = UITheme::getInstance().getMetrics();
  s.setContentMarginFromScreen(fui::Insets{int16_t(metrics.topPadding + metrics.headerHeight + 8), 12, 12, 12});
  const auto a = s.body();
  const auto layout = kana_ui::StrokeLayout::forBody(a.x, a.y, a.width, a.height);
  auto button = [&](const char* caption, int v, const kana_ui::Box& b, bool enabled = true, bool selected = false) {
    fui::ButtonProps p;
    p.label = caption;
    p.action = 1;
    p.value = v;
    p.inputMask = fui::InputTouch;
    p.text = s.theme().smallText;
    p.minTouchSize = 48;
    p.enabled = enabled;
    p.state = selected ? fui::StateSelected : fui::StateNormal;
    s.button(p, fui::Rect{int16_t(b.x), int16_t(b.y), int16_t(b.w), int16_t(b.h)});
  };
  auto label = [&](const char* str, int y, int height, bool small = false) {
    auto style = small ? s.theme().smallText : s.theme().bodyText;
    style.align = fui::TextAlign::Center;
    style.maxLines = 2;
    s.target().text(fui::Rect{a.x, int16_t(y), a.width, int16_t(height)}, str, style);
  };
  button(text(StrId::STR_KANA_HIRA), 6, layout.hiragana, true, lesson_.script() == kana::Script::Hiragana);
  button(text(StrId::STR_KANA_KATA), 7, layout.katakana, true, lesson_.script() == kana::Script::Katakana);

  const auto& card = kana::strokeCards[lesson_.cardIndex()];
  const auto& glyph = lesson_.script() == kana::Script::Hiragana ? card.hiragana : card.katakana;
  drawGlyph(glyph, layout.artX, layout.artY, layout.artSide);
  renderer.drawText(kBigFontId, a.x + 12, layout.glyphY, glyph.glyph);
  const auto& basicCard = kana::cards[lesson_.cardIndex()];
  kana::formatSoundReading(basicCard, soundReading_);
  const int glyphWidth = renderer.getTextWidth(kBigFontId, glyph.glyph);
  const int readingWidth = renderer.getTextWidth(kReadingFontId, soundReading_.data());
  const int readingX = kana_ui::centerReadingInColumn(layout.romaji, glyphWidth, readingWidth);
  renderer.drawText(kReadingFontId, readingX, layout.romaji.y, soundReading_.data());
  std::snprintf(position_.data(), position_.size(), text(StrId::STR_KANA_STROKE_NUMBER),
                lesson_.visibleStrokes(), lesson_.strokeCount());
  label(position_.data(), layout.progress.y, layout.progress.h);
  label(text(StrId::STR_KANA_STROKE_HINT), layout.hint.y, layout.hint.h);
  auto sourceStyle = s.theme().smallText;
  sourceStyle.align = fui::TextAlign::Center;
  sourceStyle.maxLines = 1;
  s.target().text(fui::Rect{int16_t(layout.source.x), int16_t(layout.source.y),
                            int16_t(layout.source.w), int16_t(layout.source.h)},
                  text(StrId::STR_KANA_STROKE_SOURCE), sourceStyle);
  button(text(StrId::STR_KANA_STROKE_PREV), 1, layout.previousStroke, lesson_.visibleStrokes() > 1);
  button(text(StrId::STR_KANA_STROKE_RESTART), 3, layout.restart);
  button(text(StrId::STR_KANA_STROKE_NEXT), 2, layout.nextStroke, lesson_.visibleStrokes() < lesson_.strokeCount());
  button(text(StrId::STR_KANA_PREV), 4, layout.previousCard, lesson_.cardIndex() > 0);
  button(text(StrId::STR_BACK), 0, layout.back);
  button(text(StrId::STR_KANA_NEXT), 5, layout.nextCard, lesson_.cardIndex() + 1 < kana::kStrokeCardCount);
}

void KanaStrokeActivity::render(RenderLock&&) {
  renderer.clearScreen();
  const auto& metrics = UITheme::getInstance().getMetrics();
  std::snprintf(progress_.data(), progress_.size(), "%s %d / %d",
                text(lesson_.script() == kana::Script::Hiragana ? StrId::STR_KANA_HIRA : StrId::STR_KANA_KATA),
                lesson_.cardIndex() + 1, kana::kStrokeCardCount);
  GUI.drawHeader(renderer, Rect{0, metrics.topPadding, renderer.getScreenWidth(), metrics.headerHeight},
                 text(StrId::STR_JP_STROKES), progress_.data());
  renderUi();
  renderer.displayBuffer();
}
