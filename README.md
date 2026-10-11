# 翰墨 HanMo · X4 Pro

HanMo 是 XTEINK X4 Pro 的非官方客製韌體，在 CrossMux／CrossPoint 基礎上，加入 **AirNote 筆記、AirPhoto 相片整理、個人化首頁與繁體中文日文學習**。

這份來源是 `1.5.8-hanmo-bold-status-20261010` 的公開來源。2026-10-11 使用者回報已刷入，開機、閱讀、AirNote／AirPhoto 與 Wi-Fi 均正常；這是使用者基本實機驗證，不等同全部功能或長時間測試。已改用 mbedTLS 1.2/1.3，移除 wolfSSL／wolfCrypt 依賴；HTTPS 預設檢查網站名稱、信任鏈及有效日期。使用前請先設定正確時間。詳 [TLS 變更](TLS.md) 與 [來源與 SDK 對應](SOURCE-COVERAGE.md)。

網站：[翰墨 HanMo](https://www.smartnavigator.com.au/hanmo/zh.html)。請核對下載檔的完整版本名稱及 SHA256。

## 為什麼使用 HanMo？

- **AirNote**：一般文字筆記與待辦清單；可在裝置、瀏覽器編輯與排序，儲存在 SD 卡。裝置鍵盤沒有中文輸入法，中文請從瀏覽器輸入。
- **AirPhoto**：瀏覽器匯入相片、裁切或保留全圖、調整亮度／對比與黑白轉換；裝置提供縮圖／檔名清單，可選開機、休眠或關機封面。
- **自己的首頁**：放上名字或短句，調整名字與時鐘的左／中／右位置或隱藏，選擇常用捷徑；首頁文字限 23 UTF-8 位元組。
- **順手的操作**：下拉快捷按鈕可指定功能；EPUB 左右各上／中／下六個觸控區可設定操作。部分選項依主題與閱讀格式而定。
- **日文學習**：以日文卡片搭配繁體中文解說，練習假名、筆順、單字、短句與每日複習。短句含九類各 30 情境；没有音訊、手寫辨識或正式語言程度認證。

- **一致的粗體介面**：首頁、選單、設定共用由 Maruko Gothic Bold TTF 預先轉換的粗體字型，無需在裝置即時解析 TTF。詳 [字型說明](UI-FONTS.md)。

閱讀器右側的 Wi-Fi 與電量同時顯示時，順序為 **Wi-Fi → 百分比 → 電池圖示**。既有左／右／隱藏選項保留；Wi-Fi 另有置中選項。可在設定 → 閱讀器 → 自定義狀態列調整。

## 三種韌體比較

| 功能 | XTEINK 官方 | CrossMux 上游 | HanMo 本版 |
|---|---|---|---|
| 主要定位 | 原廠閱讀與 App／XT-Cloud 整合 | 開源閱讀、網路工具與輕量應用 | 延伸閱讀，加入筆記、相片與個人化流程 |
| 筆記與待辦 | 同等整合流程未確認 | 查閱文件未列出 AirNote 流程 | AirNote 編輯、勾選及排序 |
| 相片管理 | 圖片與個人化顯示 | AirPage 傳送圖片及休眠封面 | AirPhoto 轉換、裁切、預覽、縮圖／清單 |
| 首頁顯示自己的名字 | 未確認同等設定 | 查閱設定未見同等欄位 | 自訂名字／短句，中文可用網頁輸入 |
| 首頁文字左右位置 | 未確認同等設定 | 主題與 INX 版面選項 | 名字、時鐘各選左／中／右／隱藏 |
| 左右快捷按鈕 | 觸控與實體鍵；同等配置未確認 | 有側鍵前後頁順序設定 | 下拉快捷列左／中／右各位置可指定功能 |
| 閱讀觸控區 | 觸控與實體翻頁 | 觸控閱讀開關 | EPUB 六區自訂快捷操作 |
| 日文學習 | 同等流程未確認 | 查閱文件未列出此學習流程 | 假名、筆順、單字、短句與每日複習；繁中解說 |

比較是文件與本版來源核對，不是三套韌體的完整實機測試。「未確認」不代表一定沒有。公開頁面查閱日期：2026-10-09；[X4 Pro 官方介紹](https://www.xteink.com/products/xteink-x4-pro-pocket-ereader)、[CrossMux 應用說明](https://github.com/0x1abin/crossmux/blob/main/src/activities/apps/README.md)、[CrossMux 設定來源](https://github.com/0x1abin/crossmux/blob/main/src/SettingsList.h)。

## 安裝檔怎麼分？

| 類別 | 內容與命名 |
|---|---|
| 完整 HanMo | `HanMo-X4Pro-<version>-FULL.bin`；首次安裝用，須有該版本的分區、開機元件與完整驗證 |
| HanMo 更新檔 | `HanMo-X4Pro-<version>-UPDATE.bin`；僅應用程式，須確認既有分區與實際啟動槽 |
| XTEINK 官方 | 從 [XTEINK 官方](https://www.xteink.com/) 取得，保留官方版本及命名；本專案不附原廠裝置備份 |

更新BIN、完整SOURCE及文件補件見 [GitHub Releases](https://github.com/acscbubu/HanMo/releases/tag/1.5.8-hanmo-bold-status-20261010)。不可把 UPDATE 改名成 FULL。自動化工作未刷寫裝置；使用者已自行刷入並回報上述基本功能正常。

安裝請先讀 [更新與備份說明](INSTALL.md)；版本改動見 [發布說明](RELEASE-NOTES.md)，問題回報見 [支援與回報](SUPPORT.md)。驗證細節見 [驗證範圍](VALIDATION.md)。

## 原始碼與建置

見 [BUILDING.md](BUILDING.md)、[SOURCE-COVERAGE.md](SOURCE-COVERAGE.md)、[LGPL 重新連結](LGPL-RELINK.md)。`hanmo/` 為應用程式，`dependencies/` 為固定版本依賴，`sdk-source/` 與 SDK 建置配方提供對應材料。完整路徑與檔案雜湊以清單為準。

## 支持 HanMo 開發

[☕ Buy Me a Coffee · angusbeefx](https://buymeacoffee.com/angusbeefx)

## 支持上游作者

感謝 CrossMux、CrossPoint、CrossInk、FreeInk 與 CrossPlay，以及所有依賴與字型作者。可透過 [CrossPoint 上游贊助入口](https://app.royalty.dev/crosspoint-reader/crosspoint-reader) 支持其作者，或到各上游專案查看最新贊助方式。HanMo 與上游贊助各自獨立。

## 授權與致謝

HanMo 應用程式沿用 [MIT 授權](LICENSE)；mbedTLS 選用 Apache-2.0，Arduino／WebSockets 保留 LGPL。完整來源與重新連結材料一併提供，各元件條款仍適用。OFL 字型與 CC BY-SA 3.0 筆順圖資各有獨立聲明，見 [第三方告知](THIRD-PARTY-NOTICES.md) 與 [素材授權](ARTWORK-LICENSE.md)。贊助不改變授權条件。此專案並非 XTEINK 或上游作者的官方產品。
