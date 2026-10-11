# 來源、SDK 與韌體對應範圍

這份候選已替換為 Apache-2.0 mbedTLS，移除 wolfSSL／wolfCrypt 依賴。完整 HanMo、修改過的 Arduino／WebSockets／其他依賴來源、字型來源、筆順素材與建置腳本均包含。最終產物與逐檔 SHA 由發行清單記錄。

## 已能從來源建置

基準 MAP 的 82 個工具鏈／SDK archive：66 個 SDK 開源 archive 可由 `tools/rebuild-sdk.py` 實際重建，1 個 Arduino core archive 由應用建置重建。相依 NetworkClientSecure、WebSockets 等應用函式庫另外由 PIO 編譯。SDK 工程已補上固定版本的子模組及 managed components，包括 build graph 需要的 rmaker_common、NimBLE、MQTT、OpenThread 等。

`sdk-build/archive-targets.json` 列出 66 個必要輸出與來源。libmbedtls_2.a 是上游 mbedTLS 內層 libmbedtls.a 的框架命名；外層 ESP-IDF wrapper 仍叫 libmbedtls.a。兩者不可混用。

## 二進位及標準執行時的界線

10 個無線相關二進位 archive：libcore、libnet80211、libpp、libespnow、libmesh、libsmartconfig、libphy、libbtbb、libbtdm_app、libcoexist。另有 `libxt_hal.a`，ESP-IDF 自己也以預編譯 archive 連結，並未提供同目錄的完整 C／組合語言實作。它採 Tensilica MIT 告知，見 LICENSES/Xtensa-libhal-MIT.txt；不把它誤算成已重建來源。

這 11 個元件均附固定來源位置、二進位雜湊與授權資料。mbedTLS 候選不再採整體 GPLv3／wolfSSL 路線；各供應商 MIT／Apache 告知仍保留，LGPL 重建與重新連結材料另列。先前 wolfSSL 候選的待判定事項不可混套成新版，也不因替換而追溯消失。

4 個標準執行時 archive（libc、libm、libstdc++、libgcc）由固定版本 Xtensa GCC 工具鏈提供，附 newlib 授權與 GCC Runtime Library Exception 告知；本次未重建編譯器。

## 驗證意義

來源樹存在 ≠ archive 已重建；archive 已重建 ≠ 最終 BIN 確實連結；BIN 可編譯 ≠ 可在實機正常運作。本候選分別保存來源檔案清單、SDK 重建結果、最終 MAP 與 BIN／ELF 對應證據。這不是已发布網站版本的位元完全重現，也不是再散布／GitHub 放行。
