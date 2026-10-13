"""Colour vision and colour-blind-safe chart colours (TODO P2.9, D-314). Colour vision is simulated with the Machado, Oliveira and
Fernandes (2009) matrices for protanopia, deuteranopia and tritanopia at full severity; distances are CIE76 in Lab. No dependencies, so
the chart code can use it."""

from __future__ import annotations

MIN_COLOUR_DELTA = (
    18.0  # CIE76 distance below which two colours are hard to tell apart in a simulated colour-blind view
)

# Machado, Oliveira and Fernandes (2009), severity 1.0, applied to linear RGB.
MATRICES = {
    "protanopia": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
    "deuteranopia": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
    "tritanopia": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602), (0.004733, 0.691367, 0.303900)),
}  # fmt: skip


def _linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def _srgb(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * 12.92 if value <= 0.0031308 else 1.055 * value ** (1 / 2.4) - 0.055


def _rgb(hex_value: str) -> tuple[float, float, float]:
    text = hex_value.lstrip("#")
    return tuple(int(text[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def simulate(hex_value: str, kind: str) -> tuple[float, float, float]:
    """The sRGB colour a person with this colour vision type sees for `hex_value`."""
    r, g, b = (_linear(c) for c in _rgb(hex_value))
    matrix = MATRICES[kind]
    out = tuple(sum(row[i] * v for i, v in enumerate((r, g, b))) for row in matrix)
    return tuple(_srgb(v) for v in out)  # type: ignore[return-value]


def _lab(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    r, g, b = (_linear(c) for c in rgb)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


def delta(first: tuple[float, float, float], second: tuple[float, float, float]) -> float:
    a, b = _lab(first), _lab(second)
    return float(sum((x - y) ** 2 for x, y in zip(a, b, strict=True)) ** 0.5)


def palette_conflicts(colours: list[str], minimum: float = MIN_COLOUR_DELTA) -> list[tuple[str, str, str]]:
    """Pairs of colours that look alike to a colour-blind viewer (and the type of colour blindness), worst first."""
    found: list[tuple[float, str, str, str]] = []
    for i, first in enumerate(colours):
        for second in colours[i + 1 :]:
            for kind in MATRICES:
                gap = delta(simulate(first, kind), simulate(second, kind))
                if gap < minimum:
                    found.append((gap, first, second, kind))
    return [(a, b, kind) for _, a, b, kind in sorted(found)]


def _mix(first: str, second: str, share: float) -> str:
    a, b = _rgb(first), _rgb(second)
    return "#" + "".join(
        f"{round(255 * (x * (1 - share) + y * share)):02X}" for x, y in zip(a, b, strict=True)
    )


def _worst_pair(colours: list[str]) -> tuple[float, int, int]:
    worst = (999.0, 0, 0)
    for i, first in enumerate(colours):
        for j in range(i + 1, len(colours)):
            for kind in MATRICES:
                gap = delta(simulate(first, kind), simulate(colours[j], kind))
                if gap < worst[0]:
                    worst = (gap, i, j)
    return worst


def _contrast(first: str, second: str) -> float:
    def lum(value: str) -> float:
        r, g, b = (_linear(c) for c in _rgb(value))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    high, low = max(lum(first), lum(second)), min(lum(first), lum(second))
    return float((high + 0.05) / (low + 0.05))


def accessible_palette(
    palette: tuple[str, ...] | list[str],
    count: int,
    background: str = "#FFFFFF",
    minimum: float = MIN_COLOUR_DELTA,
) -> list[str]:
    """`count` chart colours from a theme's palette (the first, usually the accent, always kept) that a colour-blind viewer can tell apart:
    the combination with the best worst-case separation, then the closest pair is pulled apart in lightness while every colour keeps a
    contrast of 3:1 against the background. More colours than the palette has repeat from the start."""
    import itertools

    colours = ["#" + c.lstrip("#").upper() for c in palette]
    count = max(count, 1)
    if count > len(colours):
        return [colours[i % len(colours)] for i in range(count)]
    if count == 1:
        return colours[:1]
    rest = colours[1:]
    best = max(
        ([colours[0], *chosen] for chosen in itertools.combinations(rest, count - 1)),
        key=lambda combo: _worst_pair(combo)[0],
    )
    chosen = list(best)
    for _ in range(40):
        gap, i, j = _worst_pair(chosen)
        if gap >= minimum:
            break
        index = j if j != 0 else i
        options = []
        for towards in ("#FFFFFF", "#000000"):
            trial = _mix(chosen[index], towards, 0.12)
            if _contrast(trial, background) >= 3.0:
                options.append((_worst_pair([*chosen[:index], trial, *chosen[index + 1 :]])[0], trial))
        if not options:
            break
        score, trial = max(options)
        if score <= gap:
            break
        chosen[index] = trial
    return chosen
