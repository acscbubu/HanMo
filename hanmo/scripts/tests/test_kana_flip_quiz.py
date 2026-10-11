"""Behavior tests compile the production quiz state machine as C++17."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
INCLUDE = ROOT / "src/activities/apps/japanese"


class KanaFlipQuizTests(unittest.TestCase):
    def compile_and_run(self, source):
        with tempfile.TemporaryDirectory() as directory:
            cpp = Path(directory) / "test.cpp"
            exe = Path(directory) / "quiz-test"
            cpp.write_text('#include "KanaQuiz.h"\n' + source, encoding="utf-8")
            subprocess.run(["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", str(INCLUDE), str(cpp), "-o", str(exe)], check=True)
            subprocess.run([str(exe)], check=True)

    def test_front_reveals_answer_before_accepting_self_rating(self):
        self.compile_and_run('''
#include <cassert>
int main() {
    kana::Quiz quiz(7);
    assert(quiz.size() == 46);
    assert(quiz.position() == 0);
    assert(quiz.current() >= 0 && quiz.current() < 46);
    assert(!quiz.revealed());
    assert(!quiz.mark(true));
    assert(quiz.position() == 0);
    assert(quiz.reveal());
    assert(quiz.revealed());
    assert(!quiz.reveal());
    assert(quiz.mark(true));
    assert(!quiz.revealed());
    assert(quiz.position() == 1);
}
''')


    def test_uses_each_of_the_forty_six_cards_once_and_completes(self):
        self.compile_and_run('''
#include <array>
#include <cassert>
int main() {
    kana::Quiz quiz(123);
    std::array<bool, 46> seen{};
    const int first = quiz.current();
    for (int i = 0; i < 46; ++i) {
        int card = quiz.current();
        assert(card >= 0 && card < 46 && !seen[card]);
        seen[card] = true;
        assert(quiz.position() == i);
        assert(quiz.size() == 46);
        assert(!quiz.done());
        assert(quiz.reveal());
        assert(quiz.mark(true));
    }
    for (bool present : seen) assert(present);
    assert(quiz.done());
    assert(quiz.current() == -1);
    assert(quiz.firstKnown() == 46);
    assert(!quiz.reveal());
    assert(!quiz.mark(false));
    quiz.restart(123);
    assert(!quiz.done() && quiz.current() == first);
    assert(quiz.position() == 0 && quiz.firstKnown() == 0);
}
''')


    def test_unfamiliar_card_is_requeued_until_marked_known(self):
        self.compile_and_run('''
#include <cassert>
int main() {
    kana::Quiz quiz(99);
    int missed = quiz.current();
    assert(quiz.round() == 1);
    assert(quiz.reveal() && quiz.mark(false));
    for (int i = 1; i < 46; ++i) {
        assert(quiz.current() != missed);
        assert(quiz.reveal() && quiz.mark(true));
    }
    assert(!quiz.done());
    assert(quiz.round() == 2 && quiz.size() == 1);
    assert(quiz.position() == 0 && quiz.current() == missed);
    assert(quiz.firstKnown() == 45);
    assert(quiz.reveal() && quiz.mark(false));
    assert(quiz.round() == 3 && quiz.current() == missed);
    assert(quiz.reveal() && quiz.mark(true));
    assert(quiz.done() && quiz.firstKnown() == 45);
}
''')


if __name__ == "__main__":
    unittest.main()
