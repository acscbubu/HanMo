"""Actual Backgammon Activity + Screens + FreeInkUI, hardware seams only."""
import pathlib
import shutil
import subprocess
import tempfile
import unittest
from scripts.tests.test_memory_activity import ACTIVITY_BOUNDARY, RENDERER_BOUNDARY

# Record primitive rectangles as well, without replacing screen geometry or paint.
ACTIVITY_BOUNDARY = ACTIVITY_BOUNDARY.replace(
    "std::vector<StrokeCall> strokes;", "std::vector<StrokeCall> strokes; std::vector<fui::Rect> fills;")
ACTIVITY_BOUNDARY = ACTIVITY_BOUNDARY.replace(
    "texts.clear(); strokes.clear();", "texts.clear(); strokes.clear(); fills.clear();")
RENDERER_BOUNDARY = RENDERER_BOUNDARY.replace(
    "void fill(Rect, Paint, uint8_t, uint8_t) override {}",
    "void fill(Rect box, Paint, uint8_t, uint8_t) override { renderer_.fills.push_back(box); }")

ROOT = pathlib.Path(__file__).resolve().parents[2]
GAME_DIR = ROOT / "src/apps_local/backgammon"
OWNED = ("BackgammonFlow.h", "BackgammonScreens.h", "BackgammonScreens.cpp",
         "BackgammonActivity.h", "BackgammonActivity.cpp")

HARNESS = r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include <memory>
#include <string>
#include <utility>
#include "BackgammonScreens.h"
#define private public
#include "BackgammonActivity.h"
#undef private
namespace bg = backgammon;
namespace ui = backgammonui;
inline int seedCalls = 0, leaveCount = 0;
inline uint32_t nextSeed = 123u;
namespace shelf { void leave(GfxRenderer&, MappedInputManager&) { ++leaveCount; } }
namespace toybox { uint32_t seed() { ++seedCalls; return nextSeed++; } }
static void draw(BackgammonActivity& a) { a.noteSurfaceBuilt(); a.render(RenderLock{}); }
static bool hasText(const GfxRenderer& r, const std::string& v) {
  for (const auto& t : r.texts) if (t.value == v) return true;
  return false;
}
static fui::Rect action(const BackgammonActivity& a, fui::ActionId id, int value = 0) {
  for (size_t i = 0; i < a.interactions.count(); ++i) {
    const auto& h = a.interactions.data()[i];
    if (h.action == id && h.value == value) return h.rect;
  }
  assert(false && "requested real control is missing"); return {};
}
static void tap(BackgammonActivity& a, MappedInputManager& in, fui::Rect box) {
  assert(!box.empty()); in.tapped = true;
  in.x = box.x + box.width / 2; in.y = box.y + box.height / 2;
  a.loop(); in.tapped = false;
}
static bool hasAction(const BackgammonActivity& a, fui::ActionId id, int value = 0) {
  for (size_t i = 0; i < a.interactions.count(); ++i)
    if (a.interactions.data()[i].action == id && a.interactions.data()[i].value == value) return true;
  return false;
}
static void conserved(const bg::Game& g) {
  for (uint8_t side = 0; side < bg::kSides; ++side)
    assert(bg::onBoard(g, side) + g.bar[side] + g.off[side] == bg::kCheckers);
}
static void fixture(BackgammonActivity& a, uint8_t side, int from, int count,
                    int enemy, int enemyCount, int bar = 0) {
  a.flow.game = bg::Game{};
  bg::setCheckers(a.flow.game, from, side, count);
  bg::setCheckers(a.flow.game, enemy, bg::other(side), enemyCount);
  a.flow.game.turn = side;
  a.flow.game.bar[side] = bar;
  a.flow.game.off[side] = bg::kCheckers - count - bar;
  a.flow.game.off[bg::other(side)] = bg::kCheckers - enemyCount;
  a.flow.rolled = false; a.flow.opening = false; a.flow.openingLight = a.flow.openingDark = 0;
  a.flow.dieSlot = -1; a.flow.from = ui::kNoPoint;
  a.flow.screen = ui::Mode::Board; conserved(a.flow.game);
}
static void roll(BackgammonActivity& a, GfxRenderer&, int x, int y) {
  assert(bg::beginTurn(a.flow.game, x, y)); a.flow.rolled = true; a.flow.opening = false; draw(a);
}
static void point(BackgammonActivity& a, GfxRenderer& r, MappedInputManager& in, int at) {
  tap(a, in, ui::pointRect(r.device, at));
}
int main(int argc, char** argv) {
  assert(argc == 2); const std::string scenario = argv[1];
  GfxRenderer r; MappedInputManager in;
  auto instance = BackgammonActivity::create(r, in); assert(instance);
  auto& a = static_cast<BackgammonActivity&>(*instance);
  a.onEnter(); draw(a);
  assert(r.fonts == 1 && seedCalls == 0 && hasText(r, "LOCAL TWO PLAYERS"));
  if (scenario == "start") {
    tap(a, in, action(a, ui::ActionStart)); draw(a);
    assert(a.flow.screen == ui::Mode::Board && bg::onBoard(a.flow.game, bg::kLight) == 15);
    assert(bg::onBoard(a.flow.game, bg::kDark) == 15 && hasText(r, "OPENING ROLL"));
    assert(!hasText(r, "LIGHT TO PLAY") && !hasText(r, "DARK TO PLAY"));
    assert(hasText(r, "ONE DIE EACH - HIGHER STARTS"));
    assert(seedCalls == 1 && !a.flow.rolled && hasText(r, "ROLL"));
    uint32_t expectedSeed = 123u; int x, y; bg::rollDice(expectedSeed, x, y);
    tap(a, in, action(a, ui::ActionRoll)); draw(a);
    assert(a.flow.rolled && a.flow.rng == expectedSeed && seedCalls == 1);
    bg::Game expected{}; bg::start(expected); assert(bg::beginOpeningTurn(expected, x, y));
    assert(a.flow.game.turn==expected.turn && !a.flow.opening);
    assert(hasText(r, "OPEN L4 D3"));
    for (int i = 0; i < bg::kMaxPendingDice; ++i) assert(a.flow.game.die[i] == expected.die[i]);
    const auto before = a.flow.rng;
    a.routeAction(fui::ActionEvent{ui::ActionRoll});
    assert(a.flow.rng == before && "no reroll while a turn is active");
    assert(a.interactions.count() <= toybox::kMaxInteractions);
    puts("start: real Activity menu->board->explicit seeded core roll, no reroll OK");
  } else if (scenario == "opening_ui") {
    const uint32_t seeds[]={1u,12u,6u};
    for (int attempt=0; attempt<3; ++attempt) {
      nextSeed=seeds[attempt];
      const int calls=seedCalls; tap(a,in,action(a,ui::ActionStart)); draw(a);
      assert(seedCalls==calls+1 && a.flow.opening && hasText(r,"OPENING ROLL"));
      tap(a,in,action(a,ui::ActionRoll)); draw(a);
      if (attempt==2) {
        assert(!a.flow.rolled && a.flow.opening && hasText(r,"OPEN L1 D1"));
        assert(hasText(r,"OPENING TIE - ROLL AGAIN") && bg::pendingCount(a.flow.game)==0);
        assert(!hasAction(a,ui::ActionDie) && !hasAction(a,ui::ActionEnd));
        tap(a,in,action(a,ui::ActionRoll)); draw(a);
        assert(a.flow.rng==750905587u && hasText(r,"OPEN L4 D2"));
      }
      const uint8_t side=attempt==1?bg::kDark:bg::kLight;
      assert(a.flow.rolled && !a.flow.opening && a.flow.game.turn==side);
      assert(bg::pendingCount(a.flow.game)==2 && seedCalls==calls+1);
      assert(hasText(r,side==bg::kLight?"LIGHT TO PLAY":"DARK TO PLAY"));
      conserved(a.flow.game); tap(a,in,action(a,ui::ActionMenu)); draw(a);
    }
    puts("opening_ui: actual Activity seeded opening, both seats, visible tie and original dice OK");
  } else if (scenario == "turn_hints") {
    for (uint8_t side=0; side<bg::kSides; ++side) {
      const int runner=side==bg::kLight?0:23, wall=side==bg::kLight?2:21;
      fixture(a,side,runner,1,wall,2,1); roll(a,r,1,2);
      assert(bg::canMoveFrom(a.flow.game,bg::kBar,1));
      assert(!hasAction(a,ui::ActionDie,0) && "turn-legal UI: die stranding another die must not be selectable");
      a.routeAction(fui::ActionEvent{ui::ActionDie,0});
      assert(a.flow.dieSlot==-1 && !a.flow.legalSource(bg::kBar));
      tap(a,in,action(a,ui::ActionDie,1)); draw(a);
      tap(a,in,action(a,ui::ActionBar)); draw(a);
      point(a,r,in,bg::entryPoint(side,2)); draw(a); conserved(a.flow.game);
      tap(a,in,action(a,ui::ActionDie,0)); draw(a);
      point(a,r,in,runner); draw(a); point(a,r,in,bg::destination(side,runner,1)); draw(a);
      assert(bg::pendingCount(a.flow.game)==0); conserved(a.flow.game);
    }
    for (uint8_t side=0; side<bg::kSides; ++side) {
      auto at=[side](int p){return side==bg::kLight?p:23-p;};
      fixture(a,side,at(15),1,at(12),2);
      for (int p : {18,21,22}) bg::setCheckers(a.flow.game,at(p),side,1);
      bg::setCheckers(a.flow.game,at(19),bg::other(side),2);
      a.flow.game.off[side]=11; a.flow.game.off[bg::other(side)]=11; roll(a,r,4,3);
      tap(a,in,action(a,ui::ActionDie,1)); draw(a);
      const auto wrong=ui::pointRect(r.device,at(18));
      assert(bg::canMoveFrom(a.flow.game,at(18),3));
      for (const auto& f : r.fills)
        assert(!(f.x==wrong.x+2 && f.y==wrong.y+2 && f.width==6 && f.height==1) && "turn-illegal source must not receive a visible legal hint");
      const auto before=a.flow.game; point(a,r,in,at(18)); draw(a);
      assert(a.flow.from==ui::kNoPoint && std::memcmp(&before,&a.flow.game,sizeof(before))==0);
      point(a,r,in,at(15)); draw(a); assert(a.flow.from==at(15));
      point(a,r,in,at(18)); draw(a); conserved(a.flow.game);
      tap(a,in,action(a,ui::ActionDie,0)); draw(a);
      point(a,r,in,at(18)); draw(a); point(a,r,in,at(22)); draw(a); conserved(a.flow.game);
      assert(bg::pendingCount(a.flow.game)==0);
      // Only one entry usable: the smaller die is still shown, but disabled.
      fixture(a,side,at(10),0,at(2),2,1); roll(a,r,1,2);
      assert(!hasAction(a,ui::ActionDie,0) && hasText(r,"D1: 1"));
      assert(hasAction(a,ui::ActionDie,1));
      tap(a,in,action(a,ui::ActionDie,1)); draw(a);
      tap(a,in,action(a,ui::ActionBar)); draw(a); point(a,r,in,bg::entryPoint(side,2)); draw(a);
      assert(a.flow.canEnd()); conserved(a.flow.game);
    }
    puts("turn_hints: mirrored max-use/larger-die selection, wrong-source hint rejection, actual mapped play OK");
  } else if (scenario == "moves") {
    tap(a, in, action(a, ui::ActionStart)); draw(a);
    assert(bg::beginTurn(a.flow.game, 3, 5)); a.flow.rolled = true; a.flow.opening = false; draw(a);
    assert(hasText(r, "CHOOSE DIE, THEN FROM"));
    for (int i = 0; i < bg::kPoints; ++i) {
      const auto box = ui::pointRect(r.device, i);
      assert(!box.empty() && ui::pointAt(r.device, box.x, box.y) == i);
      assert(ui::pointAt(r.device, box.right()-1, box.bottom()-1) == i);
      assert(box.x >= r.device.safeRect().x && box.right() <= r.device.safeRect().right());
      assert(box.y >= toybox::kBodyTop && box.bottom() <= r.device.safeRect().bottom());
      bool drawn = false;
      for (const auto& s : r.strokes) if (s.box.x == box.x && s.box.y == box.y &&
          s.box.width == box.width && s.box.height == box.height) drawn = true;
      assert(drawn && "all 24 points must actually draw");
      for (size_t h = 0; h < a.interactions.count(); ++h) {
        const auto ctrl = a.interactions.data()[h].rect;
        assert(ctrl.right() <= box.x || box.right() <= ctrl.x || ctrl.bottom() <= box.y || box.bottom() <= ctrl.y);
      }
    }
    const auto before = a.flow.game;
    a.routeAction(fui::ActionEvent{ui::ActionEnd});
    assert(std::memcmp(&before, &a.flow.game, sizeof(before)) == 0);
    tap(a, in, action(a, ui::ActionDie, 0)); draw(a);
    const auto legal = ui::pointRect(r.device, 0);
    bool legalHint = false;
    for (const auto& f : r.fills)
      if (f.x == legal.x+2 && f.y == legal.y+2 && f.width == 6 && f.height == 1) legalHint = true;
    assert(legalHint && "legal FROM points must be visibly hinted, not just accepted by hit testing");
    tap(a, in, ui::pointRect(r.device, 0)); draw(a);
    assert(a.flow.from == 0 && hasText(r, "FROM 1 -> TO 4"));
    for (int mark : {0,3}) {
      const auto marked = ui::pointRect(r.device, mark).inset(fui::Insets{3,3,3,3});
      bool visible = false;
      for (const auto& s : r.strokes) if (s.box.x == marked.x && s.box.y == marked.y &&
          s.box.width == marked.width && s.box.height == marked.height && s.width == 2) visible = true;
      assert(visible && "FROM and legal destination both need visible marks");
    }
    tap(a, in, ui::pointRect(r.device, 3)); draw(a);
    assert(a.flow.game.point[0] == 1 && a.flow.game.point[3] == 1);
    assert(bg::pendingCount(a.flow.game) == 1 && a.flow.from == ui::kNoPoint);
    tap(a, in, action(a, ui::ActionDie, 1)); draw(a);
    tap(a, in, ui::pointRect(r.device, 11)); draw(a);
    tap(a, in, ui::pointRect(r.device, 16)); draw(a);
    assert(a.flow.game.point[16] == 4 && bg::pendingCount(a.flow.game) == 0);
    assert(hasText(r, "END TURN"));
    tap(a, in, action(a, ui::ActionEnd)); draw(a);
    assert(a.flow.game.turn == bg::kDark && !a.flow.rolled && hasText(r, "DARK TO PLAY"));
    assert(a.interactions.count() <= toybox::kMaxInteractions);
    puts("moves: 24 real geometric points, two dice, FROM->destination, legal END and hot-seat OK");
  } else if (scenario == "bar") {
    for (uint8_t side = 0; side < bg::kSides; ++side) {
      const int source = side == bg::kLight ? 10 : 13;
      const int entry = bg::entryPoint(side, 3);
      fixture(a, side, source, 14, entry, 1, 1);
      // Move the enemy's other fourteen from OFF onto a safe point.
      const int enemyHome = side == bg::kLight ? 5 : 18;
      bg::setCheckers(a.flow.game, enemyHome, bg::other(side), 14);
      a.flow.game.off[bg::other(side)] = 0; conserved(a.flow.game);
      roll(a, r, 3, 4);
      tap(a, in, action(a, ui::ActionDie, 0)); draw(a);
      const auto before = a.flow.game;
      point(a, r, in, source); draw(a);
      assert(a.flow.from == ui::kNoPoint && std::memcmp(&before, &a.flow.game, sizeof(before)) == 0);
      assert(hasText(r, "BAR FIRST - CHOOSE BAR"));
      tap(a, in, action(a, ui::ActionBar)); draw(a);
      assert(a.flow.from == bg::kBar && hasText(r, "FROM BAR -> TO " + std::to_string(entry + 1)));
      point(a, r, in, entry); draw(a);
      assert(a.flow.game.bar[side] == 0 && a.flow.game.bar[bg::other(side)] == 1);
      assert(bg::checkersAt(a.flow.game, entry, side) == 1 && bg::pendingCount(a.flow.game) == 1);
      conserved(a.flow.game);
      assert(!hasAction(a, ui::ActionBar));
      a.routeAction(fui::ActionEvent{ui::ActionEnd});
      assert(a.flow.game.turn == side && a.flow.rolled);
    }
    fixture(a, bg::kLight, 18, 14, 0, 2, 1);
    bg::setCheckers(a.flow.game, 1, bg::kDark, 2); a.flow.game.off[bg::kDark] = 11;
    roll(a, r, 1, 2);
    assert(hasAction(a, ui::ActionEnd) && hasText(r, "NO LEGAL MOVES - END TURN"));
    assert(hasText(r, "D1: 1") && hasText(r, "D2: 2"));
    tap(a, in, action(a, ui::ActionEnd)); draw(a);
    assert(a.flow.game.turn == bg::kDark && a.flow.game.bar[bg::kLight] == 1 && bg::pendingCount(a.flow.game) == 0);
    conserved(a.flow.game);
    puts("bar: both directions, mandatory BAR re-entry, hit conservation, blocked dice visible until END OK");
  } else if (scenario == "off") {
    for (uint8_t side = 0; side < bg::kSides; ++side) {
      const int last = side == bg::kLight ? 23 : 0;
      const int rear = side == bg::kLight ? 18 : 5;
      const int enemy = side == bg::kLight ? 0 : 23;
      fixture(a, side, last, 14, enemy, 15);
      bg::setCheckers(a.flow.game, rear, side, 1); a.flow.game.off[side] = 0;
      roll(a, r, 6, 1);
      a.routeAction(fui::ActionEvent{ui::ActionOff});
      assert(a.flow.game.off[side] == 0 && a.flow.from == ui::kNoPoint);
      tap(a, in, action(a, ui::ActionDie, 0)); draw(a);
      point(a, r, in, last); draw(a);
      assert(a.flow.from == ui::kNoPoint && !hasAction(a, ui::ActionOff));
      point(a, r, in, rear); draw(a);
      assert(a.flow.from == rear && hasText(r, "FROM " + std::to_string(rear + 1) + " -> OFF"));
      tap(a, in, action(a, ui::ActionOff)); draw(a);
      assert(a.flow.game.off[side] == 1 && a.flow.game.point[rear] == 0); conserved(a.flow.game);
      fixture(a, side, last, 1, enemy, 15);
      roll(a, r, 1, 2);
      tap(a, in, action(a, ui::ActionDie, 0)); draw(a);
      point(a, r, in, last); draw(a);
      tap(a, in, action(a, ui::ActionOff)); draw(a);
      assert(a.flow.screen == ui::Mode::Done && bg::over(a.flow.game));
      assert(a.flow.game.off[side] == 15 && bg::pendingCount(a.flow.game) == 1);
      assert(hasText(r, side == bg::kLight ? "LIGHT WINS" : "DARK WINS"));
      assert(!hasAction(a, ui::ActionRoll) && !hasAction(a, ui::ActionEnd) && !hasAction(a, ui::ActionDie));
      conserved(a.flow.game);
      const auto before = a.flow.game;
      point(a, r, in, last);
      assert(std::memcmp(&before, &a.flow.game, sizeof(before)) == 0);
      const int seeds = seedCalls;
      tap(a, in, action(a, ui::ActionAgain)); draw(a);
      assert(seedCalls == seeds + 1 && a.flow.screen == ui::Mode::Board && !a.flow.rolled);
      assert(a.flow.opening && bg::pendingCount(a.flow.game) == 0 && hasText(r, "OPENING ROLL")); conserved(a.flow.game);
      const int leaves = leaveCount;
      tap(a, in, action(a, ui::ActionMenu)); draw(a);
      assert(a.flow.screen == ui::Mode::Menu && leaveCount == leaves);
      in.back = true; a.loop(); in.back = false;
      assert(leaveCount == leaves + 1);
    }
    puts("off: legal OFF, overshoot refusal, both winners, stopped dice, AGAIN/MENU and Back OK");
  } else if (scenario == "doubles") {
    fixture(a, bg::kLight, 0, 15, 23, 15);
    roll(a, r, 3, 3);
    assert(hasText(r, "4 USES LEFT"));
    for (int slot = 0; slot < 4; ++slot) assert(hasText(r, "D" + std::to_string(slot+1) + ": 3"));
    // Selecting slot 4 still spends the core's first matching slot, not a UI copy of dice.
    tap(a, in, action(a, ui::ActionDie, 3)); draw(a);
    for (int move = 0; move < 4; ++move) {
      point(a, r, in, move * 3); draw(a);
      assert(a.flow.from == move * 3);
      point(a, r, in, (move + 1) * 3); draw(a);
      assert(bg::pendingCount(a.flow.game) == 3 - move && a.flow.game.turn == bg::kLight);
      assert(hasText(r, std::to_string(3 - move) + " USES LEFT"));
      conserved(a.flow.game);
      if (move != 3) { a.routeAction(fui::ActionEvent{ui::ActionEnd}); assert(a.flow.rolled); }
    }
    assert(a.flow.game.point[0] == 14 && a.flow.game.point[12] == 1 && hasAction(a, ui::ActionEnd));
    tap(a, in, action(a, ui::ActionEnd)); draw(a);
    assert(a.flow.game.turn == bg::kDark && !a.flow.rolled);
    puts("doubles: four visible remaining uses, repeated selected value, core spends each use once OK");
  } else if (scenario == "reveal") {
    tap(a, in, action(a, ui::ActionStart)); draw(a);
    roll(a, r, 3, 5);
    const uint32_t noDie = a.surfaceMeaning();
    r.autoPaint = false;
    tap(a, in, action(a, ui::ActionDie, 0));
    const uint32_t chosen = a.surfaceMeaning();
    assert(chosen != noDie && "selected live die changes coordinate meaning");
    draw(a); point(a, r, in, 0);
    assert(a.flow.from == ui::kNoPoint && "source cannot use an unseen dice mode");
    paintclock::notePainted(); point(a, r, in, 0);
    assert(a.flow.from == 0 && a.surfaceMeaning() != chosen);
    draw(a); const auto before = a.flow.game;
    point(a, r, in, 3);
    assert(std::memcmp(&before, &a.flow.game, sizeof(before)) == 0 && "unseen FROM must not move a checker");
    paintclock::notePainted(); point(a, r, in, 3);
    assert(bg::pendingCount(a.flow.game) == 1 && a.flow.game.point[3] == 1);
    draw(a); const uint32_t remaining = a.surfaceMeaning();
    a.flow.game.die[1] = 6;
    assert(a.surfaceMeaning() != remaining && "live die values, not just pending count, belong in meaning");
    a.flow.game.die[1] = 5;
    const uint32_t layout = a.surfaceMeaning();
    r.device.safeArea.left += 8;
    assert(a.surfaceMeaning() != layout && "live safe-area geometry belongs in meaning");
    r.device.safeArea.left -= 8;
    const uint32_t content = a.surfaceMeaning();
    a.flow.rng += 7;
    assert(a.surfaceMeaning() == content && "RNG/content is not coordinate meaning");
    // A pending -> end phase changes meaning even when the last die is blocked.
    a.flow.game.die[1] = 0;
    assert(a.surfaceMeaning() != content);
    puts("reveal: actual SurfaceGate rejects unseen die/source/phase/layout changes, not RNG content OK");
  } else if (scenario == "geometry") {
    const int sizes[][2] = {{480,800}, {800,480}, {600,800}, {480,640}};
    for (const auto& size : sizes) {
      r.device.width = size[0]; r.device.height = size[1];
      r.device.safeArea = {15,8,14,8};
      fixture(a, bg::kLight, 18, 13, 5, 12, 1);
      a.flow.game.bar[bg::kDark] = 2; a.flow.game.off[bg::kDark] = 1;
      roll(a, r, 1, 2);
      tap(a, in, action(a, ui::ActionDie, 0)); draw(a);
      assert(hasText(r, "L13") && hasText(r, "D12"));
      assert(hasText(r, "BAR L1 D2") && hasText(r, "OFF L1 D1"));
      assert(!a.interactions.overflowed() && a.interactions.count() <= 8);
      const auto safe = r.device.safeRect();
      for (size_t h = 0; h < a.interactions.count(); ++h) {
        const auto ctrl = a.interactions.data()[h].rect;
        assert(ctrl.width >= 44 && ctrl.height >= 44);
        assert(ctrl.x >= safe.x && ctrl.y >= safe.y && ctrl.right() <= safe.right() && ctrl.bottom() <= safe.bottom());
        for (size_t k = h + 1; k < a.interactions.count(); ++k) {
          const auto b = a.interactions.data()[k].rect;
          assert(ctrl.right()+6 <= b.x || b.right()+6 <= ctrl.x || ctrl.bottom()+6 <= b.y || b.bottom()+6 <= ctrl.y);
        }
      }
      for (int i = 0; i < bg::kPoints; ++i) {
        const auto p = ui::pointRect(r.device, i);
        assert(!p.empty() && p.width > 0 && p.height >= 44);
        assert(ui::pointAt(r.device, p.x + p.width/2, p.y + p.height/2) == i);
        assert(p.x >= safe.x && p.right() <= safe.right() && p.y >= toybox::kBodyTop && p.bottom() <= safe.bottom());
        for (int j = i + 1; j < bg::kPoints; ++j) {
          const auto q = ui::pointRect(r.device, j);
          assert(p.right()+6 <= q.x || q.right()+6 <= p.x || p.bottom()+6 <= q.y || q.bottom()+6 <= p.y);
        }
        for (size_t h = 0; h < a.interactions.count(); ++h) {
          const auto q = a.interactions.data()[h].rect;
          assert(p.right()+6 <= q.x || q.right()+6 <= p.x || p.bottom()+6 <= q.y || q.bottom()+6 <= p.y);
        }
        for (const auto& f : r.fills) {
          if (!p.contains(f.x + f.width/2, f.y + f.height/2)) continue;
          assert(f.x >= p.x && f.y >= p.y && f.right() <= p.right() && f.bottom() <= p.bottom());
        }
        int countTexts = 0;
        for (const auto& t : r.texts) if (p.contains(t.box.x + t.box.width/2, t.box.y + t.box.height/2)) {
          if (t.value.size() >= 2 && (t.value[0] == 'L' || t.value[0] == 'D' || t.value[0] == '-')) {
            ++countTexts;
            const int total = a.flow.game.point[i] < 0 ? -a.flow.game.point[i] : a.flow.game.point[i];
            assert(std::stoi(t.value.substr(1)) == total && static_cast<int>(t.value.size()) * 7 <= p.width);
          }
        }
        assert(countTexts == 1 && "every point must show its exact count, including 13-checker stacks");
      }
      conserved(a.flow.game);
      assert(ui::pointRect(r.device, -1).empty() && ui::pointRect(r.device,24).empty());
      assert(ui::pointAt(r.device,-1,-1) == ui::kNoPoint);
    }
    puts("geometry: 24 points across four safe layouts, exact 13-stack/BAR/OFF counts, bounded paint and disjoint controls OK");
  } else if (scenario == "whole_game") {
    tap(a, in, action(a, ui::ActionStart)); draw(a);
    int turns = 0, moves = 0;
    while (!bg::over(a.flow.game) && turns < 2000) {
      assert(!a.flow.rolled); tap(a, in, action(a, ui::ActionRoll)); draw(a);
      while (bg::hasAnyLegalMove(a.flow.game)) {
        int8_t sources[bg::kMaxLegalMoves]; int slot = -1, count = 0;
        for (int i = 0; i < bg::kMaxPendingDice; ++i) {
          if (!a.flow.game.die[i]) continue;
          count = bg::turnLegalMoves(a.flow.game, a.flow.game.die[i], sources);
          if (count) { slot = i; break; }
        }
        assert(slot >= 0 && count > 0);
        tap(a, in, action(a, ui::ActionDie, slot)); draw(a);
        const int from = sources[0];
        if (from == bg::kBar) tap(a, in, action(a, ui::ActionBar));
        else point(a, r, in, from);
        draw(a); assert(a.flow.from == from);
        const int to = a.flow.target();
        if (to == ui::kOff) tap(a, in, action(a, ui::ActionOff));
        else point(a, r, in, to);
        draw(a); ++moves; conserved(a.flow.game);
      }
      ++turns;
      if (!bg::over(a.flow.game)) { tap(a, in, action(a, ui::ActionEnd)); draw(a); }
    }
    assert(bg::over(a.flow.game) && a.flow.screen == ui::Mode::Done && moves > 0);
    assert(hasAction(a, ui::ActionAgain) && hasAction(a, ui::ActionMenu));
    std::printf("whole_game: actual hot-seat UI from opening to win, %d turns / %d moves, all 30 checkers conserved OK\n", turns, moves);
  } else { return 2; }
}
'''


def compile_activity(folder, mutations=None):
    folder = pathlib.Path(folder)
    for f in OWNED:
        if not (GAME_DIR / f).exists():
            raise AssertionError("missing playable integration file: " + f)
    rels = ["src/apps_local/backgammon/" + f for f in (*OWNED, "BackgammonCore.h")]
    rels += ["lib/GfxRenderer/RevealedInteractions.h", "lib/GfxRenderer/PaintClock.h"]
    rels += [str(p.relative_to(ROOT)) for p in (ROOT / "src/apps_local/ui").glob("*.h")
             if p.name in {"ToyboxScreen.h", "ToyboxTokens.h", "ToyboxText.h", "ToyboxMetrics.h"}]
    for rel in rels:
        dest = folder / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, dest)
    for filename, old, new in mutations or ():
        dest = folder / "src/apps_local/backgammon" / filename
        text = dest.read_text()
        if text.count(old) != 1:
            raise AssertionError("mutation must have exactly one target: " + old)
        dest.write_text(text.replace(old, new))
    seams = {
        "src/activities/Activity.h": ACTIVITY_BOUNDARY,
        "src/apps_local/ui/ToyboxTheme.h": RENDERER_BOUNDARY,
        "src/apps_local/ui/Toybox.h": '#pragma once\n',
        "src/apps_local/ui/ToyboxFonts.h": '#pragma once\nnamespace toybox { inline void ensureFonts(GfxRenderer& r) { ++r.fonts; } }\n',
        "src/apps_local/ui/ToyboxSeed.h": (ROOT / "src/apps_local/ui/ToyboxSeed.h").read_text(),
        "src/apps_local/Shelf.h": '#pragma once\nnamespace shelf { void leave(GfxRenderer&, MappedInputManager&); }\n',
        "src/components/UITheme.h": '#pragma once\nstruct GuiBoundary { void drawButtonHints(GfxRenderer&, const char*, const char*, const char*, const char*) {} };\ninline GuiBoundary GUI;\n',
        "Memory.h": '#pragma once\n#include <memory>\n#include <new>\n#include <utility>\ntemplate<class T, class... Args> std::unique_ptr<T> makeUniqueNoThrow(Args&&... args) { return std::unique_ptr<T>(new (std::nothrow) T(std::forward<Args>(args)...)); }\n',
    }
    for rel, text in seams.items():
        dest = folder / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text)
    harness = folder / "backgammon_host.cpp"
    harness.write_text(HARNESS)
    exe = folder / "backgammon_host"
    sdk = ROOT / "freeink-sdk/libs/ui/FreeInkUI"
    cmd = ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-Wno-comment",
           "-I", str(folder), "-I", str(folder / "src/apps_local/backgammon"),
           "-I", str(folder / "src"), "-I", str(sdk / "include"),
           "-I", str(ROOT / "freeink-sdk/libs/assets/Icons/include"),
           str(harness), str(folder / "src/apps_local/backgammon/BackgammonActivity.cpp"),
           str(folder / "src/apps_local/backgammon/BackgammonScreens.cpp"),
           str(sdk / "src/FreeInkUI.cpp"), "-o", str(exe)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode:
        raise AssertionError("actual Activity/Screens host compile failed:\n" + result.stderr)
    return exe


class BackgammonUITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.exe = compile_activity(cls.tmp.name)

    def run_scenario(self, name):
        result = subprocess.run([str(self.exe), name], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())

    def test_start_and_seeded_roll(self):
        self.run_scenario("start")

    def test_opening_contest_tie_and_both_seats_are_visible_in_actual_activity(self):
        self.run_scenario("opening_ui")

    def test_turn_illegal_dice_are_not_selectable_in_actual_ui(self):
        self.run_scenario("turn_hints")

    def test_points_dice_source_destination_and_hot_seat_turn(self):
        self.run_scenario("moves")

    def test_bar_priority_reentry_hits_and_blocked_turn(self):
        self.run_scenario("bar")

    def test_bearing_off_winning_again_and_menu(self):
        self.run_scenario("off")

    def test_doubles_remaining_uses_are_visible_and_spent_by_core(self):
        self.run_scenario("doubles")

    def test_surface_gate_tracks_live_dice_source_phase_and_layout(self):
        self.run_scenario("reveal")

    def test_all_points_thirteen_stack_counts_safe_geometry_and_control_bounds(self):
        self.run_scenario("geometry")

    def test_actual_ui_plays_opening_to_win_with_all_thirty_checkers(self):
        self.run_scenario("whole_game")

    def test_sensitive_mutations_are_detected_by_real_runtime(self):
        mutations = [
            ("BackgammonFlow.h", "if (!canRoll()) return false;", "if (false) return false;", "start"),
            ("BackgammonFlow.h", "live() && !backgammon::hasAnyLegalMove(game)", "live()", "moves"),
            ("BackgammonFlow.h", "backgammon::canPlayFrom(game, at, pips())", "backgammon::canMoveFrom(game, at, pips())", "turn_hints"),
            ("BackgammonFlow.h", "backgammon::turnLegalMoves(game, game.die[slot], nullptr) != 0", "backgammon::turnLegalMoves(game, game.die[slot], nullptr) >= 0", "turn_hints"),
            ("BackgammonCore.h", "game.turn = lightDie > darkDie ? kLight : kDark;", "game.turn = kLight;", "opening_ui"),
            ("BackgammonActivity.cpp", "changed = flow.pick(backgammon::kBar)", "changed = false", "bar"),
            ("BackgammonActivity.cpp", "changed = flow.pick(ui::kOff)", "changed = false", "off"),
            ("BackgammonActivity.cpp", "surfaceRevealed() && flow.pick(at)", "flow.pick(at)", "reveal"),
            ("BackgammonActivity.cpp", "for (const auto die : flow.game.die) mix(die);", "mix(0u);", "reveal"),
            ("BackgammonScreens.cpp", "count == 0 ? '-' : (light ? 'L' : 'D'), count", "count == 0 ? '-' : (light ? 'L' : 'D'), std::min(count, 5)", "geometry"),
            ("BackgammonScreens.cpp", "if (flow.legalSource(at)) toybox::bracket(", "if (false) toybox::bracket(", "moves"),
        ]
        for filename, old, new, scenario in mutations:
            with self.subTest(mutation=old), tempfile.TemporaryDirectory() as folder:
                exe = compile_activity(folder, [(filename, old, new)])
                result = subprocess.run([str(exe), scenario], capture_output=True, text=True)
                self.assertEqual(result.returncode, -6, "must fail a real runtime assertion: " + old + result.stderr)
                self.assertIn("Assertion", result.stderr)
                print("UI mutation: " + next(line for line in result.stderr.splitlines() if "Assertion" in line))
        print("mutations: all 11 sensitive UI/flow/paint/count/hint/opening regressions detected")

    def test_scope_lf_and_hardware_independent_ui(self):
        source = "\n".join((GAME_DIR / f).read_text() for f in OWNED)
        for token in ("HalGPIO", "BTN_", "millis(", "delay(", "sleep(", "drawCircle", "random_device", "<chrono>"):
            self.assertNotIn(token, source)
        for f in OWNED:
            self.assertNotIn(b"\r", (GAME_DIR / f).read_bytes())
        self.assertNotIn(b"\r", pathlib.Path(__file__).read_bytes())


if __name__ == "__main__":
    unittest.main()
