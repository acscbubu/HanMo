from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[2];language=sys.argv[1] if len(sys.argv)>1 else 'zh';SD=ROOT/'build/video'/language/'sd';OUT=ROOT/'build/video'/language
for folder in ['.crosspoint','AirNote','books','images']:(SD/folder).mkdir(parents=True,exist_ok=True)
def save(name,obj):(SD/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
zh=language!='en'
settings={'language':'ZH_TW' if zh else 'EN','onboardingVersion':1,'uiTheme':4,'homeLabel':'我的 X4 Pro' if zh else 'My X4 Pro','homeShortcut1':1,'homeShortcut2':7,'homeShortcut3':12,'homeShortcut4':11,'homeShortcut5':4,'homeShortcut6':6,'sleepTimeout':0,'autoSleepMinutes':0,'hiddenAppsMask':0}
save('.crosspoint/settings.json',settings);save('.crosspoint/state.json',{'showBootScreen':False})
save('.crosspoint/wifi.json',{'lastConnectedSsid':'Simulator WiFi (fake)','credentials':[{'ssid':'Simulator WiFi (fake)','password':'','password_len':0,'password_crc32':0}]})
text=('在安靜的畫面上，讀回自己的日常。\n\nAirNote 可以保存想法、閱讀筆記與待辦事項。\n\n今天的練習：留一點時間給自己，讀完一段文字，再記下一個想法。\n'*5 if zh else 'A quieter space for your everyday ideas.\n\nAirNote keeps thoughts, reading notes and checklists on your reader.\n\nToday: take a moment, read a page and write down one idea.\n'*5)
name='閱讀筆記.txt' if zh else 'Reading notes.txt';(SD/'AirNote'/name).write_text(text,encoding='utf-8')
todo='出門準備.txt' if zh else 'Travel checklist.txt';items=['閱讀器充電','帶充電線','下載書籍','準備水瓶','查看路線'] if zh else ['Charge the reader','Pack a USB cable','Download a book','Fill the water bottle','Check the route']
(SD/'AirNote'/todo).write_text(todo[:-4]+'\n\n#!AirNote-Todo:1\n'+'\n'.join(('[x] ' if i==1 else '[ ] ')+x for i,x in enumerate(items))+'\n',encoding='utf-8')
(SD/'AirNote/.order').write_text(todo+'\n'+name+'\n',encoding='utf-8')
book='慢慢閱讀.txt' if zh else 'Slow reading.txt';(SD/'books'/book).write_text(text,encoding='utf-8')
save('.crosspoint/recent.json',{'books':[{'path':'/books/'+book,'title':'慢慢閱讀' if zh else 'Slow reading','author':'XTEINK Demo','coverBmpPath':''}]})
print(OUT)
