# HanMo X4 Pro FULL · 2026-10-11 包裝補件

韌體版本仍是 `1.5.8-hanmo-bold-status-20261010`。FULL 中的主程式與已發布 UPDATE 完全相同，沒有重新編譯或更動功能。

## 安裝前

- 僅適用 **XTEINK X4 Pro，ESP32-S3／16MB Flash**。
- FULL 供首次安裝或重裝；從 `0x0` 寫入完整16MB，會覆蓋原有韌體、分區、NVS、Wi-Fi及裝置內設定。記憶卡不在此映像內，仍建議先備份SD內容。
- 已安裝相容HanMo而只想升級，請選UPDATE。
- 官網選「HanMo 完整檔」，或下載FULL.bin後以「手動選檔」載入。使用桌面Chrome／Edge，先備份原裝置，確認清除設定的提示再開始。
- 此FULL完成封裝／校驗／瀏覽器模擬流程檢查；**未經首次安裝實機驗收**。使用者先前確認的是相同UPDATE主程式的基本功能，不能當作FULL安裝測試。

## 重組相同檔案

將本補件解壓縮到一個資料夾，另下載同版本的UPDATE.bin。在本資料夾執行（Python 3，僅標準函式庫）：

```sh
python3 build-full.py --app /path/to/HanMo-X4Pro-1.5.8-hanmo-bold-status-20261010-UPDATE.bin --out /path/to/HanMo-X4Pro-1.5.8-hanmo-bold-status-20261010-FULL.bin
```

輸出必須是新檔案。腳本驗證每個輸入雜湊、ESP32-S3映像校驗／SHA、分區MD5及OTA初始槽。所有未配置位元組填FF，NVS、未使用的app1與coredump為空白。FULL不含私人dump或預設帳密。

## 元件來源與授權

`FULL-MANIFEST.json` 記錄來源、位移與逐檔SHA。bootloader和分區取自發布UPDATE的同次 `x4pro_custom` 建置，並另行重現：

- bootloader：官方Arduino ESP32 SDK `5.5.0+sha.87912cd291` 中 `esp32s3/bin/bootloader_dio_80m.elf`，DIO／80MHz／16MB。使用pioarduino esptool套件5.1.2轉換，逐位元等於既有bootloader.bin。**此處重現的是ELF轉BIN，沒有宣稱重新編譯bootloader C來源**。ESP-IDF bootloader採Apache-2.0，附原條款；原始來源在完整SOURCE的 `sdk-source/esp-idf/components/bootloader*`，相關SDK配方在 `sdk-source/arduino-sdk`。
- partitions：由來源 `hanmo/partitions.csv` 與 `dependencies/arduino-core-3.3.7/tools/gen_esp32part.py` 產生，重生後相同。
- boot_app0：來源 `dependencies/arduino-core-3.3.7/tools/partitions/boot_app0.bin`，採上游OTA初始化資料，CRC核對為初始app0。保留Arduino原授權。
- build-full.py：本次HanMo包裝腳本，MIT。
- UPDATE的完整程式、依賴、SDK来源、字型和圖資授權與LGPL材料，見同Release的SOURCE.tar.gz及DOCS補件；本小型補件不是它們的替代品。

轉換bootloader的等效指令：

```sh
python esptool.py --chip esp32s3 elf2image --flash-mode dio --flash-freq 80m --flash-size 16MB -o bootloader-rebuilt.bin bootloader_dio_80m.elf
python /path/to/SOURCE/dependencies/arduino-core-3.3.7/tools/gen_esp32part.py partitions.csv partitions-rebuilt.bin
```

下載：[HanMo Release](https://github.com/acscbubu/HanMo/releases/tag/1.5.8-hanmo-bold-status-20261010)。請保留原SOURCE／DOCS與此FULL補件，各元件原授權仍適用。
