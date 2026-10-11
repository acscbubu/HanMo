# HanMo X4 Pro — 1.5.8-hanmo-bold-status-20261010

韌體建置日期2026-10-10；2026-10-11補充文件與使用者實機回報。公開發布日期2026-10-11，檔名／韌體版本保持不變。

- 主頁、選單、設定改用Maruko Gothic CJK JP真實Bold，主要字級維持一般10pt／較大12pt。
- 閱讀列同在右側時順序為Wi-Fi → 百分比 → 電池，保留位置與隱藏選項。
- 保留AirNote／AirPhoto、個人化首頁、日文單字／短句／每日複習。
- 與較早公開版相比，本來源已移除CROSSPET入口、Work Hub／SKU及西洋棋，保留其他已列功能；TLS改用mbedTLS1.2／1.3，保留網站名称／CA／有效日期驗證。

使用者2026-10-11回報已刷入且開機、閱讀、AirNote／AirPhoto、Wi-Fi正常。自動化證據為兩目標編譯、16項通過／1略過、11模擬器流程41幀。詳VALIDATION.md，沒有宣稱全部功能或硬體長測通過。

僅UPDATE，沒有FULL／出廠映像。下載應同時提供：

| 檔案 | bytes | SHA256 |
|---|---:|---|
| HanMo-X4Pro-1.5.8-hanmo-bold-status-20261010-UPDATE.bin | 7419824 | `9baa09af3fae76dda4e71d847a7369389650a9337a979b3dca3ca2aa432e2e4a` |
| HanMo-X4Pro-1.5.8-hanmo-bold-status-20261010-SOURCE.tar.gz | 263092770 | `9aedac04f101989a48912af3adc698981165ae8c92724b3c74d582f86a0be85b` |

SOURCE是2026-10-10封存的完整對應來源／依賴／授權／建置及LGPL重新連結材料。本文件補件不改BIN或程式。發布時同時附2026-10-11文件補件ZIP及其SHA，保留SOURCE原雜湊；若合併成新來源包，使用不同檔名並重生清單，不能沿用原SOURCE SHA。

不應只提供GitHub自動產生的Source code ZIP而遺漏本完整SOURCE包所含依賴。新repo tag須對應实际來源及文件；正式下載連結在遠端建立且核對後填入，不預先放猜測網址。
