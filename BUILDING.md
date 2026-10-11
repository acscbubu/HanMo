# 建置 HanMo 與 SDK

驗證環境：Linux／Ubuntu WSL、Python 3.12、PlatformIO Core 6.2.0、CMake 3.30.9、Ninja 1.11.1.4、Xtensa GCC 14.2.0+20251107。預留約 12 GB 空間。第一次安裝建置工具需網路；固定來源與編譯設定包含在本專案。

ESP-IDF commit 是 `87912cd291`（原始碼版本 5.5.2）。Arduino SDK 套件標籤仍為 `5.5.0+sha.87912cd291`，兩者命名不同；不要只靠套件標籤另抓 IDF 5.5.0。

```sh
# 在此 README 所在目錄執行；先安裝系統 C/C++ 編譯器供 host 測試。
python3.12 -m venv /tmp/hanmo-tools
/tmp/hanmo-tools/bin/pip install -r requirements-sdk.txt -r hanmo/requirements.txt platformio==6.2.0

# 第一階段安裝 PIO 工具及 SDK 框架，不進行韌體編譯。
# 本版要求 TLS1.3 SDK；原廠 SDK 僅供套件安裝，不能編譯最終應用。
/tmp/hanmo-tools/bin/python tools/build-delivery.py --install-only --work-dir /tmp/hanmo-bootstrap --core-dir /tmp/hanmo-pio --pio /tmp/hanmo-tools/bin/pio --jobs 4

# 第二階段從隨附來源重建 66 個必要開源 SDK archives，並安裝進隔離 PIO。
# 另有建置相依 archive 一併產生；輸出 sdk-result.json 列實際安裝檔及 SHA。
/tmp/hanmo-tools/bin/python tools/rebuild-sdk.py --work-dir /tmp/hanmo-sdk-build --core-dir /tmp/hanmo-pio --jobs 4

# 最後在全新工作目錄重新編譯 HanMo／Arduino／各依賴。
/tmp/hanmo-tools/bin/python tools/build-delivery.py --work-dir /tmp/hanmo-final --core-dir /tmp/hanmo-pio --pio /tmp/hanmo-tools/bin/pio --jobs 4
```

上述命令必須依序執行；不要在同一 PIO 環境一邊安裝 SDK、一邊連結最終韌體。最終應用輸出：`/tmp/hanmo-final/hanmo/.pio/build/x4pro_custom/firmware.bin`，同目錄保存 ELF 與 MAP。這是 UPDATE 應用映像，沒有完整首次安裝映像，不會自動刷機。

`sdk-build/` 是針對此韌體連結元件的重建配方，不是 Espressif 所有型號／Matter／語音套件的全套重建。它使用上游來源與相同 X4 Pro DIO／Octal PSRAM 設定；重建前逐一比對 sdkconfig.h 全部 CONFIG 定義，不相符就停止。Kconfig.snapshot 保留未連結選配元件的既有設定常數與舊名稱對應，沒有換成另一套記憶體配置。

Arduino SDK 原始框架提供其餘包裝檔、標頭、連結脚本與工具；重建 archive 覆蓋後才產生最終候選。`binary-system-libraries/` 的 11 個元件仍是供應商二進位，不是假稱由來源重建。GCC/newlib 標準執行時由固定版工具鏈提供。詳 SOURCE-COVERAGE.md。

要修改來源或依賴，請編輯本專案後使用新的 `--work-dir`；舊工作目錄不會自動同步所有應用檔。不要把上一次的 BIN 當作新來源成果。建置成功代表能編譯及連結，不代表位元完全一致或已完成實機測試。

介面字型來源及重建命令見 [UI-FONTS.md](UI-FONTS.md)。產生後再進行全新的最終建置；勿直接修改 generated headers。

TLS1.3 與憑證日期驗證差異見 TLS.md；重建程式會同時安裝對應 sdkconfig.h，不能只換 archive 或只改巨集。


## 可選 host 網路測試

另需系統 gcc/g++、CMake、Ninja、Python cryptography。測試會在指定暫存目錄產生
一次性 CA／私鑰，請勿上傳它們。host mbedTLS 使用自身預設 crypto 設定，不取代實機驗收。

```sh
cmake -S sdk-source/esp-idf/components/mbedtls/mbedtls -B /tmp/hanmo-host-tls -G Ninja -DENABLE_TESTING=OFF -DENABLE_PROGRAMS=ON -DCMAKE_C_FLAGS=-Wno-error=discarded-qualifiers
cmake --build /tmp/hanmo-host-tls --target ssl_client2 -j 4
python3 tools/test-tls-engine.py --work-dir /tmp/hanmo-tls-tests --client /tmp/hanmo-host-tls/programs/ssl/ssl_client2
python3 tools/test-tls-transport.py --work-dir /tmp/hanmo-policy-tests
```

若修改版本，同時更新 VERSION 與 hanmo/platformio.ini 的 x4pro_custom 版本後綴。
build-delivery.py 會確認實際 BIN 含有 VERSION，避免檔名與装置顯示名稱不同。
