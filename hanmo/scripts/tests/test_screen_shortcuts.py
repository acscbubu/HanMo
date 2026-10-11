"""Compile production shortcut geometry, dispatch and UI callbacks with host seams."""
from pathlib import Path
import re, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[2]
def function(s,key):
 a=s.index(key); b=s.index('{',a); n=1; e=b+1
 while n: n+=(s[e]=='{')-(s[e]=='}'); e+=1
 return s[a:e]
class ShortcutTest(unittest.TestCase):
 def test_geometry_dispatch_and_failed_save(self):
  settings=(ROOT/'src/CrossPointSettings.h').read_text()
  fields='\n'.join(re.findall(r'  uint8_t (?:cornerTap\w+|quickPanel\d+) = [^;]+;',settings))
  enum=re.search(r'  enum CORNER_TAP_ACTION \{.*?\n  \};',settings,re.S).group()
  bindings=(ROOT/'src/ShortcutBindings.h').read_text().split('namespace ShortcutBindings',1)[1]
  page=(ROOT/'src/activities/settings/ShortcutSettingsActivity.cpp').read_text()
  ids=sorted(set(re.findall(r'StrId::(STR_\w+)',bindings+page)))
  pre='''#include "src/ScreenShortcutPolicy.h"
#include <cassert>
#include <functional>
#include <utility>
#include <initializer_list>
struct CrossPointSettings {
 enum {TOUCH_READER_OFF=0,TOUCH_READER_ON=1};
FIELDS
ENUM
 uint8_t screenInverted=0,orientation=0,touchReaderControls=3;
 bool saved=true;int saves=0;bool saveToFile(){++saves;return saved;}
} SETTINGS;
enum class StrId {IDS};
namespace ShortcutBindings BINDINGS
struct GfxRenderer{int w=480,h=800,refreshes=0;int getScreenWidth()const{return w;}int getScreenHeight()const{return h;}void promoteNextRefresh(int){++refreshes;}};
struct HalDisplay{enum{FULL_REFRESH};};
struct Light{bool available=true;bool present(){return available;}} Frontlight;
struct Manager{int notes=0,settings=0,apps=0;void goToAirNote(){++notes;}void goToSettings(){++settings;}
 void goToJapaneseLearning(){++apps;}void goToApps(){++apps;}void goToAirPhoto(){++apps;}
 void goToCalculator(){++apps;}void goToFileTransfer(){++apps;}void goToBrowser(){++apps;}
 void goToShelfGames(){++apps;}void goToStandby(){++apps;}}activityManager;
struct FrontlightPanelActivity{static constexpr int kTileCount=6;GfxRenderer renderer;uint8_t touchModeRestore=1;bool cleanRefreshPending=false;int updates=0,closes=0,lights=0;void requestUpdate(){++updates;}void close(){++closes;}void toggleLight(){++lights;}void runTile(int);};
struct ActivityResult{};
struct Popup{std::function<void(int)> cb;int chosen=-1;void show(StrId,const StrId*,int,int,std::function<void(int)> f){cb=f;}bool handleInput(int,std::function<void()>){if(chosen<0)return false;int v=chosen;chosen=-1;cb(v);return true;}};
struct ShortcutSettingsActivity{int page_=0,mappedInput=0,notices=0;bool saveFailed_=false;Popup popup_;struct App{void clearTapFlash(){}}app;int listCount(){return page_<0?2:6;}void notice(StrId){++notices;}void requestUpdate(){}void refreshRows(){}template<class T,class F>bool startActivityForResultWith(F,int){return true;}void activateIndex(int);bool handleCustomInput();};
'''.replace('FIELDS',fields).replace('ENUM',enum).replace('IDS',','.join(ids)).replace('BINDINGS',bindings)
  sources=[('src/activities/reader/ReaderUtils.h','inline uint8_t cornerTapAction'),('src/activities/util/FrontlightPanelActivity.cpp','void FrontlightPanelActivity::runTile'),('src/activities/settings/ShortcutSettingsActivity.cpp','void ShortcutSettingsActivity::activateIndex'),('src/activities/settings/ShortcutSettingsActivity.cpp','bool ShortcutSettingsActivity::handleCustomInput')]
  code=pre+'\n'.join(function((ROOT/p).read_text(),k) for p,k in sources)+r'''
int main(){
 for(auto d:{std::pair{480,800},{800,480},{552,768},{793,529}}){
  GfxRenderer r{d.first,d.second};int w=r.w/6,h=r.h/6;
  for(int x=-1;x<=r.w;++x)for(int y=-1;y<=r.h;++y){
   int s=ScreenShortcutPolicy::tapSlot(r.w,r.h,x,y);assert(s>=-1&&s<6);
   if(x<0||y<0||x>=r.w||y>=r.h){assert(s==-1);continue;}
   if(x>=w&&x<r.w-w)assert(s==-1);
   if(x<w&&y<h)assert(s==0);if(x<w&&y>=r.h-h)assert(s==2);
   if(x>=r.w-w&&y<h)assert(s==3);if(x>=r.w-w&&y>=r.h-h)assert(s==5);
   if(s>=0&&s%3==1)assert(y>h+6&&y<r.h-h-6);
  }
  SETTINGS.cornerTapMiddleLeft=2;SETTINGS.cornerTapMiddleRight=1;
  assert(cornerTapAction(r,0,r.h/2)==2);assert(cornerTapAction(r,r.w-1,r.h/2)==1);
  assert(cornerTapAction(r,r.w/2,r.h/2)==0);assert(cornerTapAction(r,0,h+6)==0);
 }
 SETTINGS=CrossPointSettings{};
 assert(SETTINGS.cornerTapMiddleLeft==0&&SETTINGS.cornerTapMiddleRight==0);
 for(int slot=0;slot<6;++slot){
  SETTINGS=CrossPointSettings{};assert(SETTINGS.*ShortcutBindings::panel[slot]==ScreenShortcutPolicy::DEFAULTS[slot]);
  for(int action=0;action<8;++action){
   SETTINGS=CrossPointSettings{};SETTINGS.*ShortcutBindings::panel[slot]=action;FrontlightPanelActivity p;p.runTile(slot);
   assert(p.closes==(action==1)&&p.renderer.refreshes==(action==1));assert(SETTINGS.screenInverted==(action==0));assert(SETTINGS.orientation==(action==2));assert(p.lights==(action==4));
   if(action==3){assert(SETTINGS.touchReaderControls==0);p.runTile(slot);assert(SETTINGS.touchReaderControls==3);}
  }
 }
 assert(activityManager.notes==6&&activityManager.settings==6&&activityManager.apps==0);
 FrontlightPanelActivity p;SETTINGS.quickPanel1=255;p.runTile(0);p.runTile(-1);p.runTile(6);assert(p.updates==0&&p.closes==0);
 SETTINGS.quickPanel1=4;Frontlight.available=false;p.runTile(0);assert(p.lights==0);
 for(int group=0;group<2;++group)for(int slot=0;slot<6;++slot){
  SETTINGS=CrossPointSettings{};auto field=(group==0?ShortcutBindings::panel:ShortcutBindings::taps)[slot];auto old=SETTINGS.*field;
  ShortcutSettingsActivity ui;ui.page_=group;ui.activateIndex(slot);SETTINGS.saved=false;ui.popup_.chosen=2;assert(ui.handleCustomInput());assert(SETTINGS.*field==old&&ui.notices==1&&!ui.saveFailed_);
  ui.activateIndex(slot);SETTINGS.saved=true;ui.popup_.chosen=2;assert(ui.handleCustomInput());assert(SETTINGS.*field==2&&ui.notices==1);
  ui.activateIndex(slot);ui.popup_.chosen=255;ui.handleCustomInput();assert(SETTINGS.*field==2);
 }
}
'''
  self.compile_run(code)
 def compile_run(self,code):
  with tempfile.TemporaryDirectory() as tmp:
   cpp=Path(tmp)/'test.cpp';exe=Path(tmp)/'test';cpp.write_text(code)
   subprocess.run(['g++','-std=c++20','-fsanitize=address,undefined','-I'+str(ROOT),str(cpp),'-o',str(exe)],check=True)
   subprocess.run([str(exe)],check=True)
 def test_menu_gesture_consumed(self):
  block=function((ROOT/'src/activities/reader/EpubReaderActivity.cpp').read_text(),'  if (confirmReleased || cornerOpensMenu')
  code='''#include <cassert>
bool confirmReleased=false,cornerOpensMenu=true,section=true;int renderer=0,mappedInput=0;
namespace ReaderUtils{bool isTouchMenuGesture(int,int){return false;}}
bool toolbar=false;bool usesToolbarMenu(){return toolbar;}int pendingManualTurn=1,opened=0;
struct Overlay{enum{Toolbar};};void openOverlay(int){++opened;}void openReaderMenu(){++opened;}
void tap(){'''+block+'''assert(false);}
int main(){tap();toolbar=true;tap();assert(opened==2&&pendingManualTurn==0);}
'''
  self.compile_run(code)
 def test_extra_slots_and_app_launchers(self):
  """Optional tiles and the eight app actions, against the real runTile."""
  settings=(ROOT/'src/CrossPointSettings.h').read_text()
  fields='\n'.join(re.findall(r'  uint8_t (?:cornerTap\w+|quickPanel\d+) = [^;]+;',settings))
  enum=re.search(r'  enum CORNER_TAP_ACTION \{.*?\n  \};',settings,re.S).group()
  bindings=(ROOT/'src/ShortcutBindings.h').read_text().split('namespace ShortcutBindings',1)[1]
  ids=sorted(set(re.findall(r'StrId::(STR_\w+)',bindings)))
  pre='''#include "src/ScreenShortcutPolicy.h"
#include <cassert>
#include <cstdint>
#include <iterator>
#include <utility>
struct CrossPointSettings {
 enum {TOUCH_READER_OFF=0,TOUCH_READER_ON=1};
FIELDS
ENUM
 uint8_t screenInverted=0,orientation=0,touchReaderControls=3;
 bool saveToFile(){return true;}
} SETTINGS;
enum class StrId {IDS};
namespace ShortcutBindings BINDINGS
struct GfxRenderer{int refreshes=0;void promoteNextRefresh(int){++refreshes;}};
struct HalDisplay{enum{FULL_REFRESH};};
struct Light{bool present(){return true;}} Frontlight;
struct Manager{int notes=0,settings=0,jp=0,apps=0,photo=0,calc=0,transfer=0,opds=0,games=0,standby=0;
 void goToAirNote(){++notes;}void goToSettings(){++settings;}void goToJapaneseLearning(){++jp;}
 void goToApps(){++apps;}void goToAirPhoto(){++photo;}void goToCalculator(){++calc;}
 void goToFileTransfer(){++transfer;}void goToBrowser(){++opds;}void goToShelfGames(){++games;}
 void goToStandby(){++standby;}}activityManager;
struct FrontlightPanelActivity{static constexpr int kTileCount=ScreenShortcutPolicy::PANEL_SLOT_COUNT;
 GfxRenderer renderer;uint8_t touchModeRestore=1;bool cleanRefreshPending=false;int updates=0,closes=0,lights=0;
 void requestUpdate(){++updates;}void close(){++closes;}void toggleLight(){++lights;}void runTile(int);};
'''.replace('FIELDS',fields).replace('ENUM',enum).replace('IDS',','.join(ids)).replace('BINDINGS',bindings)
  code=pre+function((ROOT/'src/activities/util/FrontlightPanelActivity.cpp').read_text(),
                    'void FrontlightPanelActivity::runTile')+r'''
namespace SP = ScreenShortcutPolicy;
int main(){
 // The saved value IS the action id, so the shipped eight must never move.
 assert(SP::Night==0&&SP::Refresh==1&&SP::Orientation==2&&SP::Touch==3);
 assert(SP::Light==4&&SP::AirNote==5&&SP::Settings==6&&SP::Disabled==7);
 assert(SP::SLOT_COUNT==6&&SP::PANEL_SLOT_COUNT==12);
 assert(std::size(ShortcutBindings::panel)==SP::PANEL_SLOT_COUNT);
 assert(std::size(ShortcutBindings::panelLabels)==SP::PANEL_SLOT_COUNT);
 // The picker lists every action exactly once and keeps "disabled" last.
 bool seen[SP::ActionCount]={};
 for(int i=0;i<SP::ActionCount;++i){const uint8_t a=SP::PICKER_ORDER[i];assert(a<SP::ActionCount&&!seen[a]);seen[a]=true;}
 assert(SP::PICKER_ORDER[SP::ActionCount-1]==SP::Disabled);
 // Untouched device: the six original slots keep their defaults, the optional ones are off.
 SETTINGS=CrossPointSettings{};
 for(int i=0;i<SP::SLOT_COUNT;++i)assert(SETTINGS.*ShortcutBindings::panel[i]==SP::DEFAULTS[i]);
 for(int i=SP::SLOT_COUNT;i<SP::PANEL_SLOT_COUNT;++i)assert(SETTINGS.*ShortcutBindings::panel[i]==SP::Disabled);
 // Each new action launches its own app and touches nothing else.
 const std::pair<uint8_t,int Manager::*> cases[]={{SP::JapaneseLearning,&Manager::jp},{SP::Apps,&Manager::apps},
  {SP::AirPhoto,&Manager::photo},{SP::Calculator,&Manager::calc},{SP::FileTransfer,&Manager::transfer},
  {SP::Opds,&Manager::opds},{SP::Games,&Manager::games},{SP::Standby,&Manager::standby}};
 assert(std::size(cases)==8);
 for(auto [action,counter]:cases){
  activityManager=Manager{};SETTINGS=CrossPointSettings{};SETTINGS.quickPanel1=action;
  FrontlightPanelActivity p;p.runTile(0);
  assert(activityManager.*counter==1&&activityManager.notes==0&&activityManager.settings==0);
  assert(SETTINGS.screenInverted==0&&SETTINGS.orientation==0&&p.closes==0&&p.lights==0&&p.renderer.refreshes==0);
 }
 // Tiles: the six slots always hold their place (a disabled one stays a gap,
 // exactly as before), optional slots join only when bound, in slot order.
 SETTINGS=CrossPointSettings{};uint8_t slots[SP::PANEL_SLOT_COUNT];
 assert(ShortcutBindings::visibleTiles(SETTINGS,slots)==SP::SLOT_COUNT);
 for(int i=0;i<SP::SLOT_COUNT;++i)assert(slots[i]==i);
 SETTINGS.quickPanel3=SP::Disabled;
 assert(ShortcutBindings::visibleTiles(SETTINGS,slots)==SP::SLOT_COUNT&&slots[2]==2);
 SETTINGS.quickPanel8=SP::JapaneseLearning;
 assert(ShortcutBindings::visibleTiles(SETTINGS,slots)==7&&slots[6]==7);
 SETTINGS.quickPanel7=SP::Apps;
 assert(ShortcutBindings::visibleTiles(SETTINGS,slots)==8&&slots[6]==6&&slots[7]==7);
 // A value saved by some future build must not become a tile.
 SETTINGS.quickPanel12=255;
 assert(ShortcutBindings::visibleTiles(SETTINGS,slots)==8);
 // Every optional slot bound: a full four-row panel.
 SETTINGS=CrossPointSettings{};
 for(int i=SP::SLOT_COUNT;i<SP::PANEL_SLOT_COUNT;++i)SETTINGS.*ShortcutBindings::panel[i]=SP::Apps;
 assert(ShortcutBindings::visibleTiles(SETTINGS,slots)==SP::PANEL_SLOT_COUNT);
}
'''
  self.compile_run(code)
if __name__=='__main__':unittest.main()
