#pragma once
#include "AirNoteTodo.h"
#include "activities/UiListActivity.h"
#include "components/OptionPopup.h"
#include <memory>

class AirNoteTodoActivity final : public UiListActivity {
 public:
  AirNoteTodoActivity(GfxRenderer& renderer, MappedInputManager& input, std::string path);
  static bool recognizes(const std::string& path);
  static bool recoverDirectory();
  void onEnter() override;
  void render(RenderLock&& lock) override;
 private:
  // Items plus one trailing row: "add item", or the bulk-actions row while
  // selecting. count_ == 0 means the note failed to load, so the single row
  // shown is the error instead.
  bool canAdd() const { return count_ && !selecting_ && count_ < AirNoteTodo::maxItems; }
  // The picker row is the only entry to multi-select that does not need a
  // long press, so it stays even on a full checklist that has no add row.
  bool canPick() const { return count_ && !selecting_; }
  // While selecting, the trailing row is the bulk-actions row instead of the add
  // row, so a full 64-item checklist can still reach the delete confirmation.
  int listCount() const override {
    if (!count_) return 1;
    return static_cast<int>(count_) + (selecting_ ? 1 : (canAdd() ? 1 : 0) + (canPick() ? 1 : 0));
  }
  const char* headerTitle() const override;
  void buildScreen(UiScreen& screen) override;
  void drawChrome() override;
  void activateIndex(int index) override;
  void onBackButton() override;
  void onRowLongPress(int index) override;
  bool handleCustomInput() override;
  void moveItem(int index, int direction);
  void showItemMenu(int index);
  void beginMultiSelect();
  void beginMultiSelect(int index);
  void toggleSelection(int index);
  void endMultiSelect();
  void showMultiActions();
  void promptBulkDelete();
  void performBulkDelete();
  unsigned selectedCount() const;
  void noteSelection();
  void promptAddItem();
  void promptEditItem(int index);
  void deleteItem(int index);
  // Add/edit/delete change the note's length, which the in-place toggle and
  // reorder paths cannot express; they rebuild the whole file instead.
  void applyEdit(const std::string& next);
  bool writeContent(const char* data, size_t length);
  std::string serialized();
  bool saveSerialized();
  OptionPopup orderPopup_;
  // The bulk-delete confirmation is raised from orderPopup_'s own selection
  // callback, so it needs a second owner: show() replaces the std::function
  // handleInput() is still executing and would destroy it mid-call.
  OptionPopup confirmPopup_;
  bool waitForConfirmRelease_=false;
  int carrying_=-1;
  bool selecting_=false;
  // 64 bytes beside items_, no heap and no per-row subtitle: rows must keep
  // subtitle == nullptr, so the selection can only show in the row glyph.
  std::array<bool, AirNoteTodo::maxItems> selected_{};
  bool load();
  void delimit(bool forDisplay);
  void rebuildRows();
  std::string path_, backup_, staging_;
  // One checked heap buffer, bounded to 16 KiB + title. Row labels point into
  // it; no duplicated labels. Arrays live in the checked Activity allocation.
  std::unique_ptr<char[]> content_;
  size_t length_ = 0, bodyOffset_ = 0, count_ = 0;
  AirNoteTodo::Items items_{};
  // items + add row + picker row, the widest the list ever gets.
  std::array<freeink::ui::ListItem, AirNoteTodo::maxItems + 2> rows_{};
  std::array<char, 33> revision_{};
  std::array<char, 256> status_{}; // Error or hint band; never part of a task row.
  std::array<char, 96> progress_{}; // Fixed storage; no extra heap allocation.
};
