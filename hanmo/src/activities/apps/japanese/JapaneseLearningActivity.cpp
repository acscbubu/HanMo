#include "JapaneseLearningActivity.h"
#include "KanaActivity.h"
#include "KanaQuizActivity.h"
#include "KanaStrokeActivity.h"
#include "KanaSimilarActivity.h"
#include "JapaneseWordsActivity.h"
#include "JapaneseSentencesActivity.h"
#include "JapaneseReviewActivity.h"

#include <cstdio>

#include <I18n.h>
#include "components/SubpageLayout.h"
#include "components/UITheme.h"

namespace fui = freeink::ui;
namespace {
constexpr std::array<StrId, 7> titles = {
    StrId::STR_JP_KANA, StrId::STR_JP_STROKES, StrId::STR_JP_QUIZ, StrId::STR_JP_SIMILAR,
    StrId::STR_JP_WORDS, StrId::STR_JP_SENTENCES, StrId::STR_JP_REVIEW};
constexpr std::array<StrId, 7> descriptions = {
    StrId::STR_JP_KANA_INFO, StrId::STR_JP_STROKES_INFO, StrId::STR_JP_QUIZ_INFO, StrId::STR_JP_SIMILAR_INFO,
    StrId::STR_JP_WORDS_INFO, StrId::STR_JP_SENTENCES_INFO, StrId::STR_JP_REVIEW_INFO};
// Explicit lookup preserves the user's global UI language without a temporary switch.
const char* jpText(StrId id) { return I18N.get(id); }
}

JapaneseLearningActivity::JapaneseLearningActivity(GfxRenderer& renderer, MappedInputManager& input, int category)
    : UiListActivity("JapaneseLearning", renderer, input),
      category_(category >= 0 && category < CATEGORY_COUNT ? category : -1) {}

const char* JapaneseLearningActivity::headerTitle() const {
  return jpText(category_ < 0 ? StrId::STR_JP_LEARNING : titles[category_]);
}

void JapaneseLearningActivity::onEnter() {
  // One line, not a label plus a subtitle: a subtitle is always drawn on its
  // own row, which is why the device broke this after 返回.
  std::snprintf(backLabel_.data(), backLabel_.size(), "%s%s", jpText(StrId::STR_BACK),
                jpText(category_ < 0 ? StrId::STR_APPS_TITLE : StrId::STR_JP_LEARNING));
  rows_[0].label = backLabel_.data();
  rows_[0].subtitle = nullptr;
  for (int i = 0; i < listCount(); ++i) rows_[i].actionValue = static_cast<int16_t>(i);
  if (category_ < 0) {
    for (int i = 0; i < CATEGORY_COUNT; ++i) rows_[i + 1].label = jpText(titles[i]);
  } else {
    rows_[1].label = jpText(descriptions[category_]);
    rows_[2].label = jpText(StrId::STR_JP_PENDING);
  }
  UiListActivity::onEnter();
}

void JapaneseLearningActivity::onBackButton() {
  app.clearTapFlash();
  if (category_ < 0) activityManager.goToApps();
  else finish();
}

void JapaneseLearningActivity::activateIndex(int index) {
  if (index < 0 || index >= listCount()) return;
  if (index == 0) { onBackButton(); return; }
  if (category_ < 0 && index == 1) {
    app.clearTapFlash();
    if (!startActivityForResultWith<KanaGroupsActivity>([this](const ActivityResult&) { requestUpdate(); })) {
      GUI.drawPopup(renderer, tr(STR_MEMORY_ERROR)); requestUpdate();
    }
    return;
  }
  if (category_ < 0 && index == 2) {
    app.clearTapFlash();
    if (!startActivityForResultWith<KanaStrokeActivity>([this](const ActivityResult&) { requestUpdate(); })) {
      GUI.drawPopup(renderer, tr(STR_MEMORY_ERROR)); requestUpdate();
    }
    return;
  }
  if (category_ < 0 && index == 3) {
    app.clearTapFlash();
    if (!startActivityForResultWith<KanaQuizActivity>([this](const ActivityResult&) { requestUpdate(); })) {
      GUI.drawPopup(renderer, tr(STR_MEMORY_ERROR)); requestUpdate();
    }
    return;
  }
  if (category_ < 0 && index == 4) {
    app.clearTapFlash();
    if (!startActivityForResultWith<KanaSimilarActivity>([this](const ActivityResult&) { requestUpdate(); })) {
      GUI.drawPopup(renderer, tr(STR_MEMORY_ERROR)); requestUpdate();
    }
    return;
  }
  if (category_ < 0 && index == 5) {
    app.clearTapFlash();
    if (!startActivityForResultWith<JapaneseWordsActivity>([this](const ActivityResult&) { requestUpdate(); })) {
      GUI.drawPopup(renderer, tr(STR_MEMORY_ERROR)); requestUpdate();
    }
    return;
  }
  if (category_ < 0 && index == 6) {
    app.clearTapFlash();
    if (!startActivityForResultWith<JapaneseSentencesActivity>([this](const ActivityResult&) { requestUpdate(); })) {
      GUI.drawPopup(renderer, tr(STR_MEMORY_ERROR)); requestUpdate();
    }
    return;
  }
  if (category_ < 0 && index == 7) {
    app.clearTapFlash();
    if (!startActivityForResultWith<JapaneseReviewActivity>([this](const ActivityResult&) { requestUpdate(); })) {
      GUI.drawPopup(renderer, tr(STR_MEMORY_ERROR)); requestUpdate();
    }
    return;
  }
  if (category_ >= 0) return;  // Other explanations are not runnable lessons.
  app.clearTapFlash();
  // Activity helper checks allocation failure; only one category child can be open.
  if (!startActivityForResultWith<JapaneseLearningActivity>(
          [this](const ActivityResult&) { requestUpdate(); }, index - 1)) {
    GUI.drawPopup(renderer, tr(STR_MEMORY_ERROR));
    requestUpdate();
  }
}

void JapaneseLearningActivity::buildScreen(UiScreen& screen) {
  const auto& metrics = UITheme::getInstance().getMetrics();
  const Rect safe = UITheme::getInstance().getScreenSafeArea(renderer, true, true);
  const Rect content = SubpageLayout::contentRect(safe, metrics);
  screen.setContentMarginFromScreen(fui::Insets{
      static_cast<int16_t>(content.y), static_cast<int16_t>(renderer.getScreenWidth() - content.x - content.width),
      static_cast<int16_t>(renderer.getScreenHeight() - content.y - content.height), static_cast<int16_t>(content.x)});
  fui::ListProps props;
  props.items = rows_.data();
  props.count = static_cast<uint16_t>(listCount());
  props.action = ACTION_ROW;
  props.inputMask = fui::InputTouch;
  props.labelText = screen.theme().smallText;
  props.labelText.maxLines = category_ < 0 ? 2 : 4;
  syncListViewport(screen, props, false);
  screen.list(props);
}
