"""Host behavior tests: compile and run the actual KeyboardEntryActivity.cpp with fake HAL/UI."""
from pathlib import Path
import subprocess
import os
import shlex
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'src/activities/util/KeyboardEntryActivity.cpp'
FAKE = r'''
#pragma once
#include <algorithm>
#include <atomic>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <string>
#include <utility>
#include <vector>
#include <cstdio>
struct Rect {int x,y,width,height;};
struct GfxRenderer;
enum class EpdFontFamily {REGULAR};
constexpr int UI_12_FONT_ID=12, SMALL_FONT_ID=8;
namespace freeink {namespace ui {
using ActionId=int;constexpr int StateNormal=0;constexpr int InputTouch=1,InputLongPress=2;
constexpr int16_t QWERTY_KEY_SHIFT=-1,QWERTY_KEY_MODE=-2,QWERTY_KEY_LANG=-4,QWERTY_KEY_BACKSPACE=8,QWERTY_KEY_ENTER=13,QWERTY_KEY_SPACE=32;
enum class KeyKind{Normal,Shift,Mode,Delete,Ok,Space,Lang};
enum class KeyboardLayoutId{QwertyEn,AzertyFr,QwertzDe,SpanishEs,CyrillicRu,CyrillicUk,CyrillicBe,CyrillicKk,HebrewIl};
struct KeyboardKey {const char* label=nullptr;const char* output=nullptr;KeyKind kind=KeyKind::Normal;int state=0;int16_t value=0;uint8_t widthUnits=1;bool enabled=true;const char* alt=nullptr;};
struct KeyboardRow {const KeyboardKey* keys=nullptr;uint8_t count=0,insetUnits=0;};
struct KeyboardLayout {const KeyboardRow* rows=nullptr;uint8_t rowCount=0;};
struct Rect{int16_t x,y,width,height;};
struct Insets{int a,b,c,d;};
struct TextStyle {int font=0;};
struct KeyboardProps {const KeyboardLayout* layout=nullptr;int keyAction=0;const char* okLabel=nullptr;const char* shiftLabel=nullptr;const char* modeLabel=nullptr;int inputMask=0,selectedIndex=0,gap=0,bottomHitOverflow=0;TextStyle labelText,altText;Insets padding{};};
struct Event{bool valid=false;int16_t value=0;bool longPress=false;explicit operator bool()const{return valid;}};
template<size_t N>struct InteractionBuffer{struct Hit{int16_t value;int x,y;};std::vector<Hit> values;void beginPublishCycle(){values.clear();}void publish(){}};
struct TouchHoldRouter{uint16_t holdMs=0,overrideHoldMs=0;struct Result{Event event{};bool activeChanged=false;};void reset(){} template<size_t N> Result update(InteractionBuffer<N>& b,bool,int16_t,int16_t,bool tapped,int16_t x,int16_t y,bool,uint32_t){if(!tapped)return {};for(auto& h:b.values)if(h.x==x&&h.y==y)return {{true,h.value,false},false};return {};}};
struct DeviceContext{};struct InputSnapshot{};
struct GfxRendererTarget{static constexpr int FONT_SMALL=8,FONT_BODY=12;explicit GfxRendererTarget(::GfxRenderer&){}void setFont(int,int){}DeviceContext deviceContext(){return {};}};
template<size_t N>struct Frame{InteractionBuffer<N>& buffer;Frame(GfxRendererTarget&,DeviceContext,InputSnapshot,InteractionBuffer<N>& b):buffer(b){}};
inline const KeyboardLayout& builtinKeyboardLayout(KeyboardLayoutId,bool shifted=false,bool symbols=false,bool numberRow=false,bool langKey=false){
 static const KeyboardKey digits[]={{"1","1",KeyKind::Normal,0,'1'},{"2","2",KeyKind::Normal,0,'2'}};
 static const KeyboardKey letters[]={{"a","a",KeyKind::Normal,0,'a'},{"b","b",KeyKind::Normal,0,'b'}};
 static const KeyboardKey lower[]={{"x","x",KeyKind::Normal,0,'x'},{"y","y",KeyKind::Normal,0,'y'}};
 static const KeyboardKey del[]={{"Del",nullptr,KeyKind::Delete,0,QWERTY_KEY_BACKSPACE}};
 static const KeyboardKey bottom[]={{"?123",nullptr,KeyKind::Mode,0,QWERTY_KEY_MODE,2},{"Space",nullptr,KeyKind::Space,0,QWERTY_KEY_SPACE,6},{"OK",nullptr,KeyKind::Ok,0,QWERTY_KEY_ENTER,2}};
 static const KeyboardKey symbolBottom[]={{"ABC",nullptr,KeyKind::Mode,0,QWERTY_KEY_MODE,2},{"Space",nullptr,KeyKind::Space,0,QWERTY_KEY_SPACE,6},{"OK",nullptr,KeyKind::Ok,0,QWERTY_KEY_ENTER,2}};
 static const KeyboardKey bottomLang[]={{"?123",nullptr,KeyKind::Mode,0,QWERTY_KEY_MODE,2},{nullptr,nullptr,KeyKind::Lang,0,QWERTY_KEY_LANG,1},{"Space",nullptr,KeyKind::Space,0,QWERTY_KEY_SPACE,5},{"OK",nullptr,KeyKind::Ok,0,QWERTY_KEY_ENTER,2}};
 static KeyboardRow rows[5];static KeyboardLayout l;rows[0]={digits,2,0};rows[1]={letters,2,0};rows[2]={lower,2,0};rows[3]={del,1,0};rows[4]={symbols?symbolBottom:langKey?bottomLang:bottom,static_cast<uint8_t>(symbols?3:langKey?4:3),0};l={rows,5};(void)shifted;(void)numberRow;return l;
}
inline const char* keyboardOutputFor(const KeyboardLayout& l,int16_t value){if(value==QWERTY_KEY_SPACE)return " ";for(int i=0;i<l.rowCount;i++)for(int k=0;k<l.rows[i].count;k++)if(l.rows[i].keys[k].value==value)return l.rows[i].keys[k].output;return nullptr;}
inline const char* keyboardAltOutputFor(const KeyboardLayout&,int16_t){return nullptr;}
inline int drawnGap=0;inline const KeyboardLayout* lastDrawn=nullptr;inline std::vector<int16_t> drawnKeys;inline std::vector<std::string> drawnLabels;
template<size_t N>void keyboard(Frame<N>& f,Rect rect,const KeyboardProps& p){lastDrawn=p.layout;drawnGap=p.gap;drawnKeys.clear();drawnLabels.clear();for(int i=0;i<p.layout->rowCount;i++)for(int j=0;j<p.layout->rows[i].count;j++){auto& k=p.layout->rows[i].keys[j];drawnKeys.push_back(k.value);drawnLabels.push_back(k.kind==KeyKind::Ok&&p.okLabel?p.okLabel:k.label?k.label:"");f.buffer.values.push_back({k.value,rect.x+10+j*35,rect.y+10+i*48});}}
}}
struct GfxRenderer{
 int width=480,height=800;mutable size_t measureBytes=0;struct Draw{int y;std::string s;};std::vector<Draw> draws;std::vector<int> cursorYs;int clipTop=-1,clipBottom=10000;
 int getScreenWidth()const{return width;}int getScreenHeight()const{return height;}
 int getLineHeight(int)const{return 16;}int getTextWidth(int,const char*s)const{return int(strlen(s))*8;}
 int getTextAdvanceX(int,const char*s,EpdFontFamily)const{const size_t n=strlen(s);measureBytes+=n;return int(n)*8;}
 void clearScreen(){draws.clear();cursorYs.clear();}void displayBuffer(){}
 void drawText(int,int,int y,const char*s,bool=true){if(y>=clipTop && y<clipBottom)draws.push_back({y,s});}
 void drawCenteredText(int,int y,const char*s,bool=true){drawText(0,0,y,s);}
 void fillRect(int,int y,int,int,bool=true){if(y>=clipTop && y<clipBottom)cursorYs.push_back(y);}
 void drawLine(int,int y,int,int,int,bool=true){if(y>=clipTop && y<clipBottom)cursorYs.push_back(y);}
 void setClipRect(int,int y,int,int h)const{const_cast<GfxRenderer*>(this)->clipTop=y;const_cast<GfxRenderer*>(this)->clipBottom=y+h;}
 void clearClipRect()const{const_cast<GfxRenderer*>(this)->clipTop=-1;const_cast<GfxRenderer*>(this)->clipBottom=10000;}
 struct ClipScope{const GfxRenderer& r;ClipScope(const GfxRenderer& r,int x,int y,int w,int h):r(r){r.setClipRect(x,y,w,h);}~ClipScope(){r.clearClipRect();}};
};
struct Metrics{int topPadding=0,headerHeight=40,verticalSpacing=6,keyboardVerticalOffset=0,sideButtonHintsWidth=0,keyboardTextFieldWidthPercent=90,keyboardKeySpacing=0,keyboardKeyHeight=48,keyboardWidthPercent=90,buttonHintsHeight=28;bool keyboardCenteredText=false;};
struct UITheme{Metrics m;static UITheme& getInstance(){static UITheme obj;return obj;}const Metrics& getMetrics()const{return m;}void drawHeader(GfxRenderer&,Rect,const char*){}void drawTextField(GfxRenderer& r,Rect box,int,bool,int,int){r.drawLine(0,box.y+box.height+22,0,0,1,true);}void drawButtonHints(GfxRenderer&,const char*,const char*,const char*,const char*){}void drawSideButtonHints(GfxRenderer&,const char*,const char*){}};
#define GUI UITheme::getInstance()
struct MappedInputManager{enum class Button{Up,Down,Left,Right,Confirm,Back};bool touch=false,tap=false,down=false,contact=false;int x=0,y=0;bool releaseConfirm=false,pressConfirm=false,pressBack=false,releaseLeft=false,releaseRight=false;unsigned heldTime=0;
 bool wasScreenTapped(int& a,int& b){a=x;b=y;return tap;}bool wasScreenTouchDown(int&a,int&b){a=x;b=y;return down;}bool isScreenTouchHeld(int&a,int&b){a=x;b=y;return contact;}
 bool wasPressed(Button b){return b==Button::Confirm&&pressConfirm;}
 bool wasReleased(Button b){return b==Button::Confirm?releaseConfirm:b==Button::Back?pressBack:b==Button::Left?releaseLeft:b==Button::Right?releaseRight:false;}
 bool isPressed(Button){return false;}unsigned getHeldTime(){return heldTime;}bool hasTouch(){return touch;}
 struct Labels{const char* btn1="",*btn2="",*btn3="",*btn4="";};Labels mapLabels(const char*,const char*,const char*,const char*){return {};}
};
struct ButtonNavigator{template<class Fn>void onPressAndContinuous(std::initializer_list<MappedInputManager::Button>,Fn) {}};
struct FakeGpio{bool deviceIsX3()const{return false;}};
struct RenderLock{};
struct KeyboardResult{std::string text;};struct ActivityResult{bool isCancelled=false;};
struct Activity {GfxRenderer& renderer;MappedInputManager& mappedInput;FakeGpio gpio;std::string result;bool completed=false,cancelled=false,updated=false;Activity(const char*,GfxRenderer& r,MappedInputManager& i):renderer(r),mappedInput(i){}virtual ~Activity()=default;virtual void onEnter(){}virtual void onExit(){}virtual void loop(){}virtual void render(RenderLock&&){}void requestUpdate(){updated=true;}void setResult(KeyboardResult r){result=std::move(r.text);}void setResult(ActivityResult r){cancelled=r.isCancelled;}void finish(){completed=true;}};
inline unsigned long millis(){return 1;}
namespace BidiUtils {inline int detectParagraphLevel(const char*,int,int){return 0;}}
namespace keyboard_layouts{inline uint16_t enabled(){return 1;}inline freeink::ui::KeyboardLayoutId startingLayout(){return freeink::ui::KeyboardLayoutId::QwertyEn;}inline freeink::ui::KeyboardLayoutId next(freeink::ui::KeyboardLayoutId v){return v;}}
enum StrId{STR_SAVE,STR_OK_BUTTON,STR_AIRNOTE_NEW_LINE,STR_KEY_SHIFT,STR_KEY_MODE_ABC,STR_KEY_MODE_SYMBOLS,STR_BACK,STR_SELECT,STR_DIR_LEFT,STR_DIR_RIGHT,STR_KB_HINT_TOGGLE_HIDE_PASSWORD,STR_KB_HINT_TOGGLE_SHOW_PASSWORD,STR_KB_HINT_RETURN_CURSOR,STR_KB_HINT_MOVE_CURSOR,STR_KB_HINT_HIDE_PASSWORD,STR_KB_HINT_SHOW_PASSWORD,STR_KB_HINT_EDIT_ENTRY,STR_KB_TIPS,STR_KB_HINT_RETURN_KEYBOARD,STR_KB_HINT_EXIT_URL_MODE,STR_KB_HINT_CLEAR_TEXT,STR_KB_HINT_SECONDARY_CHAR,STR_KB_HINT_UPPER_SECONDARY,STR_KB_HINT_LOWER_SECONDARY,STR_KB_HINT_URL_SNIPPETS};
inline const char* translate(StrId id){if(id==STR_SAVE)return "Save";if(id==STR_AIRNOTE_NEW_LINE)return "New line";return "OK";}
#define tr(id) translate(StrId::id)
'''
TEST = r'''
#include "fake.h"
#define private public
#include "KeyboardEntryActivity.h"
#undef private
#include "KeyboardEntryActivity.cpp"
using namespace freeink::ui;
void key(KeyboardEntryActivity& a,int16_t v){
 assert(a.syncSelectionToValue(v));
 assert(a.selectedKey() && a.selectedKey()->value==v);
 a.mappedInput.pressConfirm=true;a.loop();a.mappedInput.pressConfirm=false;
 a.mappedInput.releaseConfirm=true;a.loop();a.mappedInput.releaseConfirm=false;
}
void tap(KeyboardEntryActivity& a,int16_t v){
 a.render(RenderLock{});
 auto it=std::find_if(a.interactions.values.begin(),a.interactions.values.end(),[&](auto h){return h.value==v;});
 assert(it!=a.interactions.values.end());
 a.mappedInput.touch=true;a.mappedInput.tap=true;
 a.mappedInput.x=it->x;a.mappedInput.y=it->y;
 a.loop();a.mappedInput.tap=false;
}
int16_t saveKey(KeyboardEntryActivity& a){
 auto& layout=a.currentLayout();
 for(int row=0;row<layout.rowCount;row++)
  for(int col=0;col<layout.rows[row].count;col++)
   if(layout.rows[row].keys[col].kind==KeyKind::Ok)return layout.rows[row].keys[col].value;
 assert(false);return 0;
}
void test_keys_and_save(){
 GfxRenderer r;MappedInputManager i;KeyboardEntryActivity a(r,i,"Note","",16384,InputType::Multiline);a.onEnter();
 for(bool symbol:{false,true})for(bool shift:{false,true}){
  a.symbols=symbol;a.shifted=shift;a.render(RenderLock{});
  assert(drawnGap>=6);
  assert(std::count(drawnKeys.begin(),drawnKeys.end(),QWERTY_KEY_ENTER)==1);
  assert(std::find(drawnLabels.begin(),drawnLabels.end(),"New line")!=drawnLabels.end());
  assert(std::find(drawnLabels.begin(),drawnLabels.end(),"Save")!=drawnLabels.end());
 }
 a.symbols=false;a.shifted=false;
 key(a,'a');key(a,QWERTY_KEY_ENTER);assert(a.text=="a\n"&&!a.completed);
 const auto save=saveKey(a);assert(save!=QWERTY_KEY_ENTER);
 key(a,save);assert(a.completed && a.result=="a\n");
}
void test_bottom_mode_label_tracks_layer(){
 GfxRenderer r;MappedInputManager i;KeyboardEntryActivity a(r,i,"Note","",16384,InputType::Multiline);a.onEnter();
 auto modeLabel=[&](){const auto& layout=a.currentLayout();return std::string(layout.rows[layout.rowCount-1].keys[0].label);};
 a.symbols=false;assert(modeLabel()=="?123");
 a.symbols=true;assert(modeLabel()=="ABC");
 a.symbols=false;assert(modeLabel()=="?123");
}
void test_touch_matches_buttons(){
 GfxRenderer r;MappedInputManager i;KeyboardEntryActivity a(r,i,"Note","a",16384,InputType::Multiline);a.onEnter();
 const auto save=saveKey(a);
 tap(a,QWERTY_KEY_ENTER);assert(a.text=="a\n"&&!a.completed);
 tap(a,save);assert(a.completed&&a.result=="a\n");
}
void test_legacy_modes_untouched(){
 assert(builtinKeyboardLayout(KeyboardLayoutId::QwertyEn).rows[4].count==3);
 for(auto type:{InputType::Text,InputType::Password,InputType::Url}){
  GfxRenderer r;MappedInputManager i;KeyboardEntryActivity a(r,i,"Old","x",10,type);a.onEnter();a.render(RenderLock{});
  assert(std::find(drawnLabels.begin(),drawnLabels.end(),"Save")==drawnLabels.end());
  key(a,QWERTY_KEY_ENTER);assert(a.completed&&a.result=="x");
 }
}
void test_utf8_editing(){
 GfxRenderer r;MappedInputManager i;
 KeyboardEntryActivity a(r,i,"Note",std::string("A\xe4\xb8\xad\n")+"Z",16384,InputType::Multiline);a.onEnter();
 a.cursorMode=true;a.cursorPos=4;
 i.releaseLeft=true;a.loop();i.releaseLeft=false;assert(a.cursorPos==1);
 i.releaseRight=true;a.loop();i.releaseRight=false;assert(a.cursorPos==4);
 a.cursorMode=false;key(a,QWERTY_KEY_BACKSPACE);assert(a.text=="A\nZ"&&a.cursorPos==1);
 key(a,QWERTY_KEY_BACKSPACE);assert(a.text=="\nZ"&&a.cursorPos==0);
 key(a,QWERTY_KEY_ENTER);assert(a.text=="\n\nZ"&&!a.completed);
 GfxRenderer r2;MappedInputManager i2;KeyboardEntryActivity b(r2,i2,"Note","",16384,InputType::Multiline);b.onEnter();
 b.insertUtf8("中");assert(b.utf8Next(b.text,0)==3);assert(b.utf8Prev(b.text,3)==0);
}
void test_viewport_and_hard_breaks(){
 GfxRenderer r;MappedInputManager i;std::string longText;
 for(int j=0;j<420;j++)longText+="line"+std::to_string(j)+" abcdefghijklmnopqrstuvwxyz\n";
 KeyboardEntryActivity a(r,i,"Note",longText,16384,InputType::Multiline);a.onEnter();a.render(RenderLock{});
 assert(!r.draws.empty() && r.draws.size()<35);
 assert(std::any_of(r.draws.begin(),r.draws.end(),[](auto& d){return d.s.find("line419")!=std::string::npos;}));
 assert(std::none_of(r.draws.begin(),r.draws.end(),[](auto& d){return d.s.find("line0 ")!=std::string::npos;}));
 assert(!r.cursorYs.empty());for(auto y:r.cursorYs)assert(y<a.keyboardRect().y);
 size_t pos=0;bool toggle=false;
 assert(a.cursorPositionFromPoint(70,r.draws.back().y,pos,toggle));assert(pos>longText.size()/2);
 a.cursorPos=0;a.render(RenderLock{});
 assert(std::any_of(r.draws.begin(),r.draws.end(),[](auto& d){return d.s.find("line0")!=std::string::npos;}));
 GfxRenderer r2;MappedInputManager i2;
 KeyboardEntryActivity b(r2,i2,"Note",std::string("甲\n\n")+"乙\n",16384,InputType::Multiline);b.onEnter();b.render(RenderLock{});
 assert(r2.draws.size()==4);
 assert(r2.draws[0].s=="甲"&&r2.draws[1].s.empty()&&r2.draws[2].s=="乙"&&r2.draws[3].s.empty());
 size_t at=99;bool password=false;
 assert(b.cursorPositionFromPoint(24,r2.draws[1].y,at,password));assert(at==4);
 b.cursorPos=at;key(b,QWERTY_KEY_BACKSPACE);assert(b.text=="甲\n乙\n");
}
void test_16k_limit_and_render_cost(){
 GfxRenderer r;MappedInputManager i;KeyboardEntryActivity a(r,i,"Note",std::string(16384,'q'),16384,InputType::Multiline);a.onEnter();
 const auto save=saveKey(a);
 key(a,QWERTY_KEY_ENTER);assert(a.text.size()==16384&&!a.completed);
 a.render(RenderLock{});assert(r.measureBytes<1000000);
 key(a,save);assert(a.completed&&a.result.size()==16384);
}
int main(int argc,char** argv){
 assert(argc==2);
 const std::string name=argv[1];
 if(name=="keys")test_keys_and_save();
 else if(name=="mode_label")test_bottom_mode_label_tracks_layer();
 else if(name=="touch")test_touch_matches_buttons();
 else if(name=="legacy")test_legacy_modes_untouched();
 else if(name=="utf8")test_utf8_editing();
 else if(name=="viewport")test_viewport_and_hard_breaks();
 else if(name=="limit")test_16k_limit_and_render_cost();
 else assert(false);
}
'''

class KeyboardHostTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._temp = tempfile.TemporaryDirectory()
        d = Path(cls._temp.name)
        (d/'fake.h').write_text(FAKE)
        for name in ['FreeInkUI.h','FreeInkUIGfxRenderer.h','GfxRenderer.h','BidiUtils.h','HalGPIO.h','I18n.h','KeyboardLayoutSet.h','MappedInputManager.h','components/UITheme.h','fontIds.h','activities/Activity.h','util/ButtonNavigator.h']:
            f=d/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text('#include "fake.h"\n')
        (d/'main.cpp').write_text(TEST)
        cls.binary=d/'run'
        build=subprocess.run(['g++','-std=c++17','-O0','-Wall','-Wextra',
                              *shlex.split(os.environ.get('AIRNOTE_CXXFLAGS','')),
                              '-I',str(d),'-I',str(SRC.parent),str(d/'main.cpp'),'-o',str(cls.binary)],
                             capture_output=True,text=True)
        if build.returncode:
            cls._temp.cleanup()
            raise AssertionError(build.stderr)

    @classmethod
    def tearDownClass(cls):
        cls._temp.cleanup()

    def _run_case(self,name):
        run=subprocess.run([str(self.binary),name],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)

    def test_newline_and_explicit_save_on_every_layer(self):
        self._run_case('keys')

    def test_bottom_mode_label_matches_letter_or_symbols_layer(self):
        self._run_case('mode_label')

    def test_touch_and_physical_button_actions_agree(self):
        self._run_case('touch')

    def test_text_password_url_remain_submit_on_enter(self):
        self._run_case('legacy')

    def test_utf8_cursor_backspace_and_insert(self):
        self._run_case('utf8')

    def test_long_viewport_cursor_and_hard_break_hit_testing(self):
        self._run_case('viewport')

    def test_16k_byte_limit_and_bounded_render_cost(self):
        self._run_case('limit')

    def test_translation_and_all_six_builtin_font_sizes(self):
        import re
        expected={'english':'New line','chinese':'换行','chinese-traditional':'換行'}
        labels=[]
        for lang,label in expected.items():
            data=(ROOT/'lib/I18n/translations'/f'{lang}.yaml').read_text()
            found=re.findall(r'^STR_AIRNOTE_NEW_LINE: "(.*)"$',data,re.M)
            self.assertEqual(found,[label]);labels.append(label)
            self.assertRegex(data,r'(?m)^STR_SAVE: ".+"$')
        fonts=ROOT/'lib/EpdFont/builtinFonts'
        for size in (8,10,12,14,16,18):
            data=(fonts/f'notosans_cjk_{size}.h').read_text()
            if 'notosans_cjk_common_intervals.h' in data:
                data=(fonts/'notosans_cjk_common_intervals.h').read_text()
            ranges=[(int(a,16),int(b,16)) for a,b in re.findall(r'\{\s*0x([0-9A-Fa-f]+)\s*,\s*0x([0-9A-Fa-f]+)\s*,\s*0x[0-9A-Fa-f]+\s*\}',data)]
            self.assertTrue(ranges)
            for char in set(''.join(labels[1:])+'保存儲存'):
                self.assertTrue(any(lo<=ord(char)<=hi for lo,hi in ranges),(size,char))

if __name__=='__main__':unittest.main()
