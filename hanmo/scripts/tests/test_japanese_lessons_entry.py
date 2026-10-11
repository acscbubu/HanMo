"""Focused lesson integration: only the two new routes/fonts/labels/history."""
from pathlib import Path
import json
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
J = ROOT / 'src/activities/apps/japanese'
FONT = ROOT / 'lib/EpdFont/builtinFonts'


def function_body(source, signature):
    start = source.index(signature)
    brace = source.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def intervals(text):
    return [(int(a, 16), int(b, 16)) for a, b in
            re.findall(r'\{\s*(0x[0-9a-fA-F]+),\s*(0x[0-9a-fA-F]+),\s*0x[0-9a-fA-F]+\s*\}', text)]


class JapaneseLessonsEntryTests(unittest.TestCase):
    def test_actual_factory_routes_both_new_lessons_and_handles_oom_and_resume(self):
        source = (J / 'JapaneseLearningActivity.cpp').read_text()
        bodies = '\n'.join(function_body(source, 'void JapaneseLearningActivity::' + name)
                            for name in ('onBackButton()', 'activateIndex(int index)'))
        harness = r'''
#include <cassert>
#include <functional>
#include <type_traits>
class KanaGroupsActivity {}; class KanaStrokeActivity {}; class KanaQuizActivity {};
class KanaSimilarActivity {}; class JapaneseWordsActivity {}; class JapaneseSentencesActivity {};
struct ActivityResult {}; struct Renderer {};
struct App { int clears=0; void clearTapFlash() { ++clears; } } app;
struct Manager { int apps=0; void goToApps(){++apps;} } activityManager;
struct Gui { int errors=0; void drawPopup(Renderer&, const char*){++errors;} } GUI;
#define tr(id) "Memory error"
class JapaneseLearningActivity {
public:
  Renderer renderer;
  int category_=-1, updates=0, starts=0, target=0;
  bool allocation=true;
  std::function<void(const ActivityResult&)> callback;
  int listCount() const { return category_ < 0 ? 8 : 3; }
  void finish() {}
  void requestUpdate(){++updates;}
  template<class T, class F, class... Args> bool startActivityForResultWith(F fn, Args...){
    ++starts;
    target=std::is_same<T,JapaneseWordsActivity>::value ? 5 : std::is_same<T,JapaneseSentencesActivity>::value ? 6 : -1;
    if (allocation) callback=fn;
    return allocation;
  }
  void onBackButton();
  void activateIndex(int index);
};
''' + bodies + r'''
int main(){
  for(int row: {5,6}) {
    JapaneseLearningActivity a;
    int c=app.clears;
    a.activateIndex(row);
    assert(a.starts==1 && a.target==row && app.clears==c+1);
    assert(a.callback && a.updates==0);
    a.callback(ActivityResult{});
    assert(a.updates==1);
    JapaneseLearningActivity failed; failed.allocation=false;
    int e=GUI.errors;
    failed.activateIndex(row);
    assert(failed.starts==1 && failed.target==row && GUI.errors==e+1 && failed.updates==1);
  }
  JapaneseLearningActivity a;
  a.activateIndex(-1); a.activateIndex(8);
  assert(a.starts==0);
}
'''
        with tempfile.TemporaryDirectory() as d:
            cpp = Path(d) / 'routes.cpp'
            exe = Path(d) / 'routes'
            cpp.write_text(harness)
            subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', str(cpp), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)

    def test_sentence_font_has_all_emitted_hiragana_and_full_stop(self):
        path = FONT / 'hanmo_sentences_28.h'
        self.assertTrue(path.is_file(), 'the new sentence font has not been generated')
        text = path.read_text()
        self.assertIn('hanmo_sentences_28', text)
        covered = intervals(text)
        # Independent fixed first-lesson oracle, not the generated header under test.
        for sentence in ('これはほんです。', 'これはかさです。', 'これはちずです。',
                         'みずをのみます。', 'すしをたべます。', 'ほんをよみます。'):
            for ch in sentence:
                self.assertTrue(any(a <= ord(ch) <= b for a, b in covered), (sentence, ch))

    def test_new_sentence_labels_and_notes_fit_every_cjk_size(self):
        # UI/history can use any shipped size. Lesson body is fixed notes12,
        # checked separately below; 吃 is absent at stock14/16/18, not notes12.
        values = ['は表示主題，此時讀 wa。', 'です是客氣的說法。',
                  'を表示動作對象，讀 o。', 'ます是客氣的說法。']
        for locale in ('english', 'chinese', 'chinese-traditional'):
            text = (ROOT / 'lib/I18n/translations' / (locale + '.yaml')).read_text()
            keys = {line.split(': ', 1)[0]: json.loads(line.split(': ', 1)[1])
                    for line in text.splitlines() if line.startswith(('STR_JP_SENTENCES_', 'STR_CHANGE_JP_SENTENCES_'))}
            for key in ('REVEAL', 'HIDE', 'PROMPT', 'SESSION'):
                self.assertIn('STR_JP_SENTENCES_' + key, keys)
            for key in ('TITLE', 'WHAT', 'HOW', 'NOTE'):
                self.assertIn('STR_CHANGE_JP_SENTENCES_' + key, keys)
            values.extend(keys.values())
        common = (FONT / 'notosans_cjk_common_intervals.h').read_text()
        needed = {ord(ch) for value in values for ch in value if '\u4e00' <= ch <= '\u9fff'}
        missing = {}
        for size in (8, 10, 12, 14, 16, 18):
            header = (FONT / f'notosans_cjk_{size}.h').read_text()
            covered = intervals(header if f'notosans_cjk_{size}Intervals[]' in header else common)
            missing[size] = [chr(cp) for cp in sorted(needed) if not any(a <= cp <= b for a, b in covered)]
        self.assertEqual(missing, {size: [] for size in missing})

    def test_mixed_japanese_grammar_notes_use_a_real_covering_notes_font(self):
        path = FONT / 'hanmo_sentence_notes_12.h'
        self.assertTrue(path.is_file(), 'UI CJK fallback lacks the Japanese grammar particles')
        covered = intervals(path.read_text())
        for text in ('は表示主題，此時讀 wa。', 'です是客氣的說法。',
                     'を表示動作對象，讀 o。', 'ます是客氣的說法。',
                     '這是書。這是傘。這是地圖。喝水。吃壽司。讀書。'):
            for ch in text:
                self.assertTrue(any(a <= ord(ch) <= b for a, b in covered), (text, ch))

    def test_candidate_identity_and_two_new_history_entries_are_explicit(self):
        ini = (ROOT / 'platformio.ini').read_text()
        custom = ini.split('[env:x4pro_custom]', 1)[1].split('\n[', 1)[0]
        self.assertIn('${crosspoint.version}-hanmo-japanese-lessons-20261008', custom)
        entries = json.loads((ROOT / 'docs/custom-change-history-evidence.json').read_text())
        self.assertEqual([r['id'] for r in entries[:2]], ['JP_SENTENCES', 'JP_WORDS'])
        self.assertEqual(len(entries), len({r['id'] for r in entries}))
        self.assertEqual(len(entries), 63)
        header = (ROOT / 'src/activities/settings/ChangeHistoryData.h').read_text()
        for prefix in ('JP_SENTENCES', 'JP_WORDS'):
            for part in ('TITLE', 'WHAT', 'HOW', 'NOTE'):
                self.assertEqual(header.count('StrId::STR_CHANGE_' + prefix + '_' + part), 1)
        self.assertNotIn(b'\n', (ROOT / 'platformio.ini').read_bytes().replace(b'\r\n', b''))


if __name__ == '__main__':
    unittest.main()
