#pragma once
#include <array>

#include "JapaneseReview.h"
#include "activities/Activity.h"
#include "components/UiAppHost.h"

class JapaneseReviewActivity final : public Activity, protected UiAppHost {
 public:
  JapaneseReviewActivity(GfxRenderer& r, MappedInputManager& m)
      : Activity("JapaneseReview", r, m), UiAppHost(r) {}
  void onEnter() override;
  void onExit() override;
  void loop() override;
  void render(RenderLock&&) override;

 private:
  japanese::review::Progress progress_{};
  japanese::review::Progress proposed_{};
  japanese::review::Rating proposedRating_ = japanese::review::Rating::Again;
  bool pending_ = false;
  bool dayBlocked_ = false;
  japanese::review::Session session_;
  enum class Page { Dashboard, Session, Complete };
  Page page_ = Page::Dashboard;
  GfxRenderer::Orientation orientation_ = GfxRenderer::Orientation::Portrait;
  bool addedWordFont_ = false;
  std::array<bool, 3> waitForRelease_{};
  bool waitForTouchRelease_ = false;
  enum class Status { None, Saved, SaveError, StorageError, Corrupt, Clock };
  Status status_ = Status::None;
  uint32_t day_ = 0;
  std::array<char, 24> date_{};
  std::array<std::array<char, 64>, 3> counts_{};
  std::array<char, 80> position_{};
  void loadDashboard();
  void armReleaseBarriers();
  void attemptPending();
  void retryPending();
  void acceptPending();
  bool checkSessionDay();
  bool healthy() const;
  const char* statusText() const;
  const char* ratingText() const;
  void action(int value);
  void build(UiScreen& screen);
  static void screen(UiScreen& screen, void* context);
  static void event(const freeink::ui::ActionEvent& event, void* context);
};
