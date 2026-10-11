# X4 Pro 更新與備份

適用版本：`1.5.8-hanmo-bold-status-20261010`。同版本另已提供首次安裝用FULL，會清除裝置設定，請讀 [FULL安裝說明](FULL-INSTALL.md)。以下步驟僅適用保留既有設定的UPDATE。

1. 備份記憶卡的書籍、AirNote、AirPhoto及學習進度；另保存現有可用韌體及裝置備份。
2. 確認機型為 XTEINK X4 Pro，既有分區配置與本版相容。若從原廠首次安裝或不確定分區，先停在這一步；不要把 UPDATE 當作完整安裝檔。
3. 選擇支援這個配置的更新工具／本機選檔入口，載入 `HanMo-X4Pro-1.5.8-hanmo-bold-status-20261010-UPDATE.bin`（7,419,824 bytes）。確認完整版本及下方SHA256。
4. 使用應用程式更新模式。USB手動寫入前必須读取實際partition／otadata並選正確作用中槽；檔名不代表固定寫入地址。不要為更新而清除NVS／使用出廠模式。
5. 完成後重新開機，在系統資訊確認版本；測試閱讀、Wi-Fi、AirNote保存／讀回、AirPhoto開啟。HTTPS需要正確日期時間。

UPDATE SHA256：`9baa09af3fae76dda4e71d847a7369389650a9337a979b3dca3ca2aa432e2e4a`。

介面採Maruko Bold。設定 → 閱讀器 → 自定義狀態列可調位置及隱藏；Wi-Fi與電量同在右側時為Wi-Fi → 百分比 → 電池。書本內文字型另行選擇。

回復應使用事前保存且匹配該裝置分區／啟動槽的映像。新舊版本SD格式可能不同，回復前保留兩份SD資料，不要覆蓋唯一備份。請勿下載或分享別人的NVS／原廠私人dump。
