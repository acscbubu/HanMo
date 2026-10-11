#!/usr/bin/env python3
"""Generate compact C++ kana stroke data from pinned KanjiVG SVG assets.

KanjiVG stores each writing stroke as an individual `-sN` SVG path. This
script samples those paths into polylines for the 480x800 one-bit renderer;
it does not infer stroke order from a font.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

TOKEN = re.compile(r"[AaCcHhLlMmQqSsTtVvZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
PARAMS = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}


def pair(a, b):
    return (float(a), float(b))


def add(p, q):
    return (p[0] + q[0], p[1] + q[1])


def sub(p, q):
    return (p[0] - q[0], p[1] - q[1])


def scale(p, n):
    return (p[0] * n, p[1] * n)


def lerp(a, b, t):
    return add(a, scale(sub(b, a), t))


def cubic(p0, p1, p2, p3, t):
    a = lerp(p0, p1, t)
    b = lerp(p1, p2, t)
    c = lerp(p2, p3, t)
    return lerp(lerp(a, b, t), lerp(b, c, t), t)


def quadratic(p0, p1, p2, t):
    return lerp(lerp(p0, p1, t), lerp(p1, p2, t), t)


def arc_points(p0, rx, ry, rotation, large, sweep, p1):
    # SVG 1.1 endpoint-to-center conversion, sampled into a polyline.
    if abs(rx) < 1e-9 or abs(ry) < 1e-9 or (abs(p0[0] - p1[0]) < 1e-9 and abs(p0[1] - p1[1]) < 1e-9):
        return [p1]
    rx, ry = abs(rx), abs(ry)
    phi = math.radians(rotation % 360.0)
    cosphi, sinphi = math.cos(phi), math.sin(phi)
    dx, dy = (p0[0] - p1[0]) / 2.0, (p0[1] - p1[1]) / 2.0
    xp, yp = cosphi * dx + sinphi * dy, -sinphi * dx + cosphi * dy
    lam = xp * xp / (rx * rx) + yp * yp / (ry * ry)
    if lam > 1:
        factor = math.sqrt(lam)
        rx, ry = rx * factor, ry * factor
    sign = -1.0 if bool(large) == bool(sweep) else 1.0
    num = max(0.0, (rx * rx * ry * ry - rx * rx * yp * yp - ry * ry * xp * xp))
    den = rx * rx * yp * yp + ry * ry * xp * xp
    coef = sign * math.sqrt(num / den) if den else 0.0
    cxp, cyp = coef * (rx * yp / ry), coef * (-ry * xp / rx)
    cx = cosphi * cxp - sinphi * cyp + (p0[0] + p1[0]) / 2.0
    cy = sinphi * cxp + cosphi * cyp + (p0[1] + p1[1]) / 2.0

    def unit_angle(u, v):
        return math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1])

    u = ((xp - cxp) / rx, (yp - cyp) / ry)
    v = ((-xp - cxp) / rx, (-yp - cyp) / ry)
    theta = math.atan2(u[1], u[0])
    delta = unit_angle(u, v)
    if not sweep and delta > 0:
        delta -= 2 * math.pi
    if sweep and delta < 0:
        delta += 2 * math.pi
    steps = max(4, int(abs(delta) * 1024 / 2 / math.pi))
    out = []
    for i in range(1, steps + 1):
        t = theta + delta * i / steps
        out.append((cx + rx * math.cosphi(t, cosphi, sinphi), cy + ry * math.sinphi(t, cosphi, sinphi)))
    return out


# Keep the arc expression readable without adding a vector class.
def _cosphi(t, c, s):
    return c * math.cos(t) - s * math.sin(t)


def _sinphi(t, c, s):
    return s * math.cos(t) + c * math.sin(t)


# methods used by arc_points without a closure allocation in the loop
math.cosphi = _cosphi  # type: ignore[attr-defined]
math.sinphi = _sinphi  # type: ignore[attr-defined]


def parse_path(path):
    toks = TOKEN.findall(html.unescape(path))
    i = 0
    cmd = None
    cur = (0.0, 0.0)
    start = cur
    last_cubic = None
    last_quad = None
    points = []

    def has_params(n):
        return i < len(toks) and not toks[i].isalpha() and i + n <= len(toks)

    while i < len(toks):
        if toks[i].isalpha():
            cmd = toks[i]
            i += 1
        if cmd is None:
            raise ValueError("path data has numbers before a command")
        upper = cmd.upper()
        if upper == "Z":
            cur = start
            points.append(cur)
            cmd = None
            last_cubic = last_quad = None
            continue
        n = PARAMS[upper]
        if not has_params(n):
            raise ValueError(f"incomplete {cmd} path segment")
        vals = [float(x) for x in toks[i:i+n]]
        i += n
        rel = cmd.islower()
        old = cur
        if upper == "M":
            target = pair(vals[0], vals[1])
            cur = add(cur, target) if rel else target
            points.append(cur)
            start = cur
            # Subsequent coordinate pairs after M are implicit L.
            cmd = "l" if rel else "L"
            last_cubic = last_quad = None
            continue
        if upper == "L":
            target = pair(vals[0], vals[1])
            cur = add(cur, target) if rel else target
            points.append(cur)
        elif upper == "H":
            cur = (cur[0] + vals[0], cur[1]) if rel else (vals[0], cur[1])
            points.append(cur)
        elif upper == "V":
            cur = (cur[0], cur[1] + vals[0]) if rel else (cur[0], vals[0])
            points.append(cur)
        elif upper == "C":
            c1, c2, target = pair(vals[0], vals[1]), pair(vals[2], vals[3]), pair(vals[4], vals[5])
            if rel: c1, c2, target = add(cur, c1), add(cur, c2), add(cur, target)
            for j in range(1, 13): points.append(cubic(cur, c1, c2, target, j / 12))
            cur, last_cubic, last_quad = target, c2, None
            continue
        elif upper == "S":
            c1 = sub(scale(cur, 2), last_cubic) if last_cubic is not None else cur
            c2, target = pair(vals[0], vals[1]), pair(vals[2], vals[3])
            if rel: c2, target = add(cur, c2), add(cur, target)
            for j in range(1, 13): points.append(cubic(cur, c1, c2, target, j / 12))
            cur, last_cubic, last_quad = target, c2, None
            continue
        elif upper == "Q":
            c1, target = pair(vals[0], vals[1]), pair(vals[2], vals[3])
            if rel: c1, target = add(cur, c1), add(cur, target)
            for j in range(1, 10): points.append(quadratic(cur, c1, target, j / 9))
            cur, last_quad, last_cubic = target, c1, None
            continue
        elif upper == "T":
            c1 = sub(scale(cur, 2), last_quad) if last_quad is not None else cur
            target = pair(vals[0], vals[1])
            if rel: target = add(cur, target)
            for j in range(1, 10): points.append(quadratic(cur, c1, target, j / 9))
            cur, last_quad, last_cubic = target, c1, None
            continue
        elif upper == "A":
            target = pair(vals[5], vals[6])
            if rel: target = add(cur, target)
            points.extend(arc_points(cur, vals[0], vals[1], vals[2], vals[3], vals[4], target))
            cur, last_cubic, last_quad = target, None, None
            continue
        else:
            raise ValueError(f"unsupported command {upper}")
        last_cubic = last_quad = None
    # Remove adjacent duplicate coordinates and clamp round-off to the source viewBox.
    clean=[]
    for p in points:
        q=(round(p[0]),round(p[1]))
        if not clean or q != clean[-1]: clean.append(q)
    return clean


def stroke_paths(svg_path):
    root=ET.parse(svg_path).getroot()
    by_index={}
    def walk(element, inherited=None):
        style=element.attrib.get("style", "")
        match=re.search(r"--i\s*:\s*(\d+)", style)
        index=int(match.group(1)) if match else inherited
        if element.tag.endswith("path"):
            d=element.attrib.get("d")
            if index is not None and d: by_index.setdefault(index,[]).append(d)
        for child in element:
            walk(child,index)
    walk(root)
    if not by_index or set(by_index) != set(range(max(by_index)+1)):
        raise ValueError(f"non-contiguous stroke indexes in {svg_path}: {sorted(by_index)}")
    strokes=[]
    for index in range(max(by_index)+1):
        # A grouped stroke may contain corrective clip paths with geometry far
        # outside the viewBox. Its first centerline is the complete writing path;
        # the remaining paths only repair self-intersections in the filled SVG.
        strokes.append([parse_path(by_index[index][0])])
    return strokes


def kanjivg_paths(svg_path):
    root=ET.parse(svg_path).getroot()
    viewbox = root.attrib.get("viewBox", "").split()
    if len(viewbox) != 4 or viewbox[0] != "0" or viewbox[1] != "0" or viewbox[2] != "109" or viewbox[3] != "109":
        raise ValueError(f"unexpected KanjiVG viewBox in {svg_path}: {root.attrib.get('viewBox')!r}")
    by_index={}
    for element in root.iter():
        ident=element.attrib.get("id", "")
        match=re.search(r"-s(\d+)$", ident)
        d=element.attrib.get("d")
        if match and d: by_index[int(match.group(1))]=d
    if not by_index or set(by_index) != set(range(1, max(by_index)+1)):
        raise ValueError(f"non-contiguous KanjiVG strokes in {svg_path}: {sorted(by_index)}")
    strokes=[]
    for index in range(1, max(by_index)+1):
        # KanjiVG's 109x109 viewBox is normalized to the firmware's 0..1024 space.
        points=parse_path(by_index[index])
        if len(points) < 2 or any(not (0 <= x <= 109 and 0 <= y <= 109) for x,y in points):
            raise ValueError(f"KanjiVG stroke {index} has invalid points in {svg_path}")
        scaled=[(round(x*1024/109), round(y*1024/109)) for x,y in points]
        strokes.append([scaled])
    return strokes


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--check',action='store_true'); ap.add_argument('-o',default=None)
    args=ap.parse_args(); root=Path(__file__).resolve().parents[1]
    cards=json.loads((root/'data/japanese/kana-basic.json').read_text(encoding='utf-8'))['cards']
    assert len(cards)==46
    all_data=[]
    for card in cards:
        entry=[]
        for text,script in ((card[0],'hiragana'),(card[1],'katakana')):
            paths=kanjivg_paths(root/'third_party/kanjivg'/script/(text+'.svg'))
            entry.append((text,paths))
        all_data.append(entry)
    if args.check:
        print(f'checked {len(all_data)} cards; {sum(len(x[0][1])+len(x[1][1]) for x in all_data)} glyph strokes')
        return
    out=Path(args.o) if args.o else root/'src/activities/apps/japanese/KanaStroke.generated.h'
    out.parent.mkdir(parents=True,exist_ok=True)
    lines=['// Generated by scripts/generate_kana_strokes.py; do not edit.', '#pragma once', '#include <cstdint>', 'namespace kana {',
           'struct StrokePoint { uint16_t x; uint16_t y; };', 'struct StrokePart { uint8_t pointCount; const StrokePoint* points; };',
           'struct Stroke { uint8_t partCount; const StrokePart* parts; };',
           'struct GlyphStrokes { const char* glyph; uint8_t strokeCount; const Stroke* strokes; };',
           'struct StrokeCard { GlyphStrokes hiragana; GlyphStrokes katakana; };', '']
    glyph_refs=[]
    gid=0
    for entry in all_data:
        refs=[]
        for glyph,paths in entry:
            srefs=[]
            for si,parts in enumerate(paths):
                partrefs=[]
                for pi,points in enumerate(parts):
                    # Preserve all points in each source path: no silent truncation.
                    if len(points) > 255: raise ValueError(f'path too long {glyph} stroke {si} part {pi}')
                    pname=f'kStrokePoints{gid}_{si}_{pi}'
                    lines.append(f'inline constexpr StrokePoint {pname}[] = {{'+','.join('{%d,%d}'%p for p in points)+'};')
                    partrefs.append((len(points),pname))
                partname=f'kStrokeParts{gid}_{si}'
                lines.append(f'inline constexpr StrokePart {partname}[] = {{'+','.join('{%d,%s}'%x for x in partrefs)+'};')
                srefs.append((len(parts),partname))
            arr=f'kStrokes{gid}'
            lines.append(f'inline constexpr Stroke {arr}[] = {{'+','.join('{%d,%s}'%x for x in srefs)+'};')
            glyph_refs.append((glyph,len(paths),arr))
            refs.append((glyph,len(paths),arr)); gid+=1
        lines.append(f'inline constexpr StrokeCard kCard{len(glyph_refs)//2-1} = {{{{"{refs[0][0]}",{refs[0][1]},{refs[0][2]}}},{{"{refs[1][0]}",{refs[1][1]},{refs[1][2]}}}}};')
    lines.append('inline constexpr int kStrokeCardCount = 46;')
    lines.append('inline constexpr StrokeCard strokeCards[kStrokeCardCount] = {'+','.join(f'kCard{i}' for i in range(46))+'};')
    lines.append('enum class Script : uint8_t { Hiragana, Katakana };')
    lines.append('class StrokeLesson { public: StrokeLesson() = default; int cardIndex() const { return card_; } Script script() const { return script_; } int visibleStrokes() const { return visible_; } int strokeCount() const { return glyph().strokeCount; } bool nextStroke() { if (visible_ >= strokeCount()) return false; ++visible_; return true; } bool previousStroke() { if (visible_ <= 1) return false; --visible_; return true; } void restart() { visible_=1; } bool toggleScript() { script_=script_==Script::Hiragana?Script::Katakana:Script::Hiragana; visible_=1; return true; } bool nextCard() { if (card_+1 >= kStrokeCardCount) return false; ++card_; visible_=1; return true; } bool previousCard() { if (card_<=0) return false; --card_; visible_=1; return true; } private: const GlyphStrokes& glyph() const { return script_==Script::Hiragana?strokeCards[card_].hiragana:strokeCards[card_].katakana; } int card_=0; int visible_=1; Script script_=Script::Hiragana; };')
    lines.append('}  // namespace kana')
    # Keep independently licensed graphics separate from the lesson control code.
    # This is a format conversion, not a relicensing of the KanjiVG artwork.
    split = next(i for i, line in enumerate(lines) if line.startswith('enum class Script'))
    notice = [
        '// SPDX-License-Identifier: CC-BY-SA-3.0',
        '// KanjiVG artwork: Copyright (c) 2009-2026 Ulrich Apel and contributors.',
        '// Derived from KanjiVG 70a0b7ae0c18ceb5cb358274b029cce0234a43bc.',
        '// HanMo conversion: selected 92 kana; sampled curves; normalized coordinates.',
        '// See third_party/kanjivg/LICENSE and SOURCE.md. No executable lesson logic.',
    ]
    types = ['// SPDX-License-Identifier: MIT', '// Generated interface declarations; see root MIT license.',
             '#pragma once', '#include <cstdint>', 'namespace kana {', *lines[4:9], '}']
    data = [*notice, '#pragma once', '#include "KanaStrokeTypes.generated.h"',
            'namespace kana {', *lines[10:split], '}']
    wrapper = ['// SPDX-License-Identifier: MIT', '// Generated lesson control code; see root MIT license.',
               '#pragma once', '#include "KanaStrokeData.generated.h"',
               'namespace kana {', *lines[split:]]
    for name, content in [('KanaStrokeTypes.generated.h', types),
                          ('KanaStrokeData.generated.h', data), (out.name, wrapper)]:
        (out.parent/name).write_text('\n'.join(content)+'\n', encoding='utf-8')
    print('generated',out,'bytes',out.stat().st_size)

if __name__=='__main__': main()
