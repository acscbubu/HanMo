# Host-run the actual AirPhoto cover helper against fault-injecting HAL stubs.
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / 'src/activities/apps/airphoto'

STUB = r'''
#pragma once
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <map>
#include <string>
#include <vector>
#include "ScreenSettingsPolicy.h"
struct HalFile;
struct FakeStorage {
 std::map<std::string,std::string> files;
 bool shortWrite=false, failRead=false, failOpen=false, failClose=false, failRemove=false;
 int failRename=0, renames=0;
 bool exists(const char* p)const{return files.count(p)!=0;}
 bool remove(const char* p){return !failRemove && files.erase(p)!=0;}
 bool rename(const char* a,const char* b){if(++renames==failRename||!exists(a)||exists(b))return false;files[b]=files.at(a);files.erase(a);return true;}
 bool openFileForRead(const char*,const char*,HalFile&);
 bool openFileForWrite(const char*,const char*,HalFile&);
 HalFile open(const char*); bool ensureDirectoryExists(const char*);
}; inline FakeStorage Storage;
struct HalFile {
 std::string path;size_t pos=0;bool good=false;
 explicit operator bool()const{return good;}
 uint64_t fileSize64()const{return Storage.files.at(path).size();}
 size_t position()const{return pos;}
 int available()const{return static_cast<int>(fileSize64()-pos);}
 int read(void* dst,size_t n){if(Storage.failRead)return -1;const auto& s=Storage.files.at(path);n=std::min(n,s.size()-pos);memcpy(dst,s.data()+pos,n);pos+=n;return static_cast<int>(n);}
 size_t write(const uint8_t* src,size_t n){if(Storage.shortWrite&&n)--n;Storage.files[path].append(reinterpret_cast<const char*>(src),n);return n;}
 void flush(){}bool close(){good=false;return !Storage.failClose;}
 bool isDirectory()const;HalFile openNextFile();size_t getName(char*,size_t);
};
inline bool FakeStorage::openFileForRead(const char*,const char* p,HalFile& f){if(failOpen||!exists(p))return false;f.path=p;f.good=true;f.pos=0;return true;}
inline bool FakeStorage::openFileForWrite(const char*,const char* p,HalFile& f){if(failOpen)return false;files[p]="";f.path=p;f.good=true;return true;}
struct CrossPointSettings {
 uint8_t bootScreen=0,shutdownScreen=0,sleepScreen=1,quickResumeSleepScreen=1;
 char bootScreenImage[256]{},shutdownScreenImage[256]{},sleepScreenImage[256]{};
 bool failSave=false;int saves=0;
 bool saveToFile(){++saves;return !failSave;}
 static CrossPointSettings& getInstance(){static CrossPointSettings s;return s;}
};
#define SETTINGS CrossPointSettings::getInstance()
enum class BmpReaderError{Ok,Invalid};
struct Bitmap {
 HalFile& f;Bitmap(HalFile& file,bool):f(file){}
 BmpReaderError parseHeaders(){if(Storage.files[f.path].compare(0,2,"BM")!=0||f.fileSize64()<58)return BmpReaderError::Invalid;f.pos=54;return BmpReaderError::Ok;}
 int getWidth()const{return 2;}int getHeight()const{return 2;}int getRowBytes()const{return 2;}
};
struct JpegToBmpConverter {
 static bool jpegFileToBmpStreamWithSize(HalFile& in,HalFile& out,int,int){return jpegFileToBmpStream(in,out,true);}
 static bool jpegFileToBmpStream(HalFile& src,HalFile& out,bool crop){if(!crop)return false;std::string data(src.fileSize64(),' ');if(src.read(data.data(),data.size())<0)return false;auto bmp=std::string("BM")+std::string(52,'h')+"JPEG:"+data;return out.write(reinterpret_cast<const uint8_t*>(bmp.data()),bmp.size())==bmp.size();}
};
struct PngToBmpConverter {
 static bool pngFileToBmpStreamWithSize(HalFile& in,HalFile& out,int,int){return pngFileToBmpStream(in,out,true);}
 static bool pngFileToBmpStream(HalFile& src,HalFile& out,bool crop){if(!crop)return false;std::string data(src.fileSize64(),' ');if(src.read(data.data(),data.size())<0)return false;auto bmp=std::string("BM")+std::string(52,'h')+"PNG:"+data;return out.write(reinterpret_cast<const uint8_t*>(bmp.data()),bmp.size())==bmp.size();}
};
namespace airpage {
 enum class ImageFormat{None,Bmp,Jpeg};struct ImageInfo{ImageFormat format=ImageFormat::None;};
 struct SelectedImage{char path[96]{};ImageInfo image;};
 struct AirPageImageStore{static bool inspectImage(const char* p,ImageInfo& info){if(!Storage.exists(p))return false;info.format=Storage.files.at(p).compare(0,2,"BM")==0?ImageFormat::Bmp:ImageFormat::Jpeg;return true;}};
 struct AirPageWallpaper{static bool install(const SelectedImage& img,bool crop){if(!crop||!Storage.exists(img.path))return false;Storage.files["/sleep.bmp"]=Storage.files.at(img.path);SETTINGS.sleepScreen=2;SETTINGS.sleepScreenImage[0]=0;return SETTINGS.saveToFile();}};
}
'''


HARNESS = r'''
#include "ui_stub.h"
#include "src/activities/apps/airphoto/AirPhotoActivity.h"
static std::string bmp(const char* text){return std::string("BM")+std::string(53,'h')+text;}
static void choose(AirPhotoActivity& app,int index){
 assert(OptionPopup::last&&OptionPopup::last->active);
 OptionPopup::last->choice=index;OptionPopup::last->choosePending=true;app.loop();app.render(RenderLock{});
}
static void cancel(AirPhotoActivity& app){
 assert(OptionPopup::last&&OptionPopup::last->active);
 OptionPopup::last->cancelPending=true;app.loop();app.render(RenderLock{});
}
int main() {
 Storage.files["/AirPhoto/a.bmp"]=bmp("PHOTO");
 GfxRenderer renderer;MappedInputManager input;
 AirPhotoActivity photo(renderer,input);photo.onEnter();
 input.tap=true;photo.loop();input.tap=false;
 assert(renderer.lastBitmap=="/AirPhoto/a.bmp");
 input.longPress=true;photo.loop();input.longPress=false;
 assert(OptionPopup::lastLabels.size()>=2);
 assert(OptionPopup::lastLabels[0]=="Set cover"&&OptionPopup::lastLabels[1]=="Delete");
 photo.render(RenderLock{});assert(renderer.lastBitmap=="popup");
 cancel(photo);assert(renderer.lastBitmap=="/AirPhoto/a.bmp");

 input.longPress=true;photo.loop();input.longPress=false;
 photo.render(RenderLock{});choose(photo,0);
 assert(OptionPopup::last->active && OptionPopup::lastLabels.size()==4);
 assert(OptionPopup::lastLabels[0]=="Startup"&&OptionPopup::lastLabels[1]=="Sleep"&&OptionPopup::lastLabels[2]=="Shutdown");
 assert(renderer.lastBitmap=="popup"); // the submenu is the next frame, with no intermediate bare photo
 photo.render(RenderLock{});cancel(photo);assert(renderer.lastBitmap=="/AirPhoto/a.bmp");

 for(int cover=0;cover<3;++cover){
  input.longPress=true;photo.loop();input.longPress=false;
  choose(photo,0);choose(photo,cover);
  assert(renderer.lastBitmap=="/AirPhoto/a.bmp");
  assert(Storage.exists("/AirPhoto/a.bmp"));
 }
 assert(SETTINGS.bootScreen==ScreenSettingsPolicy::BootCustom);
 assert(SETTINGS.shutdownScreen==ScreenSettingsPolicy::ShutdownCustom);
 assert(SETTINGS.sleepScreen==2);

 input.longPress=true;photo.loop();input.longPress=false;
 photo.render(RenderLock{});choose(photo,1);
 assert(OptionPopup::last->active && OptionPopup::last->initial==1);
 assert(OptionPopup::lastLabels[0]=="Confirm"&&OptionPopup::lastLabels[1]=="Cancel");
 assert(OptionPopup::last->title.find("a.bmp")!=std::string::npos);
 choose(photo,1);assert(Storage.exists("/AirPhoto/a.bmp")&&renderer.lastBitmap=="/AirPhoto/a.bmp");

 input.longPress=true;photo.loop();input.longPress=false;
 choose(photo,1);choose(photo,0);
 assert(!Storage.exists("/AirPhoto/a.bmp") && renderer.lastBitmap.empty());
 assert(Storage.exists("/AirPhoto/.boot-cover.bmp") && Storage.exists("/AirPhoto/.shutdown-cover.bmp") && Storage.exists("/sleep.bmp"));

 Storage.files["/AirPhoto/b.jpg"]="JPEG-1";
 Storage.files["/AirPhoto/b.png"]="PNG-2";
 Storage.files["/AirPhoto/.view/b.bmp"]=bmp("VIEW");
 Storage.files["/AirPhoto/.thumb/b.bmp"]=bmp("THUMB");
 AirPhotoActivity shared(renderer,input);shared.onEnter();
 input.tap=true;shared.loop();input.tap=false;
 assert(renderer.lastBitmap=="/AirPhoto/.view/b.bmp");
 input.longPress=true;shared.loop();input.longPress=false;
 choose(shared,1);choose(shared,0);
 assert(!Storage.exists("/AirPhoto/b.jpg")&&Storage.exists("/AirPhoto/b.png"));
 assert(Storage.exists("/AirPhoto/.view/b.bmp")&&Storage.exists("/AirPhoto/.thumb/b.bmp"));
 assert(renderer.lastBitmap=="/AirPhoto/.thumb/b.bmp");
 input.tap=true;shared.loop();input.tap=false;
 assert(renderer.lastBitmap=="/AirPhoto/.view/b.bmp");
 Storage.failRemove=true;
 input.longPress=true;shared.loop();input.longPress=false;
 choose(shared,1);choose(shared,0);
 assert(Storage.exists("/AirPhoto/b.png"));
 assert(renderer.lastBitmap=="/AirPhoto/.view/b.bmp");
 Storage.failRemove=false;
}
'''

HARNESS = r'''
#include "stub.h"
#include "src/activities/apps/airphoto/AirPhotoActions.h"
static std::string bmp(const char* tail) { return std::string("BM")+std::string(53,'h')+tail; }
static void reset() { Storage.files.clear(); Storage.shortWrite=false; Storage.failRead=false; Storage.failOpen=false; Storage.failClose=false; Storage.failRemove=false; Storage.failRename=0; Storage.renames=0; SETTINGS=CrossPointSettings{}; }
int main(){
 reset();
 Storage.files["/AirPhoto/a.bmp"] = bmp("OLD");
 assert(airphoto::setCover("/AirPhoto/a.bmp",airphoto::Cover::Startup));
 assert(Storage.files.at("/AirPhoto/.boot-cover.bmp")==bmp("OLD"));
 assert(SETTINGS.bootScreen==ScreenSettingsPolicy::BootCustom);
 assert(std::string(SETTINGS.bootScreenImage)=="/AirPhoto/.boot-cover.bmp");

 reset();
 Storage.files["/AirPhoto/a.bmp"] = bmp("SLEEP");
 assert(airphoto::setCover("/AirPhoto/a.bmp",airphoto::Cover::Sleep));
 assert(Storage.files.at("/sleep.bmp")==bmp("SLEEP"));
 assert(SETTINGS.sleepScreen==2 && SETTINGS.sleepScreenImage[0]=='\0');

 reset();
 Storage.files["/AirPhoto/a.jpg"] = "JPEG-DATA";
 assert(airphoto::setCover("/AirPhoto/a.jpg",airphoto::Cover::Shutdown));
 assert(Storage.files.at("/AirPhoto/.shutdown-cover.bmp").rfind("BM",0)==0);
 assert(Storage.files.at("/AirPhoto/.shutdown-cover.bmp").find("JPEG:")!=std::string::npos);
 assert(SETTINGS.shutdownScreen==ScreenSettingsPolicy::ShutdownCustom);
 assert(std::string(SETTINGS.shutdownScreenImage)=="/AirPhoto/.shutdown-cover.bmp");

 reset();
 Storage.files["/AirPhoto/a.png"] = "PNG-DATA";
 assert(airphoto::setCover("/AirPhoto/a.png",airphoto::Cover::Startup));
 assert(Storage.files.at("/AirPhoto/.boot-cover.bmp").find("PNG:")!=std::string::npos);

 reset();
 Storage.files["/AirPhoto/a.png"]="PNG-DATA";
 assert(airphoto::setCover("/AirPhoto/a.png",airphoto::Cover::Sleep));
 assert(Storage.files.at("/sleep.bmp").find("PNG:")!=std::string::npos);
 assert(!Storage.exists("/AirPhoto/.sleep-cover.bmp.part"));

 reset();
 Storage.files["/AirPhoto/a.bmp"] = bmp("NEW");
 Storage.files["/AirPhoto/.boot-cover.bmp"] = bmp("PREVIOUS");
 std::snprintf(SETTINGS.bootScreenImage,sizeof(SETTINGS.bootScreenImage),"/old.bmp");
 SETTINGS.bootScreen=ScreenSettingsPolicy::BootDefault; SETTINGS.failSave=true;
 assert(!airphoto::setCover("/AirPhoto/a.bmp",airphoto::Cover::Startup));
 assert(Storage.files.at("/AirPhoto/.boot-cover.bmp")==bmp("PREVIOUS"));
 assert(SETTINGS.bootScreen==ScreenSettingsPolicy::BootDefault);
 assert(std::string(SETTINGS.bootScreenImage)=="/old.bmp");
 assert(SETTINGS.saves==2);
 assert(!Storage.exists("/AirPhoto/.boot-cover.bmp.part"));

 reset();
 Storage.files["/AirPhoto/a.bmp"] = bmp("PHOTO");
 Storage.files["/AirPhoto/.view/a.bmp"] = bmp("VIEW");
 Storage.files["/AirPhoto/.thumb/a.bmp"] = bmp("THUMB");
 assert(airphoto::deletePhoto("/AirPhoto/a.bmp","/AirPhoto/.view/a.bmp","/AirPhoto/.thumb/a.bmp",false));
 assert(!Storage.exists("/AirPhoto/a.bmp")&&!Storage.exists("/AirPhoto/.view/a.bmp")&&!Storage.exists("/AirPhoto/.thumb/a.bmp"));

 reset();
 Storage.files["/AirPhoto/a.jpg"] = "PHOTO";
 Storage.files["/AirPhoto/.view/a.bmp"] = bmp("VIEW");
 Storage.files["/AirPhoto/.thumb/a.bmp"] = bmp("THUMB");
 assert(airphoto::deletePhoto("/AirPhoto/a.jpg","/AirPhoto/.view/a.bmp","/AirPhoto/.thumb/a.bmp",true));
 assert(!Storage.exists("/AirPhoto/a.jpg"));
 assert(Storage.exists("/AirPhoto/.view/a.bmp")&&Storage.exists("/AirPhoto/.thumb/a.bmp"));

 reset();
 Storage.files["/AirPhoto/a.bmp"] = bmp("ORIGINAL");
 Storage.files["/AirPhoto/.boot-cover.bmp"] = bmp("LAST");
 std::snprintf(SETTINGS.bootScreenImage,sizeof(SETTINGS.bootScreenImage),"/AirPhoto/.boot-cover.bmp");
 SETTINGS.bootScreen=ScreenSettingsPolicy::BootCustom;
 Storage.shortWrite=true;
 assert(!airphoto::setCover("/AirPhoto/a.bmp",airphoto::Cover::Startup));
 assert(Storage.files.at("/AirPhoto/.boot-cover.bmp")==bmp("LAST") && SETTINGS.saves==0);
 assert(!Storage.exists("/AirPhoto/.boot-cover.bmp.part"));
 Storage.shortWrite=false; Storage.renames=0; Storage.failRename=2;
 assert(!airphoto::setCover("/AirPhoto/a.bmp",airphoto::Cover::Startup));
 assert(Storage.files.at("/AirPhoto/.boot-cover.bmp")==bmp("LAST") && SETTINGS.saves==0);
 assert(!Storage.exists("/AirPhoto/.boot-cover.bmp.part"));
 Storage.failRename=0;
 Storage.failRead=true;
 assert(!airphoto::setCover("/AirPhoto/a.bmp",airphoto::Cover::Startup));
 assert(Storage.files.at("/AirPhoto/.boot-cover.bmp")==bmp("LAST") && SETTINGS.saves==0);
 Storage.failRead=false;Storage.failClose=true;
 assert(!airphoto::setCover("/AirPhoto/a.bmp",airphoto::Cover::Startup));
 assert(Storage.files.at("/AirPhoto/.boot-cover.bmp")==bmp("LAST") && SETTINGS.saves==0);
 Storage.failClose=false;
 assert(airphoto::setCover("/AirPhoto/a.bmp",airphoto::Cover::Startup));
 assert(Storage.files.at("/AirPhoto/.boot-cover.bmp")==bmp("ORIGINAL"));
 assert(!Storage.exists("/AirPhoto/.boot-cover.bmp.bak"));
 assert(!Storage.exists("/AirPhoto/.boot-cover.bmp.part"));

 reset();
 Storage.files["/AirPhoto/a.bmp"]=bmp("PHOTO");
 Storage.files["/AirPhoto/.view/a.bmp"]=bmp("VIEW");
 Storage.failRemove=true;
 assert(!airphoto::deletePhoto("/AirPhoto/a.bmp","/AirPhoto/.view/a.bmp","/AirPhoto/.thumb/a.bmp",false));
 assert(Storage.exists("/AirPhoto/a.bmp") && Storage.exists("/AirPhoto/.view/a.bmp"));

 reset();
 Storage.files["/AirPhoto/a.png"]="PNG";
 Storage.files["/AirPhoto/.boot-cover.bmp"]=bmp("OLD");
 Storage.files["/AirPhoto/.boot-cover.bmp.bak"]=bmp("BACKUP");
 SETTINGS.bootScreen=ScreenSettingsPolicy::BootDefault;
 assert(airphoto::setCover("/AirPhoto/a.png",airphoto::Cover::Startup));
 assert(!Storage.exists("/AirPhoto/.boot-cover.bmp.bak"));
 assert(Storage.files.at("/AirPhoto/.boot-cover.bmp").find("PNG:")!=std::string::npos);
}
'''

class AirPhotoActionsTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();tmp=pathlib.Path(cls.tmp.name)
  (tmp/'stub.h').write_text(STUB)
  for name in ('HalStorage.h','CrossPointSettings.h','Bitmap.h','JpegToBmpConverter.h','PngToBmpConverter.h','activities/apps/airpage/AirPageImageStore.h','activities/apps/airpage/AirPageWallpaper.h'):
   file=tmp/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text('#include "stub.h"\n')
  (tmp/'main.cpp').write_text(HARNESS)
  cls.binary=tmp/'airphoto_actions'
  result=subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror','-I',str(tmp),'-I',str(ROOT),'-I',str(ROOT/'src'),str(tmp/'main.cpp'),str(SRC/'AirPhotoActions.cpp'),'-o',str(cls.binary)],capture_output=True,text=True)
  if result.returncode:raise AssertionError('host build failed:\n'+result.stderr[-5000:])
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def test_cover_transactions_and_photo_actions(self):
  result=subprocess.run([str(self.binary)],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)

if __name__ == '__main__': unittest.main()
