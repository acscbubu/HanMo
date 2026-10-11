# mbedTLS 候選

版本 1.5.8-hanmo-mbedtls-test-20261010。移除 Arduino-wolfSSL 5.7.2、wolfSSL 建置旗標及未啟用的 WolfsslCrypto 後端，使用 ESP-IDF 87912cd291 的 mbedTLS 3.6.5（選用 Apache-2.0）與 Arduino NetworkClientSecure。

SDK 從來源重建，開啟 TLS 1.3、相關密鑰交換及憑證日期檢查；TLS 1.2 保留。逐項差異在 build-config/esp32s3/mbedtls-config-delta.json；其餘硬體、Flash、PSRAM 設定不變。PSA 在連線前初始化。Arduino stop() 會清除 CA callback，因此每次連線前重新附加 SDK 內建 Mozilla 信任根。SNI 與憑證主機名稱由 Arduino 傳入 mbedTLS。

下載、KOReader、WeRead 與 Bridge 不再呼叫 setInsecure。未設定時間、憑證過期／尚未生效、網站名稱不符或未知簽發者時，連線會失敗；不會退回不驗證模式。SDK 信任根來自隨附固定版本 cacrt_all.pem，並非每天自動更新。私有 CA 可透過程式 setCACert 傳入；此候選尚無使用者 CA 匯入介面。

HTTP 重新導向預設不允許 HTTPS 降為 HTTP；跨 scheme/host/port 移除 Authorization、Proxy-Authorization、Cookie 與 Basic 驗證資料。307/308 搭配請求本文跨來源時拒絕跟隨。原有明確 http:// 服務仍是明文；本次沒有把所有自架服務強制改成 HTTPS。

連線重用、串流下載及既有短寫重試保留。TLS 耗時與記憶體尖峰尚未在 X4 Pro 量測；不能以編譯大小推定連線更快。Maruko 一致字級與日文排版優化保留。

官方資料：[mbedTLS 3.6.5 授權](https://github.com/Mbed-TLS/mbedtls/blob/mbedtls-3.6.5/LICENSE)、[ESP-IDF TLS 設定](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32s3/api-reference/protocols/mbedtls.html)。舊 wolfSSL 版本的授權義務不因新版替換而消失。
