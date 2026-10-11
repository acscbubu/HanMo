# 2026-10-04 Wi-Fi 同列／五十音卡片

使用者截圖指定資訊看板上方「電量百分比／電池」那一列。原 src/GlobalWifiStatus.h:7 的22px保留列，以及 ActivityManager.cpp:64 的 renderer reserve 正是縮小內容的原因。本版設定 reserve=0、維持完整800px視窗與原生觸控座標，讓各主題 drawHeader／drawHomeHeader 提供既有狀態行內的20x18水平位置；電池／百分比有8px間距。左／中／右／隱藏值不變。INX最近書籍首頁沿用底部電量列；閱讀器沿用其既有閱讀狀態列；沒有狀態列的全螢幕內容不覆蓋正文。灰階只清除圖示小區域，不清空整列；離線為斜線，不宣稱能接通外網。

入口：應用程式 → 日文學習 → 五十音卡片 → 全部46音／指定行。基本平假名與片假名各46字（不含已不常用的ゐ／ゑ）；Romanization採shi/chi/tsu/fu，を寫wo並註明助詞讀o，は／へ加助詞讀音提示。例字及繁中詞義自行編寫，不匯入他人插圖或音檔。換卡、左右滑、按鍵、羅馬字提示開關與無重複shuffle；不含音訊、筆順或測驗評分，其他六分類維持教材準備中。

課表校對參考：Japan Foundation Erin syllabary https://www.erin.jpf.go.jp/en/extra/syllabary/ 及官方對照PDF https://www.erin.jpf.go.jp/materials/extra/syllabary/download/erin_aiueo_romaji.pdf 。資料在 data/japanese/kana-basic.json；scripts/generate_kana_data.py 生成固定constexpr表。開始選行用13筆固定rows，牌序46bytes固定array，無逐卡heap；子活動走checked allocation。renderer原有font registry加入三項，字形在Flash，不配置整份TTF或動態教材buffer。卡片採直向，退出恢復原方向。

日文字型：Maruko Gothic CJK JP Medium，上游 https://github.com/max32002/maruko-gothic commit 97e9dd4a2fdde58084dde8d022de253f8d8415e9；TTF SHA256 387d649001a83bb0c45021d19e726ff9dd741013e0f182a3bd0e273243b2074f。保留SIL OFL1.1與上游README，scripts/build_kana_fonts.py只產生52pt基本假名／20pt例字／12pt選行標籤單色子集。命名HanMo Kana subset，字型不是筆順範本；不更改全系統中文字型。build用.venv-fonts/bin/python；原檔在lib/EpdFont/builtinFonts/source/HanMoKana，不把20MB原始TTF放進韌體。

驗收：資訊看板上下位置回復、Wi-Fi與電量同列且無重疊；左右中隱藏；日文46組與選行、最後一張循環、shuffle完整不重複、提示切換、返回與恢復方向。主機／模擬器檢查不代表實機紙感、刷新或續航已驗收。
