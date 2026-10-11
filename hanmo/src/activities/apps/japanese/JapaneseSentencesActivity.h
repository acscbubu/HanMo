#pragma once

#include "JapaneseSentenceProgress.h"
#include "JapaneseSentences.h"
#include "activities/Activity.h"
#include "components/UiAppHost.h"

class JapaneseSentencesActivity final : public Activity, protected UiAppHost {
 public:
  JapaneseSentencesActivity(GfxRenderer& renderer, MappedInputManager& input)
      : Activity("JapaneseSentences", renderer, input), UiAppHost(renderer) {}
  void onEnter() override;
  void onExit() override;
  void loop() override;
  void render(RenderLock&&) override;

 private:
  japanese::Sentences lesson_;
  japanese::sentenceprogress::Progress pending_{};
  japanese::sentenceprogress::Progress progress_{};
  uint16_t dirtyCategories_ = 0;
  bool dirtyLast_ = false;
  bool requireExistingProgress_ = false;
  enum class ProgressStatus { Hint, Saved, StorageError, Corrupt, SaveError };
  ProgressStatus progressStatus_ = ProgressStatus::Hint;
  bool retryNeeded() const {
    return progressStatus_ != ProgressStatus::Hint && progressStatus_ != ProgressStatus::Saved;
  }
  void notePending();
  void savePending();
  bool picker_ = true;
  int selectedCategory_ = 0;
  GfxRenderer::Orientation orientation_ = GfxRenderer::Orientation::Portrait;
  bool addedSentenceFont_ = false;
  bool addedNotesFont_ = false;
  uint8_t releaseBarriers_ = 0;
  void armReleaseBarriers();
  int detailsPage_ = 0;
  int detailsPages_ = 1;
  int pickerPageSize_ = 5;
  void action(int value);
  void build(UiScreen& screen);
  static void screen(UiScreen& screen, void* context);
  static void event(const freeink::ui::ActionEvent& event, void* context);
};
