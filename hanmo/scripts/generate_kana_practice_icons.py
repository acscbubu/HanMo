"""Generate six fixed 24px BW1 marker icons (0=ink, 1=transparent)."""
from pathlib import Path
import math

DEST = Path(__file__).resolve().parents[1] / 'src/activities/apps/japanese/KanaPracticeIcons.h'
SIZE = 24


def point_in_poly(x, y, vertices):
    inside = False
    for a, b in zip(vertices, vertices[1:] + vertices[:1]):
        (x1, y1), (x2, y2) = a, b
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def near_line(x, y, x1, y1, x2, y2, thickness=1.3):
    dx, dy = x2 - x1, y2 - y1
    t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    return (x - (x1 + t * dx)) ** 2 + (y - (y1 + t * dy)) ** 2 < thickness ** 2


def pixels(shape, filled):
    star = []
    for n in range(10):
        angle = -math.pi / 2 + n * math.pi / 5
        r = 10.6 if n % 2 == 0 else 4.7
        star.append((11.5 + r * math.cos(angle), 11.5 + r * math.sin(angle)))
    image = []
    for y in range(SIZE):
        row = []
        for x in range(SIZE):
            px, py = x + 0.5, y + 0.5
            if shape == 'Star':
                outline = any(near_line(px, py, *a, *b, 1.2)
                              for a, b in zip(star, star[1:] + star[:1]))
                on = outline or (filled and point_in_poly(px, py, star))
            elif shape == 'Circle':
                r2 = (px - 12) ** 2 + (py - 12) ** 2
                on = r2 <= (9.8 if filled else 9.8) ** 2 and (
                    filled or r2 >= 7.9 ** 2)
            else:
                outline = 3 <= x <= 20 and 3 <= y <= 20 and (
                    x <= 4 or x >= 19 or y <= 4 or y >= 19)
                interior = 4 <= x <= 19 and 4 <= y <= 19
                check = near_line(px, py, 6, 12, 10, 16, 1.6) or near_line(
                    px, py, 10, 16, 18, 8, 1.6)
                on = (interior and not check) if filled else outline
            row.append(on)
        image.extend(row)
    return bytes(sum((0 if image[y * SIZE + x] else 1) << (7 - x % 8)
                     for x in range(8 * byte, 8 * byte + 8))
                 for y in range(SIZE) for byte in range(3))


def main():
    lines = ['#pragma once', '#include <cstdint>', 'namespace kana::icons {',
             '// BW1, MSB first: white background is 1, dark stroke is 0.']
    for name in ('Star', 'Check', 'Circle'):
        for filled in (False, True):
            icon_name = name + ('On' if filled else 'Off')
            values = pixels(name, filled)
            lines.append('inline constexpr uint8_t k' + icon_name + '[] = {')
            for off in range(0, len(values), 12):
                lines.append('    ' + ', '.join(f'0x{n:02X}' for n in values[off:off+12]) + ',')
            lines.append('};')
    lines.append('}  // namespace kana::icons')
    DEST.write_text('\n'.join(lines) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
