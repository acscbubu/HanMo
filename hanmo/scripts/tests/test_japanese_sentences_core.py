"""Compile the actual pure lesson core with bounded state-transition checks."""
from pathlib import Path
import subprocess
import unittest
ROOT = Path(__file__).resolve().parents[2]
INCLUDE = ROOT / 'src/activities/apps/japanese'
BUILD = ROOT / 'build/japanese-sentence-progress/core'

class JapaneseSentencesCoreTests(unittest.TestCase):
    def run_cpp(self, source):
        directory = BUILD / self._testMethodName
        directory.mkdir(parents=True, exist_ok=True)
        cpp, exe = directory / 'main.cpp', directory / 'core'
        cpp.write_text('#include "JapaneseSentences.h"\n#include <cassert>\n' + source, encoding='utf-8')
        command = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-I', str(INCLUDE), str(cpp), '-o', str(exe)]
        compiled = subprocess.run(command, capture_output=True, text=True)
        (directory / 'compile.log').write_text(' '.join(command) + '\n' + compiled.stdout + compiled.stderr)
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        run = subprocess.run([str(exe)], capture_output=True, text=True)
        (directory / 'runtime.log').write_text(run.stdout + run.stderr)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_bounded_navigation_hides_on_each_changed_sentence(self):
        self.run_cpp(r'''
int main() {
  japanese::Sentences lesson;
  static_assert(japanese::Sentences::count() == 6);
  assert(lesson.position() == 0 && !lesson.revealed());
  assert(!lesson.canPrevious() && lesson.canNext());
  assert(!lesson.previous() && lesson.position() == 0);
  for (int i = 0; i < 5; ++i) {
    lesson.toggleReveal(); assert(lesson.revealed());
    assert(lesson.next());
    assert(lesson.position() == i+1 && !lesson.revealed());
  }
  assert(lesson.canPrevious() && !lesson.canNext());
  lesson.toggleReveal();
  assert(!lesson.next() && lesson.position() == 5 && lesson.revealed());
  for (int i = 5; i > 0; --i) {
    assert(lesson.previous());
    assert(lesson.position() == i-1 && !lesson.revealed());
    lesson.toggleReveal();
  }
  assert(!lesson.previous() && lesson.revealed());
  lesson.toggleReveal(); assert(!lesson.revealed());
}
''')

    def test_restore_is_bounded_hidden_and_rejects_without_mutation(self):
        self.run_cpp(r'''
int main() {
  japanese::Sentences lesson;
  for (int i = 0; i < 6; ++i) {
    assert(lesson.restore(i));
    assert(lesson.position() == i && !lesson.revealed());
    lesson.toggleReveal();
    for (int invalid : {-1,6,255,10000}) {
      assert(!lesson.restore(invalid));
      assert(lesson.position() == i && lesson.revealed());
    }
    assert(lesson.restore(i) && !lesson.revealed());
  }
}
''')

    def test_restart_clears_session_from_every_position(self):
        self.run_cpp(r'''
int main() {
  for (int i = 0; i < 6; ++i) {
    for (bool revealed : {false,true}) {
      japanese::Sentences lesson;
      for (int n = 0; n < i; ++n) lesson.next();
      if (revealed) lesson.toggleReveal();
      lesson.restart();
      assert(lesson.position() == 0 && !lesson.revealed());
      assert(!lesson.canPrevious() && lesson.canNext());
      for (int n = 0; n < 1000; ++n) lesson.next();
      assert(lesson.position() == 5);
      for (int n = 0; n < 1000; ++n) lesson.previous();
      assert(lesson.position() == 0);
    }
  }
}
''')

if __name__ == '__main__':
    unittest.main()
