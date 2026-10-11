# KanjiVG artwork boundary

Copyright (c) 2009-2026 Ulrich Apel and KanjiVG contributors. KanjiVG basic kana diagrams,
92 selected SVGs from commit 70a0b7ae0c18ceb5cb358274b029cce0234a43bc.
Source: https://github.com/KanjiVG/kanjivg/tree/70a0b7ae0c18ceb5cb358274b029cce0234a43bc
License: https://creativecommons.org/licenses/by-sa/3.0/legalcode.en

The original SVGs, conversion script, modification notice and license are retained in hanmo/third_party/kanjivg.
HanMo scales 109x109 centerlines into 0..1024 sampled coordinate arrays. The adapted coordinates
retain CC BY-SA 3.0. artwork/ supplies an editable JSON export usable independently of firmware.
KanaStrokeData.generated.h contains only attributed graphical constants. KanaStrokeTypes.generated.h
contains MIT interface structures; KanaStroke.generated.h contains MIT controller code.
This is a separate-artwork distribution analysis, not a claim that BY-SA 3.0 is GPL-compatible
or that labeling one file changes a derivative work's legal status. No artwork is relicensed to GPL.

The separation preserves all 564 original constant-declaration lines byte-for-byte, all controller
lines, 92 diagrams and the in-app source note. 22 stroke-related tests passed after regeneration.
The app builds successfully with the separated files. Existing fonts remain separately OFL-licensed.

Basis: GNU recognizes separately licensed program artwork/music, and Creative Commons permits
its licenses for separate artistic elements of software. BY-SA3's collection provisions distinguish
an independent collection from an adaptation. This package supplies the original/modified art with
its own terms, notices and editing form; source separation alone is not a universal legal guarantee.

- https://www.gnu.org/licenses/gpl-faq.en.html#WhatCaseIsOutputGPL
- https://creativecommons.org/faq/#can-i-apply-a-creative-commons-license-to-software
- https://creativecommons.org/licenses/by-sa/3.0/legalcode.en
