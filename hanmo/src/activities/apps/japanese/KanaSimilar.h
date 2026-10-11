#pragma once

#include <array>

namespace kana {

// Session-only lesson state; card identities refer to KanaData.generated.h.
class Similar {
 public:
  enum class Screen { Compare, Test, Done };

  Screen screen() const { return screen_; }
  int comparePair() const { return pair_; }
  int compareLeftCardId() const { return pair_ == 0 ? 11 : 14; }
  int compareRightCardId() const { return pair_ == 0 ? 17 : 45; }
  bool stepCompare(int delta) {
    if (screen_ != Screen::Compare || (delta != -1 && delta != 1)) return false;
    pair_ = (pair_ + delta + 2) % 2;
    return true;
  }
  bool startTest() {
    if (screen_ != Screen::Compare) return false;
    screen_ = Screen::Test;
    question_ = 0;
    score_ = 0;
    selected_ = -1;
    answered_ = false;
    return true;
  }
  int questionCount() const { return static_cast<int>(kQuestions.size()); }
  int questionIndex() const { return question_; }
  int questionPair() const { return screen_ == Screen::Test ? kQuestions[question_].pair : -1; }
  int hintPair() const { return screen_ == Screen::Compare ? pair_ : questionPair(); }
  int targetCardId() const { return screen_ == Screen::Test ? kQuestions[question_].target : -1; }
  int leftChoiceCardId() const { return screen_ == Screen::Test ? kQuestions[question_].left : -1; }
  int rightChoiceCardId() const { return screen_ == Screen::Test ? kQuestions[question_].right : -1; }
  bool answered() const { return answered_; }
  int selectedCardId() const { return selected_; }
  bool correct() const { return answered_ && selected_ == targetCardId(); }
  int score() const { return score_; }
  bool choose(int cardId) {
    if (screen_ != Screen::Test || answered_ || (cardId != leftChoiceCardId() && cardId != rightChoiceCardId()))
      return false;
    selected_ = cardId;
    answered_ = true;
    if (correct()) ++score_;
    return true;
  }
  bool next() {
    if (screen_ != Screen::Test || !answered_) return false;
    answered_ = false;
    selected_ = -1;
    if (++question_ == questionCount()) screen_ = Screen::Done;
    return true;
  }
  bool restart() {
    if (screen_ != Screen::Done) return false;
    screen_ = Screen::Test;
    question_ = 0;
    score_ = 0;
    selected_ = -1;
    answered_ = false;
    return true;
  }
  bool back() {
    if (screen_ == Screen::Compare) return false;
    screen_ = Screen::Compare;
    pair_ = 0;
    question_ = 0;
    score_ = 0;
    selected_ = -1;
    answered_ = false;
    return true;
  }

 private:
  struct Question {
    int target;
    int left;
    int right;
    int pair;
  };
  // Both members of each pair are targets. Pairs are interleaved so the
  // choice order alternates while each pair still trains both answer sides.
  static constexpr std::array<Question, 4> kQuestions{{
      {11, 11, 17, 0},
      {14, 45, 14, 1},
      {17, 11, 17, 0},
      {45, 45, 14, 1},
  }};
  Screen screen_ = Screen::Compare;
  int pair_ = 0;
  int question_ = 0;
  int score_ = 0;
  int selected_ = -1;
  bool answered_ = false;
};

}  // namespace kana
