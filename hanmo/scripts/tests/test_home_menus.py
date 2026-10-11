"""Regression checks for the production home shortcut resolver and label editor."""
from pathlib import Path
import subprocess,tempfile,unittest
from scripts.tests.test_screen_shortcuts import function
ROOT=Path(__file__).resolve().parents[2]
class HomeMenusTest(unittest.TestCase):
 def test_home_menu_and_label(self):
  source=(ROOT/'src/HomeCustomization.h').read_text()
  code=r'''#include "src/HomeShortcutPolicy.h"
#include "src/FirmwareIdentity.h"
#include <cassert>
#include <cstring>
#include <string>
struct {char homeLabel[24]="old";} SETTINGS;
'''+function(source,'inline bool validLabel')+function(source,'inline bool assignLabel')+r'''
int main(){
 using namespace HomeShortcutPolicy;
 std::array<uint8_t,6> s{};
 auto m=resolve(s,true,true);assert(m.count==6&&m.items[3]==Apps&&m.items[5]==Settings);
 m=resolve(s,false,true);assert(m.count==5&&m.items[2]==Apps&&m.items[4]==Settings);
 m=resolve(s,false,false);assert(m.count==5&&m.items[2]==Transfer&&m.items[4]==Apps);
 // Every set of choices has valid action IDs and at least one reachable slot.
 for(unsigned bits=0;bits<1000000;++bits){
  unsigned n=bits;for(auto& x:s){x=n%10;n/=10;}
  for(bool opds:{false,true})for(bool carousel:{false,true}){
   m=resolve(s,opds,carousel);assert(m.count>=1&&m.count<=6);
   for(int i=0;i<m.count;++i){assert(m.items[i]>Default&&m.items[i]<Count&&m.items[i]!=Hidden);if(!opds)assert(m.items[i]!=Opds);}
  }
 }
 static_assert(Hidden==9&&Retired==10);
 static_assert(selectionIndex(Retired)==Hidden&&selectionIndex(RetiredPrivate)==Hidden);
 static_assert(storedAction(10)==ReadingStats&&storedAction(9)==Hidden);
 for(int action=0;action<Count;++action){if(!isRetired(action))assert(storedAction(selectionIndex(action))==action);}
 assert(storedAction(Count)==Default);
 s.fill(Retired);m=resolve(s,true,true);assert(m.count==1&&m.items[0]==Settings);
 for(int action=ReadingStats;action<Count;++action){s.fill(action);m=resolve(s,true,true);assert(m.count==6&&m.items[0]==action);}
 s.fill(WeRead);m=resolve(s,true,true,false);assert(m.count==1&&m.items[0]==Settings);
 s.fill(Hidden);m=resolve(s,false,true);assert(m.count==1&&m.items[0]==Settings);
 s={AirNote,Files,Hidden,AirPage,Settings,Recent};m=resolve(s,true,true);
 assert(m.count==5&&m.items[0]==AirNote&&m.items[2]==AirPage&&m.items[4]==Recent);
 s.fill(255);assert(resolve(s,false,true).count==5);
 assert(assignLabel("安格斯 X4 Pro"));assert(std::string(SETTINGS.homeLabel)=="安格斯 X4 Pro");
 assert(assignLabel(std::string(23,'x')));assert(!assignLabel(std::string(24,'x')));assert(strlen(SETTINGS.homeLabel)==23);
 assert(!assignLabel("bad\nname"));assert(!assignLabel(std::string("a\0b",3)));assert(!assignLabel("\xc0\xaf"));
 assert(assignLabel(""));assert(!SETTINGS.homeLabel[0]);
}
'''
  with tempfile.TemporaryDirectory() as tmp:
   cpp=Path(tmp)/'test.cpp';exe=Path(tmp)/'test';cpp.write_text(code)
   subprocess.run(['g++','-std=c++20','-O1','-fsanitize=address,undefined','-I'+str(ROOT),'-I'+str(ROOT/'.pio/libdeps/x4pro_custom/ArduinoJson/src'),str(cpp),'-o',str(exe)],check=True)
   subprocess.run([str(exe)],check=True)
if __name__=='__main__':unittest.main()
