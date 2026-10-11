"""Turn obligations, opening contest, and bounded-search regression tests."""
import hashlib
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest
from scripts.tests.test_backgammon_core import HARNESS as BOARD_HARNESS, GAME_DIR

HARNESS = BOARD_HARNESS.split('int main(')[0] + r'''
#include "BackgammonFlow.h"
#include <chrono>
static Game mirrored(const Game& g) {
  Game m{};
  for (int at=0; at<kPoints; ++at) m.point[23-at] = -g.point[at];
  for (uint8_t s=0; s<kSides; ++s) { m.bar[other(s)]=g.bar[s]; m.off[other(s)]=g.off[s]; }
  for (int i=0; i<kMaxPendingDice; ++i) m.die[i]=g.die[i];
  m.turn=other(g.turn); m.outcome=Outcome::Running; return m;
}
static void conserved(const Game& g) {
  for (uint8_t s=0; s<kSides; ++s) assert(onBoard(g,s)+g.bar[s]+g.off[s]==kCheckers);
}
int main(int argc, char** argv) {
  assert(argc==2); const std::string scenario=argv[1];
  if (scenario=="max_use") {
    Game base;
    // Bar + runner on 0, closed point 2: entry with 1 strands the 2,
    // but entry with 2 permits 0->1 with the 1. Reverse the roll slots too.
    layout(base, "L1 . D2 . . . . . . . . .", ". . . . . . . . . . . .", kLight, 1);
    for (int mirror=0; mirror<2; ++mirror) for (int swap=0; swap<2; ++swap) {
      Game g=mirror ? mirrored(base) : base; const uint8_t side=g.turn;
      assert(beginTurn(g,swap?2:1,swap?1:2));
      assert(canMoveFrom(g,kBar,1)); // Board-only legality must remain distinct.
      const Game before=g;
      assert(!play(g,kBar,1) && "max-use: reject entry that strands the second die");
      assert(std::memcmp(&before,&g,sizeof(Game))==0); conserved(g);
      assert(play(g,kBar,2)); conserved(g);
      assert(play(g,side==kLight?0:23,1)); conserved(g);
      assert(pendingCount(g)==0 && endTurn(g));
    }
    puts("max_use: mirrored whole-turn maximum, reversed dice, byte-identical rejection OK");
  } else if (scenario=="larger_die") {
    Game base;
    // Both entries are open but the shared next point is closed. Only one
    // die can be used, so 2 is compulsory despite the board-legal 1.
    layout(base, ". . D2 . . . . . . . . .", ". . . . . . . . . . . .", kLight, 1);
    for (int mirror=0; mirror<2; ++mirror) for (int swap=0; swap<2; ++swap) {
      Game g=mirror ? mirrored(base) : base;
      assert(beginTurn(g,swap?2:1,swap?1:2));
      assert(canMoveFrom(g,kBar,1) && canMoveFrom(g,kBar,2));
      assert(maxUsableDice(g)==1); const Game before=g;
      assert(!play(g,kBar,1) && "larger-die: the lower die must be rejected when only one is usable");
      assert(std::memcmp(&before,&g,sizeof(Game))==0); conserved(g);
      assert(play(g,kBar,2)); conserved(g);
      assert(!hasAnyLegalMove(g) && endTurn(g));
    }
    puts("larger_die: mirrored compulsory higher die and reversed slots OK");
  } else if (scenario=="opening_tie") {
    backgammonui::Flow f; f.start(6u); const Game initial=f.game;
    assert(f.roll());
    assert(!f.rolled && pendingCount(f.game)==0 && "opening tie must reroll, never grant a double turn");
    assert(std::memcmp(&initial,&f.game,sizeof(Game))==0 && f.rng==1095634764u);
    assert(f.canRoll() && f.roll());
    assert(f.rolled && f.game.turn==kLight && pendingCount(f.game)==2);
    assert(f.game.die[0]==4 && f.game.die[1]==2 && f.rng==750905587u);
    conserved(f.game); puts("opening_tie: actual Flow seeded one die each, tie rejection, next roll uses both OK");
  } else if (scenario=="opening_seats") {
    const uint32_t seeds[]={1u,12u};
    for (int seat=0; seat<2; ++seat) {
      backgammonui::Flow f; f.start(seeds[seat]); assert(f.roll());
      assert(f.rolled && f.game.turn==seat && "opening higher seat starts, not fixed Light");
      assert(pendingCount(f.game)==2);
      assert(f.game.die[0]==(seat==0?2:1) && f.game.die[1]==(seat==0?1:6));
      const uint32_t rng=f.rng; const Game before=f.game; assert(!f.roll());
      assert(f.rng==rng && std::memcmp(&before,&f.game,sizeof(Game))==0);
      conserved(f.game);
    }
    puts("opening_seats: actual Flow both higher seats use exactly the two opening dice OK");
  } else if (scenario=="source_order") {
    Game base;
    // 15->18 with 3 makes all home and leaves a playable 4. In contrast,
    // 18->21 strands the 4: runner 15->19 is closed and nobody may bear off.
    layout(base, ". . . . . . . . . . . .", "D2 . . L1 . . L1 D2 . L1 L1 .", kLight);
    for (int mirror=0; mirror<2; ++mirror) for (int swap=0; swap<2; ++swap) {
      Game g=mirror?mirrored(base):base; auto at=[mirror](int p){return mirror?23-p:p;};
      assert(beginTurn(g,swap?3:4,swap?4:3));
      assert(canMoveFrom(g,at(18),3) && !canPlayFrom(g,at(18),3));
      assert(canPlayFrom(g,at(15),3)); const Game before=g;
      int8_t sources[kMaxLegalMoves]; assert(turnLegalMoves(g,3,sources)==1 && sources[0]==at(15));
      assert(!play(g,at(18),3) && std::memcmp(&before,&g,sizeof(Game))==0);
      assert(play(g,at(15),3)); conserved(g); assert(play(g,at(18),4)); conserved(g);
      assert(endTurn(g));
    }
    puts("source_order: mirrored same-die wrong-source rejection, home unlocking, source listing OK");
  } else if (scenario=="small_only") {
    Game base;
    layout(base, ". D2 D2 . . . . . . . . .", ". . . . . . . . . . . .", kLight,1);
    for (int mirror=0; mirror<2; ++mirror) {
      Game g=mirror?mirrored(base):base; assert(beginTurn(g,1,2));
      assert(maxUsableDice(g)==1 && canPlayFrom(g,kBar,1));
      const Game before=g; assert(!play(g,kBar,2));
      assert(std::memcmp(&before,&g,sizeof(Game))==0);
      assert(play(g,kBar,1)); conserved(g); assert(endTurn(g));
    }
    puts("small_only: unavailable higher die never suppresses usable lower die OK");
  } else if (scenario=="double_and_win") {
    Game base;
    layout(base, "L1 . . . . . . . . . . .", ". . . . . . . . . . . D2", kLight);
    for (int mirror=0; mirror<2; ++mirror) {
      auto at=[mirror](int p){return mirror?23-p:p;};
      Game g=mirror?mirrored(base):base; assert(beginTurn(g,2,2));
      assert(maxUsableDice(g)==4);
      for (int step=0; step<4; ++step) { assert(canPlayFrom(g,at(step*2),2)); assert(play(g,at(step*2),2)); conserved(g); }
      assert(pendingCount(g)==0 && endTurn(g));
      // A double may have only one possible move; all three dead uses remain
      // visible until end, and no checkers are lost by forfeiting them.
      layout(g, "D5 . . . . . . . . . . .", ". . . . L1 L1 D2 D2 D2 D2 D2 L13", kLight);
      if (mirror) g=mirrored(g);
      assert(beginTurn(g,1,1)); assert(maxUsableDice(g)==1);
      assert(play(g,at(16),1)); conserved(g); assert(pendingCount(g)==3 && endTurn(g));
      // Immediate wins are terminal, even when another order could use more
      // dice; the original small-die last-checker assertion stays valid too.
      for (int need : {1,4}) {
        const int source=24-need; Game win{};
        setCheckers(win,source,kLight,1); setCheckers(win,0,kDark,2);
        win.off[kLight]=14; win.off[kDark]=13; win.turn=kLight; win.outcome=Outcome::Running;
        if (mirror) win=mirrored(win);
        assert(beginTurn(win,need==1?1:3,need==1?2:4));
        assert(maxUsableDice(win)==(need==1?1:2));
        assert(canPlayFrom(win,at(source),need)); assert(play(win,at(source),need)); conserved(win);
        assert(over(win) && pendingCount(win)==1); const Game done=win;
        assert(!play(win,at(source),need) && !endTurn(win) && !beginTurn(win,3,3));
        assert(std::memcmp(&done,&win,sizeof(Game))==0);
      }
    }
    puts("double_and_win: mirrored four-use/dead-use doubles and immediate-win exception OK");
  } else if (scenario=="opening_inputs") {
    static_assert(sizeof(Game)==34, "Game bytes must have no padding");
    Game g; start(g); g.turn=kDark;
    const int bad[][2]={{0,6},{7,1},{1,0},{6,7}};
    for (const auto& pair : bad) { const Game before=g; assert(!beginOpeningTurn(g,pair[0],pair[1])); assert(std::memcmp(&before,&g,sizeof(Game))==0); }
    for (int face=1; face<=6; ++face) { const Game before=g; assert(!beginOpeningTurn(g,face,face)); assert(std::memcmp(&before,&g,sizeof(Game))==0); }
    for (int a=1; a<=6; ++a) for (int b=1; b<=6; ++b) {
      if (a==b) continue;
      start(g); assert(beginOpeningTurn(g,a,b));
      assert(g.turn==(a>b?kLight:kDark) && g.die[0]==a && g.die[1]==b && pendingCount(g)==2);
      const Game before=g; assert(!beginOpeningTurn(g,6,1)); assert(std::memcmp(&before,&g,sizeof(Game))==0); conserved(g);
    }
    for (int at=0; at<kPoints; ++at) {
      if (checkersAt(g,at,kLight)>0) setCheckers(g,at,kLight,0);
    }
    g.off[kLight]=15; settle(g); conserved(g); const Game done=g;
    assert(!beginOpeningTurn(g,6,1) && std::memcmp(&done,&g,sizeof(Game))==0);
    puts("opening_inputs: all six ties, 30 seat comparisons, bounds/pending/terminal byte-identical rejections OK");
  } else if (scenario=="search_cost") {
    uint32_t rng=93u; uint64_t total=0, peak=0;
    const auto begin=std::chrono::steady_clock::now();
    for (int sample=0; sample<4000; ++sample) {
      Game g{}; g.turn=sample%2; g.outcome=Outcome::Running;
      for (uint8_t side=0; side<kSides; ++side) {
        g.bar[side]=sample%9==0?1:0;
        const int pieces=sample%5==0?4:15-g.bar[side];
        for (int n=0; n<pieces; ++n) {
          int at;
          do {
            at=sample%5==0 ? offEdge(side)-direction(side)*(static_cast<int>(nextRandom(rng)%6)+1) :
                            static_cast<int>(nextRandom(rng)%24);
          } while (checkersAt(g,at,other(side))>0);
          setCheckers(g,at,side,checkersAt(g,at,side)+1);
        }
        g.off[side]=kCheckers-pieces-g.bar[side];
      }
      int a=sample%6+1, b=sample%3==0?a:(sample/6)%6+1;
      if (sample%11==0) {
        // Three uses possible but four owed: visit alternative orders instead
        // of returning immediately on a full-use branch. Two checkers at
        // distances 3 and 6 consume exactly three 3s before winning.
        layout(g, "D2 . . . . . . . . . . .", ". . . . . . L1 . . L1 . .", kLight);
        if (sample%2) g=mirrored(g);
        a=b=3;
      }
      assert(beginTurn(g,a,b)); conserved(g);
      probeNodes=0; const Game before=g; const int best=maxUsableDice(g);
      assert(best>=0 && best<=pendingCount(g));
      assert(probeNodes<=54241 && probeMaxDepth<=4);
      assert(std::memcmp(&before,&g,sizeof(Game))==0);
      total+=probeNodes; if(probeNodes>peak) peak=probeNodes;
    }
    const auto micros=std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now()-begin).count();
    assert(total>0 && probeMaxDepth==4);
    std::printf("search_cost: 4000 mirrored-seat mixed/double/bar/home rolls; nodes=%llu peak=%llu depth=%d host_us=%lld Game=%zu bytes; theoretical double bound=54241 nodes\n",
       static_cast<unsigned long long>(total),static_cast<unsigned long long>(peak),probeMaxDepth,static_cast<long long>(micros),sizeof(Game));
  } else { return 2; }
}
'''

def compile_turn(folder, mutations=(), optimized=False):
    folder = pathlib.Path(folder)
    for filename in ('BackgammonCore.h', 'BackgammonFlow.h'):
        shutil.copyfile(GAME_DIR / filename, folder / filename)
    for filename, old, new in mutations:
        dest = folder / filename
        text = dest.read_text()
        if text.count(old) != 1:
            raise AssertionError('non-unique mutation: ' + old)
        dest.write_text(text.replace(old, new))
    cpp = folder / 'turn.cpp'
    cpp.write_text('#include <cstdint>\nnamespace backgammon { inline uint64_t probeNodes=0; inline int probeMaxDepth=0; }\n' + HARNESS)
    exe = folder / 'turn'
    flags = ['-O2'] if optimized else []
    result = subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror', *flags, '-I', str(folder), str(cpp), '-o', str(exe)], capture_output=True, text=True)
    if result.returncode:
        raise AssertionError('actual core/Flow compile failed:\n' + result.stderr)
    return exe


class BackgammonTurnRulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.exe = compile_turn(cls.tmp.name)

    def run_scenario(self, name):
        result = subprocess.run([str(self.exe), name], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())

    def test_whole_turn_maximum_rejects_greedy_bar_entry_for_both_sides(self):
        self.run_scenario('max_use')

    def test_larger_die_is_compulsory_when_only_one_move_can_be_used(self):
        self.run_scenario('larger_die')

    def test_opening_tie_is_not_a_double_and_requires_another_seeded_roll(self):
        self.run_scenario('opening_tie')

    def test_higher_opening_seat_uses_both_original_opening_dice(self):
        self.run_scenario('opening_seats')

    def test_same_die_wrong_source_cannot_strand_second_die_in_mirrored_home_entry(self):
        self.run_scenario('source_order')

    def test_smaller_die_remains_legal_when_higher_die_is_blocked(self):
        self.run_scenario('small_only')

    def test_doubles_maximum_forfeits_and_immediate_win_exceptions_are_mirrored(self):
        self.run_scenario('double_and_win')

    def test_opening_parameter_bounds_ties_pending_and_finished_are_byte_identical(self):
        self.run_scenario('opening_inputs')

    def test_rule_mutations_fail_real_assertions_without_touching_production(self):
        files = [GAME_DIR / n for n in ('BackgammonCore.h', 'BackgammonFlow.h')]
        before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in files]
        mutations = [
            ('BackgammonCore.h', 'if (1 + maxUsableDice(next, 1) != maximum) return false;', 'if (false && 1 + maxUsableDice(next, 1) != maximum) return false;', 'max_use'),
            ('BackgammonCore.h', 'if (maximum == 1) {', 'if (false && maximum == 1) {', 'larger_die'),
            ('BackgammonCore.h', 'game.turn = lightDie > darkDie ? kLight : kDark;', 'game.turn = kLight;', 'opening_seats'),
            ('BackgammonFlow.h', 'if (a == b) return true;', 'if (false && a == b) return true;', 'opening_tie'),
            ('BackgammonCore.h', 'return beginTurn(game, lightDie, darkDie);', 'return beginTurn(game, lightDie, lightDie);', 'opening_inputs'),
            ('BackgammonCore.h', 'if (over(next)) return true;', 'if (false && over(next)) return true;', 'double_and_win'),
        ]
        for filename, old, new, scenario in mutations:
            with self.subTest(rule=scenario), tempfile.TemporaryDirectory() as folder:
                exe = compile_turn(folder, [(filename, old, new)])
                result = subprocess.run([str(exe), scenario], capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, -6, 'mutation must hit runtime assertion: ' + result.stderr)
                self.assertIn('Assertion', result.stderr)
                print('rule mutation: ' + next(line for line in result.stderr.splitlines() if 'Assertion' in line))
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).hexdigest() for p in files])

    def test_search_is_four_transitions_allocation_free_and_measured(self):
        core = (GAME_DIR / 'BackgammonCore.h').read_text()
        self.assertEqual(re.findall(r'^#include\s+(.+)$', core, re.M), ['<cstdint>'])
        for pattern in (r'\bnew\s', r'\b(?:malloc|calloc|realloc|time|millis|delay|sleep)\s*\(', r'#include\s*[<\"](?:vector|chrono|random|Arduino)'):
            self.assertIsNone(re.search(pattern, core))
        self.assertIn('constexpr int kMaxTurnSearchDepth = kMaxPendingDice;', core)
        self.assertIn('depth >= kMaxTurnSearchDepth', core)
        self.assertIn('maxUsableDice(next, depth + 1)', core)
        anchor = 'inline int maxUsableDice(const Game& game, const int depth = 0) {'
        # Instrument only a copied core, not the firmware API or shared state.
        instrument = anchor + '\n  ++probeNodes; if (depth>probeMaxDepth) probeMaxDepth=depth;'
        # The counters in the harness must refer to the production namespace.
        with tempfile.TemporaryDirectory() as folder:
            exe = compile_turn(folder, [('BackgammonCore.h', anchor, instrument)], optimized=True)
            result = subprocess.run([str(exe), 'search_cost'], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            print(result.stdout.strip())

if __name__ == '__main__':
    unittest.main()
