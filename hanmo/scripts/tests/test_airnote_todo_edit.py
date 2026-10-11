"""Compile and run AirNoteTodoEdit against the real AirNotePolicy/AirNoteTodo readers."""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]

class AirNoteTodoEditTest(unittest.TestCase):
    def _run(self, body):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            src = tmp / "t.cpp"
            src.write_text(body)
            subprocess.run(
                ["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                 f"-I{ROOT / 'src'}", str(src), "-o", str(tmp / "t")],
                check=True, capture_output=True, text=True,
            )
            done = subprocess.run([str(tmp / "t")], capture_output=True, text=True)
            self.assertEqual(0, done.returncode, done.stdout + done.stderr)
            # Guards against a program that exits 0 without running the checks.
            self.assertIn("all checks passed", done.stdout)

    def test_edits_round_trip_through_the_real_reader(self):
        self._run(PROGRAM)


PROGRAM = r"""
#include "AirNoteTodoEdit.h"

#include <cstdio>
#include <string>

static int failures = 0;
#define CHECK(cond) do { if (!(cond)) { std::printf("FAIL line %d: %s\n", __LINE__, #cond); ++failures; } } while (0)

int main() {
  std::string a, b, c;

  // ---- creation -------------------------------------------------------
  CHECK(AirNoteTodoEdit::createChecklist("Shopping", "milk", a));
  CHECK(a == "Shopping\n\n#!AirNote-Todo:1\n[ ] milk\n");
  CHECK(AirNoteTodoEdit::isChecklist(a));
  CHECK(AirNoteTodoEdit::readable(a));

  // An empty checklist cannot exist: parse() requires count > 0.
  CHECK(!AirNoteTodoEdit::createChecklist("Shopping", "", b));
  CHECK(!AirNoteTodoEdit::createChecklist("", "milk", b));

  // Plain notes must not start with the checklist marker.
  CHECK(AirNoteTodoEdit::createNote("Diary", "first line", b));
  CHECK(b == "Diary\n\nfirst line\n");
  CHECK(!AirNoteTodoEdit::isChecklist(b));
  CHECK(!AirNoteTodoEdit::createNote("Diary", "#!AirNote-Todo:1\n[ ] x", b));
  CHECK(!AirNoteTodoEdit::createNote("Diary", "", b));

  // ---- append ---------------------------------------------------------
  CHECK(AirNoteTodoEdit::appendItem(a, "eggs", b));
  CHECK(b == "Shopping\n\n#!AirNote-Todo:1\n[ ] milk\n[ ] eggs\n");
  CHECK(AirNoteTodoEdit::readable(b));
  CHECK(AirNoteTodoEdit::appendItem(b, "bread", c));
  CHECK(c == "Shopping\n\n#!AirNote-Todo:1\n[ ] milk\n[ ] eggs\n[ ] bread\n");
  CHECK(!AirNoteTodoEdit::appendItem(a, "", b));
  CHECK(!AirNoteTodoEdit::appendItem("not a note", "x", b));

  // Appending must survive the 64-item ceiling.
  std::string big;
  CHECK(AirNoteTodoEdit::createChecklist("Long", "item1", big));
  for (int i = 2; i <= 64; ++i) {
    std::string grown;
    CHECK(AirNoteTodoEdit::appendItem(big, ("item" + std::to_string(i)).c_str(), grown));
    big = grown;
  }
  size_t count = 0;
  CHECK(AirNoteTodoEdit::readable(big, count));
  CHECK(count == 64);
  std::string overflow;
  CHECK(!AirNoteTodoEdit::appendItem(big, "item65", overflow));

  // ---- relabel --------------------------------------------------------
  CHECK(AirNoteTodoEdit::relabelItem(c, 1, "free-range eggs", b));
  CHECK(b == "Shopping\n\n#!AirNote-Todo:1\n[ ] milk\n[ ] free-range eggs\n[ ] bread\n");
  CHECK(AirNoteTodoEdit::relabelItem(c, 0, "oat milk", b));
  CHECK(b == "Shopping\n\n#!AirNote-Todo:1\n[ ] oat milk\n[ ] eggs\n[ ] bread\n");
  CHECK(AirNoteTodoEdit::relabelItem(c, 2, "rye", b));
  CHECK(b == "Shopping\n\n#!AirNote-Todo:1\n[ ] milk\n[ ] eggs\n[ ] rye\n");
  CHECK(!AirNoteTodoEdit::relabelItem(c, 3, "nope", b));
  CHECK(!AirNoteTodoEdit::relabelItem(c, 0, "", b));

  // Checked state survives a relabel of a different row.
  std::string checked = "Shopping\n\n#!AirNote-Todo:1\n[x] milk\n[ ] eggs\n";
  CHECK(AirNoteTodoEdit::readable(checked));
  CHECK(AirNoteTodoEdit::relabelItem(checked, 1, "eggs x12", b));
  CHECK(b == "Shopping\n\n#!AirNote-Todo:1\n[x] milk\n[ ] eggs x12\n");

  // ---- remove ---------------------------------------------------------
  CHECK(AirNoteTodoEdit::removeItem(c, 1, b));
  CHECK(b == "Shopping\n\n#!AirNote-Todo:1\n[ ] milk\n[ ] bread\n");
  CHECK(AirNoteTodoEdit::removeItem(c, 2, b));
  CHECK(b == "Shopping\n\n#!AirNote-Todo:1\n[ ] milk\n[ ] eggs\n");
  CHECK(AirNoteTodoEdit::removeItem(c, 0, b));
  CHECK(b == "Shopping\n\n#!AirNote-Todo:1\n[ ] eggs\n[ ] bread\n");
  CHECK(!AirNoteTodoEdit::removeItem(c, 3, b));
  // The final item may not be removed: the result would not parse.
  CHECK(!AirNoteTodoEdit::removeItem(a, 0, b));

  // ---- unique file names ---------------------------------------------
  auto never = [](const std::string&) { return false; };
  std::string name;
  CHECK(AirNoteTodoEdit::uniqueFileName("Shopping", never, name));
  CHECK(name == "Shopping.txt");
  auto twoTaken = [](const std::string& candidate) {
    return candidate == "Shopping.txt" || candidate == "Shopping-2.txt";
  };
  CHECK(AirNoteTodoEdit::uniqueFileName("Shopping", twoTaken, name));
  CHECK(name == "Shopping-3.txt");
  auto always = [](const std::string&) { return true; };
  CHECK(!AirNoteTodoEdit::uniqueFileName("Shopping", always, name));
  CHECK(!AirNoteTodoEdit::uniqueFileName("bad/title", never, name));

  if (failures) { std::printf("%d check(s) failed\n", failures); return 1; }
  std::printf("all checks passed\n");
  return 0;
}
"""


if __name__ == "__main__":
    unittest.main()
