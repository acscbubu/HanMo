"""Compile the production activity query without pulling in hardware drivers."""

from pathlib import Path
import re
import subprocess
import tempfile

source = (Path(__file__).resolve().parents[2] / "src/InputManager.cpp").read_text()
method = re.search(r"bool InputManager::wasTouchActivity\(\) const \{.*?^\}", source, re.M | re.S)
assert method, "production wasTouchActivity method missing"
harness = """
#include <cassert>
struct InputManager {
  bool touchPressed = false, touchPressedEvent = false, touchReleasedEvent = false;
  bool touchHomeKeyEvent = false, touchHomeKeyTapEvent = false, touchHomeKeyLongEvent = false;
  bool wasTouchActivity() const;
};
""" + method[0] + """
int main() {
  InputManager input;
  assert(!input.wasTouchActivity());
  for (bool InputManager::*event : {&InputManager::touchHomeKeyEvent,
                                   &InputManager::touchHomeKeyTapEvent,
                                   &InputManager::touchHomeKeyLongEvent}) {
    input = {};
    input.*event = true;
    assert(input.wasTouchActivity() == bool(FREEINK_CAP_TOUCH));
    input.touchPressed = true;
    assert(!input.wasTouchActivity()); // Home cannot retire a held screen contact.
    input.touchPressedEvent = true;
    assert(input.wasTouchActivity() == bool(FREEINK_CAP_TOUCH));
    input.touchPressedEvent = false;
    input.touchPressed = false;
    input.touchReleasedEvent = true;
    assert(input.wasTouchActivity() == bool(FREEINK_CAP_TOUCH));
  }
  input = {};
  input.touchReleasedEvent = true;
  assert(input.wasTouchActivity() == bool(FREEINK_CAP_TOUCH));
}
"""
with tempfile.TemporaryDirectory(prefix="freeink-touch-activity-") as directory:
    root = Path(directory)
    cpp = root / "test.cpp"
    cpp.write_text("#include <initializer_list>\n" + harness)
    for touch in (0, 1):
        binary = root / f"touch-{touch}"
        subprocess.run(["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                        f"-DFREEINK_CAP_TOUCH={touch}", str(cpp), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
print("Touch activity: touch/non-touch and Home/contact edge checks passed")
