#pragma once

#include "../../activities/Activity.h"
#include "../../components/UiAppHost.h"
#include "ImportedMinesweeperRules.h"

namespace imported_minesweeper {
const char* variantActivityName(Variant variant);
}

// Shelf factory: makeUniqueNoThrow<ImportedMinesweeperActivity>(renderer, input, variant).
// The unique name is Shelf's wake identity, not a translated title.
class ImportedMinesweeperActivity final : public Activity, public UiAppHost {
 public:
  ImportedMinesweeperActivity(GfxRenderer& renderer, MappedInputManager& mappedInput,
                              imported_minesweeper::Variant variant)
      : Activity(imported_minesweeper::variantActivityName(variant), renderer, mappedInput),
        UiAppHost(renderer), variant_(variant) {}

  void onEnter() override;
  void loop() override;
  void render(RenderLock&&) override;
  uint32_t surfaceMeaning() const override;

 private:
  enum class Screen : uint8_t { Select, Playing, Paused, Finished };
  enum Action : freeink::ui::ActionId {
    ActionBoard = 1, ActionDig, ActionFlag, ActionPause, ActionResume,
    ActionRetry, ActionExit, ActionDifficulty, ActionStart,
  };
  static void screenCallback(UiScreen& screen, void* user);
  void buildScreen(UiScreen& screen);
  void drawBoard(UiScreen& screen);
  void drawButton(UiScreen& screen, freeink::ui::Rect box, const char* label,
                  Action action, int value = 0, bool selected = false);
  void goTo(Screen screen);
  void startGame();
  void leaveGame();
  void act(Action action, int value, int x, int y, bool longPress);
  void apply(imported_minesweeper::ActionResult result);
  const char* difficultyLabel() const;

  imported_minesweeper::Variant variant_;
  imported_minesweeper::Board board_;
  // Written by render from the exact rect it paints; routed only once that
  // generation was published and panel-revealed (Activity::surfaceRevealed).
  imported_minesweeper::BoardGeometry geometry_{};
  Screen screen_ = Screen::Select;
  int difficulty_ = 0;
  int selectedRow_ = 0;
  bool waitForConfirmRelease_ = false;
};
