"""Compile the real category-aware lesson and independent progress core."""
from pathlib import Path
import os
import subprocess
import unittest

ROOT = Path(os.environ.get('JAPANESE_DIALOGUES_TEST_ROOT', Path(__file__).resolve().parents[2]))
BUILD = ROOT / 'build/japanese-basic30-progress/core'

class DialoguesCoreTests(unittest.TestCase):
    def run_cpp(self, source, progress=False):
        directory = BUILD / self._testMethodName
        directory.mkdir(parents=True, exist_ok=True)
        cpp, exe = directory / 'main.cpp', directory / 'core'
        header = 'JapaneseSentenceProgress.h' if progress else 'JapaneseSentences.h'
        cpp.write_text('#include "' + header + '"\n#include <cassert>\n#include <initializer_list>\n#include <type_traits>\n' + source)
        command = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-fsanitize=undefined', '-fno-sanitize-recover=all', '-I', str(ROOT/'src/activities/apps/japanese'), str(cpp), '-o', str(exe)]
        compiled = subprocess.run(command, capture_output=True, text=True)
        (directory/'compile.log').write_text(' '.join(command)+'\n'+compiled.stdout+compiled.stderr)
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        run = subprocess.run([str(exe)], capture_output=True, text=True)
        (directory/'runtime.log').write_text(run.stdout+run.stderr)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_category_selection_and_navigation_are_relative_bounded_hidden(self):
        self.run_cpp(r'''
int main() {
  japanese::Sentences s;
  static_assert(japanese::Sentences::categoryCount()==9);
  static_assert(japanese::Sentences::categorySize(0)==30 && japanese::Sentences::categoryFirst(8)==240);
  static_assert(japanese::Sentences::categorySize(-1)==0 && japanese::Sentences::categorySize(9)==0);
  static_assert(japanese::Sentences::categoryFirst(-1)==-1 && japanese::Sentences::categoryFirst(9)==-1);
  assert(s.category()==0 && s.globalPosition()==0 && s.count()==30);
  for(int category=0;category<9;++category) {
    const int size=30,first=category*30;
    assert(japanese::Sentences::categorySize(category)==size && japanese::Sentences::categoryFirst(category)==first);
    for(int local=0;local<size;++local) {
      assert(s.selectCategory(category,local));
      assert(s.count()==size && s.category()==category && s.position()==local && s.globalPosition()==first+local);
      assert(!s.revealed()); s.toggleReveal();
      for(int bad : {-1,9,255}) {assert(!s.selectCategory(bad));assert(s.category()==category && s.position()==local && s.revealed());}
      for(int bad : {-1,size,255}) {assert(!s.selectCategory(category,bad));assert(!s.restore(bad));assert(s.position()==local && s.revealed());}
      assert(s.restore(local) && !s.revealed());
      for(int n=0;n<100;++n) s.next();
      assert(s.position()==size-1 && s.category()==category && !s.canNext());
      s.toggleReveal();assert(!s.next() && s.revealed());
      for(int n=0;n<100;++n) s.previous();
      assert(s.position()==0 && s.category()==category && !s.canPrevious() && !s.revealed());
      s.toggleReveal();assert(!s.previous() && s.revealed());
      assert(s.selectCategory(category,size-1) && !s.revealed());s.toggleReveal();s.restart();
      assert(s.position()==0 && s.category()==category && !s.revealed());
    }
  }
}
''')

    def test_record_tracks_all_270_bits_and_rejects_invalid_without_mutation(self):
        self.run_cpp(r'''
using namespace japanese::sentenceprogress;
int main() {
  static_assert(kCategoryCount==9 && kCardCount==270 && kReadBytes==34 && kMaxCardsPerCategory==30);
  static_assert(std::is_same_v<decltype(kCategoryCounts), const std::array<uint8_t,9>>);
  static_assert(std::is_same_v<decltype(kCategoryFirsts), const std::array<uint16_t,9>>);
  static_assert(categorySize(-1)==0 && categorySize(9)==0 && categoryFirst(-1)==-1 && categoryFirst(9)==-1);
  Progress p;assert(validProgress(p));
  assert(!record(p,0,0,false) && p.revision==0);
  for(int c=0;c<9;++c) {
    const int first=c*30,size=30;
    assert(categoryFirst(c)==first && categorySize(c)==size && kCategoryCounts[c]==size && kCategoryFirsts[c]==first);
    for(int l=0;l<size;++l) {
      const int g=first+l;assert(!isRead(p,g));auto rev=p.revision;
      assert(record(p,c,l,true));assert(p.revision==rev+1 && p.lastCategory==c && p.positions[c]==l);
      assert(isRead(p,g) && readCount(p,c)==l+1);
      assert(!record(p,c,l,true) && p.revision==rev+1);
      assert(!record(p,c,l,false));
    }
  }
  assert(p.readBits[33]==63 && !isRead(p,-1) && !isRead(p,270));
  for(int i=0;i<33;++i)assert(p.readBits[i]==255);
  assert(readCount(p,-1)==0 && readCount(p,9)==0);
  auto same=[&](const Progress& q){return p.revision==q.revision && p.lastCategory==q.lastCategory && p.positions==q.positions && p.readBits==q.readBits;};
  for(int c : {-1,9,255}) {auto before=p;assert(!record(p,c,0,true) && same(before));}
  for(int c=0;c<9;++c)for(int l : {-1,categorySize(c),255}) {auto before=p;assert(!record(p,c,l,true) && same(before));}
  p.lastCategory=9;assert(!validProgress(p));auto before=p;assert(!record(p,0,0,true) && same(before));p.lastCategory=0;
  for(int c=0;c<9;++c){p.positions[c]=categorySize(c);assert(!validProgress(p));p.positions[c]=0;}
  for(int bit : {64,128}){p.readBits[33]|=bit;assert(!validProgress(p) && !isRead(p,270) && !isRead(p,271));p.readBits[33]&=63;}
  p.revision=UINT32_MAX;before=p;assert(!record(p,0,29,true) && same(before));
}
''', progress=True)

    def test_merge_pending_unions_reads_and_only_selected_category_positions_once(self):
        self.run_cpp(r'''
using namespace japanese::sentenceprogress;
int main(){
  Progress latest,pending;assert(record(latest,4,2,true));assert(record(latest,1,3,true));
  for(int c=0;c<9;++c)for(int l=0;l<30;++l) assert(record(pending,c,l,true));
  pending.positions.fill(29);pending.revision=UINT32_MAX;
  auto before=latest;
  assert(mergePending(latest,pending,(1u<<0)|(1u<<8),false));
  assert(latest.revision==before.revision+1 && latest.lastCategory==before.lastCategory);
  for(int c=0;c<9;++c) {assert(readCount(latest,c)==30);assert(latest.positions[c]==(c==0 || c==8?29:before.positions[c]));}
  auto rev=latest.revision;assert(!mergePending(latest,pending,(1u<<0)|(1u<<8),false) && latest.revision==rev);
  assert(mergePending(latest,pending,0,true) && latest.lastCategory==8 && latest.revision==rev+1);
  auto unchanged=[&](const Progress& p){return latest.revision==p.revision && latest.lastCategory==p.lastCategory && latest.positions==p.positions && latest.readBits==p.readBits;};
  for(uint16_t invalid : {uint16_t(512),uint16_t(65535)}) {auto old=latest;assert(!mergePending(latest,pending,invalid,true) && unchanged(old));}
  pending.positions[0]=30;before=latest;assert(!mergePending(latest,pending,1,true) && unchanged(before));pending.positions[0]=29;
  pending.readBits[33]=255;assert(!mergePending(latest,pending,1,true) && unchanged(before));pending.readBits[33]=63;
  latest.lastCategory=9;before=latest;assert(!mergePending(latest,pending,1,true) && unchanged(before));latest.lastCategory=0;
  latest.revision=UINT32_MAX;before=latest;assert(!mergePending(latest,pending,1,true) && unchanged(before));
}
''', progress=True)

    def test_original_six_card_include_and_each_navigation_transition_remain_compatible(self):
        self.run_cpp(r'''
int main(){
  static_assert(japanese::sentences::kCardCount==6);
  assert(japanese::sentences::cards[0].id[0]=='s');
  for(int category=0;category<9;++category){japanese::Sentences s;assert(s.selectCategory(category));
   for(int position=0;position<s.count()-1;++position){s.toggleReveal();assert(s.revealed());assert(s.next() && !s.revealed() && s.position()==position+1);}
   for(int position=s.count()-1;position>0;--position){s.toggleReveal();assert(s.revealed());assert(s.previous() && !s.revealed() && s.position()==position-1);}
  }
}
''')

    def test_hidden_moves_never_mark_reads_and_preserve_independent_category_positions(self):
        self.run_cpp(r'''
using namespace japanese::sentenceprogress;
int main(){Progress p;
 for(int c=0;c<9;++c){
  assert(record(p,c,29,false));
  for(int global=0;global<270;++global)assert(!isRead(p,global));
  assert(p.positions[c]==29 && p.lastCategory==c && readCount(p,c)==0);
 }
 for(int c=0;c<9;++c){
  auto revision=p.revision;assert(record(p,c,29,true) && p.revision==revision+1);
  for(int other=0;other<9;++other){assert(p.positions[other]==(other<c?28:29));assert(isRead(p,other*30+29)==(other<=c));}
  auto bits=p.readBits;assert(record(p,c,28,false) && p.readBits==bits && p.positions[c]==28);
  for(int other=0;other<9;++other)assert(p.positions[other]==(other<=c?28:29));
 }
 for(int c=0;c<9;++c)assert(readCount(p,c)==1 && !isRead(p,c*30+28));
}
''', progress=True)

if __name__ == '__main__':
    unittest.main()
