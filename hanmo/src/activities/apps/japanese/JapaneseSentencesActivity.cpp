#include "JapaneseSentencesActivity.h"

#include <EpdFontFamily.h>
#include <I18n.h>
#include <Utf8.h>
#include <builtinFonts/hanmo_dialogues_20.h>
#include <builtinFonts/hanmo_sentence_notes_12.h>

#include <algorithm>
#include <cstdio>
#include <cstring>

#include "JapaneseDialogues.generated.h"
#include "JapaneseSentenceProgressStore.h"
#include "components/SubpageLayout.h"
#include "components/UITheme.h"
#include "fontIds.h"

namespace fui = freeink::ui;
namespace {
constexpr int kSentenceFontId = 0x4A540014;
constexpr int kNotesFontId = 0x4A53100C;
const EpdFont kSentenceFont(&hanmo_dialogues_20);
const EpdFontFamily kSentenceFamily(&kSentenceFont);
const EpdFont kNotesFont(&hanmo_sentence_notes_12);
const EpdFontFamily kNotesFamily(&kNotesFont);
const char* text(StrId id) { return I18N.get(id); }
constexpr MappedInputManager::Button kBarrierButtons[] = {
    MappedInputManager::Button::Back,  MappedInputManager::Button::Confirm, MappedInputManager::Button::Left,
    MappedInputManager::Button::Right, MappedInputManager::Button::Up,      MappedInputManager::Button::Down};
constexpr StrId kCategoryLabels[] = {
    StrId::STR_JP_DIALOGUES_BASIC,      StrId::STR_JP_DIALOGUES_DAILY,     StrId::STR_JP_DIALOGUES_RESTAURANT,
    StrId::STR_JP_DIALOGUES_SHOPPING,   StrId::STR_JP_DIALOGUES_TRANSPORT, StrId::STR_JP_DIALOGUES_HOTEL,
    StrId::STR_JP_DIALOGUES_DIRECTIONS, StrId::STR_JP_DIALOGUES_SOCIAL,    StrId::STR_JP_DIALOGUES_EMERGENCY};
// Direct renderer IDs are 32-bit; FreeInkUI FontId is 16-bit. Never put these
// dedicated font families in TextStyle. Width also reserves trailing advances.
int conservativeWidth(const GfxRenderer& renderer, int id, const char* value) {
  const auto& family = renderer.getFontMap().at(id);
  const auto* cursor = reinterpret_cast<const uint8_t*>(value);
  uint32_t cp = 0, previous = 0;
  int advance = 0;
  while ((cp = utf8NextCodepoint(&cursor))) {
    const auto* glyph = family.getGlyph(cp);
    if (!glyph) continue;
    advance += fp4::toPixel(glyph->advanceX + (previous ? family.getKerning(previous, cp) : 0));
    previous = cp;
  }
  return std::max(advance, renderer.getTextWidth(id, value));
}
// Bounded UTF-8 wrapping, with no heap allocation and no truncation. Each
// callback consumes its row synchronously; at most 192 bytes live on the stack.
template <typename Row>
int wrapped(const GfxRenderer& renderer, int id, const char* value, int width, Row row) {
  char line[192]{};
  int length = 0, count = 0;
  const char* cursor = value;
  while (*cursor) {
    const auto* next = reinterpret_cast<const uint8_t*>(cursor);
    utf8NextCodepoint(&next);
    const int bytes = static_cast<int>(reinterpret_cast<const char*>(next) - cursor);
    if (length + bytes >= static_cast<int>(sizeof(line))) {
      row(line, count++);
      length = 0;
    }
    std::memcpy(line + length, cursor, bytes);
    line[length + bytes] = '\0';
    if (length && conservativeWidth(renderer, id, line) > width) {
      line[length] = '\0';
      row(line, count++);
      std::memcpy(line, cursor, bytes);
      length = 0;
    }
    length += bytes;
    line[length] = '\0';
    cursor = reinterpret_cast<const char*>(next);
  }
  if (length) row(line, count++);
  return count;
}
}  // namespace

void JapaneseSentencesActivity::onEnter() {
  Activity::onEnter();
  orientation_ = renderer.getOrientation();
  renderer.setOrientation(GfxRenderer::Orientation::Portrait);
  addedSentenceFont_ = !renderer.getFontMap().count(kSentenceFontId);
  if (addedSentenceFont_) renderer.insertFont(kSentenceFontId, kSentenceFamily);
  addedNotesFont_ = !renderer.getFontMap().count(kNotesFontId);
  if (addedNotesFont_) renderer.insertFont(kNotesFontId, kNotesFamily);
  picker_ = true;
  progress_ = {};
  using namespace japanese::sentenceprogress;
  const auto loaded = loadProgress(Storage, progress_);
  requireExistingProgress_ = loaded == LoadStatus::Loaded || loaded == LoadStatus::Corrupt;
  progressStatus_ = loaded == LoadStatus::StorageError ? ProgressStatus::StorageError
                    : loaded == LoadStatus::Corrupt    ? ProgressStatus::Corrupt
                    : loaded == LoadStatus::Loaded     ? ProgressStatus::Saved
                                                       : ProgressStatus::Hint;
  pending_ = progress_;
  dirtyCategories_ = 0;
  dirtyLast_ = false;
  selectedCategory_ = progress_.lastCategory;
  lesson_.selectCategory(selectedCategory_, pending_.positions[selectedCategory_]);
  releaseBarriers_ = 0;
  armReleaseBarriers();
  resetUi();
  app.on(1, &JapaneseSentencesActivity::event, this);
  app.setScreen(&JapaneseSentencesActivity::screen, this);
  requestUpdate();
}

void JapaneseSentencesActivity::onExit() {
  closeRouting();
  app.clearTapFlash();
  if (addedSentenceFont_) renderer.removeFont(kSentenceFontId);
  if (addedNotesFont_) renderer.removeFont(kNotesFontId);
  addedSentenceFont_ = addedNotesFont_ = false;
  renderer.setOrientation(orientation_);
  Activity::onExit();
}

void JapaneseSentencesActivity::render(RenderLock&&) {
  renderer.clearScreen();
  const auto& metrics = UITheme::getInstance().getMetrics();
  char progress[24];
  std::snprintf(progress, sizeof(progress), "%d / %d", lesson_.position() + 1, lesson_.count());
  GUI.drawHeader(renderer, Rect{0, metrics.topPadding, renderer.getScreenWidth(), metrics.headerHeight},
                 text(picker_ ? StrId::STR_JP_DIALOGUES_PICK : kCategoryLabels[lesson_.category()]),
                 picker_ ? "" : progress);
  renderUi();
  renderer.displayBuffer();
}

void JapaneseSentencesActivity::notePending() {
  const int category = lesson_.category();
  pending_.positions[category] = static_cast<uint8_t>(lesson_.position());
  pending_.lastCategory = static_cast<uint8_t>(category);
  if (lesson_.revealed()) {
    const int global = lesson_.globalPosition();
    pending_.readBits[global / 8] |= static_cast<uint8_t>(1u << (global % 8));
  }
  dirtyCategories_ |= static_cast<uint16_t>(1u << category);
  dirtyLast_ = true;
  if (!retryNeeded()) savePending();
}

void JapaneseSentencesActivity::savePending() {
  using namespace japanese::sentenceprogress;
  Progress latest;
  const auto loaded = loadProgress(Storage, latest);
  if (loaded == LoadStatus::Corrupt || loaded == LoadStatus::StorageError) {
    if (loaded == LoadStatus::Corrupt) requireExistingProgress_ = true;
    progressStatus_ = loaded == LoadStatus::Corrupt ? ProgressStatus::Corrupt : ProgressStatus::StorageError;
    return;
  }
  if ((requireExistingProgress_ && loaded != LoadStatus::Loaded) || latest.revision < progress_.revision) {
    progressStatus_ = ProgressStatus::SaveError;
    return;
  }
  for (int i = 0; i < kReadBytes; ++i) {
    if ((latest.readBits[i] & progress_.readBits[i]) != progress_.readBits[i]) {
      progressStatus_ = ProgressStatus::SaveError;
      return;
    }
  }
  if (loaded == LoadStatus::Loaded) requireExistingProgress_ = true;
  auto desired = latest;
  for (int i = 0; i < kReadBytes; ++i) desired.readBits[i] |= pending_.readBits[i];
  for (int i = 0; i < kCategoryCount; ++i)
    if (dirtyCategories_ & (1u << i)) desired.positions[i] = pending_.positions[i];
  if (dirtyLast_) desired.lastCategory = pending_.lastCategory;
  // An uncertain earlier commit is acknowledged without a second event/write.
  const bool effective = desired.readBits != latest.readBits || desired.positions != latest.positions ||
                         desired.lastCategory != latest.lastCategory;
  if (effective) {
    desired = latest;
    if (!mergePending(desired, pending_, dirtyCategories_, dirtyLast_) || !saveProgress(Storage, desired, &latest)) {
      progressStatus_ = ProgressStatus::SaveError;
      return;  // Explicit Retry only; leave displayed scene/reveal and all pending data intact.
    }
    latest = desired;
    requireExistingProgress_ = true;
  }
  progress_ = pending_ = latest;
  dirtyCategories_ = 0;
  dirtyLast_ = false;
  progressStatus_ = requireExistingProgress_ ? ProgressStatus::Saved : ProgressStatus::Hint;
}

void JapaneseSentencesActivity::action(int value) {
  if (value == 0 && picker_) {
    closeRouting();
    app.clearTapFlash();
    finish();
    return;
  }
  bool changed = false;
  {
    RenderLock lock(*this);
    if (value == 5 && !picker_ && lesson_.revealed() && detailsPages_ > 1) {
      detailsPage_ = (detailsPage_ + 1) % detailsPages_;
      changed = true;
    } else if (value == 4 && retryNeeded()) {
      savePending();
      changed = true;
    } else if (value == 0) {
      picker_ = true;
      changed = true;
    } else if (picker_ && value >= 10 && value < 19) {
      selectedCategory_ = value - 10;
      lesson_.selectCategory(selectedCategory_, pending_.positions[selectedCategory_]);
      picker_ = false;
      changed = true;
      detailsPage_ = 0;
      notePending();
    } else if (picker_ && (value == 6 || value == 7)) {
      const int selected = std::clamp(selectedCategory_ + (value == 6 ? -1 : 1), 0, 8);
      changed = selected != selectedCategory_;
      selectedCategory_ = selected;
    } else if (!picker_) {
      if (value == 1) changed = lesson_.previous();
      if (value == 3) changed = lesson_.next();
      if (value == 2) {
        lesson_.toggleReveal();
        changed = true;
      }
      if (changed) detailsPage_ = 0;
      if (changed && (value != 2 || lesson_.revealed())) notePending();
    }
    if (changed) {
      armReleaseBarriers();
      closeRouting();
      app.clearTapFlash();
    }
  }
  if (changed) requestUpdate();
}

void JapaneseSentencesActivity::armReleaseBarriers() {
  for (int i = 0; i < 6; ++i)
    if (mappedInput.isPressed(kBarrierButtons[i])) releaseBarriers_ |= static_cast<uint8_t>(1u << i);
}

void JapaneseSentencesActivity::loop() {
  using Button = MappedInputManager::Button;
  const uint8_t inherited = releaseBarriers_;
  for (int i = 0; i < 6; ++i)
    if (!mappedInput.isPressed(kBarrierButtons[i])) releaseBarriers_ &= static_cast<uint8_t>(~(1u << i));
  if (!(inherited & 1u) && mappedInput.wasReleased(Button::Back)) {
    action(0);
    return;
  }
  const bool active = app.touchActive();
  const auto touch = routeTouch(mappedInput);
  if (touch.routed) {
    if (app.invalidated() || active != app.touchActive()) requestUpdate();
    return;
  }
  if (inherited) return;
  if (retryNeeded() && mappedInput.wasReleased(Button::Up)) {
    action(4);
    return;
  }
  if (picker_) {
    if (mappedInput.wasReleased(Button::Left) || mappedInput.wasReleased(Button::Up)) {
      action(6);
      return;
    }
    if (mappedInput.wasReleased(Button::Right) || mappedInput.wasReleased(Button::Down)) {
      action(7);
      return;
    }
    if (mappedInput.wasReleased(Button::Confirm)) action(10 + selectedCategory_);
  } else {
    if (mappedInput.wasReleased(Button::Down)) {
      action(5);
      return;
    }
    if (mappedInput.wasReleased(Button::Left)) {
      action(1);
      return;
    }
    if (mappedInput.wasReleased(Button::Right)) {
      action(3);
      return;
    }
    if (mappedInput.wasReleased(Button::Confirm)) action(2);
  }
}

void JapaneseSentencesActivity::screen(UiScreen& screen, void* context) {
  static_cast<JapaneseSentencesActivity*>(context)->build(screen);
}
void JapaneseSentencesActivity::event(const fui::ActionEvent& event, void* context) {
  static_cast<JapaneseSentencesActivity*>(context)->action(event.value);
}
void JapaneseSentencesActivity::build(UiScreen& screen) {
  const auto& metrics = UITheme::getInstance().getMetrics();
  const auto safeArea = SubpageLayout::insetHorizontal(UITheme::getInstance().getScreenSafeArea(renderer), 12);
  const auto content = SubpageLayout::contentRect(safeArea, metrics, false, std::max(0, 12 - metrics.verticalSpacing));
  screen.setContentMarginFromScreen(
      fui::Insets{int16_t(content.y), int16_t(renderer.getScreenWidth() - content.x - content.width),
                  int16_t(renderer.getScreenHeight() - content.y - content.height), int16_t(content.x)});
  const auto body = screen.body();
  // Match the active FreeInkUI small slot: it is UI_10/UI_12, not the
  // unrelated SMALL_FONT_ID, and changes with the user's UI text size.
  const int uiHeight = uiTarget.lineHeight(fui::GfxRendererTarget::FONT_SMALL);
  const int sentenceHeight = renderer.getLineHeight(kSentenceFontId);
  const int notesHeight = renderer.getLineHeight(kNotesFontId);
  const int gap = std::max(6, SubpageLayout::relatedGap(metrics));
  const int buttonHeight = std::max(44, 2 * uiHeight + 16);
  const int half = (body.width - gap) / 2;
  auto button = [&](const char* label, int value, int x, int y, int width, bool enabled) {
    fui::ButtonProps props;
    props.action = 1;
    props.value = value;
    props.label = label;
    props.inputMask = fui::InputTouch;
    props.minTouchSize = 44;
    props.enabled = enabled;
    props.text = screen.theme().smallText;
    props.text.maxLines = 2;
    props.styles = screen.theme().button;
    props.styles.disabled.foreground = fui::Paint::solid(fui::Color::LightGray);
    screen.button(props, fui::Rect{int16_t(x), int16_t(y), int16_t(width), int16_t(buttonHeight)});
  };
  auto label = [&](const char* value, int y) {
    auto style = screen.theme().smallText;
    style.maxLines = 1;
    style.align = fui::TextAlign::Center;
    screen.target().text(fui::Rect{body.x, int16_t(y), body.width, int16_t(uiHeight)}, value, style);
  };
  const StrId status = progressStatus_ == ProgressStatus::Saved          ? StrId::STR_JP_REVIEW_SAVED
                       : progressStatus_ == ProgressStatus::StorageError ? StrId::STR_JP_REVIEW_STORAGE_ERROR
                       : progressStatus_ == ProgressStatus::Corrupt      ? StrId::STR_JP_REVIEW_CORRUPT
                       : progressStatus_ == ProgressStatus::SaveError    ? StrId::STR_JP_REVIEW_SAVE_ERROR
                                                                         : StrId::STR_JP_SENTENCES_SESSION;
  const int bottomY = body.bottom() - buttonHeight;
  if (picker_) {
    const int retryY = bottomY - gap - buttonHeight;
    const int statusY = retryY - gap - uiHeight;
    pickerPageSize_ = std::clamp((statusY - gap - body.y) / (buttonHeight + gap), 1, 5);
    const int first = selectedCategory_ / pickerPageSize_ * pickerPageSize_;
    for (int i = first; i < std::min(first + pickerPageSize_, 9); ++i) {
      char row[128];
      std::snprintf(row, sizeof(row), "%s%s  %d / %d", selectedCategory_ == i ? "> " : "", text(kCategoryLabels[i]),
                    japanese::sentenceprogress::readCount(progress_, i), japanese::Sentences::categorySize(i));
      button(row, 10 + i, body.x, body.y + (i - first) * (buttonHeight + gap), body.width, true);
    }
    // Selection controls are paged through the same nine bounded categories.
    const int third = (body.width - 2 * gap) / 3;
    button(text(StrId::STR_BACK), 0, body.x, bottomY, third, true);
    button(text(StrId::STR_KANA_PREV), 6, body.x + third + gap, bottomY, third, selectedCategory_ > 0);
    button(text(StrId::STR_KANA_NEXT), 7, body.x + 2 * (third + gap), bottomY, body.width - 2 * (third + gap),
           selectedCategory_ < 8);
    if (retryNeeded()) button(text(StrId::STR_JP_REVIEW_RETRY), 4, body.x, retryY, body.width, true);
    label(text(status), statusY);
    return;
  }
  // Three fixed control rows keep Japanese still when revealing or failing a
  // save. Retry and detail pagination share the upper row, never a fourth row.
  const int firstY = bottomY - gap - buttonHeight;
  const int extraY = firstY - gap - buttonHeight;
  const int statusY = extraY - gap - uiHeight;
  const int progressY = statusY - gap - uiHeight;
  button(text(StrId::STR_BACK), 0, body.x, firstY, half, true);
  button(text(lesson_.revealed() ? StrId::STR_JP_SENTENCES_HIDE : StrId::STR_JP_SENTENCES_REVEAL), 2,
         body.x + half + gap, firstY, body.width - half - gap, true);
  button(text(StrId::STR_KANA_PREV), 1, body.x, bottomY, half, lesson_.canPrevious());
  button(text(StrId::STR_KANA_NEXT), 3, body.x + half + gap, bottomY, body.width - half - gap, lesson_.canNext());
  if (retryNeeded()) button(text(StrId::STR_JP_REVIEW_RETRY), 4, body.x, extraY, half, true);

  const auto& card = japanese::dialogues::cards[lesson_.globalPosition()];
  const bool dialogue = *card.b.japanese;
  const int markerWidth = dialogue ? conservativeWidth(renderer, kNotesFontId, "A") + gap : 0;
  const int japaneseWidth = body.width - markerWidth;
  int japaneseY = body.y;
  for (const auto* line : {&card.a, &card.b}) {
    if (!*line->japanese) continue;
    if (dialogue) renderer.drawText(kNotesFontId, body.x, japaneseY, line == &card.a ? "A" : "B");
    const int rows = wrapped(renderer, kSentenceFontId, line->japanese, japaneseWidth, [&](const char* value, int row) {
      renderer.drawText(kSentenceFontId, body.x + markerWidth, japaneseY + row * sentenceHeight, value);
    });
    japaneseY += rows * sentenceHeight + gap;
  }
  // At least one readable notes line fits below the complete Japanese block
  // on supported portrait devices. Paginate ALL rows, not clipped maxLines.
  const int detailHeight = progressY - gap - japaneseY;
  const int rowsPerPage = std::max(1, detailHeight / notesHeight);
  int total = 0;
  auto details = [&](auto row) {
    for (const auto* line : {&card.a, &card.b}) {
      if (!*line->japanese) continue;
      if (std::strcmp(line->kanaReading, line->japanese))
        wrapped(renderer, kNotesFontId, line->kanaReading, body.width, row);
      wrapped(renderer, kNotesFontId, line->romaji, body.width, row);
      wrapped(renderer, kNotesFontId, line->meaning, body.width, row);
    }
    for (const auto* note : card.grammarNotes) wrapped(renderer, kNotesFontId, note, body.width, row);
  };
  if (lesson_.revealed()) {
    // Count and paint in the same pass. Hidden answers need no wrapping, and
    // a visible page should not measure every detail line twice. No cache or
    // new heap allocation: each row is consumed synchronously as before.
    detailsPage_ = std::max(0, detailsPage_);
    auto paintDetails = [&] {
      total = 0;
      details([&](const char* value, int) {
        const int relative = total++ - detailsPage_ * rowsPerPage;
        if (relative >= 0 && relative < rowsPerPage)
          renderer.drawText(kNotesFontId, body.x, japaneseY + relative * notesHeight, value);
      });
    };
    paintDetails();
    detailsPages_ = std::max(1, (total + rowsPerPage - 1) / rowsPerPage);
    if (detailsPage_ >= detailsPages_) {
      // A layout change may invalidate the old page. Nothing was painted for
      // that out-of-range page; redraw only this uncommon clamp case.
      detailsPage_ = detailsPages_ - 1;
      paintDetails();
    }
    char caption[96];
    std::snprintf(caption, sizeof(caption), "%s %d / %d", text(StrId::STR_JP_DIALOGUES_DETAILS), detailsPage_ + 1,
                  detailsPages_);
    button(caption, 5, body.x + half + gap, extraY, body.width - half - gap, detailsPages_ > 1);
  } else {
    auto style = screen.theme().smallText;
    style.maxLines = 2;
    screen.target().text(fui::Rect{body.x, int16_t(japaneseY), body.width, int16_t(std::max(0, detailHeight))},
                         text(StrId::STR_JP_SENTENCES_PROMPT), style);
  }
  char readProgress[96];
  std::snprintf(readProgress, sizeof(readProgress), "%s %d / %d", text(StrId::STR_JP_SENTENCES_PROGRESS),
                japanese::sentenceprogress::readCount(progress_, lesson_.category()), lesson_.count());
  label(readProgress, progressY);
  label(text(status), statusY);
}
