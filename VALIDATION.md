# 候選驗證

版本 `1.5.8-hanmo-bold-status-20261010`。X4 Pro 與模擬器實際編譯成功。
映像 checksum、validation hash、ELF 對應及執行時版本字串已核對。
沿用前版由來源重建的 SDK；MAP 用到的66個 SDK archive SHA 全部一致，
11供應商原授權二進位及4標準工具鏈執行時分列。這次沒有重編 SDK。
ELF 有 mbedTLS TLS1.3 client、沒有 wolfSSL／wolfCrypt 符號或 LGPL probe 標記。

Maruko 真實 Bold TTF 離線重生8／10／12pt，各5642字元；三語1339個不同介面
翻譯字元全部直接由 Bold 提供，missing為0。歷史特殊符號以原Medium等來源補字。
公開範圍、內建字型、假名覆蓋、TLS設定的17個scoped cases：16通過、1跳過。
未全套重测舊遊戲，亦沒有重跑前版8349幀日文排版效能比較。

真實模擬器以合成SD測試：7種閱讀狀態列配置（同右、右側頁碼、分置左右、
隱藏Wi-Fi、隱藏電池、同左、Wi-Fi置中），及繁中一般／較大字級、英文、簡中
的首頁→設定→展開→返回→應用流程。共11流程41幀；閱讀7幀及UI20幀已目視檢閱。
確認右側Wi-Fi在百分比／電池左方，位置及隱藏選項保留，主介面粗體正常。
裝置修改歷史71列。詳細配置及範圍在 BUILD-VERIFICATION.json。

完整程式輸入逐byte對應 final build，generated gzip 的解壓內容一致；
gzip含時間戳，不宣稱跨環境完全位元重現。

以下繼承前版結果、這次未重跑：10項真實host TLS憑證／TLS1.2/1.3測試，
14項正式SecureClient／SecureHttpClient搭配transport stub的回歸，
3項來源守衛，Arduino／WebSockets實改並重新連結的LGPL驗證。
SDK／依賴lock及297個上游密鑰測試fixture SHA維持一致；保留前版LGPL驗證材料。

2026-10-10 建置工作未刷機。2026-10-11 使用者另回報已自行刷入，開機、閱讀、AirNote／AirPhoto及Wi-Fi正常。屬使用者回報，未取得裝置讀回SHA或逐項測試日誌；未涵蓋全部遊戲／日文教材、長時間穩定性、OTA、全部TLS端點或SD故障情境。正式發布與下載記錄見本倉庫Releases；本文件保留測試發生時的範圍。
後續已新增同程式版本的FULL封裝；見FULL-INSTALL.md及full-install/FULL-MANIFEST.json。FULL首次安裝未經實機驗收。網站pin須與實際公開版本及雜湊一致。
