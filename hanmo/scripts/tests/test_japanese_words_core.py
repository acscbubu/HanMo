"""Compile and execute the actual fixed-capacity Words core (no firmware mocks)."""
from pathlib import Path
import json
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
INCLUDE = ROOT / "src/activities/apps/japanese"
BUILD = ROOT / "build/japanese-words-child/core"


class JapaneseWordsCoreTests(unittest.TestCase):
    def run_cpp(self, source):
        BUILD.mkdir(parents=True, exist_ok=True)
        name = self._testMethodName
        cpp, exe = BUILD / (name + ".cpp"), BUILD / name
        cpp.write_text('#include "JapaneseWords.h"\n#include <cassert>\n' + source, encoding="utf-8")
        command = ["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", str(INCLUDE), str(cpp), "-o", str(exe)]
        compiled = subprocess.run(command, capture_output=True, text=True)
        (BUILD / (name + ".compile.log")).write_text(compiled.stdout + compiled.stderr, encoding="utf-8")
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        run = subprocess.run([str(exe)], capture_output=True, text=True)
        (BUILD / (name + ".runtime.log")).write_text(run.stdout + run.stderr, encoding="utf-8")
        self.assertEqual(run.returncode, 0, run.stderr)
        return run.stdout

    def test_45_unique_authored_word_ids_skip_phrase_44(self):
        source = json.loads((ROOT / "data/japanese/kana-basic.json").read_text(encoding="utf-8"))["cards"]
        self.assertEqual(len(source), 46)
        self.assertEqual(source[44][3], "みずをのむ")
        output = self.run_cpp(r'''
#include "KanaData.generated.h"
#include <array>
#include <cstring>
#include <iostream>
int main() {
  static_assert(japanese::Words::kCount == 45);
  std::array<bool, 46> seen{};
  for (int i = 0; i < japanese::Words::kCount; ++i) {
    const int id = japanese::Words::cardIdAt(i);
    assert(id == (i < 44 ? i : 45));
    assert(id >= 0 && id < 46 && id != 44 && !seen[id]);
    seen[id] = true;
    assert(std::strlen(kana::cards[id].example) > 0);
    assert(std::strlen(kana::cards[id].meaning) > 0);
    assert(std::strlen(kana::cards[id].exampleRomaji) > 0);
    const auto& c = kana::cards[id];
    std::cout << id << '\t' << c.example << '\t' << c.exampleRomaji << '\t' << c.meaning << '\n';
  }
  assert(!seen[44] && seen[45]);
  assert(japanese::Words::cardIdAt(-1) == -1);
  assert(japanese::Words::cardIdAt(45) == -1);
}
''')
        expected = [[str(i), source[i][3], source[i][5], source[i][4]] for i in [*range(44), 45]]
        self.assertEqual([row.split("\t") for row in output.splitlines()], expected)

    def test_hidden_reveal_double_mark_finish_restart(self):
        self.run_cpp(r'''
int main() {
  japanese::Words lesson;
  assert(lesson.size() == 45 && lesson.round() == 1 && lesson.position() == 0);
  assert(!lesson.done() && !lesson.revealed() && lesson.firstKnown() == 0);
  for (int i = 0; i < 45; ++i) {
    const int id = lesson.current();
    assert(id == japanese::Words::cardIdAt(i));
    assert(!lesson.mark(true) && !lesson.mark(false));
    assert(lesson.position() == i && lesson.current() == id);
    assert(lesson.reveal() && !lesson.reveal());
    assert(lesson.revealed());
    assert(lesson.mark(true));
    assert(!lesson.mark(true) && !lesson.mark(false));
    assert(!lesson.revealed() && lesson.firstKnown() == i + 1);
  }
  assert(lesson.done() && lesson.current() == -1);
  assert(!lesson.reveal() && !lesson.mark(true) && !lesson.mark(false));
  lesson.restart();
  assert(!lesson.done() && !lesson.revealed());
  assert(lesson.current() == 0 && lesson.position() == 0 && lesson.size() == 45);
  assert(lesson.firstKnown() == 0 && lesson.round() == 1);
}
''')

    def test_missed_words_repeat_after_round_first_score_once(self):
        self.run_cpp(r'''
int main() {
  japanese::Words lesson;
  for (int i = 0; i < 45; ++i) {
    assert(lesson.current() == japanese::Words::cardIdAt(i));
    assert(lesson.reveal());
    assert(lesson.mark(i != 0 && i != 44));
  }
  assert(!lesson.done() && lesson.round() == 2 && lesson.size() == 2);
  assert(lesson.position() == 0 && lesson.current() == 0 && !lesson.revealed());
  assert(lesson.firstKnown() == 43);
  assert(lesson.reveal() && lesson.mark(false));
  assert(lesson.current() == 45 && lesson.position() == 1);
  assert(lesson.reveal() && lesson.mark(true));
  assert(lesson.round() == 3 && lesson.size() == 1 && lesson.current() == 0);
  for (int round = 3; round <= 5; ++round) {
    assert(!lesson.done() && lesson.round() == round && !lesson.revealed());
    assert(!lesson.mark(false));
    assert(lesson.reveal() && lesson.mark(false));
    assert(!lesson.mark(true));
  }
  assert(lesson.round() == 6);
  assert(lesson.reveal() && lesson.mark(true));
  assert(lesson.done() && lesson.firstKnown() == 43 && lesson.current() == -1);
  lesson.restart();
  assert(lesson.round() == 1 && lesson.size() == 45 && lesson.firstKnown() == 0);
  for (int i = 0; i < 45; ++i) assert(lesson.reveal() && lesson.mark(false));
  assert(lesson.round() == 2 && lesson.size() == 45 && !lesson.done());
  for (int i = 0; i < 45; ++i) assert(lesson.reveal() && lesson.mark(true));
  assert(lesson.done() && lesson.firstKnown() == 0);
}
''')

    def test_seeded_order_is_repeatable_complete_restartable(self):
        self.run_cpp(r'''
#include <array>
int main() {
  japanese::Words a(123), b(123), c(987), sorted(0);
  std::array<bool, 46> seen{};
  bool different = false, shuffled = false;
  for (int i = 0; i < 45; ++i) {
    assert(a.current() == b.current());
    const int id = a.current();
    assert(id >= 0 && id < 46 && id != 44 && !seen[id]);
    seen[id] = true;
    different |= a.current() != c.current();
    shuffled |= a.current() != sorted.current();
    assert(a.reveal() && a.mark(true));
    assert(b.reveal() && b.mark(true));
    assert(c.reveal() && c.mark(true));
    assert(sorted.reveal() && sorted.mark(true));
  }
  assert(different && shuffled && seen[45] && !seen[44]);
  a.restart(123);
  japanese::Words again(123);
  for (int i = 0; i < 45; ++i) {
    assert(a.current() == again.current());
    assert(a.reveal() && a.mark(true));
    assert(again.reveal() && again.mark(true));
  }
  static_assert(sizeof(japanese::Words) <= 128, "bounded session RAM");
}
''')


if __name__ == "__main__":
    unittest.main()
