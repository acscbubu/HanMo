"""Real Mahjong Activity/screens/core + FreeInkUI, hardware seams only."""
import pathlib
import subprocess
import tempfile
import unittest

from scripts.tests.test_memory_activity import ACTIVITY_BOUNDARY, RENDERER_BOUNDARY

ROOT = pathlib.Path(__file__).resolve().parents[2]
GAME_DIR = ROOT / 'src/apps_local/mahjong'
OWNED = ('MahjongActivity.h', 'MahjongActivity.cpp', 'MahjongFlow.h',
         'MahjongScreens.h', 'MahjongScreens.cpp')

HARNESS = r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include <memory>
#include <string>
#include "MahjongScreens.h"
#define private public
#include "MahjongActivity.h"
#undef private
namespace mj = mahjong;
namespace ui = mahjongui;
inline int leaves = 0, seeds = 0;
inline uint32_t nextSeed = 123u;
namespace shelf { void leave(GfxRenderer&, MappedInputManager&) { ++leaves; } }
namespace toybox { uint32_t seed() { ++seeds; return nextSeed++; } }
static bool hasText(const GfxRenderer& r, const std::string& s) {
  for (const auto& t : r.texts) if (t.value == s) return true;
  return false;
}
static bool same(const mj::Game& a, const mj::Game& b) {
  return a.seed == b.seed && std::memcmp(a.tile,b.tile,mj::kSlots)==0;
}
static void draw(MahjongActivity& a) { a.noteSurfaceBuilt(); a.render(RenderLock{}); }
static void tap(MahjongActivity& a, MappedInputManager& i, fui::Rect b) {
  i.tapped=true; i.x=b.x+b.width/2; i.y=b.y+b.height/2; a.loop(); i.tapped=false;
}
static fui::Rect action(const MahjongActivity& a, fui::ActionId id) {
  for (size_t n=0;n<a.interactions.count();++n) if(a.interactions.data()[n].action==id) return a.interactions.data()[n].rect;
  assert(false && "missing actual control"); return {};
}
static void start(MahjongActivity& a, GfxRenderer& r, MappedInputManager& i) {
  a.onEnter(); draw(a); const uint32_t seed=nextSeed;
  assert(hasText(r,"MAHJONG SOLITAIRE") && hasText(r,"8 X 10 / 3 LAYERS / 144 TILES"));
  assert(hasText(r,"RANDOM DEALS MAY HAVE NO SOLUTION"));
  assert(a.interactions.count()==1 && a.interactions.count()<=toybox::kMaxInteractions);
  tap(a,i,action(a,ui::ActionStart));
  mj::Game expected{}; mj::deal(expected,seed);
  assert(same(a.flow.game,expected) && a.flow.screen==ui::Screen::Board);
  assert(a.flow.selected==mj::kNoSlot); draw(a);
  assert(a.interactions.count()==2 && hasText(r,"PICK A FREE TILE"));
  char status[64]; std::snprintf(status,sizeof(status),"%d LEFT / %d PAIRS",mj::remaining(expected),mj::availableMoves(expected));
  assert(hasText(r,status));
}
static void card(MahjongActivity& a, GfxRenderer& r, MappedInputManager& i, int slot) {
  tap(a,i,ui::tileRect(r.device,slot));
}
static void back(MahjongActivity& a, MappedInputManager& i) {
  i.back=true; a.loop(); i.back=false;
}
static void blank(mj::Game& game) {
  for (auto& tile : game.tile) tile=mj::kNoTile;
}
int main(int argc,char** argv) {
  assert(argc==2); const std::string scenario=argv[1];
  GfxRenderer r; MappedInputManager i; auto p=MahjongActivity::create(r,i); assert(p);
  auto& a=static_cast<MahjongActivity&>(*p);
  if(scenario=="start") {
    a.onEnter(); assert(a.entries==1 && a.updates==1 && r.fonts==1 && seeds==0);
    i.tapped=true; a.loop(); i.tapped=false; assert(seeds==0);
    start(a,r,i); assert(seeds==1);
    puts("start: real lifecycle -> START -> seeded core layered board OK");
  } else if(scenario=="pairing") {
    start(a,r,i);
    int first=-1, mate=-1, wrong=-1, blocked=-1;
    for(int s=0;s<mj::kSlots;++s) {
      if(ui::visibleSlot(a.flow.game,s) && !mj::freeSlot(a.flow.game,s)) blocked=s;
      for(int t=s+1;t<mj::kSlots;++t) if(mj::canPair(a.flow.game,s,t)) { first=s; mate=t; }
    }
    assert(first>=0 && blocked>=0);
    for(int s=0;s<mj::kSlots;++s)
      if(mj::freeSlot(a.flow.game,s) && !mj::tilesMatch(a.flow.game.tile[first],a.flow.game.tile[s])) { wrong=s; break; }
    assert(wrong>=0);
    const auto initial=a.flow.game; const int updates=a.updates;
    card(a,r,i,blocked); assert(same(a.flow.game,initial) && a.flow.selected==mj::kNoSlot && a.updates==updates);
    card(a,r,i,first); assert(a.flow.selected==first && same(a.flow.game,initial));
    draw(a); assert(hasText(r,"PICK A MATCH / BACK CANCELS"));
    const auto selected=ui::tileRect(r.device,first).inset(fui::Insets{3,3,3,3});
    bool marked=false;
    for(const auto& stroke:r.strokes) if(stroke.box.x==selected.x && stroke.box.y==selected.y &&
       stroke.box.width==selected.width && stroke.box.height==selected.height && stroke.width==3) marked=true;
    assert(marked);
    card(a,r,i,blocked); assert(a.flow.selected==first && same(a.flow.game,initial));
    card(a,r,i,wrong); assert(a.flow.selected==first && same(a.flow.game,initial));
    card(a,r,i,first); assert(a.flow.selected==mj::kNoSlot && same(a.flow.game,initial));
    card(a,r,i,first); card(a,r,i,mate);
    assert(a.flow.selected==mj::kNoSlot && mj::remaining(a.flow.game)==142);
    for(int s=0;s<mj::kSlots;++s) assert(a.flow.game.tile[s]==((s==first || s==mate)?mj::kNoTile:initial.tile[s]));
    draw(a); assert(a.flow.screen==ui::Screen::Board);
    puts("pairing: actual free/blocked/mismatch/duplicate picks, selected outline and core pair removal OK");
  } else if(scenario=="endings") {
    start(a,r,i);
    // A last pair of different flower ranks must complete via the real core.
    blank(a.flow.game); a.flow.game.tile[0]=mj::makeTile(mj::kFlowers,0);
    a.flow.game.tile[7]=mj::makeTile(mj::kFlowers,3); draw(a);
    card(a,r,i,0); card(a,r,i,7); draw(a);
    assert(a.flow.screen==ui::Screen::Done && mj::won(a.flow.game));
    assert(hasText(r,"DONE") && hasText(r,"0 LEFT / 0 PAIRS") && hasText(r,"AGAIN"));
    const uint32_t seed=nextSeed; tap(a,i,action(a,ui::ActionNew));
    mj::Game expected{}; mj::deal(expected,seed);
    assert(same(a.flow.game,expected) && a.flow.selected==mj::kNoSlot && a.flow.screen==ui::Screen::Board);
    draw(a);
    // One legal season pair, two unlike remaining free tiles: last legal move -> stuck.
    blank(a.flow.game);
    a.flow.game.tile[0]=mj::makeTile(mj::kSeasons,0); a.flow.game.tile[7]=mj::makeTile(mj::kSeasons,3);
    a.flow.game.tile[72]=mj::makeTile(mj::kBamboo,0); a.flow.game.tile[79]=mj::makeTile(mj::kCircles,0);
    draw(a); card(a,r,i,0); card(a,r,i,7); draw(a);
    assert(a.flow.screen==ui::Screen::Stuck && mj::deadEnd(a.flow.game));
    assert(hasText(r,"NO PAIRS") && hasText(r,"2 LEFT / 0 PAIRS") && hasText(r,"NEW"));
    const auto stuck=a.flow.game; card(a,r,i,72); assert(same(a.flow.game,stuck) && a.flow.selected==mj::kNoSlot);
    assert(a.interactions.count()==2); tap(a,i,action(a,ui::ActionMenu));
    assert(a.flow.screen==ui::Screen::Menu && a.flow.selected==mj::kNoSlot && leaves==0);
    draw(a); tap(a,i,action(a,ui::ActionStart)); draw(a);
    a.flow.game.tile[0]=mj::kNoTile;
    const uint32_t newSeed=nextSeed; tap(a,i,action(a,ui::ActionNew));
    mj::deal(expected,newSeed); assert(same(a.flow.game,expected));
    draw(a); tap(a,i,action(a,ui::ActionMenu)); draw(a); back(a,i); assert(leaves==1);
    // Core can start stuck. Do not claim a random deal is guaranteed solvable.
    ui::Flow f; f.start(123u); blank(f.game); f.game.tile[0]=mj::makeTile(mj::kBamboo,0); f.classify();
    assert(mj::deadEnd(f.game) && f.screen==ui::Screen::Stuck);
    puts("endings: real last flower/season pair -> DONE/stuck, fresh AGAIN/NEW, MENU recovery OK");
  } else if(scenario=="full_deals") {
    int done=0,stuck=0;
    for(uint32_t seed=1;seed<=40;++seed) {
      nextSeed=seed; start(a,r,i); int pairs=0;
      while(a.flow.screen==ui::Screen::Board) {
        int first=-1,mate=-1;
        for(int s=0;s<mj::kSlots && first<0;++s) for(int t=s+1;t<mj::kSlots;++t)
          if(mj::canPair(a.flow.game,s,t)) { first=s; mate=t; break; }
        assert(first>=0 && ui::visibleSlot(a.flow.game,first) && ui::visibleSlot(a.flow.game,mate));
        mj::Game expected=a.flow.game; assert(mj::removePair(expected,first,mate));
        card(a,r,i,first); draw(a); card(a,r,i,mate); draw(a);
        assert(same(a.flow.game,expected) && a.flow.selected==mj::kNoSlot);
        assert(++pairs<=72 && mj::remaining(a.flow.game)==144-pairs*2);
      }
      if(mj::won(a.flow.game)) { ++done; assert(pairs==72 && hasText(r,"DONE")); }
      else { ++stuck; assert(mj::deadEnd(a.flow.game) && hasText(r,"NO PAIRS")); }
    }
    assert(done>0 && stuck>0);
    std::printf("full_deals: 40 original 144-tile seeded boards through actual Activity; %d DONE / %d NO PAIRS (greedy, not solvability claim)\n",done,stuck);
  } else if(scenario=="geometry") {
    start(a,r,i);
    for(const auto dims : {fui::Size{480,800},fui::Size{540,960},fui::Size{600,800}}) {
      r.device.width=dims.width; r.device.height=dims.height; r.device.safeArea={14,8,16,12};
      draw(a); assert(!a.interactions.overflowed() && a.interactions.count()==2);
      int visible=0, free=0;
      for(int s=0;s<mj::kSlots;++s) {
        const auto b=ui::tileRect(r.device,s);
        assert(b.width>=44 && b.height>=44);
        assert(b.x>=r.device.safeRect().x && b.right()<=r.device.safeRect().right());
        assert(b.y>=toybox::kBodyTop+48+6);
        for(size_t h=0;h<a.interactions.count();++h) {
          const auto control=a.interactions.data()[h].rect;
          assert(b.bottom()+6<=control.y && control.bottom()<=r.device.safeRect().bottom()-32);
          assert(ui::tileAt(r.device,a.flow.game,control.x,control.y)==mj::kNoSlot);
        }
        // Independent physical-layout oracle, not visibleSlot(): highest live
        // layer at exactly these core footprint coordinates owns this rectangle.
        int top=s;
        for(int t=0;t<mj::kSlots;++t) if(a.flow.game.tile[t]!=mj::kNoTile &&
            mj::kLayout[t].x==mj::kLayout[s].x && mj::kLayout[t].y==mj::kLayout[s].y &&
            mj::kLayout[t].layer>mj::kLayout[top].layer) top=t;
        assert(ui::visibleSlot(a.flow.game,s)==(s==top));
        assert(ui::tileAt(r.device,a.flow.game,b.x,b.y)==top);
        assert(ui::tileAt(r.device,a.flow.game,b.right()-1,b.bottom()-1)==top);
        assert(ui::tileAt(r.device,a.flow.game,b.right(),b.y)==mj::kNoSlot);
        assert(ui::tileAt(r.device,a.flow.game,b.x,b.bottom())==mj::kNoSlot);
        bool drawn=false;
        for(const auto& stroke:r.strokes) if(stroke.box.x==b.x && stroke.box.y==b.y &&
           stroke.box.width==b.width && stroke.box.height==b.height) {
          assert(stroke.width==(mj::freeSlot(a.flow.game,top)?2:1)); drawn=true;
        }
        assert(drawn);
        if(s==top) {
          ++visible; if(mj::freeSlot(a.flow.game,s)) ++free;
          char marker[4]; ui::tileMarker(a.flow.game.tile[s],marker); int faces=0,depths=0;
          for(const auto& text:r.texts) if(b.contains(text.box.x+text.box.width/2,text.box.y+text.box.height/2)) {
            if(text.value==marker) ++faces;
            if(text.value=="L"+std::to_string(mj::kLayout[s].layer+1)) ++depths;
          }
          assert(faces==1 && depths==1);
        }
      }
      assert(visible==80 && free==44 && mj::remaining(a.flow.game)==144);
      assert(ui::tileRect(r.device,-1).empty() && ui::tileRect(r.device,mj::kSlots).empty());
      assert(ui::tileAt(r.device,a.flow.game,-1,-1)==mj::kNoSlot);
      std::printf("geometry %dx%d: %dx%d tiles, 80 top faces / 144 slots / 44 free, controls disjoint\n",
                  dims.width,dims.height,ui::tileRect(r.device,0).width,ui::tileRect(r.device,0).height);
    }
    // Three aligned depths: only the highest face may reach the renderer.
    blank(a.flow.game); const int base=mj::slotAt(0,4,6),middle=mj::slotAt(1,4,6),top=mj::slotAt(2,4,6);
    a.flow.game.tile[base]=mj::makeTile(mj::kBamboo,8);
    a.flow.game.tile[middle]=mj::makeTile(mj::kCircles,7);
    a.flow.game.tile[top]=mj::makeTile(mj::kDragons,2); draw(a);
    assert(!hasText(r,"B9") && !hasText(r,"O8") && hasText(r,"D3"));
    assert(ui::tileAt(r.device,a.flow.game,ui::tileRect(r.device,base).x,ui::tileRect(r.device,base).y)==top);
    a.flow.game.tile[top]=mj::kNoTile; draw(a);
    assert(!hasText(r,"B9") && hasText(r,"O8") && !hasText(r,"D3"));
    a.flow.game.tile[middle]=mj::kNoTile; draw(a);
    assert(hasText(r,"B9") && !hasText(r,"O8"));
    a.flow.game.tile[base]=mj::kNoTile; draw(a);
    const auto b=ui::tileRect(r.device,base);
    assert(ui::tileAt(r.device,a.flow.game,b.x,b.y)==mj::kNoSlot);
    // A blocked top tile cannot pass a tap through to a lower tile.
    blank(a.flow.game); a.flow.game.tile[base]=mj::makeTile(mj::kBamboo,8);
    a.flow.game.tile[top]=mj::makeTile(mj::kBamboo,8);
    a.flow.game.tile[top+1]=mj::makeTile(mj::kBamboo,8); // blocks the right, add a left neighbor at a non-edge top
    const int blocked=top+1,under=mj::slotAt(0,6,6);
    a.flow.game.tile[top+2]=mj::makeTile(mj::kBamboo,8); a.flow.game.tile[under]=mj::makeTile(mj::kBamboo,8);
    draw(a); card(a,r,i,blocked); assert(a.flow.selected==mj::kNoSlot);
    assert(ui::tileAt(r.device,a.flow.game,ui::tileRect(r.device,under).x,ui::tileRect(r.device,under).y)==blocked);
    puts("depth: hidden faces never drawn; topmost present hit, newly uncovered depths and blocked top pick OK");
  } else if(scenario=="markers") {
    const char* groups="BCOWDFS"; char marker[4];
    for(int g=0;g<mj::kGroupCount;++g) for(int n=0;n<mj::kGroupSize[g];++n) {
      ui::tileMarker(mj::makeTile(g,n),marker);
      assert(marker[0]==groups[g] && marker[1]=='1'+n && marker[2]=='\0');
      blank(a.flow.game); a.flow.screen=ui::Screen::Board; a.flow.game.tile[0]=mj::makeTile(g,n); draw(a);
      assert(hasText(r,marker));
    }
    ui::tileMarker(mj::kNoTile,marker); assert(std::strcmp(marker,"?")==0);
    blank(a.flow.game); a.flow.screen=ui::Screen::Board;
    a.flow.game.tile[0]=mj::makeTile(mj::kFlowers,0); a.flow.game.tile[7]=mj::makeTile(mj::kSeasons,0);
    draw(a); card(a,r,i,0); card(a,r,i,7);
    assert(a.flow.selected==0 && mj::remaining(a.flow.game)==2);
    puts("markers: all ASCII suit/rank faces painted; F and S distinguishable and not cross-matching OK");
  } else if(scenario=="reveal") {
    a.onEnter(); draw(a); const auto menuMeaning=a.surfaceMeaning();
    tap(a,i,action(a,ui::ActionStart)); const auto liveMeaning=a.surfaceMeaning();
    assert(menuMeaning!=liveMeaning);
    int first=-1,mate=-1;
    for(int s=0;s<mj::kSlots;++s) for(int t=s+1;t<mj::kSlots;++t)
      if(mj::canPair(a.flow.game,s,t)) { first=s; mate=t; }
    assert(first>=0);
    r.autoPaint=false; draw(a); card(a,r,i,first); assert(a.flow.selected==mj::kNoSlot);
    paintclock::notePainted(); card(a,r,i,first); assert(a.flow.selected==first && a.surfaceMeaning()==liveMeaning);
    draw(a); card(a,r,i,mate); assert(mj::remaining(a.flow.game)==142 && a.surfaceMeaning()==liveMeaning);
    // A geometry-driving device size or safe-area change must not reuse meaning.
    r.device.width+=20; assert(a.surfaceMeaning()!=liveMeaning); r.device.width-=20;
    r.device.safeArea.left+=2; assert(a.surfaceMeaning()!=liveMeaning); r.device.safeArea.left-=2;
    r.device.orientation=fui::Orientation::PortraitInverted; assert(a.surfaceMeaning()!=liveMeaning);
    r.device.orientation=fui::Orientation::Portrait;
    a.flow.screen=ui::Screen::Stuck; assert(a.surfaceMeaning()!=liveMeaning); draw(a); paintclock::notePainted();
    tap(a,i,action(a,ui::ActionNew)); draw(a); card(a,r,i,0); assert(a.flow.selected==mj::kNoSlot);
    paintclock::notePainted(); card(a,r,i,0); assert(a.flow.selected==0);
    puts("reveal: actual SurfaceGate blocks unseen screen/live/geometry transitions, admits consecutive selections OK");
  } else if(scenario=="compact") {
    start(a,r,i); r.device.width=800; r.device.height=480; draw(a);
    assert(hasText(r,"USE PORTRAIT FOR READABLE TILES"));
    const auto before=a.flow.game;
    for(int s=0;s<mj::kSlots;++s) assert(ui::tileRect(r.device,s).empty());
    i.tapped=true; i.x=400; i.y=240; a.loop(); i.tapped=false;
    assert(same(a.flow.game,before) && a.flow.selected==mj::kNoSlot);
    assert(a.interactions.count()==2);
    tap(a,i,action(a,ui::ActionMenu)); draw(a);
    const auto footer=action(a,ui::ActionStart);
    for(const auto& text:r.texts) if(text.value!="START") assert(text.box.bottom()<footer.y);
    puts("compact: unusably small board is honestly disabled; readable portrait prompt and menu/NEW remain reachable OK");
  } else if(scenario=="navigation") {
    start(a,r,i); const int seedCount=seeds;
    a.routeAction(fui::ActionEvent{ui::ActionStart}); assert(seeds==seedCount);
    int free=0; while(!mj::freeSlot(a.flow.game,free)) ++free;
    card(a,r,i,free); const auto before=a.flow.game;
    back(a,i); assert(a.flow.screen==ui::Screen::Board && a.flow.selected==mj::kNoSlot && same(a.flow.game,before));
    draw(a); back(a,i); assert(a.flow.screen==ui::Screen::Menu && leaves==0);
    draw(a); a.routeAction(fui::ActionEvent{ui::ActionNew}); assert(seeds==seedCount);
    const auto button=action(a,ui::ActionStart);
    i.tapped=true; i.x=button.x+1; i.y=button.y+1; back(a,i); i.tapped=false;
    assert(leaves==1 && seeds==seedCount && a.flow.screen==ui::Screen::Menu);
    puts("navigation: Back cancels before menu, menu exits shelf, simultaneous Back wins, stale actions inert OK");
  } else { return 2; }
}
'''


def compile_ui(folder, mutations=None):
    folder = pathlib.Path(folder)
    for name in OWNED:
        if not (GAME_DIR / name).exists():
            raise AssertionError('missing playable integration file: ' + name)
    rels = ['src/apps_local/mahjong/' + name for name in (*OWNED, 'MahjongCore.h')]
    rels += ['lib/GfxRenderer/RevealedInteractions.h', 'lib/GfxRenderer/PaintClock.h']
    rels += ['src/apps_local/ui/' + name for name in ('ToyboxScreen.h','ToyboxTokens.h','ToyboxText.h','ToyboxMetrics.h')]
    for rel in rels:
        dst=folder/rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        text=(ROOT/rel).read_text()
        for old,new in (mutations or {}).get(pathlib.Path(rel).name, []):
            if text.count(old)!=1:
                raise AssertionError('mutation anchor must be unique: '+old)
            text=text.replace(old,new)
        dst.write_text(text, encoding='utf-8')
    seams = {
        'src/activities/Activity.h': ACTIVITY_BOUNDARY,
        'src/apps_local/ui/ToyboxTheme.h': RENDERER_BOUNDARY,
        'src/apps_local/ui/ToyboxFonts.h': '#pragma once\nnamespace toybox { inline void ensureFonts(GfxRenderer& r) { ++r.fonts; } }\n',
        'src/apps_local/ui/ToyboxSeed.h': (ROOT/'src/apps_local/ui/ToyboxSeed.h').read_text(),
        'src/apps_local/Shelf.h': '#pragma once\nnamespace shelf { void leave(GfxRenderer&, MappedInputManager&); }\n',
        'src/components/UITheme.h': '#pragma once\nstruct GuiBoundary { void drawButtonHints(GfxRenderer&,const char*,const char*,const char*,const char*) {} };\ninline GuiBoundary GUI;\n',
        'Memory.h': '#pragma once\n#include <memory>\n#include <new>\n#include <utility>\ntemplate<class T,class... Args> std::unique_ptr<T> makeUniqueNoThrow(Args&&... a) { return std::unique_ptr<T>(new(std::nothrow) T(std::forward<Args>(a)...)); }\n',
    }
    for rel,text in seams.items():
        dst=folder/rel
        dst.parent.mkdir(parents=True,exist_ok=True)
        dst.write_text(text,encoding='utf-8')
    harness=folder/'mahjong_ui_host.cpp'
    harness.write_text(HARNESS,encoding='utf-8')
    exe=folder/'mahjong_ui_host'
    sdk=ROOT/'freeink-sdk/libs/ui/FreeInkUI'
    cmd=['g++','-std=c++17','-Wall','-Wextra','-Werror','-Wno-comment','-I',str(folder),
         '-I',str(folder/'src/apps_local/mahjong'),'-I',str(folder/'src'),'-I',str(sdk/'include'),
         '-I',str(ROOT/'freeink-sdk/libs/assets/Icons/include'),str(harness),
         str(folder/'src/apps_local/mahjong/MahjongActivity.cpp'),
         str(folder/'src/apps_local/mahjong/MahjongScreens.cpp'),str(sdk/'src/FreeInkUI.cpp'),'-o',str(exe)]
    result=subprocess.run(cmd,capture_output=True,text=True)
    if result.returncode:
        raise AssertionError('real Mahjong UI compile failed:\n'+result.stderr)
    return exe


class MahjongUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.exe=compile_ui(cls.tmp.name)

    def scenario(self,name):
        result=subprocess.run([str(self.exe),name],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        print(result.stdout.strip())

    def test_menu_start_reaches_actual_layered_seeded_board(self):
        self.scenario('start')

    def test_picks_use_core_free_rules_and_only_matching_distinct_tiles_remove(self):
        self.scenario('pairing')

    def test_complete_stuck_and_new_menu_recovery(self):
        self.scenario('endings')

    def test_back_cancels_before_menu_and_stale_controls_are_inert(self):
        self.scenario('navigation')

    def test_real_draw_depth_occlusion_geometry_boundaries_and_topmost_hits(self):
        self.scenario('geometry')

    def test_all_ascii_markers_and_flower_season_groups(self):
        self.scenario('markers')

    def test_surface_gate_blocks_unpainted_mode_and_device_geometry_changes(self):
        self.scenario('reveal')

    def test_too_small_orientation_does_not_offer_unreadable_tile_hits(self):
        self.scenario('compact')

    def test_full_random_deals_finish_through_real_geometry_and_activity(self):
        self.scenario('full_deals')

    def test_compile_clean_mutations_are_caught_without_editing_production(self):
        mutations = (
            ('depth', 'geometry', {'MahjongScreens.cpp': [
                ('for (int other = slot + 1; other < mahjong::kSlots; ++other)',
                 'for (int other = mahjong::kSlots; other < mahjong::kSlots; ++other)')]}),
            ('top-hit', 'geometry', {'MahjongScreens.cpp': [
                ('for (int slot = mahjong::kSlots - 1; slot >= 0; --slot) {\n    if (!visibleSlot(game, slot)) continue;',
                 'for (int slot = 0; slot < mahjong::kSlots; ++slot) {\n    if (game.tile[slot] == mahjong::kNoTile) continue;')]}),
            ('mismatch', 'pairing', {'MahjongFlow.h': [
                ('if (!mahjong::removePair(game, selected, slot)) return false;',
                 'game.tile[selected] = mahjong::kNoTile; game.tile[slot] = mahjong::kNoTile;')]}),
            ('reveal', 'reveal', {'MahjongActivity.cpp': [
                ('|| !surfaceRevealed()', '|| false')]}),
        )
        for label, scenario, edits in mutations:
            with self.subTest(mutation=label), tempfile.TemporaryDirectory() as folder:
                exe=compile_ui(folder,edits)  # A compiler error is not a caught behavior.
                result=subprocess.run([str(exe),scenario],capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0,'mutation escaped: '+label)
                self.assertIn('Assertion',result.stderr)
                print('compile-clean mutation caught: '+label)

    def test_owned_units_are_lf_bounded_and_free_of_hardware_storage_timers(self):
        source='\n'.join((GAME_DIR/name).read_text() for name in OWNED)
        for token in ('HalGPIO','BTN_','delay(','millis(','sleep(','random_device','Storage.', 'Preferences', 'nvs_'):
            self.assertNotIn(token,source)
        for name in OWNED:
            self.assertNotIn(b'\r',(GAME_DIR/name).read_bytes())
        self.assertNotIn(b'\r',pathlib.Path(__file__).read_bytes())
        self.assertIn('makeUniqueNoThrow<MahjongActivity>',source)
        self.assertIn('toybox::ensureFonts(renderer)',source)
        self.assertEqual(source.count('toybox::seed()'),1)


if __name__=='__main__':
    unittest.main()
