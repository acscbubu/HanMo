"""Host tests of production gesture policy, recognizer and reader dispatch."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
STUB=r"""
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <vector>
#include "src/ReaderGesturePolicy.h"
#include "src/activities/reader/ReaderPinchGesture.h"
struct Settings {
 uint8_t touchReaderControls=1,gestureNextPage=0,gesturePreviousPage=0;
 uint8_t gesturePinchFont=0,gestureRotation=0,gestureStatusBar=0;
 uint8_t gestureSwipeUp=0,gestureSwipeDown=0,gestureSwipeLeft=0,gestureSwipeRight=0;
 uint8_t fontPointSize=12,sdFontFlashPreload=0,frontlightBrightness=60,frontlightOn=1,frontlightWarmth=50;
 char sdFontFamilyName[8]={};bool saveOk=true;bool saveToFile(){return saveOk;}
} SETTINGS;
std::vector<uint8_t> availableSizes{12,14,16};
struct Fonts{int reg=0;int& registry(){return reg;}}sdFontSystem;
std::vector<uint8_t> readerFontPointSizes(int*,const char*){return availableSizes;}
uint8_t snapToNearestPointSize(const std::vector<uint8_t>& values,uint8_t value){return *std::min_element(values.begin(),values.end(),[&](int a,int b){return std::abs(a-value)<std::abs(b-value);});}
struct GfxRenderer{int getScreenWidth()const{return 480;}int getScreenHeight()const{return 800;}};
struct MappedInputManager {
 enum class SwipeDir{None,Left,Right,Up,Down};uint8_t contacts=0;SwipeDir multi=SwipeDir::None,single=SwipeDir::None;
 bool rotation=false,clockwise=true,tapped=false;int tx=0,ty=0,x1=100,y1=100,x2=200,y2=100,suppressed=0;
 bool hasTouch()const{return true;}uint8_t gestureContactCount()const{return contacts;}
 bool getTwoFingerTouch(int& a,int& b,int& c,int& d)const{a=x1;b=y1;c=x2;d=y2;return contacts==2;}
 bool twoFingerRotation(bool& cw)const{cw=clockwise;return rotation;}
 SwipeDir twoFingerSwipe()const{return multi;}SwipeDir wasSwipe()const{return single;}
 bool wasScreenTapped(int& x,int& y)const{x=tx;y=ty;return tapped;}
 void swallowCurrentTouch(){++suppressed;}
};
struct{unsigned long lastTouchHeldMs(){return 0;}}gpio;
struct Light{int brightnessValue=60,warmthValue=50;bool present()const{return true;}bool hasColorTemperature()const{return true;}void setBrightness(int v){brightnessValue=v;}void setOn(bool){}void setWarmth(int v){warmthValue=v;}}Frontlight;
struct RenderLock{template<class T>RenderLock(T&) {}};
struct UITheme{static UITheme& getInstance(){static UITheme theme;return theme;}int getStatusBarHeight(){return 32;}};
class ReaderActivity {
 public:GfxRenderer renderer;MappedInputManager mappedInput;ReaderPinchGesture pinchGesture;
 bool gestureMultiSequence=false,gestureConsumed=false,gestureInvalid=false,gestureWaitForRelease=false,gestureStatusHidden=false;
 bool end=false,text=true;int fontChanges=0,rotations=0,chapters=0,updates=0;
 bool supportsGestureText()const{return text;}bool isAtEndOfBook()const{return end;}
 void gestureFontChanged(){++fontChanges;}void gestureRotate(bool cw){rotations+=cw?1:-1;}void gestureChapter(bool f){chapters+=f?1:-1;}
 void requestUpdate(){++updates;}bool stepGestureFont(bool);bool handleReadingGestures();
};
namespace ReaderUtils {struct TouchPageTurn{bool prev,next;unsigned long heldMs;};}
"""
TEST=r"""
int main(){using namespace ReaderGesturePolicy;
 // Legacy Off/Tap/Swipe/Inverted values survive untouched; center taps remain free.
 assert(effective(0,0)==Disabled&&effective(0,1)==Tap&&effective(0,2)==Swipe&&effective(0,3)==InvertedTap);
 ReaderActivity a;a.mappedInput.tapped=true;a.mappedInput.tx=400;
 assert(ReaderUtils::detectTouchPageTurn(a.renderer,a.mappedInput).next);
 a.mappedInput.tx=240;assert(!ReaderUtils::detectTouchPageTurn(a.renderer,a.mappedInput).next);
 SETTINGS.gestureNextPage=TapSwipe;a.mappedInput.tapped=false;a.mappedInput.single=MappedInputManager::SwipeDir::Left;
 assert(ReaderUtils::detectTouchPageTurn(a.renderer,a.mappedInput).next);
 SETTINGS.gestureNextPage=InvertedTap;a.mappedInput.single=MappedInputManager::SwipeDir::None;a.mappedInput.tapped=true;a.mappedInput.tx=10;
 auto overlap=ReaderUtils::detectTouchPageTurn(a.renderer,a.mappedInput);assert(!overlap.prev&&!overlap.next);
 SETTINGS.gesturePreviousPage=InvertedTap;assert(ReaderUtils::detectTouchPageTurn(a.renderer,a.mappedInput).next);
 SETTINGS.touchReaderControls=0;assert(!ReaderUtils::detectTouchPageTurn(a.renderer,a.mappedInput).next);
 SETTINGS=Settings{};a=ReaderActivity{};
 // Two consecutive samples, one pinch action per sequence, including 2 -> 1 -> 2.
 SETTINGS.gesturePinchFont=1;a.mappedInput.contacts=2;assert(a.handleReadingGestures());
 a.mappedInput.x1=80;a.mappedInput.x2=220;assert(a.handleReadingGestures());assert(a.fontChanges==0);
 a.handleReadingGestures();assert(a.fontChanges==1&&SETTINGS.fontPointSize==14);
 a.mappedInput.contacts=1;a.handleReadingGestures();a.mappedInput.contacts=2;a.mappedInput.x2=250;a.handleReadingGestures();assert(a.fontChanges==1);
 a.mappedInput.contacts=0;a.mappedInput.rotation=true;SETTINGS.gestureRotation=1;a.handleReadingGestures();assert(a.rotations==0);
 a.mappedInput.rotation=false;assert(!a.handleReadingGestures());
 // Rotation completes with one contact still down: dispatch once, consume the remainder.
 a.mappedInput.contacts=2;a.mappedInput.x1=100;a.mappedInput.x2=200;a.handleReadingGestures();
 a.mappedInput.contacts=1;a.mappedInput.rotation=true;a.handleReadingGestures();assert(a.rotations==1&&a.gestureWaitForRelease);
 a.mappedInput.rotation=false;a.mappedInput.tapped=true;a.mappedInput.ty=790;SETTINGS.gestureStatusBar=1;a.handleReadingGestures();assert(!a.gestureStatusHidden);
 a.mappedInput.contacts=0;a.handleReadingGestures();assert(!a.gestureStatusHidden);a.handleReadingGestures();assert(a.gestureStatusHidden);
 a.handleReadingGestures();assert(!a.gestureStatusHidden);a.mappedInput.tapped=false;
 // Three-contact sequence cannot shrink into a valid two-finger gesture.
 a.mappedInput.contacts=3;a.handleReadingGestures();a.mappedInput.contacts=2;a.handleReadingGestures();a.mappedInput.contacts=0;a.mappedInput.rotation=true;a.handleReadingGestures();assert(a.rotations==1);
 a.mappedInput.rotation=false;
 SETTINGS.gestureSwipeUp=Brighter;a.mappedInput.multi=MappedInputManager::SwipeDir::Up;a.handleReadingGestures();assert(SETTINGS.frontlightBrightness==70&&Frontlight.brightnessValue==70);
 SETTINGS.saveOk=false;a.handleReadingGestures();assert(SETTINGS.frontlightBrightness==70);
 SETTINGS.gestureSwipeUp=LargerFont;a.handleReadingGestures();assert(SETTINGS.fontPointSize==14&&a.fontChanges==1);
 SETTINGS.saveOk=true;a.handleReadingGestures();assert(SETTINGS.fontPointSize==16&&a.fontChanges==2);a.handleReadingGestures();assert(a.fontChanges==2);
 SETTINGS.gestureSwipeUp=PreviousChapter;a.handleReadingGestures();assert(a.chapters==-1);
 a.text=false;SETTINGS.gestureSwipeUp=SmallerFont;a.handleReadingGestures();assert(a.fontChanges==2);
 a.mappedInput.multi=MappedInputManager::SwipeDir::None;a.end=true;assert(!a.handleReadingGestures());
 assert(rotated(3,true)==0&&rotated(0,false)==3);
 // Pure recognizer rejects parallel translation, rotation wobble and contact-ID order swaps.
 ReaderPinchGesture p;p.update(0,0,100,0);p.update(30,0,130,0);assert(p.update(30,0,170,0)==ReaderPinchGesture::Action::None);
 p.reset();p.update(0,0,100,0);p.update(0,0,100,40);assert(p.update(0,0,150,60)==ReaderPinchGesture::Action::None);
 p.reset();p.update(0,0,100,0);p.update(100,0,0,0);assert(p.update(100,0,0,0)==ReaderPinchGesture::Action::None);
}
"""
class GestureTest(unittest.TestCase):
 def test_production_policy_pinch_and_runtime_dispatch(self):
  runtime=(ROOT/'src/activities/reader/ReaderActivity.cpp').read_text()
  runtime=runtime[runtime.index('bool ReaderActivity::stepGestureFont('):]
  utils=(ROOT/'src/activities/reader/ReaderUtils.h').read_text()
  utils=utils[utils.index('inline TouchPageTurn detectTouchPageTurn('):utils.index('// EPUB shortcuts')]
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'test.cpp').write_text(STUB+'\nnamespace ReaderUtils {\n'+utils+'}\n'+runtime+TEST)
   subprocess.run(['g++','-std=c++17','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(ROOT),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
   subprocess.run([str(p/'test')],check=True)
if __name__=='__main__':unittest.main()
