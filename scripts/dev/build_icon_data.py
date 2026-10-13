"""Builds the bundled icon data (TODO P2.3, D-283) from the two npm packages, so the data can be rebuilt and audited:

    npm pack lucide-static @material-symbols/svg-400        (ISC and Apache-2.0)
    extract both tarballs, then:
    python scripts/dev/build_icon_data.py <lucide package folder> <material-symbols package folder>

Writes src/forge/data/icons/: lucide.json.gz (every Lucide icon as its drawing elements plus search tags),
material.json.gz (a curated set of Material Symbols, outlined style, as path data) and the licence texts. Nothing is
downloaded at run time."""

from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "src" / "forge" / "data" / "icons"

# Material Symbols chosen for presentations: business, data, people, places, tech, health, actions, arrows.
MATERIAL = """
check close add remove search home settings person group mail call chat calendar_month schedule location_on language lock
shield verified trending_up trending_down bar_chart pie_chart analytics payments savings account_balance shopping_cart
local_shipping inventory_2 factory engineering build code terminal storage cloud bolt lightbulb rocket_launch flag star favorite
thumb_up thumb_down handshake public eco water_drop energy_savings_leaf health_and_safety medical_services school menu_book science
psychology track_changes insights speed timer hourglass_empty event groups support_agent security key visibility download upload
share link attach_file description folder image play_arrow pause arrow_forward arrow_back arrow_upward arrow_downward expand_more
chevron_right info warning error help notifications sync autorenew refresh edit delete save print tune filter_alt sort apps
dashboard table_chart timeline map directions_car flight train directions_bike restaurant coffee home_work apartment store
storefront campaign mic videocam headphones phone_iphone laptop desktop_windows devices wifi bluetooth battery_full power memory hub
lan api extension widgets category label bookmark sentiment_satisfied emoji_events workspace_premium military_tech diversity_3
volunteer_activism local_hospital vaccines bloodtype monitor_heart sell receipt_long request_quote balance gavel policy badge
contact_page assignment task_alt checklist fact_check rule published_with_changes swap_horiz compare_arrows alt_route account_tree
schema deployed_code smart_toy auto_awesome magic_button lightbulb_circle cycle partner_exchange conversion_path
""".split()


def lucide(package: Path) -> dict[str, object]:
    nodes = json.loads((package / "icon-nodes.json").read_text(encoding="utf-8"))
    tags = json.loads((package / "tags.json").read_text(encoding="utf-8"))
    icons = {
        name: {"n": [[tag, attrs] for tag, attrs in drawing], "t": tags.get(name, [])} for name, drawing in nodes.items()
    }
    return {"viewBox": [0, 0, 24, 24], "style": "stroke", "strokeWidth": 2, "icons": icons}


def material(package: Path) -> dict[str, object]:
    icons: dict[str, str] = {}
    for name in MATERIAL:
        file = package / "outlined" / f"{name}.svg"
        if not file.is_file():
            continue
        paths = re.findall(r'<path d="([^"]+)"', file.read_text(encoding="utf-8"))
        if paths:
            icons[name] = " ".join(paths)
    return {"viewBox": [0, -960, 960, 960], "style": "fill", "icons": icons}


def write(name: str, data: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    (OUT / name).write_bytes(gzip.compress(text.encode("utf-8"), 9, mtime=0))


def main(lucide_folder: str, material_folder: str) -> int:
    lucide_path, material_path = Path(lucide_folder), Path(material_folder)
    write("lucide.json.gz", lucide(lucide_path))
    set_ = material(material_path)
    write("material.json.gz", set_)
    (OUT / "LICENSE-lucide.txt").write_text((lucide_path / "LICENSE").read_text(encoding="utf-8"), encoding="utf-8")
    (OUT / "LICENSE-material-symbols.txt").write_text(
        (material_path / "LICENSE").read_text(encoding="utf-8"), encoding="utf-8"
    )
    print(f"lucide: {len(lucide(lucide_path)['icons'])} icons; material: {len(set_['icons'])} of {len(MATERIAL)} chosen")  # type: ignore[arg-type]
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
