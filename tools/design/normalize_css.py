"""Snap workbench.css onto the design-system scales (idempotent).

type   12 14 16 20 24 32 px        (<=12->12, 13-15->14, 16-17->16, 18-21->20, 22-29->24, >=30->32;
                                     page titles are pinned to 32 desktop / 24 compact by selector)
weight 400 500 600 700             (350->400, 450->500, 550/620/650->600)
space  multiples of 4 px           (padding, margin, gap, inset; 1px hairlines and calc() kept)
radius 6 10 14 px, 50% / 999px     (<=6->6, 7-11->10, 12-30->14)
Run: .venv/bin/python -m tools.design.normalize_css [--check]
"""
import re
import sys
from pathlib import Path

CSS = Path(__file__).resolve().parents[2] / "core/web/src/workbench/workbench.css"
SPACE_PROPS = r"padding(?:-(?:top|right|bottom|left|inline|block)(?:-start|-end)?)?|margin(?:-(?:top|right|bottom|left|inline|block)(?:-start|-end)?)?|gap|row-gap|column-gap|inset|top|right|bottom|left"
PAGE_TITLES = (".wb h1", ".wb-page-heading h1")


def snap_type(v):
    return 12 if v <= 12 else 14 if v <= 15 else 16 if v <= 17 else 20 if v <= 21 else 24 if v <= 29 else 32


def snap_space(v):
    return v if v <= 1 else int(4 * round(v / 4 + 1e-9)) or 4


def snap_radius(v):
    return v if v >= 30 else 6 if v <= 6 else 10 if v <= 11 else 14


def px(value, fn):
    if "calc(" in value or "var(" in value and "px" not in value:
        return value
    def one(m):
        sign, num = m.group(1), float(m.group(2))
        out = fn(num)
        return f"{sign}{int(out) if float(out).is_integer() else out}px"
    return re.sub(r"(-?)(\d*\.?\d+)px", one, value)


def normalize(css):
    out, selector = [], ""
    for line in css.split("\n"):
        stripped = line.strip()
        if stripped.endswith("{"):
            selector = stripped[:-1].strip()
        m = re.match(r"^(\s*)([a-z-]+)\s*:\s*(.+?);\s*$", line)
        if m:
            indent, prop, value = m.groups()
            if prop == "font-size" and "px" in value:
                if selector in PAGE_TITLES:
                    value = "32px" if indent.count(" ") <= 2 else "24px"
                else:
                    value = px(value, snap_type)
            elif prop == "font-weight" and re.fullmatch(r"\d+( !important)?", value.strip()):
                w, rest = int(value.split()[0]), value[len(value.split()[0]):]
                value = str({350: 400, 450: 500, 550: 600, 620: 600, 650: 600}.get(w, w)) + rest
            elif re.fullmatch(SPACE_PROPS, prop) and "px" in value:
                value = px(value, snap_space)
            elif prop.startswith("border") and "radius" in prop and "px" in value:
                value = px(value, snap_radius)
            line = f"{indent}{prop}: {value};"
        out.append(line)
    return "\n".join(out)


if __name__ == "__main__":
    src = CSS.read_text()
    new = normalize(src)
    if "--check" in sys.argv:
        sys.exit(0 if new == src else 1)
    CSS.write_text(new)
    print("normalized", sum(a != b for a, b in zip(src.split("\n"), new.split("\n"))), "lines")
