#include "ImportedMinesweeperActivity.h"

#include <I18n.h>

#include <algorithm>
#include <cstdio>

#include "../Shelf.h"
#include "../ui/ToyboxSeed.h"
#include "../../components/UITheme.h"
#include "fontIds.h"

namespace fui = freeink::ui;
namespace ms = imported_minesweeper;

namespace imported_minesweeper {
const char* variantActivityName(Variant variant) {
  switch (variant) {
    case Variant::Biscuit: return "ImportedMinesweeperBiscuit";
  }
  return "ImportedMinesweeperUnknown";
}
}  // namespace imported_minesweeper

namespace {
const char* brand(const ms::Variant variant) {
  switch (variant) {
    case ms::Variant::Biscuit: return "BISCUIT";
  }
  return "";
}

const char* tierLabel(const int difficulty) {
  switch (difficulty) {
    case 0: return tr(STR_MINESWEEPER_DIFFICULTY_EASY);
    case 1: return tr(STR_MINESWEEPER_DIFFICULTY_MEDIUM);
    default: return tr(STR_MINESWEEPER_DIFFICULTY_HARD);
  }
}
}  // namespace

void ImportedMinesweeperActivity::onEnter() {
  Activity::onEnter();
  difficulty_ = ms::defaultDifficulty(variant_);
  resetUi();
  app.setScreen(&ImportedMinesweeperActivity::screenCallback, this);
  screen_ = Screen::Select;
  waitForConfirmRelease_ = mappedInput.isPressed(MappedInputManager::Button::Confirm);
  requestUpdate();
}

uint32_t ImportedMinesweeperActivity::surfaceMeaning() const {
  uint32_t meaning = paintclock::mixMeaning(paintclock::kMeaningSeed, static_cast<uint32_t>(variant_));
  meaning = paintclock::mixMeaning(meaning, static_cast<uint32_t>(screen_));
  return paintclock::mixMeaning(meaning, static_cast<uint32_t>(difficulty_));
}

void ImportedMinesweeperActivity::goTo(const Screen screen) {
  if (screen_ == screen) return;
  screen_ = screen;
  // A touch in flight must not route through the previous screen's buttons.
  closeRouting();
  app.clearTapFlash();
  app.setScreen(&ImportedMinesweeperActivity::screenCallback, this);
  requestUpdate();
}

void ImportedMinesweeperActivity::startGame() {
  board_.reset(variant_, difficulty_, toybox::seed());
  goTo(Screen::Playing);
  requestUpdate();
}

void ImportedMinesweeperActivity::leaveGame() {
  app.clearTapFlash();
  shelf::leave(renderer, mappedInput);
}

void ImportedMinesweeperActivity::apply(ms::ActionResult result) {
  if (!result.changed) return;
  if (board_.phase() != ms::Phase::Playing) {
    goTo(Screen::Finished);
  } else {
    requestUpdate();
  }
}

void ImportedMinesweeperActivity::act(Action action, int value, int x, int y, bool longPress) {
  switch (action) {
    case ActionBoard: {
      if (screen_ != Screen::Playing || !surfaceRevealed()) return;
      int row = 0;
      int col = 0;
      if (!geometry_.cellAt(x, y, row, col)) return;
      board_.setCursor(row, col);
      apply(board_.confirm(longPress ? 500ul : 0ul));
      return;
    }
    case ActionDig:
      if (screen_ == Screen::Playing) apply(board_.confirm(0));
      return;
    case ActionFlag:
      if (screen_ == Screen::Playing) apply(board_.confirm(500));
      return;
    case ActionPause:
      if (screen_ == Screen::Playing) goTo(Screen::Paused);
      return;
    case ActionResume:
      if (screen_ == Screen::Paused) goTo(Screen::Playing);
      return;
    case ActionStart:
      if (screen_ == Screen::Select) startGame();
      return;
    case ActionRetry:
      if (screen_ == Screen::Paused || screen_ == Screen::Finished) startGame();
      return;
    case ActionExit:
      leaveGame();
      return;
    case ActionDifficulty:
      if (value < 0 || value > 2) return;
      if (screen_ == Screen::Select) {
        difficulty_ = value;
        startGame();
      } else if (screen_ == Screen::Finished) {
        difficulty_ = value;
        requestUpdate();
      }
      return;
    default:
      return;
  }
}

void ImportedMinesweeperActivity::loop() {
  // routeTouch maps panel contacts through the live renderer orientation and
  // routes touch-down/up/long-press against the published FreeInkUI table.
  const auto touch = routeTouch(mappedInput, true);
  if (touch.routed && app.invalidated()) requestUpdate();
  if (touch) {
    act(static_cast<Action>(touch.event.action), touch.event.value,
        touch.snap.touchX, touch.snap.touchY, touch.event.longPress);
    return;
  }

  if (mappedInput.wasReleased(MappedInputManager::Button::Back)) {
    if (screen_ == Screen::Playing) goTo(Screen::Paused);
    else if (screen_ == Screen::Paused) goTo(Screen::Playing);
    else leaveGame();
    return;
  }
  if (waitForConfirmRelease_) {
    if (!mappedInput.isPressed(MappedInputManager::Button::Confirm)) waitForConfirmRelease_ = false;
    return;  // Consume the transition's release as well.
  }

  if (screen_ == Screen::Select) {
    if (mappedInput.wasReleased(MappedInputManager::Button::Up) && difficulty_ > 0) {
      --difficulty_;
      requestUpdate();
    } else if (mappedInput.wasReleased(MappedInputManager::Button::Down) && difficulty_ < 2) {
      ++difficulty_;
      requestUpdate();
    } else if (mappedInput.wasReleased(MappedInputManager::Button::Confirm)) {
      startGame();
    }
    return;
  }
  if (screen_ == Screen::Paused) {
    if (mappedInput.wasReleased(MappedInputManager::Button::Confirm)) goTo(Screen::Playing);
    return;
  }
  if (screen_ == Screen::Finished) {
    if (mappedInput.wasReleased(MappedInputManager::Button::Confirm)) startGame();
    else if (mappedInput.wasReleased(MappedInputManager::Button::Left) && difficulty_ > 0) {
      --difficulty_;
      requestUpdate();
    } else if (mappedInput.wasReleased(MappedInputManager::Button::Right) && difficulty_ < 2) {
      ++difficulty_;
      requestUpdate();
    }
    return;
  }

  if (mappedInput.wasReleased(MappedInputManager::Button::Up) && board_.move(ms::Direction::Up)) requestUpdate();
  else if (mappedInput.wasReleased(MappedInputManager::Button::Down) && board_.move(ms::Direction::Down)) requestUpdate();
  else if (mappedInput.wasReleased(MappedInputManager::Button::Left) && board_.move(ms::Direction::Left)) requestUpdate();
  else if (mappedInput.wasReleased(MappedInputManager::Button::Right) && board_.move(ms::Direction::Right)) requestUpdate();
  else if (mappedInput.wasReleased(MappedInputManager::Button::Confirm)) {
    apply(board_.confirm(mappedInput.getHeldTime()));
  }
}

const char* ImportedMinesweeperActivity::difficultyLabel() const { return tierLabel(difficulty_); }

void ImportedMinesweeperActivity::drawButton(UiScreen& screen, fui::Rect box, const char* label,
                                               Action action, int value, bool selected) {
  fui::ButtonProps button;
  button.label = label;
  button.action = action;
  button.value = static_cast<int16_t>(value);
  button.inputMask = fui::InputTouch;  // physical buttons use the explicit loop path
  button.state = selected ? fui::StateSelected : fui::StateNormal;
  button.minTouchSize = 1;            // never grow a target into the 8px gap
  screen.button(button, box);
}

void ImportedMinesweeperActivity::screenCallback(UiScreen& screen, void* user) {
  static_cast<ImportedMinesweeperActivity*>(user)->buildScreen(screen);
}

void ImportedMinesweeperActivity::buildScreen(UiScreen& screen) {
  const auto& metrics = UITheme::getInstance().getMetrics();
  screen.setContentMarginFromScreen(fui::Insets{0, 0, static_cast<int16_t>(metrics.buttonHintsHeight + 8), 0});
  // The untranslated proper noun identifies the pinned source; all gameplay
  // words are existing tr() keys. No upstream icons or font files are copied.
  screen.header(tr(STR_MINESWEEPER_TITLE), nullptr, brand(variant_));
  const int16_t margin = std::max<int16_t>(8, screen.theme().spaceMd);
  screen.insetContent(fui::Insets{margin, margin, margin, margin});

  const int16_t gap = std::max<int16_t>(8, screen.theme().spaceSm);
  const int16_t height = std::max<int16_t>(44, screen.theme().rowHeight);
  if (screen_ == Screen::Select) {
    const fui::Rect body = screen.body();
    for (int tier = 0; tier < 3; ++tier) {
      const ms::Profile config = ms::profile(variant_, tier);
      char description[40];
      std::snprintf(description, sizeof(description), "%d x %d · %d %s", config.cols, config.rows,
                    config.mines, tr(STR_MINESWEEPER_MINES));
      const int16_t rowY = static_cast<int16_t>(body.y + tier * (height + gap + 22));
      const fui::Rect row{body.x, rowY, body.width, height};
      drawButton(screen, row, tierLabel(tier), ActionDifficulty, tier, tier == difficulty_);
      fui::TextStyle text = screen.theme().smallText;
      text.align = fui::TextAlign::Center;
      screen.target().text(fui::Rect{body.x, static_cast<int16_t>(rowY + height), body.width, gap + 20},
                           description, text);
    }
    const fui::Rect exit = screen.takeBottom(height, gap);
    drawButton(screen, exit, tr(STR_EXIT), ActionExit);
    return;
  }
  if (screen_ == Screen::Paused) {
    const fui::Rect title = screen.takeTop(height, gap);
    fui::TextStyle text = screen.theme().titleText;
    text.color = fui::Color::Black;
    text.align = fui::TextAlign::Center;
    screen.target().text(title, tr(STR_GAME_GAME_MENU), text);
    drawButton(screen, screen.takeTop(height, gap), tr(STR_GAME_RESUME), ActionResume);
    drawButton(screen, screen.takeTop(height, gap), tr(STR_GAME_NEW_GAME), ActionRetry);
    drawButton(screen, screen.takeTop(height, gap), tr(STR_EXIT), ActionExit);
    return;
  }
  if (screen_ == Screen::Finished) {
    const fui::Rect title = screen.takeTop(height, gap);
    fui::TextStyle text = screen.theme().titleText;
    text.color = fui::Color::Black;
    text.align = fui::TextAlign::Center;
    screen.target().text(title, board_.phase() == ms::Phase::Won ? tr(STR_MINESWEEPER_CLEARED)
                                                          : tr(STR_MINESWEEPER_BOOM), text);
    const ms::Profile config = ms::profile(variant_, difficulty_);
    char detail[40];
    std::snprintf(detail, sizeof(detail), "%s · %d x %d · %d %s", difficultyLabel(), config.cols,
                  config.rows, config.mines, tr(STR_MINESWEEPER_MINES));
    text = screen.theme().smallText;
    text.align = fui::TextAlign::Center;
    screen.target().text(screen.takeTop(height, gap), detail, text);
    drawButton(screen, screen.takeTop(height, gap), tr(STR_MINESWEEPER_PLAY_AGAIN), ActionRetry);
    for (int tier = 0; tier < 3; ++tier) {
      drawButton(screen, screen.takeTop(height, gap), tierLabel(tier), ActionDifficulty, tier, tier == difficulty_);
    }
    drawButton(screen, screen.takeTop(height, gap), tr(STR_EXIT), ActionExit);
    return;
  }

  // Touch-primary X4 Pro: Dig and Flag are independently tappable, and Pause /
  // Exit work without an assigned front Back/Confirm button.
  const fui::Rect pause = screen.takeBottom(height, gap);
  drawButton(screen, pause, tr(STR_GAME_GAME_MENU_BTN), ActionPause);
  const fui::Rect tools = screen.takeBottom(height, gap);
  const int16_t half = static_cast<int16_t>((tools.width - gap) / 2);
  drawButton(screen, fui::Rect{tools.x, tools.y, half, tools.height}, tr(STR_MINESWEEPER_MODE_DIG), ActionDig);
  drawButton(screen, fui::Rect{static_cast<int16_t>(tools.x + half + gap), tools.y, half, tools.height},
             tr(STR_MINESWEEPER_MODE_FLAG), ActionFlag);
  char status[48];
  std::snprintf(status, sizeof(status), "%s · %d %s · %d %s", difficultyLabel(),
                board_.minesPlaced() ? board_.mineCount() : board_.settings().mines,
                tr(STR_MINESWEEPER_MINES), board_.flagCount(), tr(STR_MINESWEEPER_FLAGS));
  fui::TextStyle text = screen.theme().smallText;
  text.align = fui::TextAlign::Center;
  screen.target().text(screen.takeTop(height, gap), status, text);
  drawBoard(screen);
}

void ImportedMinesweeperActivity::drawBoard(UiScreen& screen) {
  const fui::Rect body = screen.body();
  const ms::Profile size = board_.settings();
  geometry_ = ms::fitBoard(ms::Rect{body.x, body.y, body.width, body.height}, size.rows, size.cols);
  if (!geometry_.pitch) return;
  const fui::Rect boardRect{static_cast<int16_t>(geometry_.x), static_cast<int16_t>(geometry_.y),
                             static_cast<int16_t>(geometry_.width()), static_cast<int16_t>(geometry_.height())};
  screen.frame().hit(boardRect, ActionBoard, 0, fui::InputTouch | fui::InputLongPress);
  const int font = SMALL_FONT_ID;
  for (int row = 0; row < size.rows; ++row) {
    for (int col = 0; col < size.cols; ++col) {
      const int x = geometry_.x + col * geometry_.pitch;
      const int y = geometry_.y + row * geometry_.pitch;
      const int cell = geometry_.cell;
      const bool chosen = row == board_.cursorRow() && col == board_.cursorCol();
      const ms::CellState state = board_.state(row, col);
      if (state != ms::CellState::Revealed) renderer.fillRectDither(x, y, cell, cell, LightGray);
      renderer.drawRect(x, y, cell, cell, chosen ? 2 : 1, true);
      const char* mark = nullptr;
      char digit[2] = {};
      if (state == ms::CellState::Flagged) mark = "F";  // symbol, not translated prose
      else if (state == ms::CellState::Revealed && board_.isMine(row, col)) mark = "*";
      else if (state == ms::CellState::Revealed && board_.adjacent(row, col) > 0) {
        digit[0] = static_cast<char>('0' + board_.adjacent(row, col));
        mark = digit;
      }
      if (mark != nullptr) {
        const int width = renderer.getTextWidth(font, mark);
        const int height = renderer.getTextHeight(font);
        renderer.drawText(font, x + (cell - width) / 2, y + (cell - height) / 2, mark);
      }
    }
  }
}

void ImportedMinesweeperActivity::render(RenderLock&&) {
  renderer.clearScreen();
  renderUi();
  const char* backLabel = screen_ == Screen::Playing ? tr(STR_GAME_GAME_MENU_BTN) : tr(STR_BACK);
  const char* confirmLabel = screen_ == Screen::Select ? tr(STR_SELECT) :
                             screen_ == Screen::Playing ? tr(STR_MINESWEEPER_MODE_DIG) :
                             screen_ == Screen::Paused ? tr(STR_GAME_RESUME) : tr(STR_MINESWEEPER_PLAY_AGAIN);
  const auto labels = mappedInput.mapLabels(backLabel, confirmLabel, "", "");
  GUI.drawButtonHints(renderer, labels.btn1, labels.btn2, labels.btn3, labels.btn4);
  renderer.displayBuffer();
}
