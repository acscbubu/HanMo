"""Real Activity TU, UiAppHost and FreeInkApp runtime; only hardware seams.
Final acceptance requires the parent's generated dialogue fonts and all locales.
"""
from pathlib import Path
import json
import os
import re
import subprocess
import unittest
from scripts.tests.test_japanese_sentences_ui import STUBS as LEGACY_SEAMS
from scripts.tests.test_japanese_review_store import FAKE_STORAGE

ROOT = Path(os.environ.get('JAPANESE_DIALOGUES_UI_ROOT', Path(__file__).resolve().parents[2]))
INCLUDE = ROOT / 'src/activities/apps/japanese'
ACTIVITY_SOURCE = Path(os.environ.get('JAPANESE_DIALOGUES_UI_ACTIVITY_SOURCE', INCLUDE/'JapaneseSentencesActivity.cpp'))
FUI = ROOT / 'freeink-sdk/libs/ui/FreeInkUI/include'
BUILD = ROOT / 'build/japanese-basic30-ui'
STRINGS = ['STR_JP_SENTENCES','STR_BACK','STR_KANA_PREV','STR_KANA_NEXT',
    'STR_JP_SENTENCES_REVEAL','STR_JP_SENTENCES_HIDE','STR_JP_SENTENCES_PROMPT',
    'STR_JP_SENTENCES_SESSION','STR_JP_SENTENCES_PROGRESS','STR_JP_REVIEW_SAVED',
    'STR_JP_REVIEW_SAVE_ERROR','STR_JP_REVIEW_STORAGE_ERROR','STR_JP_REVIEW_CORRUPT','STR_JP_REVIEW_RETRY']
CATEGORY_KEYS = ['STR_JP_DIALOGUES_' + s for s in ['BASIC','DAILY','RESTAURANT','SHOPPING','TRANSPORT','HOTEL','DIRECTIONS','SOCIAL','EMERGENCY']]
STRINGS += CATEGORY_KEYS + ['STR_JP_DIALOGUES_PICK','STR_JP_DIALOGUES_DETAILS']
# These labels permit the first RED tracer before the parent adds locale keys.
# They are NEVER used in the final acceptance mode.
TEMP_LABELS = ['基礎','生活','餐廳','購物','交通','住宿','問路','社交','緊急','選擇分類','更多解說']

PREFIX = r'''
#include "activities/Activity.h"
#include "components/UiAppHost.h"
#include "components/UITheme.h"
#include "components/UIScale.h"
#include "I18n.h"
#include "JapaneseReviewStore.h"
#include "fixtures/japanese_basic30_legacy_ui.h"
#if __has_include("JapaneseSentenceProgressStore.h")
#include "JapaneseSentenceProgressStore.h"
#endif
#if __has_include("JapaneseDialogues.generated.h")
#include "JapaneseDialogues.generated.h"
#endif
#define private public
#define protected public
#include "JapaneseSentencesActivity.h"
#undef protected
#undef private
namespace fui = freeink::ui;
constexpr int expectedCounts[9]={30,30,30,30,30,30,30,30,30};
constexpr int expectedFirsts[9]={0,30,60,90,120,150,180,210,240};
bool has(const GfxRenderer& r,const char* value) {
  for(const auto& d:r.draws) if(d.text==value)return true;
  return false;
}
const Draw& find(const GfxRenderer& r,const char* value) {
  for(const auto& d:r.draws) if(d.text==value)return d;
  assert(false && "required paint missing");return r.draws.front();
}
void paint(JapaneseSentencesActivity& a){a.render(RenderLock(a));assert(!a.app.interactionOverflowed());}
using B=MappedInputManager::Button;
void release(JapaneseSentencesActivity& a,MappedInputManager& i,B b){
  i.clear();i.released[int(b)]=true;a.loop();i.clear();
}
void touch(JapaneseSentencesActivity& a,MappedInputManager& i,int x,int y,bool press=false){
  i.clear();i.touch.touchPressed=press;i.touch.touchReleased=!press;
  i.touch.touchX=x;i.touch.touchY=y;a.loop();i.clear();
}
void tap(JapaneseSentencesActivity& a,MappedInputManager& i,GfxRenderer& r,StrId id){
  paint(a);const auto d=find(r,I18N.get(id));touch(a,i,d.x+d.width/2,d.y+d.height/2);
}
'''

class JapaneseDialoguesRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get('JAPANESE_DIALOGUES_UI_BOOTSTRAP') != '1':
            required=[INCLUDE/'JapaneseDialogues.generated.h',ROOT/'lib/EpdFont/builtinFonts/hanmo_dialogues_20.h']
            missing=[str(p.relative_to(ROOT)) for p in required if not p.exists()]
            if missing:
                raise RuntimeError('Parent-only generation not ready: '+', '.join(missing)+
                    '. Temporary authored-data/real-font verification uses JAPANESE_DIALOGUES_UI_BOOTSTRAP=1; it is not the final production-generated acceptance.')
    def run_cpp(self, body, require_current_content=True):
        # Focused control/storage tests may use authentic existing content while
        # assembly is pending. They never claim all-270 content/font acceptance.
        if require_current_content:
            if os.environ.get('JAPANESE_DIALOGUES_UI_BOOTSTRAP') == '1':
                size = len(json.loads((ROOT/'data/japanese/sentences-dialogues.json').read_text())['cards'])
                ready = size == 270
            else:
                generated = (INCLUDE/'JapaneseDialogues.generated.h').read_text()
                ready = bool(re.search(r'kCardCount\s*=\s*270\b', generated))
            if not ready:
                raise RuntimeError('Parent integration required: genuine authored 270-card aggregate / generated header and fonts are not ready. No fabricated bootstrap content is permitted.')
        directory = BUILD / self._testMethodName
        directory.mkdir(parents=True,exist_ok=True)
        seams = {k:v for k,v in LEGACY_SEAMS.items() if k not in
            ['EpdFontFamily.h','JapaneseReviewStore.h','I18n.h','HalStorage.h'] and not k.startswith('builtinFonts/')}
        seams['Arduino.h'] = '#pragma once\n#include <cstddef>\n'
        seams['components/UITheme.h'] = seams['components/UITheme.h'].replace('const char* progress) const', 'const char* progress="") const')
        # Real GfxRendererTarget adapter and actual built-in font metrics.
        seams.pop('FreeInkUIGfxRenderer.h', None)
        seams.pop('fontIds.h', None)
        (directory/'fontIds.h').unlink(missing_ok=True)
        (directory/'FreeInkUIGfxRenderer.h').unlink(missing_ok=True)
        seams['activities/Activity.h'] = (ROOT/'scripts/tests/fixtures/japanese_dialogues_ui_host.h').read_text()
        seams['GfxRenderer.h'] = '#pragma once\n#include "activities/Activity.h"\n'
        seams['UiAppHelpers.h'] = r'''
#pragma once
#include "components/UiAppHost.h"
#include "activities/Activity.h"
#include "components/UIScale.h"
#include "components/UIThemeTokens.h"
inline freeink::ui::GfxRendererTarget makeUiTarget(const GfxRenderer& r){
  freeink::ui::GfxRendererTarget t(r);const auto spec=uiScaleSpec();
  t.setFont(t.FONT_SMALL,spec.smallFontId);t.setFont(t.FONT_BODY,spec.bodyFontId);t.setFont(t.FONT_TITLE,spec.titleFontId);return t;
}
inline void refreshSharedUiThemeTokens(const freeink::ui::GfxRendererTarget&){}
template<typename App> void applySharedUiTheme(App& app,const freeink::ui::GfxRendererTarget& t){
  app.setTheme(uiThemeTokens(t));
}
inline freeink::ui::InputSnapshot touchSnapshotFrom(const MappedInputManager& i,bool=false){return i.touch;}
'''
        # UITheme's production safe area is the entire panel without hints.
        seams['components/UITheme.h'] = seams['components/UITheme.h'].replace(
            'Rect{12,0,r.getScreenWidth()-24,r.getScreenHeight()-12}',
            'Rect{0,0,r.getScreenWidth(),r.getScreenHeight()}')
        seams['components/UITheme.h'] = seams['components/UITheme.h'].replace('r.drawText(1,','r.drawText(UI_12_FONT_ID,').replace('r.getTextWidth(1,','r.getTextWidth(UI_12_FONT_ID,')
        theme=(ROOT/'src/components/themes/BaseTheme.h').read_text()
        metrics=theme[theme.index('struct ThemeMetrics {'):theme.index('\nenum UIIcon')]
        base=theme[theme.index('namespace BaseMetrics {'):theme.index('\nclass BaseTheme {')]
        seams['components/themes/BaseTheme.h'] = '#pragma once\n'+metrics+'\n'+base+'\n'
        seams['components/UITheme.h'] = seams['components/UITheme.h'].replace('ThemeMetrics metrics;', 'ThemeMetrics metrics=BaseMetrics::values;').replace('  ThemeMetrics metrics', '  bool showSelectionCursor()const{return true;}\n  ThemeMetrics metrics')
        for name in ['UIScale.h','UIThemeTokens.h']:
            seams['components/'+name]=(ROOT/'src/components'/name).read_text()
        seams['CrossPointSettings.h']='#pragma once\nstruct CrossPointSettings { int uiTextSize=0; };\ninline CrossPointSettings settings;\n#define SETTINGS settings\n'
        seams['BoardConfig.h']='#pragma once\n#define FREEINK_DEVICE_X4PRO 1\n'
        # HAL permits legacy reads only; ANY legacy/arbitrary write is fatal.
        hal = FAKE_STORAGE.replace('static void allowed(const char* path){assert(std::string(path).rfind("/.crosspoint/japanese-review-v1.bin",0)==0);}',
            'static void allowed(const char* p){const std::string s(p);assert(s.rfind("/.crosspoint/japanese-review-v1.bin",0)==0 || s.rfind("/.crosspoint/japanese-sentences-v2.bin",0)==0 || s.rfind("/.crosspoint/japanese-sentences-v4.bin",0)==0);}\n static void writable(const char* p){const std::string s(p);assert(s=="/.crosspoint/japanese-sentences-v4.bin" || s=="/.crosspoint/japanese-sentences-v4.bin.part" || s=="/.crosspoint/japanese-sentences-v4.bin.bak");}')
        hal = hal.replace('remove(const char* p){allowed(p);','remove(const char* p){writable(p);')
        hal = hal.replace('rename(const char* from,const char* to){allowed(from);allowed(to);','rename(const char* from,const char* to){writable(from);writable(to);')
        hal = hal.replace('openFileForWrite(const char*,const char* p,HalFile& f){allowed(p);','openFileForWrite(const char*,const char* p,HalFile& f){writable(p);')
        hal = hal.replace('bool available=true,', 'bool requireActivityLock=false;bool available=true,').replace('requireLock=false','requireLock=true')
        hal = hal.replace('openFileForWrite(const char*,const char* p,HalFile& f){writable(p);',
            'openFileForWrite(const char*,const char* p,HalFile& f){writable(p);assert(!requireActivityLock || renderDepth>0);')
        seams['HalStorage.h'] = hal + '\ninline FakeFS dialogueStorage;\n#define Storage dialogueStorage\n'
        # Remove any historical trace overlays left in this owned build directory.
        for name in ['JapaneseSentenceProgress.h','JapaneseSentenceProgressStore.h','JapaneseSentencesActivity.h','JapaneseSentences.h']:
            (directory/name).unlink(missing_ok=True)
        arrays=[]
        temporary = os.environ.get('JAPANESE_DIALOGUES_UI_BOOTSTRAP')=='1'
        for locale in ['chinese-traditional','chinese','english']:
            values=dict(re.findall(r'^(STR_\w+): (".*")$', (ROOT/f'lib/I18n/translations/{locale}.yaml').read_text(),re.M))
            for key,label in zip(CATEGORY_KEYS+['STR_JP_DIALOGUES_PICK','STR_JP_DIALOGUES_DETAILS'],TEMP_LABELS):
                if temporary and key not in values:values[key]=json.dumps(label,ensure_ascii=False)
            missing=[k for k in STRINGS if k not in values]
            self.assertFalse(missing,'parent locale integration missing: '+str(missing))
            arrays.append('{'+','.join(json.dumps(json.loads(values[k]),ensure_ascii=False) for k in STRINGS)+'}')
        seams['I18n.h']='#pragma once\nenum class StrId {'+','.join(STRINGS)+'};\nstruct I18n {int language=0; static I18n& getInstance(){static I18n i;return i;} const char* get(StrId id)const{static const char* a[3]['+str(len(STRINGS))+']={'+','.join(arrays)+'};return a[language][int(id)];}};\n#define I18N I18n::getInstance()\n'
        if temporary:
            import importlib.util
            spec=importlib.util.spec_from_file_location('dialogue_generator',ROOT/'scripts/generate_japanese_dialogues.py')
            generator=importlib.util.module_from_spec(spec);spec.loader.exec_module(generator)
            (directory/'JapaneseDialogues.generated.h').write_text(generator.generate(json.loads((ROOT/'data/japanese/sentences-dialogues.json').read_text())))
        else:
            (directory/'JapaneseDialogues.generated.h').unlink(missing_ok=True)
        if temporary:
            fonts=BUILD/'bootstrap-fonts';fonts.mkdir(parents=True,exist_ok=True)
            data=json.loads((ROOT/'data/japanese/sentences-dialogues.json').read_text())
            lines=[c[k] for c in data['cards'] for k in ['a','b']]
            primary=' �'+''.join(l['japanese']+l['kanaReading'] for l in lines)
            notes='0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:./- �：'+''.join(''.join(l.values()) for l in lines)+''.join(''.join(c['grammarNotes']) for c in data['cards'])
            for name,size,chars in [('hanmo_dialogues_20',20,primary),('hanmo_sentence_notes_12',12,notes)]:
                output=fonts/(name+'.h')
                import hashlib
                fingerprint=hashlib.sha256((str(size)+chars).encode()).hexdigest()
                stamp=fonts/(name+'.sha256')
                if not output.exists() or not stamp.exists() or stamp.read_text()!=fingerprint:
                    with output.open('w') as stream:
                        subprocess.run([__import__('os').environ.get('HANMO_FONT_PYTHON', __import__('sys').executable),str(ROOT/'lib/EpdFont/scripts/fontconvert.py'),name,str(size),str(ROOT/'lib/EpdFont/builtinFonts/source/HanMoKana/MarukoGothicCJKjp-Medium.ttf'),'--mono','--characters',chars],stdout=stream,check=True)
                    stamp.write_text(fingerprint)
                seams['builtinFonts/'+name+'.h']='#pragma once\n#include "'+str(output)+'"\n'
        else:
            for name in ['hanmo_dialogues_20','hanmo_sentence_notes_12']:
                (directory/'builtinFonts'/ (name+'.h')).unlink(missing_ok=True)
        for name,content in seams.items():
            p=directory/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
        for name in ['JapaneseReviewStore.h','EpdFontFamily.h']:(directory/name).unlink(missing_ok=True)
        for name,source in [('JapaneseSentencesActivity.cpp',ACTIVITY_SOURCE),('UiAppHost.cpp',ROOT/'src/components/UiAppHost.cpp')]:
            (directory/name).write_bytes(source.read_bytes())
        (directory/'main.cpp').write_text(PREFIX+body)
        command=['c++','-std=c++20','-Wall','-Wextra','-Werror','-Wno-missing-field-initializers','-fsanitize='+os.environ.get('JAPANESE_DIALOGUES_UI_SANITIZERS','undefined'),'-fno-sanitize-recover=all','-DARDUINO_ARCH_ESP32=1',
            '-DJP_UI_FINAL_GLYPH_COVERAGE='+('0' if temporary else '1'),'-I',str(directory),'-I',str(ROOT/'scripts/tests'),'-I',str(ROOT/'src'),'-I',str(ROOT/'src/components'),'-I',str(INCLUDE),'-I',str(FUI),
            '-I',str(ROOT/'lib/hal'),'-I',str(ROOT/'lib/EpdFont'),'-I',str(ROOT/'lib/Utf8'),str(directory/'main.cpp'),str(directory/'JapaneseSentencesActivity.cpp'),
            str(directory/'UiAppHost.cpp'),str(FUI.parent/'src/FreeInkUI.cpp'),str(ROOT/'lib/EpdFont/EpdFont.cpp'),
            str(ROOT/'lib/EpdFont/EpdFontFamily.cpp'),str(ROOT/'lib/Utf8/Utf8.cpp'),'-o',str(directory/'runtime')]
        compiled=subprocess.run(command,text=True,capture_output=True)
        (directory/'compile.log').write_text(' '.join(command)+'\n'+compiled.stdout+compiled.stderr)
        self.assertEqual(compiled.returncode,0,compiled.stderr)
        run=subprocess.run([str(directory/'runtime')],text=True,capture_output=True)
        (directory/'runtime.log').write_text(run.stdout+run.stderr)
        frames=[]
        for line in run.stdout.splitlines():
            parts=line.split('|')
            if parts[0]=='FRAME':
                frame=dict(zip(('language','height','category','position','picker','revealed','details_page','error','ui_text_size'),map(int,parts[1:])))
                frame.update(draws=[],boxes=[]);frames.append(frame)
            elif parts[0]=='DRAW':
                draw=dict(zip(['font','x','y','width','height'],map(int,parts[1:6])));draw['text']='|'.join(parts[6:]);frames[-1]['draws'].append(draw)
            elif parts[0]=='BOX':frames[-1]['boxes'].append(dict(zip(['x','y','width','height'],map(int,parts[1:]))))
        if frames:(directory/'paint-frames.json').write_text(json.dumps(frames,ensure_ascii=False,indent=2))
        self.assertEqual(run.returncode,0,run.stderr)

    def test_entry_is_category_picker_no_writes_back_finishes(self):
        self.run_cpp(r'''
int main(){
 GfxRenderer r;MappedInputManager i;JapaneseSentencesActivity a(r,i);a.onEnter();paint(a);
 assert(has(r,I18N.get(StrId::STR_JP_DIALOGUES_PICK)));
 assert(!has(r,japanese::dialogues::cards[0].a.japanese));
 assert(Storage.writes==0 && Storage.renames==0);
 release(a,i,B::Back);assert(a.finishes==1 && !a.routingReady());
}
''', require_current_content=False)

    def test_all_categories_bounded_navigation_return_resume_hidden(self):
        self.run_cpp(r'''
int main(){
 GfxRenderer r;MappedInputManager i;JapaneseSentencesActivity a(r,i);a.onEnter();
 for(int c=0;c<9;++c){
  a.action(10+c);assert(!a.picker_ && a.lesson_.category()==c && a.lesson_.position()==0);
  for(int n=0;n<expectedCounts[c];++n){
   release(a,i,B::Confirm);assert(a.lesson_.revealed());
   release(a,i,B::Right);assert(a.lesson_.position()==std::min(n+1,expectedCounts[c]-1));
   if(n<expectedCounts[c]-1)assert(!a.lesson_.revealed());
  }
  release(a,i,B::Back);assert(a.picker_ && a.finishes==0 && a.selectedCategory_==c);
 }
 for(int c=0;c<9;++c){
  a.action(10+c);assert(a.lesson_.position()==expectedCounts[c]-1 && !a.lesson_.revealed());
  for(int n=expectedCounts[c]-1;n>0;--n){release(a,i,B::Left);assert(a.lesson_.position()==n-1);}
  release(a,i,B::Left);assert(a.lesson_.position()==0);a.action(0);
 }
 a.action(0);assert(a.finishes==1);
}
''', require_current_content=False)

    def test_failed_save_holds_pending_offline_explicit_retry_single_batch(self):
        self.run_cpp(r'''
int main(){
 GfxRenderer r;MappedInputManager i;JapaneseSentencesActivity a(r,i);a.onEnter();
 Storage.shortWrite=true;a.action(10);a.action(2);
 assert(Storage.writes==1);
 const int failedWrites=Storage.writes;
 for(int c=0;c<9;++c){
  if(!a.picker_){a.action(0);}a.action(10+c);
  for(int n=0;n<expectedCounts[c];++n){if(!a.lesson_.revealed())a.action(2);a.action(3);}
 }
 assert(Storage.writes==failedWrites && a.lesson_.revealed());
 for(int n=0;n<270;++n)assert(japanese::sentenceprogress::isRead(a.pending_,n));
 Storage.shortWrite=false;a.action(4);assert(Storage.writes==failedWrites+1);
 for(int n=0;n<270;++n)assert(japanese::sentenceprogress::isRead(a.pending_,n));
 a.onExit();a.onEnter();assert(a.picker_);a.action(18);
 assert(a.lesson_.position()==29 && !a.lesson_.revealed());
 for(int n=0;n<270;++n)assert(japanese::sentenceprogress::isRead(a.pending_,n));
}
''', require_current_content=False)

    def test_all_270_scenes_510_lines_reveal_pagination_three_locale_geometry(self):
        self.run_cpp(r'''
#include <iostream>
void snapshot(const GfxRenderer& r,const JapaneseSentencesActivity& a){
 std::cout<<"FRAME|"<<I18N.language<<"|"<<r.height<<"|"<<a.lesson_.category()<<"|"<<a.lesson_.position()<<"|"<<a.picker_<<"|"<<a.lesson_.revealed()<<"|"<<a.detailsPage_<<"|"<<a.retryNeeded()<<"|"<<SETTINGS.uiTextSize<<"\n";
 for(const auto& d:r.draws)std::cout<<"DRAW|"<<d.font<<"|"<<d.x<<"|"<<d.y<<"|"<<d.width<<"|"<<d.height<<"|"<<d.text<<"\n";
 for(const auto& b:r.boxes){const auto r=b.rect;std::cout<<"BOX|"<<r.x<<"|"<<r.y<<"|"<<r.width<<"|"<<r.height<<"\n";}
}
void geometry(const GfxRenderer& r){
 for(size_t n=0;n<r.boxes.size();++n){const auto b=r.boxes[n].rect;
  assert(b.width>=44 && b.height>=44 && b.x>=12 && b.right()<=r.width-12);
  assert(b.y>=58 && b.bottom()<=r.height-12);
  for(size_t m=n+1;m<r.boxes.size();++m){const auto c=r.boxes[m].rect;
   assert(b.right()+6<=c.x || c.right()+6<=b.x || b.bottom()+6<=c.y || c.bottom()+6<=b.y);
  }
 }
 for(size_t n=0;n<r.draws.size();++n){const auto& d=r.draws[n];
#if JP_UI_FINAL_GLYPH_COVERAGE
  const auto& font=r.fonts.at(r.resolvedFont(d.font,d.text.c_str()));
  const auto* cpText=reinterpret_cast<const uint8_t*>(d.text.c_str());uint32_t cp;
  while((cp=utf8NextCodepoint(&cpText)))assert(font.hasCodepoint(cp));
#endif
  assert(d.x>=12 && d.x+d.width<=r.width-12 && d.y+d.height<=r.height-12);
  for(size_t m=n+1;m<r.draws.size();++m){const auto& e=r.draws[m];
   assert(d.x+d.width<=e.x || e.x+e.width<=d.x || d.y+d.height<=e.y || e.y+e.height<=d.y);
  }
  for(const auto& box:r.boxes){const auto b=box.rect;
   const bool inside=d.x>=b.x && d.x+d.width<=b.right() && d.y>=b.y && d.y+d.height<=b.bottom();
   assert(inside || d.x+d.width<=b.x || b.right()<=d.x || d.y+d.height<=b.y || b.bottom()<=d.y);
  }
 }
}
std::string primary(const GfxRenderer& r){std::string out;for(const auto& d:r.draws)if(d.font==0x4A540014)out+=d.text;return out;}
std::string notes(const GfxRenderer& r){std::string out;for(const auto& d:r.draws)if(d.font==0x4A53100C && d.text!="A" && d.text!="B")out+=d.text;return out;}
void coverage(const GfxRenderer& r,int font,const char* value){
 const auto* p=reinterpret_cast<const uint8_t*>(value);uint32_t cp;
 while((cp=utf8NextCodepoint(&p)))assert(r.fonts.at(font).hasCodepoint(cp));
}
int main(){
 int scenes=0,utterances=0,frames=0;
 for(int language=0;language<3;++language)for(int height:{800,900})for(int uiSize:{0,1}){
  Storage=FakeFS{};SETTINGS.uiTextSize=uiSize;I18N.language=language;GfxRenderer r;r.height=height;
  MappedInputManager i;JapaneseSentencesActivity a(r,i);a.onEnter();
  for(int c=0;c<9;++c){
   a.action(10+c);
   for(int n=0;n<expectedCounts[c];++n){const auto& card=japanese::dialogues::cards[expectedFirsts[c]+n];
    assert(card.category==c);paint(a);geometry(r);snapshot(r,a);
    const auto header=std::to_string(n+1)+" / 30";
    const auto readProgress=std::string(I18N.get(StrId::STR_JP_SENTENCES_PROGRESS))+" "+std::to_string(n)+" / 30";
    assert(has(r,header.c_str()) && has(r,readProgress.c_str()));
    assert(primary(r)==std::string(card.a.japanese)+card.b.japanese);
    assert(notes(r).empty());assert(!has(r,card.a.romaji) && !has(r,card.a.meaning));
    if(c){assert(has(r,"A") && has(r,"B"));}
    coverage(r,0x4A540014,card.a.japanese);coverage(r,0x4A540014,card.b.japanese);
    a.action(2);std::string expected;
    for(const auto* line:{&card.a,&card.b}){if(!*line->japanese)continue;
     if(std::strcmp(line->kanaReading,line->japanese))expected+=line->kanaReading;
     expected+=line->romaji;expected+=line->meaning;
     for(const char* s:{line->kanaReading,line->romaji,line->meaning})coverage(r,0x4A53100C,s);
    }
    for(const char* s:card.grammarNotes){expected+=s;coverage(r,0x4A53100C,s);}
    std::string got;int page=0;
    do{paint(a);geometry(r);snapshot(r,a);++frames;
     assert(primary(r)==std::string(card.a.japanese)+card.b.japanese);
     got+=notes(r);assert(expected.compare(0,got.size(),got)==0);
     if(got==expected)break;
     a.action(5);++page;
    }while(page<32);
    assert(got==expected && page<32);
    assert(japanese::sentenceprogress::isRead(a.progress_,expectedFirsts[c]+n));
    a.action(2);Storage.available=false;a.action(2);paint(a);assert(a.retryNeeded());
    for(int p=0;p<a.detailsPages_;++p){paint(a);geometry(r);snapshot(r,a);a.action(5);}
    Storage.available=true;a.action(4);assert(!a.retryNeeded());
    a.action(2);paint(a);geometry(r);assert(notes(r).empty());
    ++scenes;utterances+=c?2:1;a.action(3);
   }
   a.action(0);paint(a);geometry(r);snapshot(r,a);
  }
 }
 assert(scenes==3240 && utterances==6120);
 std::cout<<"COVERAGE|"<<scenes<<"|"<<utterances<<"|"<<frames<<"\n";
}
''')

    def test_picker_physical_selection_paging_touch_all_nine_committed_counts(self):
        self.run_cpp(r'''
const Draw& categoryRow(const GfxRenderer& r,const char* label){
 for(const auto& d:r.draws)if(d.text.find(label)!=std::string::npos && d.text.find(" / ")!=std::string::npos)return d;
 assert(false);return r.draws.front();
}
int main(){
 const StrId categories[]={StrId::STR_JP_DIALOGUES_BASIC,StrId::STR_JP_DIALOGUES_DAILY,StrId::STR_JP_DIALOGUES_RESTAURANT,
  StrId::STR_JP_DIALOGUES_SHOPPING,StrId::STR_JP_DIALOGUES_TRANSPORT,StrId::STR_JP_DIALOGUES_HOTEL,
  StrId::STR_JP_DIALOGUES_DIRECTIONS,StrId::STR_JP_DIALOGUES_SOCIAL,StrId::STR_JP_DIALOGUES_EMERGENCY};
 for(int language=0;language<3;++language){Storage=FakeFS{};I18N.language=language;
  GfxRenderer r;MappedInputManager i;JapaneseSentencesActivity a(r,i);a.onEnter();
  for(int c=0;c<9;++c){
   paint(a);const int writes=Storage.writes;
   if(c){release(a,i,B::Down);paint(a);}assert(a.selectedCategory_==c && Storage.writes==writes);
   const auto row=categoryRow(r,I18N.get(categories[c]));assert(row.text.find("0 / 30")!=std::string::npos);
   touch(a,i,row.x+row.width/2,row.y+row.height/2);
   assert(!a.picker_ && a.lesson_.category()==c && !a.lesson_.revealed());
   paint(a);tap(a,i,r,StrId::STR_JP_SENTENCES_REVEAL);assert(a.lesson_.revealed());
   tap(a,i,r,StrId::STR_KANA_NEXT);assert(a.lesson_.position()==1 && !a.lesson_.revealed());
   tap(a,i,r,StrId::STR_BACK);assert(a.picker_ && a.finishes==0);
   paint(a);assert(categoryRow(r,I18N.get(categories[c])).text.find("1 / 30")!=std::string::npos);
   release(a,i,B::Confirm);assert(!a.picker_ && a.lesson_.position()==1 && !a.lesson_.revealed());
   release(a,i,B::Back);
  }
  release(a,i,B::Right);assert(a.selectedCategory_==8);
  for(int c=7;c>=0;--c){release(a,i,B::Up);assert(a.selectedCategory_==c);}
  release(a,i,B::Left);assert(a.selectedCategory_==0);
 }
}
''')

    def test_touch_transition_inherited_releases_stale_table_and_back_priority(self):
        self.run_cpp(r'''
int main(){
 GfxRenderer r;MappedInputManager i;JapaneseSentencesActivity a(r,i);
 i.held[int(B::Confirm)]=true;a.onEnter();paint(a);
 release(a,i,B::Confirm);assert(a.picker_);release(a,i,B::Confirm);assert(!a.picker_ && !a.lesson_.revealed());
 paint(a);auto reveal=find(r,I18N.get(StrId::STR_JP_SENTENCES_REVEAL));
 touch(a,i,reveal.x+reveal.width/2,reveal.y+reveal.height/2);assert(a.lesson_.revealed() && !a.routingReady());
 touch(a,i,reveal.x+reveal.width/2,reveal.y+reveal.height/2);assert(a.lesson_.revealed());
 paint(a);const auto next=find(r,I18N.get(StrId::STR_KANA_NEXT));
 touch(a,i,next.x+next.width/2,next.y+next.height/2);assert(a.lesson_.position()==1 && !a.lesson_.revealed());
 touch(a,i,next.x+next.width/2,next.y+next.height/2);assert(a.lesson_.position()==1);
 paint(a);reveal=find(r,I18N.get(StrId::STR_JP_SENTENCES_REVEAL));
 i.touch.touchReleased=true;i.touch.touchX=reveal.x+reveal.width/2;i.touch.touchY=reveal.y+reveal.height/2;
 i.released[int(B::Back)]=true;a.loop();assert(a.picker_ && !a.lesson_.revealed() && a.finishes==0);i.clear();
 paint(a);auto row=r.draws[1];
 for(const auto& d:r.draws)if(d.text.find("0 / 30")!=std::string::npos){row=d;break;}
 i.held[int(B::Confirm)]=true;i.touch.touchReleased=true;i.touch.touchX=row.x+row.width/2;i.touch.touchY=row.y+row.height/2;
 a.loop();assert(!a.picker_ && !a.lesson_.revealed());
 release(a,i,B::Confirm);assert(!a.lesson_.revealed()); // held gesture crossed picker->lesson by touch
 release(a,i,B::Confirm);assert(a.lesson_.revealed());
 a.onExit();i.clear();i.held[int(B::Down)]=true;a.onEnter();paint(a);
 release(a,i,B::Down);assert(a.selectedCategory_==a.progress_.lastCategory);
 release(a,i,B::Down);assert(a.selectedCategory_==std::min(8,int(a.progress_.lastCategory)+1));
}
''', require_current_content=False)

    def test_physical_details_and_explicit_retry_error_label_committed_count(self):
        self.run_cpp(r'''
int main(){
 GfxRenderer r;MappedInputManager i;JapaneseSentencesActivity a(r,i);a.onEnter();a.action(11);
 a.action(3);a.action(3);a.action(3);paint(a); // daily-04 needs pagination with actual UI_10 metrics
 Storage.shortWrite=true;a.action(2);paint(a);
 assert(a.retryNeeded() && has(r,I18N.get(StrId::STR_JP_REVIEW_SAVE_ERROR)) && has(r,I18N.get(StrId::STR_JP_REVIEW_RETRY)));
 assert(!has(r,I18N.get(StrId::STR_JP_REVIEW_SAVED)) && japanese::sentenceprogress::readCount(a.progress_,1)==0);
 assert(a.detailsPages_>1);release(a,i,B::Down);assert(a.detailsPage_==1);
 const int writes=Storage.writes;Storage.shortWrite=false;release(a,i,B::Up);
 assert(!a.retryNeeded() && Storage.writes==writes+1 && a.lesson_.revealed() && a.detailsPage_==1);
 paint(a);assert(has(r,I18N.get(StrId::STR_JP_REVIEW_SAVED)) && !has(r,I18N.get(StrId::STR_JP_REVIEW_RETRY)));
 release(a,i,B::Up);assert(Storage.writes==writes+1); // no hidden automatic retry
}
''')

    def test_import_45_words_basic_unchanged_no_entry_write_and_v4_isolation(self):
        self.run_cpp(r'''
int main(){
 japanese::review::Progress old;
 for(int n=0;n<45;++n)assert(japanese::review::applyRating(old,japanese::Words::cardIdAt(n),japanese::review::Rating::Known,japanese::review::kMinDay));
 for(int n=0;n<6;++n)assert(japanese::review::recordSentence(old,n,true));
 const auto bytes=japanese::review::encodeProgress(old);const std::vector<uint8_t> original(bytes.begin(),bytes.end());
 Storage.files[japanese::review::kProgressPath]=original;
 Storage.files["/canary.bin"]={7,3,9};Storage.files["/.crosspoint/kana-practice.bin"]={1,8,4};
 GfxRenderer r;MappedInputManager i;JapaneseSentencesActivity a(r,i);a.onEnter();paint(a);
 assert(Storage.writes==0 && Storage.renames==0 && a.pending_.positions[0]==5);
 assert(japanese::sentenceprogress::readCount(a.progress_,0)==6);
 for(int c=1;c<9;++c)assert(japanese::sentenceprogress::readCount(a.progress_,c)==0);
 a.action(11);a.action(2);a.onExit();
 assert(Storage.files[japanese::review::kProgressPath]==original && Storage.files["/canary.bin"]==std::vector<uint8_t>({7,3,9}));
 assert(Storage.files["/.crosspoint/kana-practice.bin"]==std::vector<uint8_t>({1,8,4}));
 Storage.files[japanese::review::kProgressPath]={0}; // v4 ignores later corrupt legacy
 const int writes=Storage.writes;a.onEnter();assert(a.picker_ && Storage.writes==writes);
 assert(japanese::sentenceprogress::readCount(a.progress_,0)==6 && japanese::sentenceprogress::readCount(a.progress_,1)==1);
 a.action(10);assert(a.lesson_.position()==5 && !a.lesson_.revealed());a.onExit();
 // Legacy backup import is read-only too: never call v1 recovery/rename.
 Storage=FakeFS{};Storage.files[japanese::review::kProgressBackup]=original;
 a.onEnter();assert(Storage.renames==0 && Storage.writes==0 && Storage.files[japanese::review::kProgressBackup]==original);
 assert(!Storage.exists(japanese::review::kProgressPath));
}
''', require_current_content=False)

    def test_uncertain_commit_explicit_retry_no_duplicate_revision_or_write(self):
        self.run_cpp(r'''
int main(){using namespace japanese::sentenceprogress;
 Progress old;assert(record(old,0,2,true));auto bytes=encodeProgress(old);Storage.files[kProgressPath]={bytes.begin(),bytes.end()};
 GfxRenderer r;MappedInputManager i;JapaneseSentencesActivity a(r,i);a.onEnter();a.action(10);Storage.reads=0;
 Storage.afterRead=[](FakeFS& fs,const std::string& path){if(path==kProgressPart)fs.failReadAt=fs.reads+2;};
 a.action(2); // already-read reveal is a no-op, move to a new read event
 a.action(3); // uncertain committed position event
 assert(a.retryNeeded() && a.lesson_.position()==3 && !a.lesson_.revealed());
 const int writes=Storage.writes;const auto revision=a.progress_.revision;
 Storage.afterRead={};Storage.failReadAt=0;Progress committed;assert(loadProgress(Storage,committed)==LoadStatus::Loaded);
 assert(committed.revision==revision+1 && committed.positions[0]==3);
 a.action(4);assert(!a.retryNeeded() && Storage.writes==writes && a.progress_.revision==committed.revision);
 assert(a.lesson_.position()==3 && !a.lesson_.revealed());a.action(4);assert(Storage.writes==writes);
}
''', require_current_content=False)

    def test_concurrent_writer_retry_unions_reads_only_dirty_positions_one_revision(self):
        self.run_cpp(r'''
int main(){using namespace japanese::sentenceprogress;
 Progress old;assert(record(old,0,1,true));auto bytes=encodeProgress(old);Storage.files[kProgressPath]={bytes.begin(),bytes.end()};
 GfxRenderer r;MappedInputManager i;JapaneseSentencesActivity a(r,i);a.onEnter();
 auto other=old;assert(record(other,8,4,true));const auto external=encodeProgress(other);
 Storage.afterRead=[&](FakeFS& fs,const std::string& path){if(path==kProgressPart)fs.files[kProgressPath]={external.begin(),external.end()};};
 a.action(11);assert(a.retryNeeded());a.action(3);a.action(2);
 const int writes=Storage.writes;Storage.afterRead={};a.action(4);
 assert(!a.retryNeeded() && Storage.writes==writes+1 && a.lesson_.category()==1 && a.lesson_.position()==1 && a.lesson_.revealed());
 Progress p;assert(loadProgress(Storage,p)==LoadStatus::Loaded);
 assert(p.revision==other.revision+1 && p.positions[8]==4 && p.positions[0]==1 && p.positions[1]==1 && p.lastCategory==1);
 assert(isRead(p,1) && isRead(p,31) && isRead(p,244));
}
''', require_current_content=False)

    def test_real_store_fault_matrix_pending_retry_and_no_automatic_saves(self):
        self.run_cpp(r'''
int main(){using namespace japanese::sentenceprogress;
 for(int fault=0;fault<13;++fault){Storage=FakeFS{};Progress old;assert(record(old,0,2,true));
  const auto bytes=encodeProgress(old);Storage.files[kProgressPath]={bytes.begin(),bytes.end()};
  GfxRenderer r;MappedInputManager i;JapaneseSentencesActivity a(r,i);a.onEnter();a.action(10);
  if(fault==0)Storage.shortWrite=true;
  if(fault==1)Storage.failWriteClose=true;
  if(fault==2)Storage.corruptClose=true;
  if(fault==3)Storage.failReadPath=kProgressPart;
  if(fault==4)Storage.failOpenPath=kProgressPart;
  if(fault==5)Storage.failClosePath=kProgressPart;
  if(fault==6)Storage.dirFail=true;
  if(fault==7)Storage.failRenameAt=1;
  if(fault==8)Storage.failRenameAt=2;
  if(fault==9)Storage.failRenames={2,3};
  if(fault==10){Storage.files[kProgressBackup]={bytes.begin(),bytes.end()};Storage.failRemovePath=kProgressBackup;}
  if(fault==11)Storage.available=false;
  if(fault==12)Storage.failReadPath=kProgressPath;
  a.action(3);assert(a.retryNeeded() && a.lesson_.position()==3 && Storage.handles==0);
  paint(a);assert(has(r,I18N.get(StrId::STR_JP_REVIEW_RETRY)) && !has(r,I18N.get(StrId::STR_JP_REVIEW_SAVED)));
  const int writes=Storage.writes;a.action(2);a.action(3);assert(a.lesson_.position()==4 && !a.lesson_.revealed());
  assert(Storage.writes==writes && isRead(a.pending_,3) && !isRead(a.progress_,3));
  Storage.available=true;Storage.shortWrite=Storage.failWriteClose=Storage.corruptClose=Storage.dirFail=false;
  Storage.failReadPath=Storage.failOpenPath=Storage.failClosePath=Storage.failRemovePath="";
  Storage.failRenameAt=0;Storage.failRenames.clear();
  tap(a,i,r,StrId::STR_JP_REVIEW_RETRY);assert(!a.retryNeeded() && Storage.writes==writes+1 && Storage.handles==0);
  Progress p;assert(loadProgress(Storage,p)==LoadStatus::Loaded && p.positions[0]==4 && isRead(p,2) && isRead(p,3));
  a.onExit();
 }
}
''', require_current_content=False)

    def test_corrupt_future_missing_committed_rollback_and_bit_regression_fail_closed(self):
        self.run_cpp(r'''
int main(){using namespace japanese::sentenceprogress;
 for(int fault=0;fault<6;++fault){Storage=FakeFS{};
  Progress old;assert(record(old,8,5,true));const auto bytes=encodeProgress(old);
  Storage.files[kProgressPath]={bytes.begin(),bytes.end()};
  GfxRenderer r;MappedInputManager i;JapaneseSentencesActivity a(r,i);a.onEnter();a.action(18);
  if(fault==0)Storage.files[kProgressPath][0]^=1;
  if(fault==1){auto future=bytes;future[4]=5;detail::put(future.data()+kProgressBytes-4,detail::checksum(future.data(),kProgressBytes-4),4);Storage.files[kProgressPath]={future.begin(),future.end()};}
  if(fault==2)Storage.files.erase(kProgressPath);
  if(fault==3){auto rollback=encodeProgress(Progress{});Storage.files[kProgressPath]={rollback.begin(),rollback.end()};}
  if(fault==4){auto regress=old;regress.readBits={};++regress.revision;auto b=encodeProgress(regress);Storage.files[kProgressPath]={b.begin(),b.end()};}
  if(fault==5){Storage.files.erase(kProgressPath);japanese::review::Progress legacy;auto b=japanese::review::encodeProgress(legacy);Storage.files[japanese::review::kProgressPath]={b.begin(),b.end()};}
  const auto files=Storage.files;const int writes=Storage.writes;
  a.action(1);a.action(2);assert(a.retryNeeded());a.action(4);
  assert(a.retryNeeded() && Storage.writes==writes && Storage.files==files && isRead(a.pending_,244));
  a.onExit();
 }
 // Initial corrupt/future legacy never authorizes new v4 initialization.
 for(int future=0;future<2;++future){Storage=FakeFS{};japanese::review::Progress legacy;auto b=japanese::review::encodeProgress(legacy);
  b[4]=future?2:0;japanese::review::detail::put(b.data()+b.size()-4,japanese::review::detail::checksum(b.data(),b.size()-4),4);
  Storage.files[japanese::review::kProgressPath]={b.begin(),b.end()};const auto files=Storage.files;
  GfxRenderer r;MappedInputManager i;JapaneseSentencesActivity a(r,i);a.onEnter();a.action(10);a.action(2);a.action(4);
  assert(a.retryNeeded() && Storage.writes==0 && Storage.files==files);
 }
}
''', require_current_content=False)

    def test_orientation_font_ids_ownership_cleanup_and_reader_font_invariant(self):
        self.run_cpp(r'''
#include <builtinFonts/hanmo_dialogues_20.h>
#include <builtinFonts/hanmo_sentence_notes_12.h>
int main(){
 for(auto orientation:{GfxRenderer::Orientation::LandscapeClockwise,GfxRenderer::Orientation::LandscapeCounterClockwise,GfxRenderer::Orientation::PortraitInverted}){
  Storage=FakeFS{};GfxRenderer r;r.orientation=orientation;const auto* reader=r.fonts.at(1).getData();
  MappedInputManager i;JapaneseSentencesActivity a(r,i);a.onEnter();
  assert(r.orientation==GfxRenderer::Orientation::Portrait && r.fonts.count(0x4A540014) && r.fonts.count(0x4A53100C));
  assert(!r.fonts.count(0x0014) && !r.fonts.count(0x100C));
  assert(r.getLineHeight(0x4A540014)==hanmo_dialogues_20.advanceY && r.getLineHeight(0x4A53100C)==hanmo_sentence_notes_12.advanceY);
  a.onExit();assert(r.orientation==orientation && !r.fonts.count(0x4A540014) && !r.fonts.count(0x4A53100C) && r.fonts.at(1).getData()==reader);
  assert(!a.routingReady() && !a.app.touchActive());
 }
 GfxRenderer r;EpdFont primary(&hanmo_dialogues_20),notes(&hanmo_sentence_notes_12);
 r.insertFont(0x4A540014,EpdFontFamily(&primary));r.insertFont(0x4A53100C,EpdFontFamily(&notes));
 MappedInputManager i;JapaneseSentencesActivity a(r,i);a.onEnter();a.onExit();
 assert(r.fonts.count(0x4A540014) && r.fonts.count(0x4A53100C));
}
''', require_current_content=False)

    def test_progress_mutations_share_activity_render_lock(self):
        self.run_cpp(r'''
int main(){
 GfxRenderer r;MappedInputManager i;JapaneseSentencesActivity a(r,i);a.onEnter();Storage.requireActivityLock=true;
 a.action(11);assert(renderDepth==0);a.action(2);assert(renderDepth==0);
 a.action(3);assert(renderDepth==0);a.action(0);a.action(0);assert(a.finishes==1 && renderDepth==0);
}
''', require_current_content=False)

    def test_picker_status_back_fixed_after_storage_failure(self):
        self.run_cpp(r'''
int main(){using namespace japanese::sentenceprogress;
 Progress p;assert(record(p,0,1,true));const auto bytes=encodeProgress(p);Storage.files[kProgressPath]={bytes.begin(),bytes.end()};
 GfxRenderer r;MappedInputManager i;JapaneseSentencesActivity a(r,i);a.onEnter();paint(a);
 const int statusY=find(r,I18N.get(StrId::STR_JP_REVIEW_SAVED)).y;
 const int backY=find(r,I18N.get(StrId::STR_BACK)).y;
 Storage.available=false;a.action(11);a.action(0);paint(a);
 assert(find(r,I18N.get(StrId::STR_JP_REVIEW_STORAGE_ERROR)).y==statusY && find(r,I18N.get(StrId::STR_BACK)).y==backY);
 assert(has(r,I18N.get(StrId::STR_JP_REVIEW_RETRY)) && a.picker_);
}
''', require_current_content=False)

    def test_missing_empty_read_committed_snapshot_never_reinitializes(self):
        self.run_cpp(r'''
int main(){using namespace japanese::sentenceprogress;
 for(int fault=0;fault<2;++fault){Storage=FakeFS{};Progress old;assert(record(old,8,5,false));
  const auto bytes=encodeProgress(old);Storage.files[kProgressPath]={bytes.begin(),bytes.end()};
  GfxRenderer r;MappedInputManager i;JapaneseSentencesActivity a(r,i);a.onEnter();a.action(18);
  assert(a.progress_.revision>0 && readCount(a.progress_,8)==0);
  if(fault==0)Storage.files.erase(kProgressPath);
  else {const auto rollback=encodeProgress(Progress{});Storage.files[kProgressPath]={rollback.begin(),rollback.end()};}
  const int writes=Storage.writes;const auto files=Storage.files;a.action(1);a.action(4);
  assert(a.retryNeeded() && Storage.writes==writes && Storage.files==files && a.lesson_.position()==4);
 }
}
''', require_current_content=False)

if __name__=='__main__':unittest.main()
