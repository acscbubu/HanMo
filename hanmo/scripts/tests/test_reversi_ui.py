"""Compile actual Reversi Activity/Screens and real FreeInkUI/reveal gates.

Reuse the exercised Memory hardware seams, never surrogate game/UI routing.
Host verification does not claim firmware or physical e-ink acceptance.
"""
import hashlib
import pathlib
import shutil
import subprocess
import tempfile
import unittest

from scripts.tests.test_memory_activity import ACTIVITY_BOUNDARY, RENDERER_BOUNDARY

ROOT = pathlib.Path(__file__).resolve().parents[2]
GAME_DIR = ROOT / "src/apps_local/reversi"
OWNED = ("ReversiActivity.h", "ReversiActivity.cpp", "ReversiFlow.h",
         "ReversiScreens.h", "ReversiScreens.cpp")

BOUNDARY = ACTIVITY_BOUNDARY.replace(
    "struct StrokeCall", "struct FillCall { fui::Rect box; fui::Paint paint; };\nstruct StrokeCall"
).replace(
    "std::vector<StrokeCall> strokes;", "std::vector<StrokeCall> strokes;\n  std::vector<FillCall> fills;"
).replace(
    "texts.clear(); strokes.clear();", "texts.clear(); strokes.clear(); fills.clear();"
).replace(
    "bool back = false, tapped = false;",
    "bool back = false, tapped = false, confirm = false, up = false, down = false, left = false, right = false;\n"
    "  bool heldConfirm = false;"
).replace(
    "return b == Button::Back && back;",
    "return b == Button::Back ? back : b == Button::Confirm ? confirm : b == Button::Up ? up : "
    "b == Button::Down ? down : b == Button::Left ? left : right;"
).replace(
    "struct Labels {", "bool isPressed(Button b) const { return b == Button::Confirm && heldConfirm; }\n  struct Labels {"
)
RENDER_BOUNDARY = RENDERER_BOUNDARY.replace(
    "void fill(Rect, Paint, uint8_t, uint8_t) override {}",
    "void fill(Rect box, Paint paint, uint8_t, uint8_t) override { renderer_.fills.push_back({box, paint}); }"
)

HARNESS = r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include <memory>
#include <string>
#include <utility>
#include "ReversiScreens.h"
#define private public
#include "ReversiActivity.h"
#undef private
namespace rv = reversi;
namespace ui = reversiui;
inline int leaveCount = 0;
namespace shelf { void leave(GfxRenderer&, MappedInputManager&) { ++leaveCount; } }
static bool sameGame(const rv::Game& a, const rv::Game& b) {
  for (int c=0;c<8;++c) for (int r=0;r<8;++r) if (a.cell[c][r]!=b.cell[c][r]) return false;
  return a.turn==b.turn && a.outcome==b.outcome && a.lastColumn==b.lastColumn && a.lastRow==b.lastRow;
}
static void draw(ReversiActivity& a) { a.noteSurfaceBuilt(); a.render(RenderLock{}); }
static void tap(ReversiActivity& a, MappedInputManager& i, fui::Rect box) {
  assert(!box.empty());
  i.tapped=true; i.x=box.x+box.width/2; i.y=box.y+box.height/2; a.loop(); i.tapped=false;
}
static fui::Rect actionRect(const ReversiActivity& a, fui::ActionId action) {
  for (size_t n=0;n<a.interactions.count();++n) if(a.interactions.data()[n].action==action)
    return a.interactions.data()[n].rect;
  assert(false && "real screen must register requested control"); return {};
}
static void cell(ReversiActivity& a, GfxRenderer& r, MappedInputManager& i, int c, int row) {
  tap(a,i,ui::cardRect(r.device,row*8+c));
}
static bool hasText(const GfxRenderer& r, const char* value) {
  for(const auto& text:r.texts) if(text.value==value) return true;
  return false;
}
static void start(ReversiActivity& a, GfxRenderer& r, MappedInputManager& i) {
  a.onEnter(); draw(a);
  assert(hasText(r,"REVERSI") && hasText(r,"LOCAL TWO PLAYER"));
  assert(a.interactions.count()==1);
  tap(a,i,actionRect(a,ui::ActionStart));
  rv::Game expected{}; rv::start(expected);
  assert(a.screen==rv::Screen::Board && sameGame(a.game,expected));
  draw(a);
  assert(hasText(r,"SOLID TO MOVE") && hasText(r,"SOLID 2   OUTLINE 2"));
}
bool sameRect(fui::Rect a, fui::Rect b) {
  return a.x==b.x && a.y==b.y && a.width==b.width && a.height==b.height;
}
bool gap(fui::Rect a, fui::Rect b) {
  return a.right()+6<=b.x || b.right()+6<=a.x || a.bottom()+6<=b.y || b.bottom()+6<=a.y;
}
int main(int argc,char** argv) {
  assert(argc==2); GfxRenderer r; MappedInputManager input;
  auto instance=ReversiActivity::create(r,input); assert(instance);
  auto& a=static_cast<ReversiActivity&>(*instance);
  const std::string scenario=argv[1];
  if(scenario=="opening") {
    start(a,r,input);
    assert(r.fonts==1 && a.entries==1 && a.interactions.count()==1);
    assert(hasText(r,"+ LEGAL MOVE"));
    int markers=0;
    for(const auto& text:r.texts) if(text.value=="+") {
      const int index=ui::cellAt(r.device,text.box.x+text.box.width/2,text.box.y+text.box.height/2);
      assert(index>=0 && rv::legalAt(a.game,index%8,index/8)); ++markers;
    }
    assert(markers==4 && "actual screen must draw all and only opening legal hints");
    const rv::Game before=a.game; const int updates=a.updates;
    cell(a,r,input,0,0); cell(a,r,input,3,3);
    input.tapped=true; input.x=-1; input.y=-1; a.loop(); input.tapped=false;
    assert(sameGame(before,a.game) && a.updates==updates);
    rv::Game expected=a.game; assert(rv::play(expected,3,2));
    cell(a,r,input,3,2);
    assert(sameGame(a.game,expected) && a.updates==updates+1);
    assert(a.game.cell[3][3]==rv::kDark && a.game.turn==rv::kLight);
    draw(a);
    assert(hasText(r,"OUTLINE TO MOVE") && hasText(r,"SOLID 4   OUTLINE 1"));
    assert(a.interactions.count()<=toybox::kMaxInteractions);
    puts("opening: real START->8x8 hot-seat, legal hints, flip, score, invalid touch no-op OK");
  } else if(scenario=="ending") {
    for(const uint8_t mover:{rv::kDark,rv::kLight}) {
      start(a,r,input);
      for(int c=0;c<8;++c) for(int row=0;row<8;++row) a.game.cell[c][row]=rv::kEmpty;
      a.game.cell[1][0]=a.game.cell[2][0]=a.game.cell[4][0]=rv::other(mover);
      a.game.cell[3][0]=mover; a.game.turn=mover; a.game.outcome=rv::Outcome::Running;
      draw(a);
      rv::Game expected=a.game; assert(rv::play(expected,0,0));
      cell(a,r,input,0,0); draw(a);
      assert(sameGame(a.game,expected) && a.screen==rv::Screen::Board);
      assert(a.game.turn==mover && rv::legalMoveCount(a.game,rv::other(mover))==0);
      assert(hasText(r,mover==rv::kDark?"OUTLINE PASS - NO MOVE":"SOLID PASS - NO MOVE"));
      assert(hasText(r,mover==rv::kDark?"SOLID TO MOVE":"OUTLINE TO MOVE"));
      const auto lastRect=ui::cardRect(r.device,5);
      assert(rv::play(expected,5,0)); cell(a,r,input,5,0); draw(a);
      assert(sameGame(a.game,expected) && a.screen==rv::Screen::Done);
      assert(rv::discCount(a.game,rv::kEmpty)>0 && hasText(r,"NO MOVES - GAME OVER"));
      assert(hasText(r,mover==rv::kDark?"SOLID WINS":"OUTLINE WINS"));
      assert(hasText(r,mover==rv::kDark?"SOLID 6   OUTLINE 0":"SOLID 0   OUTLINE 6"));
      assert(a.interactions.count()==2 && sameRect(lastRect,ui::cardRect(r.device,5)));
      assert(gap(actionRect(a,ui::ActionMenu),actionRect(a,ui::ActionAgain)));
      const auto frozen=a.game; const int updates=a.updates;
      cell(a,r,input,6,0); assert(sameGame(a.game,frozen) && a.updates==updates);
      tap(a,input,actionRect(a,ui::ActionAgain)); draw(a);
      rv::start(expected); assert(sameGame(a.game,expected) && a.screen==rv::Screen::Board);
      assert(a.interactions.count()==1 && hasText(r,"SOLID TO MOVE"));
    }
    // A legal last move flips exactly one, settling a full 32/32 board as DRAW.
    start(a,r,input);
    for(int c=0;c<8;++c) for(int row=0;row<8;++row)
      a.game.cell[c][row]=row>=4?rv::kLight:rv::kDark;
    a.game.cell[0][0]=rv::kEmpty; a.game.cell[1][0]=rv::kLight;
    a.game.turn=rv::kDark; draw(a);
    assert(rv::capturedBy(a.game,0,0,rv::kDark)==1);
    cell(a,r,input,0,0); draw(a);
    assert(a.screen==rv::Screen::Done && a.game.outcome==rv::Outcome::Draw);
    assert(hasText(r,"DRAW") && hasText(r,"SOLID 32   OUTLINE 32"));
    assert(hasText(r,"NO MOVES - GAME OVER") && hasText(r,"AGAIN"));
    puts("ending: visible automatic passes, two-stuck ending before full board, both winners, DRAW and AGAIN OK");
  } else if(scenario=="buttons") {
    a.onEnter(); draw(a);
    input.confirm=true; a.loop(); input.confirm=false;
    assert(a.screen==rv::Screen::Board && "logical Confirm must activate START");
    draw(a); rv::Game expected=a.game; assert(rv::play(expected,3,2));
    input.confirm=true; a.loop(); input.confirm=false;
    assert(sameGame(a.game,expected) && "Confirm plays the initially selected legal move");
    draw(a);
    const auto frozen=a.game; const int updates=a.updates;
    input.up=true; a.loop(); input.up=false; draw(a);
    input.confirm=true; a.loop(); input.confirm=false;
    assert(sameGame(a.game,frozen) && a.updates==updates+1);
    // A Shelf's inherited Confirm hold/release cannot start this Activity.
    input.heldConfirm=true; a.onEnter(); draw(a);
    input.confirm=true; a.loop(); assert(a.screen==rv::Screen::Menu);
    input.heldConfirm=false; a.loop(); assert(a.screen==rv::Screen::Menu);
    input.confirm=false;
    input.confirm=true; a.loop(); input.confirm=false;
    assert(a.screen==rv::Screen::Board);
    puts("buttons: logical Confirm, directional cursor, illegal Confirm no-op and inherited-release barrier OK");
  } else if(scenario=="geometry") {
    for(const auto size:{fui::Size{480,800},fui::Size{800,480},fui::Size{600,900}}) {
      r.device.width=size.width; r.device.height=size.height;
      r.device.safeArea={14,8,12,6};
      start(a,r,input);
      const auto safe=r.device.safeRect();
      for(int index=0;index<64;++index) {
        const auto box=ui::cardRect(r.device,index);
        assert(box.width==box.height && box.width>=(size.width<size.height?44:22));
        assert(box.x>=safe.x && box.right()<=safe.right() && box.y>=toybox::kBodyTop);
        assert(box.bottom()<=actionRect(a,ui::ActionMenu).y-6);
        assert(ui::cellAt(r.device,box.x,box.y)==index);
        assert(ui::cellAt(r.device,box.right()-1,box.bottom()-1)==index);
        bool painted=false;
        for(const auto& stroke:r.strokes) if(sameRect(stroke.box,box)) painted=true;
        assert(painted && "drawing must use the exact inverse hit geometry");
        fui::InputSnapshot hit{}; hit.touchReleased=true;
        hit.touchX=box.x+box.width/2; hit.touchY=box.y+box.height/2;
        assert(a.interactions.route(hit).action==fui::NO_ACTION);
        for(size_t h=0;h<a.interactions.count();++h) assert(gap(box,a.interactions.data()[h].rect));
        for(int j=index+1;j<64;++j) assert(gap(box,ui::cardRect(r.device,j)));
        if(index%8<7) {
          const auto next=ui::cardRect(r.device,index+1); assert(next.x-box.right()==6);
          for(int x=box.right();x<next.x;++x) assert(ui::cellAt(r.device,x,box.y)==rv::kNoCell);
        }
        if(index<56) {
          const auto below=ui::cardRect(r.device,index+8); assert(below.y-box.bottom()==6);
          for(int y=box.bottom();y<below.y;++y) assert(ui::cellAt(r.device,box.x,y)==rv::kNoCell);
        }
        const auto piece=a.game.cell[index%8][index/8];
        if(piece!=rv::kEmpty) {
          fui::Color colour=fui::Color::Transparent;
          for(const auto& fill:r.fills)
            if(fill.box.contains(box.x+box.width/2,box.y+box.height/2)) colour=fill.paint.color;
          assert(colour==(piece==rv::kDark?fui::Color::Black:fui::Color::White));
        }
      }
      const auto footer=actionRect(a,ui::ActionMenu);
      assert(footer.height>=44 && footer.x>=safe.x && footer.right()<=safe.right());
      assert(footer.bottom()<=safe.bottom()-36 && a.interactions.count()==1);
      assert(ui::cardRect(r.device,-1).empty() && ui::cardRect(r.device,64).empty());
      assert(ui::cellAt(r.device,footer.x,footer.y)==rv::kNoCell);
      assert(ui::cellAt(r.device,-1,-1)==rv::kNoCell);
      std::printf("geometry: %dx%d, %dpx squares, 6px gaps, 1 control, solid/outline ink OK\n",
                  size.width,size.height,ui::cardRect(r.device,0).width);
    }
  } else if(scenario=="navigation") {
    auto back=[&]() { input.back=true; a.loop(); input.back=false; };
    a.onEnter(); input.confirm=true; a.loop(); input.confirm=false;
    assert(a.screen==rv::Screen::Menu && !a.interactionsReady);
    back(); assert(leaveCount==1);
    for(const auto state:{rv::Screen::Board,rv::Screen::Done}) {
      start(a,r,input); a.screen=state;
      if(state==rv::Screen::Done) {
        for(int c=0;c<8;++c) for(int row=0;row<8;++row) a.game.cell[c][row]=rv::kDark;
        rv::settle(a.game);
      }
      draw(a); const auto before=a.game; const int leaves=leaveCount;
      back(); assert(a.screen==rv::Screen::Menu && !a.interactionsReady && leaveCount==leaves);
      assert(sameGame(before,a.game)); draw(a); back(); assert(leaveCount==leaves+1);
      start(a,r,input); a.screen=state;
      if(state==rv::Screen::Done) a.game.outcome=rv::Outcome::DarkWins;
      draw(a); const int exited=leaveCount;
      tap(a,input,actionRect(a,ui::ActionMenu)); assert(leaveCount==exited+1);
    }
    a.onEnter(); draw(a); const auto control=actionRect(a,ui::ActionStart);
    input.tapped=true; input.x=control.x+1; input.y=control.y+1;
    const int leaves=leaveCount; back(); input.tapped=false;
    assert(leaveCount==leaves+1 && a.screen==rv::Screen::Menu);
    puts("navigation: pre-render taps inert, board/result Back->Menu->Shelf, MENU exits and Back priority OK");
  } else if(scenario=="reveal") {
    a.onEnter(); draw(a); const uint32_t menu=a.surfaceMeaning();
    tap(a,input,actionRect(a,ui::ActionStart));
    const uint32_t live=a.surfaceMeaning(); assert(live!=menu);
    r.autoPaint=false; draw(a); const auto opening=a.game;
    cell(a,r,input,3,2); assert(sameGame(a.game,opening));
    paintclock::notePainted(); cell(a,r,input,3,2);
    assert(a.game.turn==rv::kLight && a.surfaceMeaning()!=live);
    draw(a); const auto light=a.game;
    cell(a,r,input,2,2); assert(sameGame(a.game,light) && "next seat requires completed paint");
    paintclock::notePainted(); cell(a,r,input,2,2); assert(!sameGame(a.game,light));
    draw(a); paintclock::notePainted(); const uint32_t content=a.surfaceMeaning();
    a.cursor=63; a.passedSide=rv::kLight; a.game.lastColumn=7;
    assert(a.surfaceMeaning()==content && "cursor, pass banner, last move are not geometry meaning");
    r.device.safeArea.left+=4; assert(a.surfaceMeaning()!=content);
    r.device.safeArea.left-=4;
    a.game.outcome=rv::Outcome::Draw; assert(a.surfaceMeaning()!=content);
    a.screen=rv::Screen::Done; draw(a);
    const auto again=actionRect(a,ui::ActionAgain);
    const auto frozen=a.game; tap(a,input,again);
    assert(a.screen==rv::Screen::Done && sameGame(a.game,frozen) && "unpainted AGAIN must not restart");
    paintclock::notePainted(); tap(a,input,again);
    assert(a.screen==rv::Screen::Board); draw(a);
    cell(a,r,input,3,2); assert(a.game.lastColumn==rv::kNoCell);
    paintclock::notePainted(); cell(a,r,input,3,2); assert(a.game.lastColumn==3);
    puts("reveal: real gates block unseen board/turn/AGAIN/layout, ignore transient cursor and reopen on paint OK");
  } else if(scenario=="fullgame") {
    start(a,r,input); rv::Game expected=a.game; int moves=0;
    while(!rv::over(expected)) {
      int index=-1;
      for(int n=0;n<64;++n) if(rv::legalAt(expected,n%8,n/8)) {index=n;break;}
      assert(index>=0 && moves<60 && "core must automatically pass rather than stall");
      assert(rv::play(expected,index%8,index/8));
      cell(a,r,input,index%8,index/8); ++moves;
      assert(sameGame(a.game,expected)); draw(a);
      assert(a.interactions.count()==(rv::over(expected)?2u:1u));
    }
    assert(a.screen==rv::Screen::Done && hasText(r,"AGAIN"));
    assert(rv::discCount(a.game,rv::kDark)+rv::discCount(a.game,rv::kLight)==moves+4);
    std::printf("fullgame: %d real geometry-routed local moves -> settled result OK\n",moves);
  } else { return 2; }
}
'''


def compile_activity(folder, mutations=None):
    folder = pathlib.Path(folder)
    rels = ["src/apps_local/reversi/" + f for f in (*OWNED, "ReversiCore.h")]
    rels += ["lib/GfxRenderer/RevealedInteractions.h", "lib/GfxRenderer/PaintClock.h"]
    rels += ["src/apps_local/ui/" + f for f in
             ("ToyboxScreen.h", "ToyboxTokens.h", "ToyboxText.h", "ToyboxMetrics.h")]
    for rel in rels:
        target = folder / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, target)
    for filename, old, new in mutations or []:
        path = folder / "src/apps_local/reversi" / filename
        source = path.read_text()
        assert source.count(old) == 1, "mutation anchor must be unique"
        path.write_text(source.replace(old, new), encoding="utf-8")
    seams = {
        "src/activities/Activity.h": BOUNDARY,
        "src/apps_local/ui/ToyboxTheme.h": RENDER_BOUNDARY,
        "src/apps_local/ui/Toybox.h": '#pragma once\n',
        "src/apps_local/ui/ToyboxFonts.h": '#pragma once\nnamespace toybox { inline void ensureFonts(GfxRenderer& r) { ++r.fonts; } }\n',
        "src/apps_local/Shelf.h": '#pragma once\nnamespace shelf { void leave(GfxRenderer&, MappedInputManager&); }\n',
        "src/components/UITheme.h": '#pragma once\nstruct GuiBoundary { void drawButtonHints(GfxRenderer&, const char*, const char*, const char*, const char*) {} };\ninline GuiBoundary GUI;\n',
        "Memory.h": '#pragma once\n#include <memory>\n#include <new>\n#include <utility>\n#define LOG_ERR(...) ((void)0)\ntemplate<class T, class... Args> std::unique_ptr<T> makeUniqueNoThrow(Args&&... args) { return std::unique_ptr<T>(new (std::nothrow) T(std::forward<Args>(args)...)); }\n',
    }
    for rel, text in seams.items():
        target = folder / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    harness = folder / "reversi_host.cpp"
    harness.write_text(HARNESS, encoding="utf-8")
    exe = folder / "reversi_host"
    sdk = ROOT / "freeink-sdk/libs/ui/FreeInkUI"
    cmd = ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-Wno-comment",
           "-I", str(folder), "-I", str(folder / "src/apps_local/reversi"),
           "-I", str(folder / "src"), "-I", str(sdk / "include"),
           "-I", str(ROOT / "freeink-sdk/libs/assets/Icons/include"),
           str(harness), str(folder / "src/apps_local/reversi/ReversiActivity.cpp"),
           str(folder / "src/apps_local/reversi/ReversiScreens.cpp"),
           str(sdk / "src/FreeInkUI.cpp"), "-o", str(exe)]
    compiled = subprocess.run(cmd, capture_output=True, text=True)
    if compiled.returncode:
        raise AssertionError("actual Reversi Activity/Screens compile failed:\n" + compiled.stderr)
    return exe


class ReversiUITest(unittest.TestCase):
    def run_scenario(self, scenario):
        for filename in OWNED:
            self.assertTrue((GAME_DIR / filename).exists(), "missing playable UI: " + filename)
        cls = type(self)
        if not hasattr(cls, "exe"):
            cls.tmp = tempfile.TemporaryDirectory()
            cls.addClassCleanup(cls.tmp.cleanup)
            cls.exe = compile_activity(cls.tmp.name)
        result = subprocess.run([str(cls.exe), scenario], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())

    def test_opening_legal_hints_flip_score_and_invalid_touch(self):
        self.run_scenario("opening")

    def test_mandatory_pass_results_draw_and_again(self):
        self.run_scenario("ending")

    def test_logical_buttons_and_inherited_confirm_release(self):
        self.run_scenario("buttons")

    def test_shared_geometry_safe_areas_gaps_and_piece_ink(self):
        self.run_scenario("geometry")

    def test_back_menu_and_one_gesture_priority(self):
        self.run_scenario("navigation")

    def test_async_paint_gates_turn_layout_and_again_not_cursor(self):
        self.run_scenario("reveal")

    def test_complete_hot_seat_game_uses_real_core_and_routed_taps(self):
        self.run_scenario("fullgame")

    def test_source_safety_and_read_only_core(self):
        text = "\n".join((GAME_DIR / name).read_text() for name in OWNED)
        for token in ("HalGPIO", "BTN_", "millis(", "delay(", "sleep(", "random_device", "toybox::seed("):
            self.assertNotIn(token, text)
        self.assertNotRegex(text, r"(?:SD|NVS|Storage)\.")
        self.assertIn("mappedInput.wasScreenTapped", text)
        self.assertIn("makeUniqueNoThrow<ReversiActivity>", text)
        self.assertIn("toybox::Frame", text)
        self.assertIn("surfaceRevealed()", text)
        self.assertNotRegex((GAME_DIR / "ReversiActivity.cpp").read_text(), r"(?:surface|screen)\.button\(")
        for name in OWNED:
            self.assertNotIn(b"\r", (GAME_DIR / name).read_bytes())
        self.assertNotIn(b"\r", pathlib.Path(__file__).read_bytes())
        self.assertEqual(hashlib.sha256((GAME_DIR / "ReversiCore.h").read_bytes()).hexdigest(),
                         "8831b60b6f55ecb7e47d0d2240c09241cea12d387e2774b3132c5620324c77e1")

    def test_mutation_sensitivity_without_editing_production(self):
        originals = {name: hashlib.sha256((GAME_DIR / name).read_bytes()).digest()
                     for name in (*OWNED, "ReversiCore.h")}
        mutations = [
            ("reveal guard removed", "reveal", "ReversiActivity.cpp",
             "screen != rv::Screen::Board || !surfaceRevealed()", "screen != rv::Screen::Board"),
            ("inverse hit index shifted", "geometry", "ReversiScreens.cpp",
             "if (!card.empty() && card.contains(x, y)) return index;",
             "if (!card.empty() && card.contains(x, y)) return (index + 1) % reversi::kCells;"),
            ("legal hints concealed", "opening", "ReversiScreens.cpp",
             'if (reversi::legalAt(game, column, row)) label(screen, card, "+");',
             'if (false) label(screen, card, "+");'),
            ("automatic pass notice removed", "ending", "ReversiScreens.cpp",
             "model.passedSide == reversi::kLight", "false"),
            ("terminal navigation removed", "ending", "ReversiActivity.cpp",
             "if (rv::over(game)) goTo(rv::Screen::Done);",
             "if (rv::over(game)) goTo(rv::Screen::Board);"),
            ("inherited Confirm guard removed", "buttons", "ReversiActivity.cpp",
             "!consumeConfirm && mappedInput.wasReleased(MappedInputManager::Button::Confirm)",
             "(consumeConfirm || !consumeConfirm) && mappedInput.wasReleased(MappedInputManager::Button::Confirm)"),
        ]
        for label, scenario, filename, old, new in mutations:
            with self.subTest(mutation=label), tempfile.TemporaryDirectory() as folder:
                exe = compile_activity(folder, [(filename, old, new)])
                result = subprocess.run([str(exe), scenario], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0, "mutation survived: " + label)
                self.assertIn("Assertion", result.stderr, result.stdout + result.stderr)
                print("mutation killed: " + label + " (host assertion, exit " + str(result.returncode) + ")")
        self.assertEqual(originals, {name: hashlib.sha256((GAME_DIR / name).read_bytes()).digest()
                                     for name in originals})
        print("mutation originals: all UI files and read-only core SHA-256 unchanged")


if __name__ == "__main__":
    unittest.main()
