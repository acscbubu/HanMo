# Webserver Endpoints

This document describes the HTTP, WebSocket, WebDAV, and discovery endpoints
available while CrossPoint Reader is in File Transfer or Calibre Wireless mode.

- HTTP server: port 80
- WebSocket upload server: port 81
- UDP discovery listener: port 8134
- WebDAV: port 80, handled by the same HTTP server

Examples use `crosspoint.local`. If mDNS does not resolve on your network, use
the IP address shown on the device screen.

## HTTP Pages

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/` | Home/status page |
| `GET` | `/files` | File manager page |
| `GET` | `/device` or `/device/` | Wi-Fi, OPDS, AirPage and AirNote tools |
| `GET` | `/settings` | System and reader settings page |
| `GET` | `/fonts` | SD-card font manager page |
| `GET` | `/js/jszip.min.js` | JavaScript asset used by the file manager |

The routes are identical in every firmware. Both page locales are embedded;
Simplified-Chinese device UI selects `zh-CN`, and every other UI language uses
the English pages. Page locale follows the UI language directly.

The main menu defaults to Home, File Managers, Device, Fonts, Settings.
`/device` reuses the compressed settings/tool shell and selects its content by
pathname; it does not fetch system settings. `/settings` fetches only settings.
The tool anchors are `/device#wifi`, `/device#opds`, `/device#airpage` and
`/device#airnote`. Legacy `/settings#airnote` (and the other tool anchors)
redirects to its corresponding Device URL. Main-menu browser order uses a new
`crossmux.nav.pages.v2` key; other drag-order preferences are preserved.

## Device Status

### `GET /api/status`

```bash
curl http://crosspoint.local/api/status
```

Response:

```json
{
  "version": "1.0.0",
  "ip": "192.168.1.100",
  "mode": "STA",
  "rssi": -45,
  "freeHeap": 123456,
  "uptime": 3600,
  "device": "X4"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `version` | string | Firmware version |
| `ip` | string | Device IP address |
| `mode` | string | `"STA"` for joined Wi-Fi or `"AP"` for hotspot mode |
| `rssi` | number | Wi-Fi RSSI in dBm; `0` in AP mode |
| `freeHeap` | number | Free heap in bytes |
| `uptime` | number | Seconds since boot |
| `device` | string | `"X3"` or `"X4"` hardware detection |

## File Management

### `GET /api/files`

Lists files and folders under a directory.

```bash
curl "http://crosspoint.local/api/files?path=/Books"
```

Query parameters:

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `path` | No | `/` | Directory to list |

Response:

```json
[
  {"name":"MyBook.epub","size":1234567,"isDirectory":false,"isEpub":true},
  {"name":"Notes","size":0,"isDirectory":true,"isEpub":false}
]
```

Hidden dotfiles are omitted unless the device setting `showHiddenFiles` is
enabled. `System Volume Information` and `XTCache` are always hidden/protected.

The response schema is unchanged for large directories. Entries are scanned
once and streamed as a chunked response in bounded batches, so the complete
listing is never retained in RAM. If the server could not reserve its 1400-byte
batch buffer when network mode started, this endpoint returns HTTP `503` with
`{"error":"Insufficient memory"}` instead of starting a partial JSON response.

### `GET /download`

Downloads a file from the SD card.

```bash
curl -OJ "http://crosspoint.local/download?path=/Books/MyBook.epub"
```

Query parameters:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `path` | Yes | File path to download |

Protected dotfiles, `System Volume Information`, and `XTCache` cannot be
downloaded. EPUB files are served as `application/epub+zip`; other files use
`application/octet-stream`.

### `POST /upload`

Uploads a file with HTTP multipart form data.

```bash
curl -X POST -F "file=@mybook.epub" "http://crosspoint.local/upload?path=/Books"
```

Query parameters:

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `path` | No | `/` | Destination directory |

Successful response:

```text
File uploaded successfully: mybook.epub
```

Notes:

- Existing files with the same name are overwritten.
- EPUB cache data for the uploaded path is cleared after a successful upload.
- HTTP upload uses a 4 KB write buffer before flushing to the SD card.

### `POST /mkdir`

Creates a folder.

```bash
curl -X POST -d "name=NewFolder&path=/" http://crosspoint.local/mkdir
```

Form parameters:

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `name` | Yes | - | New folder name |
| `path` | No | `/` | Parent folder |

### `POST /rename`

Renames a file.

```bash
curl -X POST -d "path=/Books/old.epub&name=new.epub" http://crosspoint.local/rename
```

Form parameters:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `path` | Yes | Existing file path |
| `name` | Yes | New file name, not a path |

Only files can be renamed through this endpoint. The old EPUB cache path is
cleared before the rename.

### `POST /move`

Moves a file into an existing folder.

```bash
curl -X POST -d "path=/Books/mybook.epub&dest=/Read" http://crosspoint.local/move
```

Form parameters:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `path` | Yes | Existing file path |
| `dest` | Yes | Existing destination folder |

Only files can be moved through this endpoint. The old EPUB cache path is
cleared before the move.

### `POST /delete`

Deletes one or more files or empty folders.

```bash
curl -X POST -d "path=/Books/mybook.epub" http://crosspoint.local/delete
curl -X POST -d 'paths=["/Books/old.epub","/OldFolder"]' http://crosspoint.local/delete
```

Form parameters:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `path` | Yes, unless `paths` is provided | Single path to delete |
| `paths` | Yes, unless `path` is provided | JSON array of paths to delete |

Protected items cannot be deleted. Non-empty folders are rejected. EPUB cache
data for deleted files is cleared.

## Settings API

### `GET /api/settings`

Returns a streamed JSON array of editable settings. Each item contains common
fields plus type-specific fields.

```bash
curl http://crosspoint.local/api/settings
```

Example item:

```json
{
  "key": "fontSize",
  "name": "Reader Font Size",
  "category": "Reader",
  "type": "enum",
  "value": 1,
  "options": ["12 pt", "14 pt", "16 pt", "18 pt"]
}
```

For an enum, `value` is always an index into `options`, never the option's text.
For a toggle it is `0` or `1`; for a numeric value it is an integer and may be
negative. `fontSize` is one of the settings whose `options` are built at request
time — they are the point sizes the selected font family actually ships, so a
family installed at 10/12/14 offers three options. (`fontFamily` and
`dictionaryName` vary the same way, from the SD card contents.)

Types:

| Type | Extra fields |
|------|--------------|
| `toggle` | `value` (`0` or `1`) |
| `enum` | `value`, `options` |
| `value` | `value`, `min`, `max`, `step` |
| `string` | `value` |

The font-family setting includes SD-card font families when they are installed.

Reader display settings include:

| Key | Type | Behavior |
|-----|------|----------|
| `readingGuideLineEnabled` | toggle | Enables line guides for EPUB and TXT |
| `readingGuideLineStyle` | enum | Solid, three dash lengths, dotted, or wavy |
| `readingGuideLineOffset` | value | Signed vertical offset from `-30` to `30` pixels |
| `readingBackgroundEnabled` | toggle | Uses the existing custom background cache for EPUB and TXT |

The API can enable or disable an existing reading background, but selecting and
converting a PNG is a device workflow under **Settings > Reader > Reading
Background > Custom Image**. Disabling the setting does not delete that cache.

### `POST /api/settings`

Applies a partial settings update from a JSON object.

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"fontSize":2,"showHiddenFiles":1}' \
  http://crosspoint.local/api/settings
```

Successful response:

```text
Applied 2 setting(s)
```

## Font Management API

### `GET /api/fonts`

Lists installed SD-card font families.

```bash
curl http://crosspoint.local/api/fonts
```

Response:

```json
{
  "maxFamilies": 128,
  "families": [
    {
      "name": "Literata",
      "sizes": [12, 14, 16, 18],
      "files": [
        {"name": "Literata_12.cpfont", "size": 123456}
      ]
    }
  ]
}
```

### `POST /api/fonts/upload`

Uploads one `.cpfont` file into a family folder.

```bash
curl -X POST \
  -F "family=Literata" \
  -F "file=@Literata_12.cpfont" \
  http://crosspoint.local/api/fonts/upload
```

The handler validates the family name, `.cpfont` filename, and `CPFONT` magic
bytes before accepting the file.

Successful response:

```json
{"ok":true}
```

### `POST /api/fonts/delete`

Deletes an installed font family.

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"family":"Literata"}' \
  http://crosspoint.local/api/fonts/delete
```

Successful response:

```json
{"ok":true}
```

## OPDS Server API

### `GET /api/opds`

Lists saved OPDS servers. Passwords are never returned.

```bash
curl http://crosspoint.local/api/opds
```

Response:

```json
[
  {
    "index": 0,
    "name": "My Catalog",
    "url": "http://calibre.local:8080/opds",
    "username": "reader",
    "hasPassword": true
  }
]
```

### `POST /api/opds`

Adds or updates an OPDS server. Include `index` to update an existing entry.
If `password` is omitted during an update, the existing password is preserved.

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"name":"My Catalog","url":"http://calibre.local:8080/opds","username":"reader","password":"secret"}' \
  http://crosspoint.local/api/opds
```

### `POST /api/opds/delete`

Deletes an OPDS server by index.

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"index":0}' \
  http://crosspoint.local/api/opds/delete
```

## Wi-Fi Credential API

### `GET /api/wifi`

Lists saved Wi-Fi networks. Passwords are never returned.

```bash
curl http://crosspoint.local/api/wifi
```

Response:

```json
[
  {
    "index": 0,
    "ssid": "HomeWiFi",
    "hasPassword": true,
    "isLastConnected": true
  }
]
```

### `POST /api/wifi`

Adds or updates a saved Wi-Fi network. Include `index` to update an existing
entry. If `password` is omitted during an update, the existing password is
preserved.

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"ssid":"HomeWiFi","password":"secret"}' \
  http://crosspoint.local/api/wifi
```

### `POST /api/wifi/delete`

Deletes a saved Wi-Fi network by index.

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"index":0}' \
  http://crosspoint.local/api/wifi/delete
```

## WebSocket Upload

### Port 81

The WebSocket path is used for fast binary uploads from the file manager and
Calibre plugin workflows.

Connection:

```text
ws://crosspoint.local:81/
```

Protocol:

1. Client sends text: `START:<filename>:<size>:<path>`
2. Server replies `READY`
3. Client sends binary chunks
4. Server sends `PROGRESS:<received>:<total>` every 64 KB or at completion
5. Server sends `DONE` when complete or `ERROR:<message>` on failure

Example session:

```text
Client -> START:mybook.epub:1234567:/Books
Server -> READY
Client -> [binary chunk]
Server -> PROGRESS:65536:1234567
...
Server -> DONE
```

Error messages include:

| Message | Cause |
|---------|-------|
| `ERROR:Upload already in progress` | A second upload was started before the first completed |
| `ERROR:Invalid START format` | Malformed START message or invalid size token |
| `ERROR:Failed to create file` | Destination file could not be opened |
| `ERROR:No upload in progress` | Binary data arrived without a matching START |
| `ERROR:Upload overflow` | Client sent more bytes than declared |
| `ERROR:Write failed - disk full?` | SD write failed |

Incomplete WebSocket uploads are deleted on disconnect or error.

## WebDAV

The same HTTP server registers a WebDAV-compatible handler for file manager clients.

Supported methods:

```text
OPTIONS, GET, HEAD, PUT, DELETE, PROPFIND, MKCOL, MOVE, COPY, LOCK, UNLOCK
```

Notes:

- `PUT` writes to a temporary `.davtmp` file first, then renames it into place.
- Protected paths are rejected.
- `LOCK` and `UNLOCK` are accepted for client compatibility only. The server
  does not implement full WebDAV Class 2 locking semantics such as persistent
  locks or lock discovery.

## UDP Discovery

The server listens on UDP port `8134`. When it receives the text payload
`hello`, it replies to the sender with:

```text
crosspoint (on <hostname>);81
```

The final field is the WebSocket upload port.

## Network Modes

### Station Mode (STA)

- Device joins an existing 2.4 GHz Wi-Fi network.
- `crosspoint.local` is advertised with mDNS when available.
- `/api/status` returns `"mode": "STA"` and RSSI in dBm.

### Access Point Mode (AP)

- Device creates an open hotspot named `CrossPoint-Reader`.
- The device shows a Wi-Fi QR code and URL QR code.
- The fallback IP is typically `192.168.4.1`.
- `/api/status` returns `"mode": "AP"` and `"rssi": 0`.

### Calibre Wireless

Calibre Wireless starts the same web server in STA mode and displays setup
instructions plus WebSocket upload progress on the device screen.


## Custom hotspot name

`GET /api/settings` includes `hotspotName` in System settings, with a default of
`XTEINK-X4-PRO`. The same setting is editable on the device through the existing
touchscreen keyboard. It occupies 33 fixed bytes in settings; the editor reuses
the existing checked activity allocation, without a new resident heap buffer.

`POST /api/settings` accepts an empty string to restore the default, or a valid
UTF-8 name of 1–32 bytes. Whitespace-only names, control characters, malformed
UTF-8, non-string JSON values and oversized names are rejected with HTTP 400
before any settings are applied. A failed SD-card save returns HTTP 500 and
restores the previous in-memory hotspot name. The saved JSON uses `hotspotName`;
older settings without that field retain the default. Invalid saved values are
repaired to the default, never truncated inside a UTF-8 code point.

Saving does not disconnect the current hotspot session. Exit hotspot/file
transfer mode and enter Hotspot Mode again to advertise the new name. The active
session screen and QR retain their original SSID until that restart. This does
not rename an external Wi-Fi network, the web page title, or the mDNS hostname.

Hardware acceptance: check both web and touch editors, restart hotspot and
reconnect using the new name, then reboot and confirm persistence. Try Chinese,
a 32-byte name, and an empty field. Host checks and compilation do not establish
radio, touchscreen or SD-card acceptance on the physical X4 Pro.

Wi-Fi QR payloads escape punctuation in custom names using the [ZXing Wi-Fi parser format](https://github.com/zxing/zxing/blob/master/core/src/main/java/com/google/zxing/client/result/WifiResultParser.java).


## Firmware display identity (2026-09-22)

System settings expose `versionDisplayName` (empty by default; up to 32 UTF-8 bytes)
and `showVersionNumber` (1 by default). Blank names use the translated original
firmware name. Controls, malformed UTF-8, whitespace-only ASCII names and oversized
names are rejected without truncation. POST validates both fields before applying
any settings; SD-save failure restores both identity fields and returns HTTP 500.
Legacy settings keep the defaults; malformed saved identity fields are repaired.

Both device and web settings can edit these fields. The device settings header,
About firmware name and boot title use the name. Turning off the number removes
the About version row and hides the number in the header and boot splash. The
name remains visible. Changes apply on the next render and persist on SD.
The existing web page branding is separate; `/api/status.version`, update screens,
OTA comparisons, User-Agent and diagnostic logs retain the real build version.

Memory: 33 fixed bytes for the name and one byte for visibility (plus struct
alignment); formatting uses a bounded stack buffer. Name editing reuses the
existing checked keyboard activity. No additional framebuffer or display cache.
Adding System rows resets the existing System custom ordering to the default.

Validation: `python3 -m unittest scripts.tests.test_version_identity
 scripts.tests.test_hotspot_name`; `node scripts/tests/test_version_settings.mjs`
and `node scripts/tests/test_hotspot_settings.mjs`; `pio run -e x4pro_custom`.
On hardware, edit a name, toggle visibility, inspect About, reboot, clear the
name, and verify defaults and persistence. Hardware acceptance is separate
from compilation and host tests.

## 2026-09-23 — AirNote 待辦清單

裝置設定網頁 Device → AirNote 可選「一般筆記／待辦清單」。待辦每行一項，最多 64 項、每項 240 UTF-8 位元組、整體含格式標記最多 16 KiB；網頁可用勾選預覽，按儲存後提交。X4 Pro 應用 → AirNote 選同一份 TXT，會改以待辦清單呈現，觸控項目或按確認鍵切換完成狀態。每次成功寫入後才更新畫面；重開與網頁載入均保留狀態。

格式為標題、空白行，接著 `#!AirNote-Todo:1` 格式行和 `[ ] 事項`／`[x] 事項`。一般筆記格式不變。API 支援可選 type=text/todo，GET 回傳 type，待辦 text 為不含格式行的項目文字。舊客戶端缺少 type 時不得覆寫待辦。原 revision 衝突保護涵蓋裝置勾選；請先複製網頁草稿再重新載入。

裝置沿用 UiListActivity 的觸控、按鍵與換頁，24px Mask1 方框圖示，清單間隔至少 6px。使用一份經 checked allocation 配置且上限約 16 KiB 的 TXT 緩衝區；64 項 offset 及清單列存在 Activity 內，顯示標籤指向該緩衝區，沒有額外複製。顯示分隔符與還原寫檔皆在 RenderLock 保護下。保存前核對 SD 檔案摘要，沿用 staging/backup 可恢复替換和閱讀快取清除，失敗保留原勾選狀態。返回 AirNote 目錄時會恢復中斷保存的原檔。

已通過編譯、含 ASan/UBSan 的實際 Activity 主機測試、一般筆記回歸與兩份網頁的待辦瀏覽器流程。尚未刷入或完成 X4 Pro 實機觸控／SD 卡驗證。

## 2026-09-23 — 待辦進度位置修正

使用者實機照片確認：完成進度原先附在第一項的副標題。現改由 AirNoteTodoActivity::drawChrome 傳給主題標題列右側，獨立固定 96-byte 進度緩衝區，不增加動態配置。每次完成或取消仍依成功保存的狀態更新。所有待辦列 subtitle 為空，清單採無副標題的列高度；失敗訊息置於獨立固定提示列，內容區同步保留其高度。INX 標題以實際剩餘寬度省略；Base 標題為手動右側標籤預留空間；RoundedRaff 現在呈現右側標籤並保留電池區。

主機測試確認第一項無進度、標題進度隨勾選更新、失敗時進度不變且錯誤列獨立，以及原儲存故障／衝突保護。修正版尚未刷入實體 X4 Pro，照片僅證明前版排版問題。
