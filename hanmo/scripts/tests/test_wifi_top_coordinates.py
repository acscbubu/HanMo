from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class TopStatusCoordinates(unittest.TestCase):
 def test_real_renderer_transform_roundtrip_all_rotations(self):
  src=(ROOT/'lib/GfxRenderer/GfxRenderer.cpp').read_text()
  def body(start):
   a=src.index(start);b=src.index('{',a);level=1;i=b+1
   while level:
    level+=(src[i]=='{')-(src[i]=='}');i+=1
   return src[a:i]
  code=r"""#include <cassert>
#include <cstdint>
#include <algorithm>
class GfxRenderer {public:
 enum Orientation{Portrait,LandscapeClockwise,PortraitInverted,LandscapeCounterClockwise};
 Orientation orientation=Portrait;uint16_t panelWidth=800,panelHeight=480;
 int systemStatusHeight_=22;bool drawingSystemStatus_=false;
 void tapToLogical(float,float,int&,int&) const;int getScreenWidth() const;int getScreenHeight() const;
};
"""+body('static inline void rotateCoordinates')+'\n'+body('void GfxRenderer::tapToLogical')+'\n'+body('int GfxRenderer::getScreenWidth()')+'\n'+body('int GfxRenderer::getScreenHeight()')+r"""
int main(){GfxRenderer r;
 for(int inset:{0,22})for(int rot=0;rot<4;rot++){
  r.systemStatusHeight_=inset;r.orientation=GfxRenderer::Orientation(rot);
  for(int x:{0,5,r.getScreenWidth()/2,r.getScreenWidth()-1})
  for(int y:{0,5,r.getScreenHeight()/2,r.getScreenHeight()-1}){
   int px,py,rx,ry;rotateCoordinates(r.orientation,x,y,&px,&py,800,480,inset);
   assert(px>=0&&px<800&&py>=0&&py<480);
   r.tapToLogical((px+.25f)/800,(py+.25f)/480,rx,ry);assert(x==rx&&y==ry);
  }
  if(inset){int px,py,x,y;rotateCoordinates(r.orientation,10,10,&px,&py,800,480,0);
   r.tapToLogical((px+.25f)/800,(py+.25f)/480,x,y);assert(y<0);
  }
 }
}
"""
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.cpp').write_text(code)
   subprocess.run(['g++','-std=c++17',str(p/'test.cpp'),'-o',str(p/'test')],check=True,capture_output=True)
   subprocess.run([str(p/'test')],check=True)
if __name__=='__main__':unittest.main()
