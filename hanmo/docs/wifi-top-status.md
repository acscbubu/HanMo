> 2026-10-04 已由 docs/kana-status.md 的共用既有狀態列取代；取消額外22px高度。以下為先前方案歷史。

# X4 Pro Wi-Fi top status row (2026-10-04)

The 22px global status reservation moves from the bottom to the top. Content height is unchanged from the first info-board prototype; its logical origin moves down by 22px. Rotation, clipped/strip drawing, fast fills, region copies, partial display windows and grayscale preconditioning use the same inset. System status drawing bypasses the content inset. Gray overlay planes clear the top band and retain the BW base icon. Touch/long-press/held coordinates subtract the inset; taps on the reserved row do not activate content. Top-edge swipes remain available.

No new framebuffer or heap allocation. See GfxRenderer.cpp rotateCoordinates/tapToLogical and MappedInputManager.cpp wasScreenTapped. Existing Wi-Fi position settings/IDs and info-board/print behaviour remain unchanged. Prototype only; hardware verification pending.
