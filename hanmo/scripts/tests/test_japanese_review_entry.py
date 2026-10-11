"""Only new review routing, UI labels/glyphs and private source identity."""
from pathlib import Path
import json
import re
import subprocess
import tempfile
import unittest
from scripts.tests.test_japanese_lessons_entry import function_body, intervals

ROOT = Path(__file__).resolve().parents[2]
J = ROOT / 'src/activities/apps/japanese'

class JapaneseReviewEntryTests(unittest.TestCase):
    def test_actual_seventh_route_success_oom_and_parent_refresh(self):
        source = (J / 'JapaneseLearningActivity.cpp').read_text()
        bodies = '\n'.join(function_body(source, 'void JapaneseLearningActivity::' + sig)
                           for sig in ('onBackButton()', 'activateIndex(int index)'))
        harness = r'''
#include <cassert>
#include <functional>
#include <type_traits>
class KanaGroupsActivity {}; class KanaStrokeActivity {}; class KanaQuizActivity {};
class KanaSimilarActivity {}; class JapaneseWordsActivity {}; class JapaneseSentencesActivity {};
class JapaneseReviewActivity {};
struct ActivityResult {}; struct Renderer {};
struct App { int clears=0; void clearTapFlash(){++clears;} } app;
struct Manager { void goToApps(){} } activityManager;
struct Gui { int errors=0; void drawPopup(Renderer&,const char*){++errors;} } GUI;
#define tr(x) "OOM"
class JapaneseLearningActivity {
 public:
 Renderer renderer; int category_=-1,starts=0,target=0,updates=0; bool allocation=true;
 std::function<void(const ActivityResult&)> callback;
 int listCount()const{return category_<0?8:3;}
 void finish(){} void requestUpdate(){++updates;}
 template<class T,class F,class... Args> bool startActivityForResultWith(F f,Args...){
 ++starts;target=std::is_same<T,JapaneseReviewActivity>::value?7:-1;
 if(allocation)callback=f;
 return allocation;
 }
 void onBackButton();void activateIndex(int index);
};
''' + bodies + r'''
int main(){
 JapaneseLearningActivity a;a.activateIndex(7);
 assert(a.starts==1&&a.target==7&&a.callback&&app.clears==1);
 a.callback(ActivityResult{});assert(a.updates==1);
 JapaneseLearningActivity b;b.allocation=false;b.activateIndex(7);
 assert(b.starts==1&&b.target==7&&GUI.errors==1&&b.updates==1);
 JapaneseLearningActivity c;c.activateIndex(-1);c.activateIndex(8);assert(c.starts==0);
}
'''
        with tempfile.TemporaryDirectory() as d:
            cpp=Path(d)/'route.cpp'; exe=Path(d)/'route'
            cpp.write_text(harness)
            subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror',str(cpp),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)

    def test_new_labels_and_history_cover_all_six_stock_cjk_sizes(self):
        keys=['START','NEW','DUE','DONE','AGAIN','FAMILIAR','KNOWN','SAVED','SAVE_ERROR',
              'STORAGE_ERROR','CORRUPT','CLOCK','RETRY','COMPLETE','RULES']
        values=[]
        for locale in ('english','chinese','chinese-traditional'):
            text=(ROOT/'lib/I18n/translations'/f'{locale}.yaml').read_text()
            pairs={line.split(': ',1)[0]:json.loads(line.split(': ',1)[1]) for line in text.splitlines()
                   if line.startswith(('STR_JP_REVIEW_','STR_JP_SENTENCES_PROGRESS','STR_CHANGE_JP_REVIEW_'))}
            for k in keys:self.assertIn('STR_JP_REVIEW_'+k,pairs)
            for k in ('TITLE','WHAT','HOW','NOTE'):self.assertIn('STR_CHANGE_JP_REVIEW_'+k,pairs)
            self.assertIn('STR_JP_SENTENCES_PROGRESS',pairs)
            values.extend(pairs.values())
        font=ROOT/'lib/EpdFont/builtinFonts'
        common=(font/'notosans_cjk_common_intervals.h').read_text()
        needed={ord(ch) for s in values for ch in s if '\u4e00'<=ch<='\u9fff'}
        for size in (8,10,12,14,16,18):
            h=(font/f'notosans_cjk_{size}.h').read_text()
            cov=intervals(h if f'notosans_cjk_{size}Intervals[]' in h else common)
            self.assertEqual([chr(cp) for cp in sorted(needed) if not any(a<=cp<=b for a,b in cov)],[],size)

    def test_new_candidate_and_newest_history_not_old_two_lesson_identity(self):
        data=(ROOT/'platformio.ini').read_bytes()
        custom=data.decode().split('[env:x4pro_custom]',1)[1].split('\n[',1)[0]
        self.assertIn('${crosspoint.version}-hanmo-japanese-review-20261008',custom)
        self.assertNotIn(b'\n',data.replace(b'\r\n',b''))
        rows=json.loads((ROOT/'docs/custom-change-history-evidence.json').read_text())
        self.assertEqual(rows[0]['id'],'JP_REVIEW')
        self.assertEqual(len(rows),64)
        self.assertEqual(len(rows),len({r['id'] for r in rows}))
        self.assertEqual([r['id'] for r in rows[1:3]],['JP_SENTENCES','JP_WORDS'])
        header=(ROOT/'src/activities/settings/ChangeHistoryData.h').read_text()
        for part in ('TITLE','WHAT','HOW','NOTE'):
            self.assertEqual(header.count('StrId::STR_CHANGE_JP_REVIEW_'+part),1)
        for locale,field in [('chinese-traditional','traditional'),('chinese','simplified'),('english','english')]:
            text=(ROOT/'lib/I18n/translations'/f'{locale}.yaml').read_text()
            for part,value in zip(('TITLE','WHAT','HOW','NOTE'),rows[0][field]):
                self.assertIn('STR_CHANGE_JP_REVIEW_'+part+': '+json.dumps(value,ensure_ascii=False),text)

if __name__=='__main__':unittest.main()
