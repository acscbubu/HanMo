"""Host runtime tests compiling the real fixed-capacity Japanese review core."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(os.environ.get('JAPANESE_REVIEW_TEST_ROOT', Path(__file__).resolve().parents[2]))


class ReviewCoreTests(unittest.TestCase):
    def run_cpp(self, body):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            source = temp / 'main.cpp'
            source.write_text('#include "activities/apps/japanese/JapaneseReview.h"\n#include <cassert>\n#include <limits>\nusing namespace japanese::review;\nint main(){\n' + body + '\n}\n')
            command = ['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-fsanitize=undefined', '-fno-sanitize-recover=all', '-I', str(ROOT / 'src'), str(source), '-o', str(temp / 'test')]
            built = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run([str(temp / 'test')], text=True, capture_output=True)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)

    def test_supported_day_and_default_counts(self):
        self.run_cpp(r'''
Progress p;
static_assert(kMinDay == 19723 && kMaxDay == 47481);
assert(!validDay(0,p) && !validDay(kMinDay-1,p) && !validDay(kMaxDay+1,p));
assert(validDay(kMinDay,p) && validDay(kMaxDay,p));
auto s=stats(p,kMinDay); assert(s.fresh==45 && s.due==0 && s.completed==0);
p.latestDay=kMinDay+3; assert(!validDay(kMinDay+2,p) && validDay(kMinDay+3,p));
''')

    def test_new_ratings_shared_ids_eligibility_and_all_or_nothing(self):
        self.run_cpp(r'''
Progress p; const uint32_t day=kMinDay+10;
Progress forbidden;assert(!applyRating(forbidden,44,Rating::Known,day));assert(forbidden.revision==0 && forbidden.words[44].reviews==0);
assert(applyRating(p,0,Rating::Again,day));
assert(applyRating(p,1,Rating::Familiar,day));
assert(applyRating(p,45,Rating::Known,day));
assert(p.words[0].dueDay==day+1 && p.words[0].intervalDays==1);
assert(p.words[1].dueDay==day+3 && p.words[1].intervalDays==3);
assert(p.words[44].dueDay==day+7 && p.words[44].intervalDays==7);
assert(p.words[44].reviews==1 && p.words[44].rating==3);
assert(p.revision==3 && p.latestDay==day);
auto s=stats(p,day);assert(s.completed==3 && s.fresh==42 && s.due==0);
s=stats(p,day+1);assert(s.completed==0 && s.due==1 && s.fresh==42);
const auto before=p;
for(int id: {-1,44,46}) assert(!applyRating(p,id,Rating::Again,day));
assert(!applyRating(p,2,static_cast<Rating>(0),day));
assert(!applyRating(p,2,static_cast<Rating>(4),day));
assert(!applyRating(p,0,Rating::Known,day));
assert(!applyRating(p,1,Rating::Known,day+1));
assert(!applyRating(p,2,Rating::Again,day-1));
assert(p.revision==before.revision && p.latestDay==before.latestDay);
for(int i=0;i<45;++i) assert(p.words[i].dueDay==before.words[i].dueDay && p.words[i].reviews==before.words[i].reviews);
Progress end;assert(!applyRating(end,0,Rating::Again,kMaxDay));assert(end.revision==0);
''')

    def test_known_rungs_saturation_overflow_and_clock_without_rebucket(self):
        self.run_cpp(r'''
Progress p; uint32_t day=kMinDay;
for(int expected: {7,14,30,30}) {
 assert(applyRating(p,3,Rating::Known,day));
 assert(p.words[3].intervalDays==expected); day=p.words[3].dueDay;
}
assert(applyRating(p,3,Rating::Again,day));day=p.words[3].dueDay;
assert(applyRating(p,3,Rating::Known,day));assert(p.words[3].intervalDays==3);day=p.words[3].dueDay;
assert(applyRating(p,3,Rating::Known,day));assert(p.words[3].intervalDays==7);
p.words[3].reviews=65535;p.revision=65535;
day=p.words[3].dueDay;assert(applyRating(p,3,Rating::Familiar,day));
assert(p.words[3].reviews==65535 && p.revision==65536);
const auto due=p.words[3].dueDay;assert(validDay(day+300,p));
(void)stats(p,day+300);assert(p.words[3].dueDay==due);
p.revision=UINT32_MAX;assert(!applyRating(p,4,Rating::Known,day));
assert(p.words[4].reviews==0 && p.revision==UINT32_MAX);
Progress boundary;assert(applyRating(boundary,0,Rating::Known,kMaxDay-7));
assert(boundary.words[0].dueDay==kMaxDay);
Progress refuse;assert(!applyRating(refuse,0,Rating::Known,kMaxDay-6));assert(refuse.revision==0);
''')

    def test_sentence_only_changes_are_idempotent_and_do_not_need_clock(self):
        self.run_cpp(r'''
Progress p;assert(!recordSentence(p,0,false));assert(p.revision==0);
assert(recordSentence(p,5,false));assert(p.sentencePosition==5 && p.revision==1 && p.latestDay==0);
assert(recordSentence(p,5,true));assert(p.sentenceReadMask==32 && p.revision==2);
assert(!recordSentence(p,5,true));assert(p.revision==2);
assert(recordSentence(p,0,true));assert(p.sentenceReadMask==33 && p.sentencePosition==0 && p.revision==3);
assert(!recordSentence(p,-1,true) && !recordSentence(p,6,true));assert(p.revision==3);
auto s=stats(p,kMinDay);assert(s.fresh==45 && s.completed==0);
p.revision=UINT32_MAX;assert(!recordSentence(p,1,true));assert(p.sentenceReadMask==33 && p.sentencePosition==0);
''')

    def test_session_due_order_fresh_ids_reveal_and_restart_skip(self):
        self.run_cpp(r'''
Progress p;assert(applyRating(p,3,Rating::Familiar,kMinDay));
assert(applyRating(p,1,Rating::Again,kMinDay));assert(applyRating(p,2,Rating::Again,kMinDay));
assert(applyRating(p,4,Rating::Known,kMinDay));
Session s;assert(s.done() && s.current()==-1 && !s.reveal() && !s.advance());
assert(s.start(p,kMinDay+3));assert(s.size()==44 && s.position()==0 && s.current()==1 && !s.revealed());
assert(!s.advance());assert(s.reveal() && !s.reveal());
assert(applyRating(p,1,Rating::Known,kMinDay+3));assert(s.advance());assert(s.current()==2 && !s.revealed());
assert(s.reveal() && s.advance() && s.current()==3);assert(s.reveal() && s.advance() && s.current()==0);
int last=-1;
while(!s.done()) {assert(s.current()!=44 && s.current()>last);last=s.current();assert(s.reveal() && s.advance());}
assert(last==45 && s.position()==44 && !s.advance() && s.current()==-1);
Session restarted;assert(restarted.start(p,kMinDay+3));assert(restarted.current()==2 && restarted.size()==43);
assert(!restarted.start(p,kMinDay+2));assert(restarted.current()==2); // failed start is atomic
Progress all;for(int i=0;i<45;++i) assert(applyRating(all,japanese::Words::cardIdAt(i),Rating::Again,kMinDay));
assert(s.start(all,kMinDay) && s.done() && s.size()==0 && s.current()==-1);
''')


if __name__ == '__main__':
    unittest.main()
