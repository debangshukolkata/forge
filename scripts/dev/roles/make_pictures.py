"""Makes the pictures of the role challenge with headless Edge (build machine only; the PNG files are committed).

.venv\\Scripts\\python scripts\\dev\\roles\\make_pictures.py"""

from __future__ import annotations

import io
import math
from pathlib import Path

from PIL import Image, ImageFilter
from playwright.sync_api import sync_playwright

FOLDER = Path(__file__).resolve().parent / "pictures"
BASE = "<style>*{box-sizing:border-box;font-family:Segoe UI,Arial}body{margin:0;background:#f4f6fa;color:#1c2433}</style>"


def _bar(x: int, value: int, name: str) -> str:
    return (
        f'<rect x="{x}" y="{340 - 4 * value}" width="60" height="{4 * value}" fill="#3465c4"/>'
        f'<text x="{x + 30}" y="365" text-anchor="middle" font-size="16">{name}</text>'
    )


_AXIS = "".join(
    f'<line x1="70" x2="560" y1="{340 - 4 * v}" y2="{340 - 4 * v}" stroke="#ccd"/>'
    f'<text x="60" y="{345 - 4 * v}" text-anchor="end" font-size="14">{v}</text>'
    for v in range(0, 81, 10)
)
_HEAD = '<svg xmlns="http://www.w3.org/2000/svg" width="620" height="400" style="background:#fff">'


def _box(x: int, y: int, text: str) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="120" height="50" rx="6" fill="#e8eefb" stroke="#3465c4"/>'
        f'<text x="{x + 60}" y="{y + 31}" text-anchor="middle" font-size="16">{text}</text>'
    )


def _arrow(path: str, label: str = "", x: int = 0, y: int = 0) -> str:
    return (
        f'<path d="{path}" fill="none" stroke="#333" stroke-width="2" marker-end="url(#a)"/>'
        f'<text x="{x}" y="{y}" font-size="14">{label}</text>'
    )


_MARK = '<defs><marker id="a" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><path d="M0,0L10,4L0,8z"/></marker></defs>'


def _switch(on: bool) -> str:
    side, colour = ("right", "#3465c4") if on else ("left", "#b4bac6")
    return (
        f'<span style="display:inline-block;width:40px;height:22px;border-radius:11px;background:{colour};position:relative">'
        f'<i style="position:absolute;{side}:3px;top:3px;width:16px;height:16px;border-radius:8px;background:#fff"></i></span>'
    )


def _setting(name: str, on: bool) -> str:
    return (
        '<div style="display:flex;justify-content:space-between;padding:14px 0;border-bottom:1px solid #e3e6ee">'
        f"<span>{name}</span>{_switch(on)}</div>"
    )


def _row(label: str, value: str, extra: str = "") -> str:
    return f'<div style="margin-top:14px{extra}"><label style="display:block;font-size:14px;margin-bottom:4px">{label}</label><div style="border:1px solid #aab2c2;border-radius:6px;padding:9px;background:#fff">{value}</div></div>'


def _card(title: str, value: str) -> str:
    return f'<div style="background:#fff;border:1px solid #dde2ec;border-radius:8px;padding:16px;width:210px;height:100px"><div style="font-size:14px;color:#4a5568">{title}</div><div style="font-size:28px;font-weight:600;white-space:nowrap">{value}</div></div>'


def _table(rows: list[tuple[str, str]], total: str) -> str:
    cells = "".join(
        f'<tr><td style="padding:8px 14px">{a}</td><td style="padding:8px 14px;text-align:right">{b}</td></tr>'
        for a, b in rows
    )
    return f'<table style="background:#fff;border-collapse:collapse;width:320px">{cells}<tr style="font-weight:700;border-top:2px solid #333"><td style="padding:8px 14px">Total</td><td style="padding:8px 14px;text-align:right">{total}</td></tr></table>'


def _lines(colours: tuple[str, str]) -> str:
    return (
        '<svg width="420" height="230" style="background:#fff"><polyline points="28,160 120,120 220,130 320,70 400,50" fill="none" stroke="#2563eb" stroke-width="3"/>'
        '<polyline points="28,180 120,170 220,150 320,120 400,87" fill="none" stroke="#f97316" stroke-width="3"/>'
        f'<rect x="20" y="10" width="14" height="14" fill="{colours[0]}"/><text x="40" y="22" font-size="13">North (blue line)</text>'
        f'<rect x="170" y="10" width="14" height="14" fill="{colours[1]}"/><text x="190" y="22" font-size="13">South (orange line)</text>'
        + "".join(
            f'<text x="{x}" y="215" font-size="12" text-anchor="middle">{m}</text>'
            for x, m in zip((30, 120, 220, 320, 395), ("Jan", "Feb", "Mar", "Apr", "May"), strict=True)
        )
        + "".join(
            f'<text x="2" y="{y}" font-size="11">{v}</text>'
            for y, v in ((194, "0"), (144, "150"), (94, "300"))
        )
        + "</svg>"
    )


def _dashboard(total: str, second: str, colours: tuple[str, str]) -> str:
    return (
        '<div style="padding:28px;width:840px"><h1 style="margin:0 0 18px;font-size:24px">Sales overview, May 2026</h1>'
        f'<div style="display:flex;gap:18px">{_card("Orders", "1,204")}{_card("Best customer", second)}{_card("Returns", "2.1 %")}</div>'
        f'<div style="display:flex;gap:24px;margin-top:22px">{_lines(colours)}{_table([("Sales by region, May", "Units"), ("North", "420"), ("South", "310"), ("East", "270")], total)}</div></div>'
    )


PAGES: dict[str, tuple[int, int, str]] = {
    "chart": (
        620,
        400,
        _HEAD
        + _AXIS
        + _bar(100, 30, "Q1")
        + _bar(220, 45, "Q2")
        + _bar(340, 72, "Q3")
        + _bar(460, 60, "Q4")
        + "</svg>",
    ),
    "scan": (
        640,
        420,
        '<div style="background:#fff;padding:26px;height:420px;font-family:Courier New;font-size:15px;line-height:1.75">'
        "<b>DELIVERY NOTE</b> &nbsp; No. DN-70418<br>Date: 9 March 2026 &nbsp; Order of: 27 February 2026<br><br>"
        "Pos &nbsp;Article &nbsp; &nbsp; &nbsp; &nbsp;Quantity &nbsp;Price<br>1 &nbsp; &nbsp;Washers M8 &nbsp; &nbsp; 360 &nbsp; &nbsp; &nbsp; 151.20<br>"
        "2 &nbsp; &nbsp;Bolts M8x40 &nbsp; &nbsp;136 &nbsp; &nbsp; &nbsp; 623.40<br>3 &nbsp; &nbsp;Brackets &nbsp; &nbsp; &nbsp; &nbsp;55 &nbsp; &nbsp; &nbsp;1,100.00<br><br>"
        'Total: 1,874.60<br><br>Received by: <i style="font-family:Segoe Script;font-size:22px">B. Okafor</i></div>',
    ),
    "screen": (
        560,
        380,
        '<div style="padding:26px"><div style="display:flex;gap:26px;border-bottom:1px solid #ccd;margin-bottom:8px">'
        '<span style="padding:8px 0">General</span><span style="padding:8px 0;border-bottom:3px solid #3465c4;font-weight:600">Privacy</span><span style="padding:8px 0">Billing</span></div>'
        + _setting("Daily summary", True)
        + _setting("Show my status", False)
        + _setting("Share with team", True)
        + _setting("Usage statistics", False)
        + '<div style="margin-top:20px"><button style="padding:9px 20px;border:0;border-radius:6px;background:#d8dce5;color:#9aa1b0" disabled>Save</button> '
        '<button style="padding:9px 20px;border:1px solid #3465c4;border-radius:6px;background:#fff;color:#3465c4">Reset</button></div></div>',
    ),
    "flow": (
        640,
        400,
        '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="400" style="background:#fff">'
        + _MARK
        + _box(20, 40, "Draft")
        + _box(200, 40, "Check")
        + _box(400, 40, "Publish")
        + _box(200, 170, "Repair")
        + _box(20, 300, "Reject")
        + _box(400, 300, "Archive")
        + _arrow("M140,65 H198")
        + _arrow("M320,65 H398", "yes", 345, 56)
        + _arrow("M260,90 V168", "no", 268, 135)
        + _arrow("M200,195 H80 V92", "fixed", 100, 187)
        + _arrow("M240,220 V325 H142", "hopeless", 250, 275)
        + _arrow("M460,90 V298")
        + _arrow("M80,350 V380 H460 V352")
        + "</svg>",
    ),
    "form": (
        620,
        520,
        '<div style="padding:28px;width:520px"><h1 style="margin:0;font-size:24px">Register a device</h1>'
        '<p style="color:#e3e7ee">All fields are needed. The serial number is on the back of the device.</p>'
        + _row("Device name", "Printer, second floor")
        + '<div style="color:#b42318;font-size:13px;margin-top:4px">Enter a valid e-mail address.</div>'
        + _row("E-mail", "anna.example.org")
        + _row("Serial number", "SN-4471-0092")
        + '<button style="margin-top:22px;width:96px;height:40px;overflow:hidden;white-space:nowrap;border:0;border-radius:6px;background:#3465c4;color:#fff;font-size:16px;text-align:left;padding:0 10px">Register this device</button></div>',
    ),
    "dashboard": (
        840,
        480,
        _dashboard("1,150", "Bartholomew &amp; Featherstone Ltd", ("#f97316", "#2563eb")),
    ),
    "good": (840, 480, _dashboard("1,000", "Nordwind", ("#2563eb", "#f97316"))),
    "phone": (
        375,
        560,
        '<div style="width:375px;overflow:hidden;padding:18px;position:relative;height:560px"><h1 style="font-size:26px;margin:0">Lakeside walks</h1>'
        '<p style="position:absolute;top:34px;left:18px;margin:0;font-size:16px">Four easy tours for a Sunday afternoon</p>'
        '<div style="margin-top:34px;width:339px;height:170px;border:1px solid #999;background:#fff;font-size:14px;padding:6px">&#10060; lake-view.jpg</div>'
        '<p style="white-space:nowrap;font-size:17px">The north shore path is closed until the end of the spring floods.</p>'
        '<button style="width:339px;height:48px;border:0;border-radius:8px;background:#1f6f4a;color:#fff;font-size:17px">See all tours</button></div>',
    ),
}

_STOCK = [
    ("KX-303", "12.40", 51),
    ("KX-304", "18.65", 8),
    ("KX-330", "21.90", 14),
    ("KX-334", "18.56", 80),
    ("KX-340", "9.75", 73),
    ("KX-343", "33.10", 37),
    ("KX-344", "27.05", 5),
    ("KX-403", "41.80", 0),
    ("KX-404", "14.45", 48),
    ("KX-430", "16.65", 0),
    ("KX-433", "48.10", 19),
    ("KX-434", "40.95", 91),
]
_HANDS = (
    f'<line x1="420" y1="160" x2="{420 + 45 * math.sin(math.radians(258.5)):.1f}" y2="{160 - 45 * math.cos(math.radians(258.5)):.1f}" stroke="#111" stroke-width="6"/>'
    f'<line x1="420" y1="160" x2="{420 + 75 * math.sin(math.radians(222)):.1f}" y2="{160 - 75 * math.cos(math.radians(222)):.1f}" stroke="#111" stroke-width="3"/>'
)


def _gauge() -> str:
    """0 to 10 bar over 270 degrees; the needle is at 6.4."""

    def at(value: float, radius: float) -> tuple[float, float]:
        angle = math.radians(225 - 27 * value)
        return 150 + radius * math.cos(angle), 160 - radius * math.sin(angle)

    out = '<circle cx="150" cy="160" r="110" fill="#fff" stroke="#333" stroke-width="3"/>'
    for tick in range(51):
        value = tick / 5
        (x1, y1), (x2, y2) = at(value, 105), at(value, 90 if tick % 5 == 0 else 98)
        out += f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#333"/>'
        if tick % 10 == 0:
            x, y = at(value, 74)
            out += f'<text x="{x:.1f}" y="{y + 5:.1f}" font-size="15" text-anchor="middle">{value:.0f}</text>'
    x, y = at(6.4, 88)
    out += f'<line x1="150" y1="160" x2="{x:.1f}" y2="{y:.1f}" stroke="#c22" stroke-width="3"/><text x="150" y="225" text-anchor="middle">bar</text>'
    out += '<circle cx="420" cy="160" r="100" fill="#fff" stroke="#333" stroke-width="3"/>'
    for hour in range(12):
        angle = math.radians(30 * hour)
        out += f'<line x1="{420 + 88 * math.sin(angle):.1f}" y1="{160 - 88 * math.cos(angle):.1f}" x2="{420 + 97 * math.sin(angle):.1f}" y2="{160 - 97 * math.cos(angle):.1f}" stroke="#111" stroke-width="3"/>'
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="560" height="320" style="background:#eef">'
        + out
        + _HANDS
        + "</svg>"
    )


def _shapes() -> str:
    """Placed on a grid so that nothing overlaps; the frame holds exactly the first eleven."""
    inside = ["rt", "bc", "gs", "rt", "bc", "rc", "bt", "rt", "bc", "gs", "bc"]
    outside = ["rt", "bc", "gs", "bc", "rt", "bt", "rc", "bc", "rt", "bc", "gs", "rt", "bc", "bt", "rc"]
    inner = [(120 + 70 * (i % 4) + 9 * (i % 3), 105 + 70 * (i // 4) + 7 * (i % 2)) for i in range(11)]
    outer = (
        [(40 + 88 * i, 28 + 6 * (i % 2)) for i in range(7)]
        + [(48 + 84 * i, 352 - 5 * (i % 3)) for i in range(6)]
        + [(470, 140), (520, 250)]
    )
    colours = {"r": "#d22", "b": "#25c", "g": "#2a5"}
    out = '<rect x="82" y="66" width="310" height="222" fill="none" stroke="#333" stroke-width="3"/>'
    for kind, (x, y) in zip([*inside, *outside], [*inner, *outer], strict=True):
        fill = colours[kind[0]]
        if kind[1] == "t":
            out += f'<path d="M{x},{y - 15}L{x + 15},{y + 12}H{x - 15}z" fill="{fill}"/>'
        elif kind[1] == "c":
            out += f'<circle cx="{x}" cy="{y}" r="14" fill="{fill}"/>'
        else:
            out += f'<rect x="{x - 13}" y="{y - 13}" width="26" height="26" fill="{fill}"/>'
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="385" style="background:#fff">'
        + out
        + "</svg>"
    )


def _curves() -> str:
    def place(month: int, value: float) -> str:
        return f"{70 + 85 * month},{330 - 3 * value}"

    a = " ".join(place(m, v) for m, v in enumerate([20, 30, 38, 52, 70, 85]))
    b = " ".join(place(m, v) for m, v in enumerate([70, 60, 58, 51, 40, 25]))
    out = "".join(
        f'<line x1="70" x2="520" y1="{330 - 3 * v}" y2="{330 - 3 * v}" stroke="#dde"/><text x="60" y="{335 - 3 * v}" text-anchor="end" font-size="13">{v}</text>'
        for v in range(0, 101, 20)
    )
    out += "".join(
        f'<text x="{70 + 85 * m}" y="352" text-anchor="middle" font-size="13">{n}</text>'
        for m, n in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun"))
    )
    out += f'<polyline points="{a}" fill="none" stroke="#333" stroke-width="3"/><polyline points="{b}" fill="none" stroke="#333" stroke-width="3" stroke-dasharray="8 6"/>'
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="560" height="370" style="background:#fff">'
        + out
        + "</svg>"
    )


PAGES |= {
    "table": (
        620,
        470,
        '<div style="background:#fff;padding:20px;height:470px;font-size:15px"><b>Price list, spring</b><table style="border-collapse:collapse;margin-top:8px;width:520px">'
        '<tr><th align="left">Code</th><th align="right">Price</th><th align="right">In stock</th></tr>'
        + "".join(
            f'<tr style="border-top:1px solid #bbb"><td style="padding:5px 0">{c}</td><td align="right">{p}</td><td align="right">{n}</td></tr>'
            for c, p, n in _STOCK
        )
        + "</table></div>",
    ),
    "gauge": (560, 320, _gauge()),
    "shapes": (640, 385, _shapes()),
    "lines": (560, 370, _curves()),
}


def main() -> None:
    FOLDER.mkdir(exist_ok=True)
    with sync_playwright() as play:
        browser = play.chromium.launch(channel="msedge")
        for name, (width, height, html) in PAGES.items():
            page = browser.new_page(viewport={"width": width, "height": height})
            page.set_content(BASE + html)
            picture = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
            if name in ("scan", "table"):  # as a cheap scanner gives it: turned, grey, soft
                picture = picture.convert("L").rotate(2.4, expand=True, fillcolor=205)
                picture = picture.resize((picture.width * 3 // 4, picture.height * 3 // 4)).filter(
                    ImageFilter.GaussianBlur(0.6)
                )
                picture = picture.point(lambda v: 60 + v * 3 // 4)
            picture.save(FOLDER / f"{name}.png", optimize=True)
            page.close()
        browser.close()


if __name__ == "__main__":
    main()
