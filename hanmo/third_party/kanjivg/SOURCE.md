# Kana stroke data provenance

Imported from `KanjiVG/kanjivg` commit `70a0b7ae0c18ceb5cb358274b029cce0234a43bc`:

- Source repository: https://github.com/KanjiVG/kanjivg
- Imported paths: `kanji/03042.svg` through the basic hiragana set and `kanji/030a2.svg` through the basic katakana set, restricted to the 46 basic cards in `data/japanese/kana-basic.json`.
- The SVGs provide individual `kvg:<code>-sN` paths in stroke order, with a 109×109 viewBox. The generator scales those centerlines to the firmware's 0..1024 coordinates; it does not infer order from the Maruko/Kana display font.
- KanjiVG is released under Creative Commons Attribution-Share Alike 3.0. The verbatim upstream license text is in `LICENSE`; the app's source note and distribution package must retain attribution, license link and modification notice.
- The former StrokeSVG import remains outside the runtime source tree only as research; the shipped generated data uses KanjiVG to avoid treating a font-derived asset as the authority.

The app displays a source note and does not provide handwriting recognition or scoring.

## HanMo source-delivery separation (2026-10-09)

Copyright (c) 2009-2026 Ulrich Apel and KanjiVG contributors.
Title: KanjiVG basic kana stroke diagrams (92 selected SVGs).
Source: https://github.com/KanjiVG/kanjivg/tree/70a0b7ae0c18ceb5cb358274b029cce0234a43bc
License: https://creativecommons.org/licenses/by-sa/3.0/

The original SVGs and the converted coordinates in KanaStrokeData.generated.h
remain CC BY-SA 3.0. Changes: selecting the basic kana, sampling curves to
polylines, normalizing 109x109 coordinates to 0..1024, and serializing arrays.
No endorsement is implied. The MIT lesson controller and interface declarations
are separate generated files. The renderer reads these coordinates as artwork;
the artwork does not implement program behavior. Recipients can extract,
modify, and regenerate the art independently using the included generator.
Keep this attribution and the included license when distributing converted art.
Do not describe the art as MIT or automatically upgrade its license to GPL.
