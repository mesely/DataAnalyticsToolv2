"""Light-theme text tones that fail WCAG 1.4.3 are darkened (same hue) until they reach 4.6:1 on both white
cards and the page background. Only tones used exclusively as `color:` and never inside the dark sidebar are
touched, and only under .wb[data-theme="light"]; the dark theme keeps its own remap. Writes a generated block
at the end of workbench.css between markers (idempotent).
Run: .venv/bin/python -m tools.design.contrast_tones
"""
import colorsys
import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[2] / "core/web/src/workbench/workbench.css"
BEGIN, END = "/* >>> generated: light text contrast (tools/design/contrast_tones.py) */", "/* <<< generated: light text contrast */"
SURFACES = ("ffffff", "f7f8fb")
NAV = re.compile(r"sidebar|wb-nav|wb-user|wb-brand|wb-project|wb-mobile|data-theme=\"dark\"")


def lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a, b):
    x, y = sorted([lum(a), lum(b)], reverse=True)
    return (x + 0.05) / (y + 0.05)


def darken(h, target=4.6):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    hue, light, sat = colorsys.rgb_to_hls(r, g, b)
    while light > 0:
        out = "".join(f"{round(v * 255):02x}" for v in colorsys.hls_to_rgb(hue, light, sat))
        if min(ratio(out, s) for s in SURFACES) >= target:
            return out
        light -= 0.005
    return "1c2941"


def render(css):
    """Return workbench.css with the generated block (re)computed; render(render(x)) == render(x)."""
    if BEGIN in css:
        css = css[:css.index(BEGIN)].rstrip() + "\n"
    base = css.split('.wb[data-theme="dark"] {')[0]
    light = dict(re.findall(r"--tone-([0-9a-f]{6}):\s*#([0-9a-f]{6});", base))
    uses, nav = {}, set()
    for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        for prop, val in re.findall(r"([a-z-]+)\s*:\s*([^;]+);", body):
            for tone in re.findall(r"var\(--tone-([0-9a-f]{6})\)", val):
                uses.setdefault(tone, set()).add("color" if prop == "color" else "other")
                if NAV.search(selector):
                    nav.add(tone)
    changes = []
    for tone, kinds in sorted(uses.items()):
        hexv = light.get(tone, tone)
        if kinds != {"color"} or tone in nav or ratio(hexv, "ffffff") < 2.0:
            continue  # backgrounds/borders, dark-sidebar text, or near-white tints used on dark surfaces
        if min(ratio(hexv, s) for s in SURFACES) < 4.6:
            changes.append((tone, darken(hexv)))
    block = [BEGIN, '.wb[data-theme="light"] {'] + [f"  --tone-{t}: #{v};" for t, v in changes] + ["}", END, ""]
    return css.rstrip() + "\n\n" + "\n".join(block), len(changes)


def main():
    css, n = render(CSS.read_text())
    CSS.write_text(css)
    print(f"{n} light-theme text tones darkened to >= 4.6:1")


if __name__ == "__main__":
    main()
