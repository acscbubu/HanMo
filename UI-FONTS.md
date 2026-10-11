# Maruko 介面字型

依使用者要求，主要介面文字統一字級：預設標題、選單、設定項皆為 10pt；選擇較大介面字級時一起改為12pt。電量、頁碼、次要說明保留緊湊字級。這裡 pt 是轉換器的字級，並非螢幕像素；不是把日文教學大字卡或閱讀內文也縮成一樣。

首頁、選單、設定與其他使用共用 UI 字型 ID 的頁面，改用 Maruko Gothic CJK JP Bold 的預先點陣化字型。8／10／12 pt 各保留 5,642 個字元；目前三種介面翻譯的 1,339 個不同字元全部由 Maruko 支援。這不是收錄所有中日文字；任意罕用人名、擴充漢字仍可能缺字。JP 字形與台灣常用字形可能不同。

以現有常用 CJK 子集、原介面外文字元、全部翻譯及基本平／片假名組成字元集。Bold 不含的歷史特殊符號先使用 Maruko Medium 補字，其餘使用原有 Noto／Ubuntu 來源；目前全部介面翻譯字元均直接由 Bold 提供。全部保留原授權。Bold 同時供一般／粗體 UI 請求使用，採用作者提供的真實 Bold TTF，也沒有改讀書內文的字型選擇、筆順圖資或遊戲專用字型。

TTF 在電腦上用 FreeType 轉成未壓縮的 1-bit 內建字圖；裝置直接讀字圖，不新增 TTF 解析、字圖解壓縮或 SD 字型讀取。這避免這些額外運算，但不等於已量測整機更快。實機顯示、殘影與按鍵延遲仍需確認。

官方 App 的版本紀錄提供「製作並推送 X4 Pro 系統字型」及 `.xtfont`。本候選參考其先製作字型的流程，輸出 HanMo 原有 EpdFont 格式；不能直接載入官方 `.xtfont`，也不是把任意 TTF 放 SD 卡就能換介面。

```sh
# 在 hanmo/，使用已安裝 requirements 的 Python；生成器會核對全部必要字元。
python scripts/generate_ui_fonts.py
```

生成清單、TTF SHA256 與三份輸出 SHA256：`hanmo/docs/ui-font-build.json`。驗證工具使用 fonttools 4.59.0、freetype-py 2.5.1；不同 FreeType／工具版本可能產生不同點陣。重建不要求逐位元相同。

來源：[Maruko Gothic](https://github.com/max32002/maruko-gothic)（SIL OFL 1.1），[官方 App 更新紀錄](https://apps.apple.com/us/app/xteink/id6754496214)。原始 TTF、OFL 與版權原文位於 `hanmo/lib/EpdFont/builtinFonts/source/HanMoKana/`。

Bold 來源固定於上游 commit `97e9dd4a2fdde58084dde8d022de253f8d8415e9`。原始檔、下載來源、SHA256 及原 OFL 見 `hanmo/docs/maruko-bold-source.json`、`MarukoGothicCJKjp-Bold.ttf` 與 `Maruko-Bold-OFL.txt`。
