from pathlib import Path
import importlib.util, json, re, subprocess, tempfile

here=Path(__file__).resolve().parent
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('generator',root/'scripts/gen_i18n.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
keys=re.findall(r'^\s+(STR_\w+),', (root/'lib/I18n/I18nKeys.h').read_text(),re.M)
en=mod.parse_yaml_file(str(root/'lib/I18n/translations/english.yaml'))
assert keys
checks=[]
for locale,language in [('english','EN'),('chinese','ZH_CN'),('chinese-traditional','ZH_TW')]:
    data=mod.parse_yaml_file(str(root/f'lib/I18n/translations/{locale}.yaml'))
    for key in keys:
        value=json.dumps(data.get(key,en[key]),ensure_ascii=True)
        checks.append(f'assert(std::string(I18N.get(StrId::{key},Language::{language})) == {value});')
zh=mod.parse_yaml_file(str(root/'lib/I18n/translations/chinese-traditional.yaml'))
intervals=(root/'lib/EpdFont/builtinFonts/notosans_cjk_common_intervals.h').read_text()
ranges=[(int(a,16),int(b,16)) for a,b in re.findall(r'\{\s*0x([0-9A-Fa-f]+),\s*0x([0-9A-Fa-f]+),',intervals)]
text=''.join(v for k,v in zh.items() if k.startswith('STR_JP_') or k.startswith('STR_CHANGE_JP_'))
missing=sorted({c for c in text if not c.isspace() and not any(a<=ord(c)<=b for a,b in ranges)})
assert not missing, ('Missing built-in glyphs',missing)

stub=r'''
#pragma once
#include <array>
#include <cstdint>
#include <I18n.h>
struct GfxRenderer { int getScreenWidth() const{return 480;} int getScreenHeight() const{return 800;} };
struct MappedInputManager {};
struct Rect { int x,y,width,height; };
namespace freeink::ui {
struct Text { int maxLines=1; };
struct ListItem { const char* label=nullptr; const char* subtitle=nullptr; int16_t actionValue=0; };
struct Insets { int16_t top,right,bottom,left; };
struct ListProps { ListItem* items=nullptr; uint16_t count=0; int action=0,inputMask=0; Text labelText; };
constexpr int InputTouch=1;
}
struct UiScreen { struct Theme{freeink::ui::Text smallText;}; Theme t; Theme& theme(){return t;}
 void setContentMarginFromScreen(freeink::ui::Insets){} void list(freeink::ui::ListProps){} };
struct ActivityResult {};
struct ThemeMetrics {};
struct UITheme { static UITheme& getInstance(){static UITheme t;return t;} ThemeMetrics m;
 const ThemeMetrics& getMetrics(){return m;} Rect getScreenSafeArea(GfxRenderer&,bool,bool){return {0,0,480,800};}
 void drawPopup(GfxRenderer&,const char*){++errors;} int errors=0; };
#define GUI UITheme::getInstance()
struct UiListActivity {
 struct App{void clearTapFlash(){}} app;
 struct Manager{int exits=0;void goToApps(){++exits;}} activityManager;
 GfxRenderer& renderer; bool finished=false, failAllocation=false; int opened=-1,updates=0;
 UiListActivity(const char*,GfxRenderer& r,MappedInputManager&):renderer(r){}
 virtual ~UiListActivity()=default; virtual void onEnter(){}
 virtual int listCount() const=0; virtual const char* headerTitle() const=0;
 virtual void buildScreen(UiScreen&)=0; virtual void activateIndex(int)=0; virtual void onBackButton()=0;
 void requestUpdate(){++updates;} void finish(){finished=true;}
 template<typename T,typename F> bool startActivityForResultWith(F,int category=100){if(failAllocation)return false; opened=category;return true;}
 void syncListViewport(UiScreen&,freeink::ui::ListProps&,bool){}
 static constexpr int ACTION_ROW=1;
};
'''
with tempfile.TemporaryDirectory(prefix='jp-check-') as folder:
    p=Path(folder)
    for rel in ['activities/UiListActivity.h','components/UITheme.h','components/SubpageLayout.h']:
        (p/rel).parent.mkdir(parents=True,exist_ok=True)
    (p/'activities/UiListActivity.h').write_text(stub)
    (p/'components/UITheme.h').write_text('#pragma once\n#include "activities/UiListActivity.h"\n')
    (p/'components/SubpageLayout.h').write_text('#pragma once\n#include "activities/UiListActivity.h"\nnamespace SubpageLayout { inline Rect contentRect(Rect r,const ThemeMetrics&){return r;} }\n')
    cpp=r'''
#include <cassert>
#include <string>
#include <array>
#include "activities/UiListActivity.h"
#define private public
#include "activities/apps/japanese/JapaneseLearningActivity.h"
#undef private
'''+(root/'src/activities/apps/japanese/JapaneseLearningActivity.cpp').read_text().replace('#include \"JapaneseLearningActivity.h\"','').replace('#include \"KanaActivity.h\"','class KanaGroupsActivity {};')+r'''
int main(){
I18N.setLanguage(Language::EN);
'''+ '\n'.join(checks) +r'''
assert(I18N.getLanguage()==Language::EN);
assert(std::string(I18N.get(static_cast<StrId>(65535)))=="???");
GfxRenderer renderer; MappedInputManager input;
JapaneseLearningActivity folder(renderer,input); folder.onEnter();
assert(folder.listCount()==8);
assert(std::string(folder.headerTitle())=="日文學習");
const char* expected[]={"五十音卡片","筆順教學","翻卡測驗","容易混淆的字","單字卡","短句閱讀","每日複習"};
for(int i=0;i<7;++i){
 assert(std::string(folder.rows_[i+1].label)==expected[i]);
 folder.activateIndex(i+1); assert(folder.opened==(i==0?100:i));
 JapaneseLearningActivity child(renderer,input,i); child.onEnter();
 assert(child.listCount()==3); assert(std::string(child.headerTitle())==expected[i]);
 assert(std::string(child.rows_[2].label)=="教材準備中，尚未開放練習。");
 child.activateIndex(1); assert(!child.finished && child.opened==-1);
 child.activateIndex(2); assert(!child.finished && child.opened==-1);
 child.activateIndex(0); assert(child.finished && child.activityManager.exits==0);
}
folder.opened=-1; folder.activateIndex(-1); folder.activateIndex(8); assert(folder.opened==-1);
folder.failAllocation=true; folder.activateIndex(1); assert(folder.opened==-1 && GUI.errors==1);
folder.activateIndex(0); assert(folder.activityManager.exits==1 && !folder.finished);
JapaneseLearningActivity bad(renderer,input,999); bad.onEnter(); assert(bad.listCount()==8);
JapaneseLearningActivity back(renderer,input,2); back.onBackButton(); assert(back.finished);
assert(I18N.getLanguage()==Language::EN);
}
'''
    (p/'test.cpp').write_text(cpp,encoding='utf-8')
    exe=p/'test'
    cmd=['g++','-std=c++20','-DENABLE_CHINESE_VERSION','-I',str(p),'-I',str(root/'src'),'-I',str(root/'lib/I18n'),str(p/'test.cpp'),str(root/'lib/I18n/I18n.cpp'),str(root/'lib/I18n/I18nStrings.cpp'),'-o',str(exe)]
    subprocess.run(cmd,check=True)
    subprocess.run([str(exe)],check=True)
report={'result':'passed','translation_roundtrips':len(checks),'native_categories':7,'covered':['folder/child titles','touch Back row','logical Back handler','invalid row/category bounds','allocation failure stays in folder','pending lessons noninteractive','explicit Traditional Chinese without global language mutation','all generated strings unchanged after English dedup','new Chinese glyph interval coverage'],'limits':['UI host harness; no hardware input/rendering','Glyph interval presence only; actual on-device glyph appearance needs review']}
(here/'behavior-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
