## Current update: direct destination (2026-09-24)

AirNote files: long-press, choose Move to position, then tap a destination row. Tasks: long-press an item, then tap its destination. Back cancels; a drop preserves relative order and checkbox state. Web note ordering accepts a 1-based destination shown to users, sent as zero-based `target` with order revision; checklist dropdowns edit the draft until Save. The older adjacent-direction API remains compatible. Storage uses the same recoverable replacement and conflict validation. Taps & Gestures is now under Settings > Reader on device and web. The earlier notes below describe the original release.

# AirNote ordering and reader gestures — 2026-09-24

Baseline: CrossMux 651ef5a plus the existing quick-panel custom working tree. Firmware identity remains 1.5.8-custom; no upstream branch merge.

## AirNote

`/AirNote/.order` is a UTF-8 newline-separated filename catalog. It never renames notes or embeds note text. Existing catalog entries come first; newly added/unlisted notes follow in SD directory order. The same order is used by the device and paginated web API. Non-AirNote files/subfolders stay accessible after the ordered notes in the device browser. Renamed files are treated as new entries. Deleted entries and duplicate catalog lines are ignored; malformed/truncated catalogs fail closed for writes and retain device file access.

Device: hold a root AirNote file, choose Move up/down. Hold a checklist row to move it; a normal tap still checks/unchecks. Web: note move buttons save immediately without replacing the editor draft. Checklist preview arrows change the draft; press Save to persist it.

GET /api/airnote returns notes, nextOffset, total and orderRevision. Continuation requests may send orderRevision; PUT /api/airnote/order accepts {name,direction:-1|1,orderRevision}. A digest includes current visible filenames, so new/deleted notes and another client reorder invalidate old requests. Note-content revision checks remain independent. Writes use .order.part/.order.bak recoverable replacement. Directory scans do not allocate a second file list: they stream 128-byte filename buffers; duplicate/membership checks rescan the catalog, trading SD reads for bounded RAM. The device reuses its existing file vector. Checklist moves rotate whole serialized lines in the existing <=16 KiB buffer, then restore the prior bytes on a failed save.

## Taps & Gestures

Device: Settings > Reader > Taps & Gestures. Web: Settings > Reader > Taps & Gestures. Nine persistent byte fields are added through the shared settings schema. Page settings default to Inherit, retaining legacy tap/swipe/inverted controls. New gesture toggles and two-finger mappings default off. The legacy Reading touch control remains the master enable.

Next and previous pages independently support Inherit, Tap and swipe, Tap only, Swipe only, Inverted tap, Disabled. Center taps remain reserved for the existing reader menu. If independently inverted page zones overlap, ambiguous taps produce no page turn. Existing six EPUB tap shortcuts still run before ordinary page-turn dispatch; enabled status-bar taps own the status-bar band.

Pinch/rotation/status-bar visibility apply to EPUB and ordinary TXT/Markdown readers. AirNote checklist rows retain their checkbox/reorder behavior. Font resize steps through the active font family's installed sizes, clamped at the ends. The built-in fallback has only 12pt, so resizing requires a multi-size SD family. TXT reflow retains its source byte offset in memory as well as using existing progress storage. Status-bar hiding is session-only and retains the page's reserved bar space to avoid re-pagination; tap the same band to show it. Reopening the book restores it.

Two-finger directional actions: none, brightness +/-10, warmth +/-10, next/previous EPUB spine chapter, font larger/smaller for EPUB/TXT. Unsupported format actions are consumed without affecting navigation (e.g. chapter/font actions in XTC). Brightness/warmth apply only where the light hardware supports them. XTC retains its fixed-layout behavior; pinch/rotation/status-tap are not enabled for it. Actions may be assigned to multiple directions in this fork.

HAL exposes a fixed-size normalized snapshot and completed events from the existing GT911 SDK. No SDK update or direct SDK use in activities. The pinch recognizer is a fixed-size member with no heap allocation; font-size stepping reuses the existing small installed-size vector. All multi-contact sequences, including invalid 3+ contacts and 2->1 release, are consumed once. A pinch suppresses later swipe/rotation events. Settings save failures restore font/light/orientation values. Settings subpage uses a fixed nine-row array and the existing modal popup.

CrossInk provenance and MIT license: crossink-gestures-attribution.md.

## Verification limits

Host tests compile production storage, checklist, gesture recognizer and reader-dispatch code with fault-injecting HAL stubs, ASan/UBSan. Browser tests run both locales at desktop/mobile widths against a mocked device API. PlatformIO targets x4pro_custom. These checks do not establish GT911 gesture thresholds or SD durability on physical hardware. No device is flashed by this task.
