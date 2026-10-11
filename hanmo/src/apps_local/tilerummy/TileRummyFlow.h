#pragma once

#include "TileRummyCore.h"

// Complete table plus loose tray; single bounded undo, no solver or heap.
// A census reserves indistinguishable hand copies. The original Game is not
// edited until the actual core accepts the COMPLETE proposed table.
namespace tilerummyui {
namespace tr = tilerummy;
constexpr int kPageTiles = 8;
enum class Screen : uint8_t { Menu, Board, Handoff, Done };
enum class View : uint8_t { Hand, Table, Loose };
enum class Note : uint8_t { Choose, Group, Run, Locked, Full, Loose, Verdict, EmptyPool };
struct Draft {
  tr::Table table{};
  tr::Hand loose{};
};
static_assert(sizeof(Draft) < 640, "bounded table and loose tray");
struct Flow {
  tr::Settings settings = tr::defaultSettings();
  tr::Game game{};
  Screen screen = Screen::Menu;
  View view = View::Hand;
  Draft draft{}, previous{};
  int activeSet = -1, selected = -1, page = 0, previousSet = -1;
  bool undoReady = false, blocked = false;
  uint8_t emptyPasses = 0;
  Note note = Note::Choose;
  tr::MoveResult result{tr::MoveProblem::NothingPlayed, tr::kNoSet, tr::SetProblem::Ok, 0, 0};
  bool begin(uint32_t seed) {
    if (!tr::settingsValid(settings)) return false;
    game = {};
    if (!tr::start(game, settings, seed)) return false;
    blocked = false;
    emptyPasses = 0;
    screen = Screen::Board;
    resetDraft();
    return true;
  }
  void resetDraft() {
    draft = {};
    draft.table = game.table;
    activeSet = draft.table.setCount ? draft.table.setCount - 1 : -1;
    selected = -1;
    page = 0;
    view = View::Hand;
    undoReady = false;
    note = game.poolCount ? Note::Choose : Note::EmptyPool;
    result = {tr::MoveProblem::NothingPlayed, tr::kNoSet, tr::SetProblem::Ok, 0, 0};
  }
  void cancel() { resetDraft(); }
  void menu() {
    resetDraft();
    screen = Screen::Menu;
  }
  void ready() {
    if (screen == Screen::Handoff) screen = Screen::Board;
  }
  bool live() const { return screen == Screen::Board && !tr::over(game) && !blocked; }
  bool validSet() const { return activeSet >= 0 && activeSet < draft.table.setCount; }
  bool setEditable() const {
    return live() && validSet() && (game.melded[game.turn] || activeSet >= game.table.setCount);
  }
  int itemCount() const {
    if (view == View::Hand) return game.hands[game.turn].count;
    if (view == View::Loose) return draft.loose.count;
    return validSet() ? draft.table.sets[activeSet].count : 0;
  }
  int pageCount() const {
    const int n = itemCount();
    return n ? (n + kPageTiles - 1) / kPageTiles : 1;
  }
  void clampPage() {
    if (page >= pageCount()) page = pageCount() - 1;
    if (page < 0) page = 0;
  }
  void setView(View next) {
    view = next;
    selected = -1;
    page = 0;
  }
  bool changePage(int delta) {
    const int next = page + delta;
    if (!live() || next < 0 || next >= pageCount()) return false;
    page = next;
    selected = -1;
    return true;
  }
  bool changeSet(int delta) {
    if (!live() || draft.table.setCount == 0) return false;
    const int next = activeSet + delta;
    if (next < 0 || next >= draft.table.setCount) return false;
    activeSet = next;
    selected = -1;
    page = 0;
    return true;
  }
  tr::Tile itemTile(int index) const {
    if (index < 0 || index >= itemCount()) return tr::kNoTile;
    if (view == View::Hand) return game.hands[game.turn].tiles[index];
    if (view == View::Loose) return draft.loose.tiles[index];
    return draft.table.sets[activeSet].tiles[index];
  }
  int handReserved(tr::Tile tile) const {
    int n = 0;
    for (int s = 0; s < draft.table.setCount; ++s)
      for (int i = 0; i < draft.table.sets[s].count; ++i) n += draft.table.sets[s].tiles[i] == tile;
    for (int i = 0; i < draft.loose.count; ++i) n += draft.loose.tiles[i] == tile;
    for (int s = 0; s < game.table.setCount; ++s)
      for (int i = 0; i < game.table.sets[s].count; ++i) n -= game.table.sets[s].tiles[i] == tile;
    return n;
  }
  bool handAvailable(int index) const {
    const tr::Hand& hand = game.hands[game.turn];
    if (index < 0 || index >= hand.count) return false;
    int ordinal = 0;
    for (int i = 0; i <= index; ++i) ordinal += hand.tiles[i] == hand.tiles[index];
    return ordinal > handReserved(hand.tiles[index]);
  }
  bool select(int index) {
    if (!live() || index < page * kPageTiles || index >= (page + 1) * kPageTiles || index >= itemCount()) return false;
    if (view == View::Hand && !handAvailable(index)) return false;
    selected = index;
    return true;
  }
  void saveUndo() {
    previous = draft;
    previousSet = activeSet;
    undoReady = true;
  }
  bool undo() {
    if (!live() || !undoReady) return false;
    draft = previous;
    activeSet = previousSet;
    selected = -1;
    clampPage();
    undoReady = false;
    note = Note::Choose;
    return true;
  }
  bool newSet(bool run) {
    if (!live()) return false;
    const int firstEditable = game.melded[game.turn] ? 0 : game.table.setCount;
    for (int s = firstEditable; s < draft.table.setCount; ++s) {
      if (draft.table.sets[s].count == 0) {
        activeSet = s;
        selected = -1;
        page = 0;
        note = run ? Note::Run : Note::Group;
        return true;
      }
    }
    if (draft.table.setCount == tr::kMaxSets) {
      note = Note::Full;
      return false;
    }
    saveUndo();
    activeSet = draft.table.setCount++;
    draft.table.sets[activeSet] = {};
    selected = -1;
    page = 0;
    note = run ? Note::Run : Note::Group;
    return true;
  }
  bool canAdd() const {
    return setEditable() && selected >= 0 && selected < itemCount() && view != View::Table &&
           draft.table.sets[activeSet].count < tr::kMaxSetTiles && (view == View::Loose || handAvailable(selected));
  }
  bool canRemove() const {
    return setEditable() && view == View::Table && selected >= 0 && selected < itemCount() &&
           draft.loose.count < tr::kMaxHand;
  }
  bool canReturn() const {
    return live() && view == View::Loose && selected >= 0 && selected < itemCount() &&
           handReserved(itemTile(selected)) > 0;
  }
  void removeLoose(int index) {
    for (int i = index + 1; i < draft.loose.count; ++i) draft.loose.tiles[i - 1] = draft.loose.tiles[i];
    draft.loose.tiles[--draft.loose.count] = tr::kNoTile;
  }
  bool addSelected() {
    if (!canAdd()) {
      if (validSet() && !setEditable()) note = Note::Locked;
      return false;
    }
    saveUndo();
    tr::Set& set = draft.table.sets[activeSet];
    set.tiles[set.count++] = itemTile(selected);
    if (view == View::Loose) removeLoose(selected);
    selected = -1;
    clampPage();
    note = Note::Choose;
    return true;
  }
  bool removeSelected() {
    if (!canRemove()) {
      if (validSet() && !setEditable()) note = Note::Locked;
      return false;
    }
    saveUndo();
    tr::Set& set = draft.table.sets[activeSet];
    draft.loose.tiles[draft.loose.count++] = set.tiles[selected];
    for (int i = selected + 1; i < set.count; ++i) set.tiles[i - 1] = set.tiles[i];
    set.tiles[--set.count] = tr::kNoTile;
    selected = -1;
    clampPage();
    note = Note::Loose;
    return true;
  }
  bool returnSelected() {
    if (!canReturn()) return false;
    saveUndo();
    removeLoose(selected);
    selected = -1;
    clampPage();
    note = Note::Choose;
    return true;
  }
  bool moveSelected(int delta) {
    if (!canRemove()) return false;
    tr::Set& set = draft.table.sets[activeSet];
    const int next = selected + delta;
    if (next < 0 || next >= set.count) return false;
    saveUndo();
    const tr::Tile tile = set.tiles[selected];
    set.tiles[selected] = set.tiles[next];
    set.tiles[next] = tile;
    selected = next;
    page = selected / kPageTiles;
    note = Note::Choose;
    return true;
  }
  bool commit() {
    if (!live()) return false;
    tr::Table complete{};
    int8_t map[tr::kMaxSets]{};
    for (int s = 0; s < draft.table.setCount; ++s) {
      if (draft.table.sets[s].count == 0) continue;
      map[complete.setCount] = static_cast<int8_t>(s);
      complete.sets[complete.setCount++] = draft.table.sets[s];
    }
    result = tr::checkPlay(game, complete);
    if (draft.loose.count) {
      note = Note::Loose;
      return false;
    }
    note = Note::Verdict;
    if (result.problem != tr::MoveProblem::Ok) {
      if (result.failedSet != tr::kNoSet) {
        result.failedSet = map[result.failedSet];
        activeSet = result.failedSet;
        setView(View::Table);
      }
      return false;
    }
    if (!tr::play(game, complete)) return false;
    emptyPasses = 0;
    resetDraft();
    screen = tr::over(game) ? Screen::Done : Screen::Handoff;
    return true;
  }
  bool draw() {
    if (!live()) return false;
    // Explicit empty-pool PASS. No search and no invented automatic winner.
    // Only ALL players' consecutive declared passes mark a blocked session.
    const bool empty = game.poolCount == 0;
    resetDraft();
    if (!tr::drawTile(game)) {
      if (!empty || tr::over(game)) return false;
      tr::passTurn(game);
      ++emptyPasses;
    } else {
      emptyPasses = 0;
    }
    blocked = emptyPasses >= game.settings.players;
    resetDraft();
    screen = blocked ? Screen::Done : Screen::Handoff;
    return true;
  }
};
static_assert(sizeof(Flow) < 2400, "bounded whole flow with one undo");
}  // namespace tilerummyui
