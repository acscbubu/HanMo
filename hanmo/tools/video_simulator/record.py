import os,sys,json,time,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
# Coordinates belong only to the fixed 480x800 simulator video target.
H='TAP:440,770';A='TAP:120,770'
def scene(key,zh,en,zc,ec,events,start=7,duration=7):return dict(key=key,zh=zh,en=en,zc=zc,ec=ec,events=events,start=start,duration=duration)
SCENES=[
scene('home','你的 X4 Pro','Your X4 Pro','熟悉的閱讀器，自己的首頁。\n下方捷徑可依習慣配置。','A familiar reader, made yours.\nChoose the shortcuts on your home screen.',[],3),
scene('files','書籍與檔案','Books & files','從 SD 卡開啟書籍和資料夾。','Browse books and folders on the SD card.',[(3000,'TAP:40,770')],4),
scene('airnote','AirNote 隨身筆記','AirNote notebooks','筆記與待辦清單集中在一起。\n可從裝置設定網頁新增、編輯。','Keep notes and checklists together.\nCreate and edit them on the device web page.',[(3000,A)],4),
scene('todo','完成，就打勾','Check it off','點擊事項切換完成狀態。\n進度固定在標題右側。','Tap an item to mark it complete.\nProgress stays beside the title.',[(3000,A),(5000,'TAP:130,130'),(9000,'TAP:100,130')],7),
scene('order','直接移到指定位置','Move directly to a position','長按確認鍵選取目前事項，\n再點選目的位置。','Hold Confirm to pick up the selected item,\nthen tap its destination.',[(3000,A),(5000,'TAP:130,130'),(8500,'ENTER:900'),(12000,'TAP:100,360')],7,9),
scene('note','像讀書一樣讀筆記','Read your notes like a book','文字筆記可直接在閱讀器翻閱。','Read your saved text on the reader.',[(3000,A),(5000,'TAP:130,190')],7),
scene('apps','應用程式','Applications','閱讀、筆記與日常小工具。','Reading, notes and everyday utilities.',[(3000,'TAP:360,770')],4),
scene('display','顯示設定','Display settings','畫面、首頁與應用程式選單，\n集中調整。','Personalise your screen, home layout\nand application menu in one place.',[(3000,H)],4),
scene('screens','開機、關機與休眠','Boot, power off & sleep','三種畫面分別設定，\n可選擇自己的 BMP 圖片。','Choose each screen separately,\nincluding your own BMP images.',[(3000,H),(5000,'TAP:120,185')],7),
scene('shortcuts','首頁捷徑選單','Home shortcut menu','工作數據等常用應用，\n也能放到首頁。','Add Dashboard and other everyday apps\nto your home shortcuts.',[(3000,H),(5000,'TAP:120,630')],7),
scene('hometext','主頁文字選單','Home text menu','調整主頁文字、電量與時鐘位置。','Arrange your home label, battery and clock.',[(3000,H),(5000,'TAP:120,686')],7),
scene('appmenu','應用程式選單','Application menu','依照自己的習慣選擇顯示項目。','Choose which applications are visible.',[(3000,H),(5000,'TAP:120,742')],7),
scene('reader','閱讀器設定','Reader settings','字體、閱讀方向與狀態列，\n依照閱讀習慣調整。','Adjust fonts, orientation and the status bar\nto suit the way you read.',[(3000,H),(5000,'TAP:180,112')],7),
scene('gestures','輕觸與手勢','Taps & Gestures','位於「設定 → 閱讀器」。\n影片展示設定，實機手勢仍需測試。','Located in Settings > Reader.\nGesture sensitivity needs physical-device testing.',[(3000,H),(5000,'TAP:180,112'),(7000,'TAP:120,352')],9),
scene('controls','操作設定','Controls','按鍵、觸控與螢幕快捷列。','Buttons, touch controls and screen shortcuts.',[(3000,H),(5000,'TAP:300,112')],7),
scene('panel','六個螢幕快捷列按鈕','Six screen shortcut buttons','配置下拉快捷列與六個輕觸區域。','Configure pull-down shortcuts\nand six reading tap zones.',[(3000,H),(5000,'TAP:300,112'),(7000,'TAP:120,185')],9),
scene('system','自己的名稱與版本','Your name. Your version.','自訂熱點、版本名稱，\n也能選擇是否顯示版本號碼。','Customise the hotspot and version name.\nChoose whether the version number is shown.',[(3000,H),(5000,'TAP:420,112')],7),
scene('standby','閱讀以外的時刻','Between reading sessions','待機時鐘，保留簡潔的日常。','A simple clock for the moments between books.',[(3000,'BACK')],4),
]
def run(lang,s):
 out=ROOT/'build/video'/lang;env=os.environ.copy();env.update(CROSSPOINT_SIM_SD=str(out/'sd'),XTEINK_VIDEO_LANGUAGE=lang,SDL_AUDIODRIVER='dummy',SDL_VIDEO_WINDOW_POS='0,0',SDL_RENDER_DRIVER='software',CROSSPOINT_SIM_INPUT_SCRIPT=';'.join(f'{t}:{e}' for t,e in s['events'])+f";{(s['start']+s['duration']+2)*1000}:QUIT",CROSSPOINT_SIM_SCREENSHOTS=f"{(s['start']+1)*1000}:{out}/{s['key']}.bmp")
 subprocess.run([sys.executable,str(ROOT/'tools/video_simulator/seed.py'),lang],stdout=subprocess.DEVNULL,check=True)
 with (out/(s['key']+'.log')).open('w') as log:
  p=subprocess.Popen([str(ROOT/'.pio/build/simulator_x4pro_video/program')],cwd=out,env=env,stdout=log,stderr=log)
  try:
   time.sleep(s['start'])
   wid=subprocess.check_output(['xdotool','search','--name','Simulator -'],text=True).splitlines()[0]
   geom=dict(line.split('=',1) for line in subprocess.check_output(['xdotool','getwindowgeometry','--shell',wid],text=True).splitlines() if '=' in line)
   origin=geom['X']+','+geom['Y']
   subprocess.run(['xdotool','mousemove','1279','899'],check=True)
   subprocess.run(['ffmpeg','-y','-loglevel','error','-f','x11grab','-framerate','12','-video_size','480x800','-i',os.environ['DISPLAY']+'+'+origin,'-t',str(s['duration']),'-c:v','libx264','-preset','ultrafast','-crf','18','-pix_fmt','yuv420p',str(out/(s['key']+'-raw.mp4'))],check=True)
   p.wait(timeout=8)
  finally:
   if p.poll() is None:p.terminate();p.wait(timeout=5)
 subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(out/(s['key']+'.bmp')),str(out/(s['key']+'.png'))],check=True)
if __name__=='__main__':
 lang=sys.argv[1];key=sys.argv[2] if len(sys.argv)>2 else 'all'
 if len(sys.argv)>3 and sys.argv[3]=='inside':run(lang,next(s for s in SCENES if s['key']==key))
 else:
  for s in SCENES:
   if key not in ('all',s['key']):continue
   subprocess.run(['xvfb-run','-a','-s','-screen 0 1280x900x24',sys.executable,__file__,lang,s['key'],'inside'],check=True)
   print(lang,s['key'],flush=True)
