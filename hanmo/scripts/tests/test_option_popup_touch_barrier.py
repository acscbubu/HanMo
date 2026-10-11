"""Compile the production OptionPopup touch barrier; a new first tap must work."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'src/components/OptionPopup.h'


def method(source, marker):
    start = source.index(marker)
    brace = source.index('{', start)
    depth = 0
    for end in range(brace, len(source)):
        if source[end] == '{':
            depth += 1
        elif source[end] == '}':
            depth -= 1
            if depth == 0:
                return source[start:end + 1].replace(marker, marker.replace(' ', ' OptionPopup::', 1), 1)
    raise AssertionError('unclosed OptionPopup method: ' + marker)


STUB = r'''
#include <algorithm>
#include <atomic>
#include <cassert>
#include <functional>
#include <string>
#include <vector>
namespace freeink { namespace ui {
struct InputSnapshot { bool touchPressed=false, touchReleased=false, touchHeld=false; int touchX=0; };
struct ActionEvent { int action=0, value=0; explicit operator bool() const {return action!=0;} };
struct Interaction { int action=0, value=0; };
struct InteractionBuffer {
  int pressCount=0, releaseCount=0; Interaction item{1,1};
  ActionEvent routePublished(const InputSnapshot& snap) {
    if(snap.touchPressed) ++pressCount;
    if(snap.touchReleased) {++releaseCount; return {1,1};}
    return {};
  }
  int activeIndex() const {return 0;}
  const Interaction* publishedData() const {return &item;}
};
}}
struct MappedInputManager {
  enum class Button {NavPrevious, NavNext, Confirm, Back};
  freeink::ui::InputSnapshot snap{};
  bool wasPressed(Button) {return false;}
  bool wasReleased(Button) {return false;}
  bool isPressed(Button) {return false;}
};
freeink::ui::InputSnapshot touchSnapshotFrom(const MappedInputManager& input) {return input.snap;}
struct UITheme {static UITheme& getInstance() {static UITheme theme; return theme;}
                bool hasMainTabs() const {return false;}};
struct OptionPopup {
  static constexpr int MAX_OPTIONS=16, ACTION_OPTION=1, ACTION_CHROME=2;
  bool active=false, ignoreInitialTouchContact=false, ignoreInitialConfirmRelease=false;
  std::atomic<bool> uiReady{false};
  int selectedIndex=0;
  std::vector<std::string> ownedStrings{"Edit","Select items"};
  std::function<void(int)> onSelectCallback;
  freeink::ui::InteractionBuffer interactions;
  void finishShow(int, std::function<void(int)>);
  bool handleInput(MappedInputManager&, const std::function<void()>&);
};
'''

MAIN = r'''
int main() {
  MappedInputManager input;
  int selected=-1, updates=0;
  auto repaint=[&]{++updates;};
  // A popup opened by a physical button or a touch release has no old finger
  // left to consume. Its first new tap must select the second option.
  OptionPopup popup;
  popup.finishShow(0,[&](int index){selected=index;});
  popup.uiReady=true;
  input.snap.touchPressed=true;input.snap.touchHeld=true;
  assert(popup.handleInput(input,repaint));
  assert(popup.interactions.pressCount==1 && popup.selectedIndex==1);
  input.snap={};input.snap.touchReleased=true;
  assert(popup.handleInput(input,repaint));
  assert(!popup.active && selected==1 && popup.interactions.releaseCount==1);
  // An old contact already held at show time must still be swallowed through
  // its release. Only the NEXT full tap may choose an option.
  OptionPopup held;
  selected=-1;held.finishShow(0,[&](int index){selected=index;});held.uiReady=true;
  input.snap={};input.snap.touchHeld=true;
  assert(held.handleInput(input,repaint));
  input.snap={};input.snap.touchReleased=true;
  assert(held.handleInput(input,repaint));
  assert(held.active && selected==-1 && held.interactions.releaseCount==0);
  input.snap={};input.snap.touchPressed=true;input.snap.touchHeld=true;
  assert(held.handleInput(input,repaint));
  input.snap={};input.snap.touchReleased=true;
  assert(held.handleInput(input,repaint));
  assert(!held.active && selected==1);
}
'''


class PopupTouchBarrierTest(unittest.TestCase):
    def test_first_new_touch_and_inherited_contact(self):
        source = SOURCE.read_text()
        # Compile the real member bodies, not a re-implementation of their logic.
        bodies = (method(source, 'bool handleInput(') + '\n' +
                  method(source, 'void finishShow('))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'popup.cpp'
            exe = Path(tmp) / 'popup'
            path.write_text(STUB + '\n' + bodies + '\n' + MAIN)
            subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-fno-exceptions', str(path), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    unittest.main()
