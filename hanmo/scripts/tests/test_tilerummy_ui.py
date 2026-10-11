"""TILE RUMMY real bounded flow and real Activity/Screens host tests."""
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
GAME_DIR = ROOT / 'src/apps_local/tilerummy'
FLOW_HARNESS = r'''
#include "TileRummyFlow.h"
#include <cassert>
#include <cstring>
#include <cstdio>
namespace tr = tilerummy;
namespace ui = tilerummyui;
int main() {
  ui::Flow flow;
  assert(tr::settingsValid(flow.settings));
  for (int p = tr::kMinPlayers; p <= tr::kMaxPlayers; ++p)
    for (int h : tr::kStartingHandOptions)
      for (int m : tr::kMeldMinimumOptions)
        for (int j = 0; j <= tr::kMaxJokers; ++j) {
          flow.settings = {static_cast<uint8_t>(p), static_cast<uint8_t>(h),
                           static_cast<uint8_t>(m), static_cast<uint8_t>(j)};
          assert(flow.begin(12345));
          tr::Game expected{};
          assert(tr::start(expected, flow.settings, 12345));
          assert(std::memcmp(&flow.game, &expected, sizeof(expected)) == 0);
          assert(flow.screen == ui::Screen::Board);
        }
  puts("settings: all 144 offered settings reach actual seeded core start OK");
}
'''


EDITOR_HARNESS = r'''
#include "TileRummyFlow.h"
#include <cassert>
#include <cstring>
#include <cstdio>
namespace tr = tilerummy;
namespace ui = tilerummyui;
static tr::Tile t(int c, int n) { return tr::makeTile(c,n); }
static void fixture(ui::Flow& f, int n = 10) {
  f.begin(77); f.game.table = {}; f.game.hands[0] = {};
  f.game.hands[0].tiles[0]=t(0,n); f.game.hands[0].tiles[1]=t(1,n);
  f.game.hands[0].tiles[2]=t(2,n); f.game.hands[0].tiles[3]=t(3,1);
  f.game.hands[0].count=4; f.resetDraft();
}
static void add(ui::Flow& f, int i) {
  f.setView(ui::View::Hand); assert(f.select(i)); assert(f.addSelected());
}
static void census(const tr::Game& g, int* c) {
  tr::clearCensus(c); tr::countTiles(g.pool,g.poolCount,c); tr::countTable(g.table,c);
  for(int p=0;p<g.settings.players;++p) tr::countTiles(g.hands[p].tiles,g.hands[p].count,c);
}
int main() {
  ui::Flow f; fixture(f);
  const tr::Game before=f.game;
  assert(f.newSet(false)); add(f,0); assert(!f.commit());
  assert(f.result.problem==tr::MoveProblem::InvalidSet && f.result.failedSet==0);
  assert(f.result.setProblem==tr::SetProblem::TooFewTiles);
  assert(std::memcmp(&before,&f.game,sizeof(before))==0);
  assert(f.undo()); assert(f.draft.table.sets[0].count==0);
  add(f,0); add(f,1); add(f,2);
  int original[tr::kTileKinds], after[tr::kTileKinds]; census(f.game,original);
  assert(f.commit()); census(f.game,after);
  assert(std::memcmp(original,after,sizeof(original))==0);
  assert(f.game.turn==1 && f.game.melded[0] && f.game.hands[0].count==1);
  assert(f.screen==ui::Screen::Handoff); f.ready();
  // Existing table is readable, but locked until this player's initial meld.
  assert(f.activeSet==0); f.setView(ui::View::Table); assert(f.select(0));
  assert(!f.removeSelected()); assert(std::memcmp(&f.game.table,&before.table,sizeof(before.table))!=0);
  f.game.turn=0; f.game.hands[0].tiles[0]=t(3,10); f.resetDraft();
  // Rearrange a real table tile via the loose tray; reorder run seats is explicit.
  f.setView(ui::View::Table); assert(f.select(0)); assert(f.removeSelected());
  assert(f.draft.loose.count==1 && f.draft.table.sets[0].count==2);
  f.setView(ui::View::Loose); assert(f.select(0)); assert(!f.returnSelected());
  assert(f.addSelected()); add(f,0); assert(f.commit());
  assert(f.screen==ui::Screen::Done && f.game.winner==0 && f.game.hands[0].count==0);
  fixture(f,6); f.settings.meldMinimum=30; f.game.settings.meldMinimum=30;
  assert(f.newSet(false)); add(f,0); add(f,1); add(f,2);
  const tr::Game small=f.game; assert(!f.commit());
  assert(f.result.problem==tr::MoveProblem::MeldTooSmall && f.result.meldScore==18);
  assert(std::memcmp(&small,&f.game,sizeof(small))==0);
  f.cancel(); assert(f.draft.table.setCount==0 && f.draft.loose.count==0);
  assert(f.newSet(true)); add(f,0); f.setView(ui::View::Table); assert(f.select(0));
  assert(f.removeSelected()); f.setView(ui::View::Loose); assert(f.select(0));
  assert(f.returnSelected() && f.handAvailable(0));
  add(f,0); const tr::Game drawn=f.game; tr::Game expected=drawn; assert(tr::drawTile(expected));
  assert(f.draw()); assert(std::memcmp(&expected,&f.game,sizeof(expected))==0);
  assert(f.draft.loose.count==0 && f.draft.table.setCount==0);
  f.ready(); f.game.poolCount=0; const tr::Game empty=f.game;
  assert(f.draw()); assert(f.game.turn==(empty.turn+1)%empty.settings.players);
  assert(f.game.poolCount==0 && f.game.winner==tr::kNoPlayer);
  f.ready(); assert(f.draw()); assert(f.blocked && f.screen==ui::Screen::Done);
  f.begin(1); f.game.melded[0]=true; f.game.table.setCount=tr::kMaxSets;
  for(int s=0;s<tr::kMaxSets;++s) { f.game.table.sets[s].count=3;
    for(int n=0;n<3;++n) f.game.table.sets[s].tiles[n]=t(s%4,n+1); }
  f.resetDraft(); f.draft.table.sets[7].count=0;
  assert(f.newSet(true) && f.activeSet==7 && "melded player must reuse an emptied original set at max bound");
  std::printf("bounded storage: Flow=%zu Draft=%zu Game=%zu bytes\n",sizeof(ui::Flow),sizeof(ui::Draft),sizeof(tr::Game));
  puts("editor: rejection rollback, undo/cancel, initial threshold, real rearrange, conservation, win and empty-pool passes OK");
}
'''


def compile_flow(folder, harness=FLOW_HARNESS):
    if not (GAME_DIR / 'TileRummyFlow.h').exists():
        raise AssertionError('missing bounded playable flow: TileRummyFlow.h')
    folder = pathlib.Path(folder)
    source = folder / 'flow_host.cpp'
    source.write_text(harness, encoding='utf-8')
    exe = folder / 'flow_host'
    result = subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-I', str(GAME_DIR),
                             str(source), '-o', str(exe)], capture_output=True, text=True)
    if result.returncode:
        raise AssertionError(result.stderr)
    return exe


class TileRummyFlowTest(unittest.TestCase):
    def test_complete_proposed_table_editor_and_core_turn_rules(self):
        with tempfile.TemporaryDirectory() as folder:
            exe = compile_flow(folder, EDITOR_HARNESS)
            result = subprocess.run([str(exe)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            print(result.stdout.strip())

    def test_selected_settings_reach_actual_core_start(self):
        with tempfile.TemporaryDirectory() as folder:
            exe = compile_flow(folder)
            result = subprocess.run([str(exe)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            print(result.stdout.strip())


# Keep actual FreeInkUI/Toybox/reveal behavior; reuse ONLY hardware seams.
from scripts.tests.test_memory_activity import ACTIVITY_BOUNDARY, RENDERER_BOUNDARY
ACTIVITY_BOUNDARY = ACTIVITY_BOUNDARY.replace(
    'bool back = false, tapped = false;',
    'bool back=false, tapped=false, confirm=false, up=false, down=false, left=false, right=false;').replace(
    'return b == Button::Back && back;',
    'switch(b) { case Button::Back: return back; case Button::Confirm: return confirm; '
    'case Button::Up: return up; case Button::Down: return down; case Button::Left: return left; '
    'case Button::Right: return right; } return false;')

ACTIVITY_HARNESS = r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>
#include "TileRummyScreens.h"
#define private public
#include "TileRummyActivity.h"
#undef private
namespace ui = tilerummyui;
namespace tr = tilerummy;
inline int leaves=0, seeds=0;
inline uint32_t nextSeed=12345;
namespace shelf { void leave(GfxRenderer&, MappedInputManager&) { ++leaves; } }
namespace toybox { uint32_t seed() { ++seeds; return nextSeed++; } }
static void draw(TileRummyActivity& a) { a.noteSurfaceBuilt(); a.render(RenderLock{}); }
static void tap(TileRummyActivity& a, MappedInputManager& i, fui::Rect r) {
  assert(!r.empty()); i.tapped=true; i.x=r.x+r.width/2; i.y=r.y+r.height/2;
  a.loop(); i.tapped=false;
}
static fui::Rect rect(TileRummyActivity& a, fui::ActionId id, int value=0) {
  for(size_t n=0;n<a.interactions.count();++n) {
    const auto& h=a.interactions.data()[n]; if(h.action==id && h.value==value) return h.rect;
  }
  std::fprintf(stderr,"missing action %d/%d\n",id,value); assert(false); return {};
}
static void action(TileRummyActivity& a,MappedInputManager& i,fui::ActionId id,int value=0) {
  tap(a,i,rect(a,id,value)); draw(a);
}
static bool text(GfxRenderer& r,const char* value) {
  for(const auto& t:r.texts) if(t.value==value) return true; return false;
}
static void start(TileRummyActivity& a,GfxRenderer& r,MappedInputManager& i) {
  a.onEnter(); draw(a); assert(text(r,"TILE RUMMY")); action(a,i,ui::ActionStart);
  assert(a.flow.screen==ui::Screen::Board);
}
static void fixture(TileRummyActivity& a) {
  auto& f=a.flow; f.game.table={}; f.game.hands[0]={}; f.game.turn=0;
  for(int n=0;n<3;++n) f.game.hands[0].tiles[n]=tr::makeTile(n,10);
  f.game.hands[0].tiles[3]=tr::makeTile(3,1); f.game.hands[0].count=4;
  f.resetDraft(); draw(a);
}
static void tile(TileRummyActivity& a,GfxRenderer& r,MappedInputManager& i,int index) {
  tap(a,i,ui::tileRect(r.device,a.flow,index)); draw(a);
}
static void geometry(TileRummyActivity& a,GfxRenderer& r) {
  assert(a.interactions.count()<=24 && !a.interactions.overflowed());
  for(size_t h=0;h<a.interactions.count();++h) {
    const auto box=a.interactions.data()[h].rect;
    assert(box.width>=44 && box.height>=44);
    assert(box.x>=r.device.safeRect().x && box.right()<=r.device.safeRect().right());
    assert(box.y>=toybox::kBodyTop && box.bottom()<=r.device.safeRect().bottom());
    for(size_t j=h+1;j<a.interactions.count();++j) {
      const auto b=a.interactions.data()[j].rect;
      assert(box.right()+6<=b.x || b.right()+6<=box.x || box.bottom()+6<=b.y || b.bottom()+6<=box.y);
    }
  }
  const int first=a.flow.page*ui::kPageTiles;
  for(int n=first;n<a.flow.itemCount() && n<first+ui::kPageTiles;++n) {
    auto box=ui::tileRect(r.device,a.flow,n); assert(box.width>=44 && box.height>=44);
    assert(ui::tileAt(r.device,a.flow,box.x,box.y)==n);
    assert(ui::tileAt(r.device,a.flow,box.right()-1,box.bottom()-1)==n);
    assert(ui::tileAt(r.device,a.flow,box.right(),box.y)==-1);
    assert(ui::tileAt(r.device,a.flow,box.x,box.bottom())==-1);
    bool painted=false;
    for(const auto& s:r.strokes) if(s.box.x==box.x && s.box.y==box.y && s.box.width==box.width && s.box.height==box.height) painted=true;
    assert(painted && "shared tile rect must be actually painted");
    for(size_t h=0;h<a.interactions.count();++h) {
      auto b=a.interactions.data()[h].rect;
      assert(box.right()+6<=b.x || b.right()+6<=box.x || box.bottom()+6<=b.y || b.bottom()+6<=box.y);
    }
  }
}
int main(int argc,char**argv) {
  assert(argc==2); GfxRenderer r; MappedInputManager input;
  auto instance=TileRummyActivity::create(r,input); assert(instance);
  auto& a=static_cast<TileRummyActivity&>(*instance); std::string scenario=argv[1];
  if(scenario=="settings") {
    a.onEnter(); draw(a); geometry(a,r);
    action(a,input,ui::ActionPlayers); action(a,input,ui::ActionHand);
    action(a,input,ui::ActionMeld); action(a,input,ui::ActionJokers);
    auto settings=a.flow.settings; assert(settings.players==3 && settings.startingHand==18 && settings.meldMinimum==40 && settings.jokers==0);
    auto seed=nextSeed; action(a,input,ui::ActionStart);
    tr::Game expected{}; tr::start(expected,settings,seed);
    assert(std::memcmp(&expected,&a.flow.game,sizeof(expected))==0);
    a.flow.screen=ui::Screen::Done; a.flow.blocked=true; draw(a);
    seed=nextSeed; action(a,input,ui::ActionAgain); tr::start(expected,settings,seed);
    assert(std::memcmp(&expected,&a.flow.game,sizeof(expected))==0 && seeds==2);
    action(a,input,ui::ActionMenu); assert(a.flow.screen==ui::Screen::Menu);
    assert(std::memcmp(&settings,&a.flow.settings,sizeof(settings))==0);
    input.back=true; a.loop(); input.back=false; assert(leaves==1);
    puts("activity settings/again: four real setting controls, core deal, same-settings replay and menu/back OK");
  } else if(scenario=="playable") {
    start(a,r,input); fixture(a); geometry(a,r); const auto before=a.flow.game;
    action(a,input,ui::ActionNewGroup); tile(a,r,input,0); action(a,input,ui::ActionAdd);
    action(a,input,ui::ActionPlay); assert(text(r,"SET 1: NEED 3 TILES"));
    assert(std::memcmp(&before,&a.flow.game,sizeof(before))==0);
    action(a,input,ui::ActionView,static_cast<int>(ui::View::Hand));
    tile(a,r,input,1); action(a,input,ui::ActionAdd); tile(a,r,input,2); action(a,input,ui::ActionAdd);
    action(a,input,ui::ActionPlay); assert(a.flow.game.turn==1 && a.flow.game.melded[0]);
    assert(a.flow.screen==ui::Screen::Handoff && !text(r,"R10") && text(r,"PLAYER 2 - YOUR TURN"));
    action(a,input,ui::ActionReady); a.flow.game.turn=0; a.flow.game.hands[0].tiles[0]=tr::makeTile(3,10);
    a.flow.resetDraft(); draw(a); tile(a,r,input,0); action(a,input,ui::ActionAdd);
    action(a,input,ui::ActionPlay); assert(a.flow.game.winner==0 && a.flow.screen==ui::Screen::Done);
    assert(text(r,"PLAYER 1 WINS")); action(a,input,ui::ActionAgain);
    assert(a.flow.game.winner==tr::kNoPlayer && a.flow.game.hands[0].count==a.flow.settings.startingHand);
    puts("actual Activity: menu->select tiles->invalid feedback->complete PLAY->hot-seat->extension->win->AGAIN OK");
  } else if(scenario=="run") {
    start(a,r,input); fixture(a); auto& f=a.flow; f.game.settings.meldMinimum=20;
    f.game.hands[0].tiles[0]=tr::makeTile(0,7); f.game.hands[0].tiles[1]=tr::makeTile(0,9);
    f.game.hands[0].tiles[2]=tr::makeTile(0,8); f.resetDraft(); draw(a);
    action(a,input,ui::ActionNewRun);
    for(int n=0;n<3;++n) { tile(a,r,input,n); action(a,input,ui::ActionAdd); }
    const auto before=f.game; const auto draft=f.draft;
    action(a,input,ui::ActionPlay); assert(text(r,"SET 1: RUN NOT IN ORDER"));
    assert(std::memcmp(&before,&f.game,sizeof(before))==0 && std::memcmp(&draft,&f.draft,sizeof(draft))==0);
    tile(a,r,input,2); action(a,input,ui::ActionMove,-1);
    assert(f.draft.table.sets[0].tiles[1]==tr::makeTile(0,8));
    action(a,input,ui::ActionPlay); assert(f.game.melded[0] && f.game.turn==1);
    puts("actual run editor: exact failed set/reason, byte-identical rejection, explicit seat reordering then legal opening OK");
  } else if(scenario=="draw") {
    start(a,r,input); fixture(a); action(a,input,ui::ActionNewGroup);
    tile(a,r,input,0); action(a,input,ui::ActionAdd);
    auto expected=a.flow.game; assert(tr::drawTile(expected)); action(a,input,ui::ActionDraw);
    assert(std::memcmp(&expected,&a.flow.game,sizeof(expected))==0);
    assert(a.flow.draft.table.setCount==0 && a.flow.draft.loose.count==0 && a.flow.screen==ui::Screen::Handoff);
    action(a,input,ui::ActionReady); a.flow.game.poolCount=0; draw(a);
    assert(text(r,"PASS EMPTY")); action(a,input,ui::ActionDraw);
    assert(a.flow.game.winner==tr::kNoPlayer && !a.flow.blocked);
    action(a,input,ui::ActionReady); action(a,input,ui::ActionDraw);
    assert(a.flow.screen==ui::Screen::Done && a.flow.blocked && text(r,"BLOCKED - ALL PLAYERS PASSED"));
    assert(a.flow.game.winner==tr::kNoPlayer);
    puts("actual draw: draft discarded, core draw/advance exact, empty pool explicit passes and no fabricated winner OK");
  } else if(scenario=="controls") {
    a.onEnter(); r.device.width=800; r.device.height=480; draw(a); geometry(a,r);
    r.device.width=480; r.device.height=800; draw(a);
    input.down=true; a.loop(); input.down=false; draw(a);
    assert(a.focus==0); input.confirm=true; a.loop(); input.confirm=false; draw(a);
    assert(a.flow.settings.players==3);
    for(int n=0;n<4;++n) { input.down=true; a.loop(); input.down=false; draw(a); }
    input.confirm=true; a.loop(); input.confirm=false; draw(a);
    assert(a.flow.screen==ui::Screen::Board);
    fixture(a);
    for(size_t n=0;n<a.interactions.count();++n)
      assert(a.interactions.data()[n].action!=ui::ActionAdd && a.interactions.data()[n].action!=ui::ActionRemove);
    action(a,input,ui::ActionNewRun);
    input.down=true; a.loop(); input.down=false; draw(a);
    input.confirm=true; a.loop(); input.confirm=false; draw(a);
    assert(a.flow.selected==0); action(a,input,ui::ActionAdd);
    assert(a.flow.draft.table.sets[0].count==1);
    input.back=true; a.loop(); input.back=false; draw(a);
    assert(a.flow.screen==ui::Screen::Menu && a.flow.settings.players==3);
    puts("logical buttons: same control actions and tile geometry; disabled controls absent; landscape settings fit OK");
  } else if(scenario=="rearrange") {
    start(a,r,input); auto& f=a.flow; f.game.table={}; f.game.melded[0]=true;
    f.game.hands[0]={}; f.game.hands[0].count=2;
    f.game.hands[0].tiles[0]=tr::makeTile(0,4); f.game.hands[0].tiles[1]=tr::makeTile(3,13);
    f.game.table.setCount=2;
    for(int s=0;s<2;++s) { f.game.table.sets[s].count=3;
      for(int n=0;n<3;++n) f.game.table.sets[s].tiles[n]=tr::makeTile(0,n+(s?5:1)); }
    f.resetDraft(); draw(a); action(a,input,ui::ActionView,static_cast<int>(ui::View::Table));
    for(int n=0;n<3;++n) { tile(a,r,input,0); action(a,input,ui::ActionRemove); }
    assert(f.draft.loose.count==3); action(a,input,ui::ActionSet,-1);
    action(a,input,ui::ActionView,static_cast<int>(ui::View::Hand)); tile(a,r,input,0); action(a,input,ui::ActionAdd);
    action(a,input,ui::ActionView,static_cast<int>(ui::View::Loose));
    for(int n=0;n<3;++n) { tile(a,r,input,0); action(a,input,ui::ActionAdd); }
    action(a,input,ui::ActionPlay); assert(f.game.table.setCount==1 && f.game.table.sets[0].count==7);
    assert(f.game.turn==1 && f.game.hands[0].count==1);
    for(int n=0;n<7;++n) assert(f.game.table.sets[0].tiles[n]==tr::makeTile(0,n+1));
    puts("actual editor: remove existing tiles into loose tray, transfer sets, add bridge tile, compact COMPLETE table and commit OK");
  } else if(scenario=="paging") {
    start(a,r,input);
    for(int orientation=0;orientation<2;++orientation) {
      r.device.width=orientation?800:480; r.device.height=orientation?480:800;
      auto& f=a.flow; f.game.hands[0].count=tr::kMaxHand;
      for(int n=0;n<tr::kMaxHand;++n) f.game.hands[0].tiles[n]=static_cast<tr::Tile>(n%tr::kTileKinds);
      f.game.table={}; f.resetDraft(); draw(a);
      for(int p=0;p<f.pageCount();++p) {
        assert(f.page==p); geometry(a,r);
        for(int n=p*ui::kPageTiles;n<f.itemCount() && n<(p+1)*ui::kPageTiles;++n) {
          char identity[8]; ui::tileText(f.itemTile(n),identity,sizeof(identity)); assert(text(r,identity));
        }
        if(p+1<f.pageCount()) action(a,input,ui::ActionPage,1);
      }
      assert(!f.changePage(1)); assert(ui::tileRect(r.device,f,-1).empty());
      f.game.table.setCount=tr::kMaxSets; f.game.melded[0]=true;
      for(int s=0;s<tr::kMaxSets;++s) {
        f.game.table.sets[s].count=tr::kMaxSetTiles;
        for(int n=0;n<tr::kMaxSetTiles;++n) f.game.table.sets[s].tiles[n]=tr::makeTile(s%4,n+1);
      }
      f.resetDraft(); f.setView(ui::View::Table); f.activeSet=0; draw(a);
      for(int s=0;s<tr::kMaxSets;++s) {
        assert(f.activeSet==s); geometry(a,r); action(a,input,ui::ActionPage,1); geometry(a,r);
        if(s+1<tr::kMaxSets) action(a,input,ui::ActionSet,1);
      }
      assert(!f.changeSet(1)); assert(!f.newSet(false));
    }
    char identity[8]; const char* expected[]={"R13","B13","Y13","K13","J"};
    for(int n=0;n<5;++n) { ui::tileText(n==4?tr::kJoker:tr::makeTile(n,13),identity,sizeof(identity)); assert(std::strcmp(identity,expected[n])==0); }
    puts("real screen geometry: 106 hand tiles, 35 sets x13 tiles, portrait/landscape, mono identities and <=24 controls OK");
  } else if(scenario=="reveal") {
    start(a,r,input); fixture(a); action(a,input,ui::ActionNewGroup);
    const auto before=a.flow.game; const auto meaning=a.surfaceMeaning();
    r.autoPaint=false; action(a,input,ui::ActionView,static_cast<int>(ui::View::Table));
    assert(a.surfaceMeaning()!=meaning); auto count=a.flow.draft.table.sets[0].count;
    tap(a,input,rect(a,ui::ActionNewRun)); assert(a.flow.draft.table.sets[0].count==count);
    paintclock::notePainted(); action(a,input,ui::ActionView,static_cast<int>(ui::View::Hand));
    tile(a,r,input,0); assert(a.flow.selected==-1 && "unseen view cannot select a tile");
    paintclock::notePainted(); tile(a,r,input,0); assert(a.flow.selected==0);
    tap(a,input,rect(a,ui::ActionAdd)); assert(a.flow.draft.table.sets[0].count==0 && "new ADD live state needs paint");
    paintclock::notePainted(); action(a,input,ui::ActionAdd);
    assert(std::memcmp(&before,&a.flow.game,sizeof(before))==0);
    r.autoPaint=true; draw(a); tile(a,r,input,1); action(a,input,ui::ActionAdd);
    assert(a.flow.draft.table.sets[0].count==2);
    auto old=a.surfaceMeaning(); a.flow.page=1; assert(a.surfaceMeaning()!=old); a.flow.page=0;
    old=a.surfaceMeaning(); a.flow.game.poolCount=0; assert(a.surfaceMeaning()!=old);
    puts("real reveal gate: unseen editor/view/page and live controls inert, painted consecutive edits accepted OK");
  } else return 2;
}
'''


def compile_activity(folder, mutation=None):
    folder = pathlib.Path(folder)
    names = ['TileRummyCore.h', 'TileRummyFlow.h', 'TileRummyScreens.h', 'TileRummyScreens.cpp',
             'TileRummyActivity.h', 'TileRummyActivity.cpp']
    for name in names:
        if not (GAME_DIR / name).exists():
            raise AssertionError('missing playable integration: ' + name)
        dest = folder / 'src/apps_local/tilerummy' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(GAME_DIR / name, dest)
    for rel in ['lib/GfxRenderer/RevealedInteractions.h', 'lib/GfxRenderer/PaintClock.h'] + [
        'src/apps_local/ui/' + n for n in ['ToyboxScreen.h', 'ToyboxTokens.h', 'ToyboxText.h', 'ToyboxMetrics.h']]:
        dest = folder / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, dest)
    seams = {
        'src/activities/Activity.h': ACTIVITY_BOUNDARY,
        'src/apps_local/ui/ToyboxTheme.h': RENDERER_BOUNDARY,
        'src/apps_local/ui/ToyboxFonts.h': '#pragma once\nnamespace toybox { inline void ensureFonts(GfxRenderer& r) { ++r.fonts; } }\n',
        'src/apps_local/ui/ToyboxSeed.h': (ROOT / 'src/apps_local/ui/ToyboxSeed.h').read_text(),
        'src/apps_local/Shelf.h': '#pragma once\nnamespace shelf { void leave(GfxRenderer&, MappedInputManager&); }\n',
        'src/components/UITheme.h': '#pragma once\nstruct GuiBoundary { void drawButtonHints(GfxRenderer&, const char*, const char*, const char*, const char*) {} };\ninline GuiBoundary GUI;\n',
        'Memory.h': '#pragma once\n#include <memory>\n#include <new>\n#include <utility>\ntemplate<class T, class... Args> std::unique_ptr<T> makeUniqueNoThrow(Args&&... args) { return std::unique_ptr<T>(new (std::nothrow) T(std::forward<Args>(args)...)); }\n',
        'Logging.h': '#pragma once\n#define LOG_ERR(...) ((void)0)\n',
    }
    for rel, value in seams.items():
        dest = folder / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(value, encoding='utf-8')
    if mutation:
        path = folder / 'src/apps_local/tilerummy/TileRummyScreens.cpp'
        source = path.read_text()
        old, new = mutation
        assert old in source
        path.write_text(source.replace(old, new, 1))
    source = folder / 'activity_host.cpp'
    source.write_text(ACTIVITY_HARNESS)
    exe = folder / 'activity_host'
    sdk = ROOT / 'freeink-sdk/libs/ui/FreeInkUI'
    result = subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-Wno-comment',
        '-Wno-misleading-indentation', '-I', str(folder), '-I', str(folder / 'src/apps_local/tilerummy'),
        '-I', str(sdk / 'include'), '-I', str(ROOT / 'freeink-sdk/libs/assets/Icons/include'),
        str(source), str(folder / 'src/apps_local/tilerummy/TileRummyActivity.cpp'),
        str(folder / 'src/apps_local/tilerummy/TileRummyScreens.cpp'), str(sdk / 'src/FreeInkUI.cpp'),
        '-o', str(exe)], capture_output=True, text=True)
    if result.returncode:
        raise AssertionError('actual Activity+Screens compile failed:\n' + result.stderr)
    return exe


class TileRummyActivityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.folder.cleanup)
        cls.exe = compile_activity(cls.folder.name)

    def scenario(self, name):
        result = subprocess.run([str(self.exe), name], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())

    def test_settings_menu_and_again_really_deal_chosen_configuration(self):
        self.scenario('settings')

    def test_actual_activity_tile_editor_invalid_play_handoff_extension_win(self):
        self.scenario('playable')

    def test_every_hand_set_seat_pages_and_shared_geometry_in_two_orientations(self):
        self.scenario('paging')

    def test_unseen_view_page_live_controls_are_gated_until_paint(self):
        self.scenario('reveal')

    def test_logical_buttons_and_disabled_controls_and_landscape_settings(self):
        self.scenario('controls')

    def test_real_activity_existing_table_can_be_repartitioned(self):
        self.scenario('rearrange')

    def test_run_rejection_reports_reason_and_can_be_fixed_by_seat_reordering(self):
        self.scenario('run')

    def test_draw_discards_draft_and_empty_pool_is_explicit_no_winner(self):
        self.scenario('draw')

    def test_only_logical_input_seed_and_bounded_ascii_ui_sources(self):
        names = ('TileRummyActivity.h', 'TileRummyActivity.cpp', 'TileRummyFlow.h',
                 'TileRummyScreens.h', 'TileRummyScreens.cpp')
        source = '\n'.join((GAME_DIR / name).read_text() for name in names)
        for token in ('HalGPIO', 'BTN_', 'millis(', 'delay(', 'sleep(', '<chrono>',
                      'std::vector', 'std::map', 'random_device', 'malloc('):
            self.assertNotIn(token, source)
        self.assertEqual(source.count('toybox::seed()'), 1)
        self.assertIn('makeUniqueNoThrow<TileRummyActivity>', source)
        for name in names:
            self.assertNotIn(b'\r', (GAME_DIR / name).read_bytes())
        self.assertTrue((GAME_DIR / 'TileRummyScreens.cpp').read_text().isascii())

    def test_compile_clean_mono_identity_mutation_is_killed(self):
        with tempfile.TemporaryDirectory() as folder:
            exe = compile_activity(folder, ('"RBYK"', '"RRRR"'))
            result = subprocess.run([str(exe), 'paging'], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0, 'colour-letter mutation must fail behavior')
            self.assertIn('std::strcmp(identity,expected[n])==0', result.stderr)


if __name__ == '__main__':
    unittest.main()
