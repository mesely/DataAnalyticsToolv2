"""No tracked file carries a NUL byte (finding A6-F1, ruling D-123.2).

    .venv/bin/python -m tools.nul_scan

Exit 0 when clean, 1 when a tracked file contains one, naming the file,
the byte offset and the line — because "this file is binary" is exactly
the message that hid the defect for four milestones.

**Why this guard exists.** Git classifies a file as binary when it finds
a NUL in the first 8 KB, and renders every diff of it as
``Bin N -> M bytes``. Three source files used the byte as a separator
inside template literals, so `core/src/setup.ts`, `core/src/ratelimit.ts`
and `core/src/visibility.ts` had been unreviewable in diff since CP-4 —
two of them enforcement code that the CP-4 security reviews therefore
read whole rather than as changes. The repo's first engineering norm is
*small, reviewable diffs*; for those files it had silently not held.

The fix at each site was to write the escape (``\\u0000``) instead of
embedding the byte, which changes no runtime behaviour at all. This
scanner is the half that makes it stay fixed: the defect is invisible by
construction, so nothing but a mechanical check would catch its return.

**The scan is whole-file, not first-8-KB.** Git's heuristic stops at
8 KB; a NUL past that point would leave the file diffable today and turn
it binary the moment a line is added above. Guarding the property rather
than the symptom means the guard does not depend on where in the file
somebody types.

**BINARY_PATHS contains named image exceptions (AW-7).** Analytic UI screenshots
and original brand JPEGs are intentionally binary. Each exact path is listed
below; text/code files are never exempted. Additional binary assets require
a visible named exception and an evidence manifest update. A pattern listed here that matches no
tracked file is itself an error: stale exemptions are how allowlists rot.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Exact named image exceptions; no broad extension exemption (AW-7).
BINARY_PATHS: tuple[str, ...] = (
    'core/web/src/workbench/assets/avatars/analyst-analyst.jpg',
    'core/web/src/workbench/assets/avatars/analyst-automotive.jpg',
    'core/web/src/workbench/assets/avatars/analyst-banking.jpg',
    'core/web/src/workbench/assets/avatars/analyst-core.jpg',
    'core/web/src/workbench/assets/avatars/analyst-energy.jpg',
    'core/web/src/workbench/assets/avatars/analyst-health.jpg',
    'core/web/src/workbench/assets/avatars/analyst-logistics.jpg',
    'core/web/src/workbench/assets/avatars/analyst-retail.jpg',
    'core/web/src/workbench/assets/avatars/analyst-strategist.jpg',
    'core/web/src/workbench/assets/avatars/analyst-telecom.jpg',
    'core/web/src/workbench/assets/avatars/app-mark.jpg',
    'core/web/src/workbench/assets/data-preparation.jpeg',
    'core/web/src/workbench/assets/favicon.png',
    'core/web/src/workbench/assets/mascot/mascot-hanging.png',
    'core/web/src/workbench/assets/mascot/mascot-reading.png',
    'core/web/src/workbench/assets/mascot/mascot-searching.png',
    'core/web/src/workbench/assets/mascot/mascot-waving.png',
    'core/web/src/workbench/assets/model-studio.jpeg',
    'core/web/src/workbench/assets/relationship-explorer.jpeg',
    'docs/evidence/phase10/01-dark-overview.jpeg',
    'docs/evidence/phase10/02-light-overview.jpeg',
    'docs/evidence/phase10/03-decisions-light.jpeg',
    'docs/evidence/phase10/04-evidence-reference.jpeg',
    'docs/evidence/phase11/01-forecast-dark.jpeg',
    'docs/evidence/phase11/02-encoding-light-before.jpeg',
    'docs/evidence/phase11/03-parquet-mobile-before.jpeg',
    'docs/evidence/phase11/04-narrative-mobile-dark.jpeg',
    'docs/evidence/phase11/05-encoding-mobile-final.jpeg',
    'docs/evidence/phase11/06-decision-light-final.jpeg',
    'docs/evidence/phase3/mobile-final.jpeg',
    'docs/evidence/phase3/uci-temporal-final.jpeg',
    'docs/evidence/phase3/uci-temporal.jpeg',
    'docs/evidence/phase4/01-before.jpeg',
    'docs/evidence/phase4/02-overview.jpeg',
    'docs/evidence/phase4/03-analysis.jpeg',
    'docs/evidence/phase4/04-network.jpeg',
    'docs/evidence/phase4/05-temporal.jpeg',
    'docs/evidence/phase4/06-mobile.jpeg',
    'docs/evidence/phase4/07-findings.jpeg',
    'docs/evidence/phase4/08-library-empty.jpeg',
    'docs/evidence/phase4/09-provider-fallback.jpeg',
    'docs/evidence/phase4/overview-delivery.jpeg',
    'docs/evidence/phase5/01-before.jpeg',
    'docs/evidence/phase5/02-preview.jpeg',
    'docs/evidence/phase5/03-mobile.jpeg',
    'docs/evidence/phase6/01-contract.jpeg',
    'docs/evidence/phase6/02-wine-result.jpeg',
    'docs/evidence/phase6/03-mobile.jpeg',
    'docs/evidence/phase6/04-regression.jpeg',
    'docs/evidence/phase6/05-preparation-art.jpeg',
    'docs/evidence/phase6/06-model-art.jpeg',
    'docs/evidence/phase6/07-overview-art.jpeg',
    'docs/evidence/phase6/08-mobile-art.jpeg',
    'docs/evidence/workspace-overview.jpeg',
    'docs/showcase/01-overview-dark.jpg',
    'docs/showcase/02-overview-light.jpg',
    'docs/showcase/03-chart-studio-compare.jpg',
    'docs/showcase/04-chart-studio-interval.jpg',
    'docs/showcase/05-chart-studio-exclusion.jpg',
    'docs/showcase/06-chart-studio-trend.jpg',
    'docs/showcase/07-reasoning-tree.jpg',
    'docs/showcase/08-decision-forecast.jpg',
    'docs/showcase/09-code-export-readme.jpg',
    'docs/showcase/10-code-export-python.jpg',
    'docs/showcase/11-analysis-assistant.jpg',
    'docs/showcase/12-network.jpg',
    'docs/showcase/13-temporal.jpg',
    'docs/showcase/14-sql-lab.jpg',
    'docs/showcase/15-data-preparation.jpg',
    'docs/showcase/16-model-studio.jpg',
    'docs/showcase/17-mobile-overview.jpg',
    'docs/showcase/18-mobile-chart-studio.jpg',
    'docs/showcase/19-sign-in.jpg',
    'docs/showcase/20-empty-findings.jpg',
    'docs/showcase/21-chart-studio-groq.jpg',
    'docs/showcase/22-assistant-groq.jpg',
    'docs/showcase/chart-studio.gif',
)


def tracked_files(root: Path = REPO_ROOT) -> list[str]:
    """Every path git tracks, from git itself rather than a directory walk.

    A walk would sweep in `node_modules/`, `dist/`, `__pycache__` and the
    venv — none of which the guard has any claim over, and one of which
    (node_modules) contains real binaries. What git tracks is exactly
    what a diff can be unreviewable in.
    """
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    return [p for p in out.split("\0") if p]


def exempt(path: str) -> bool:
    return any(fnmatch(path, pattern) for pattern in BINARY_PATHS)


def scan(root: Path = REPO_ROOT) -> list[tuple[str, int, int, str]]:
    """Tracked files containing a NUL: (path, offset, line number, line)."""
    findings: list[tuple[str, int, int, str]] = []
    for rel in tracked_files(root):
        if exempt(rel):
            continue
        full = root / rel
        try:
            data = full.read_bytes()
        except (FileNotFoundError, IsADirectoryError, PermissionError):
            # A submodule or a path deleted in the working tree: not this
            # guard's business, and failing on it would make the check
            # about the checkout rather than about the content.
            continue
        offset = data.find(b"\0")
        if offset == -1:
            continue
        line_no = data.count(b"\n", 0, offset) + 1
        start = data.rfind(b"\n", 0, offset) + 1
        end = data.find(b"\n", offset)
        raw = data[start:] if end == -1 else data[start:end]
        findings.append((rel, offset, line_no, raw.decode("utf-8", "replace")))
    return findings


def stale_exemptions(root: Path = REPO_ROOT) -> list[str]:
    """Patterns in BINARY_PATHS matching nothing git tracks."""
    files = tracked_files(root)
    return [p for p in BINARY_PATHS if not any(fnmatch(f, p) for f in files)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)

    stale = stale_exemptions(args.root)
    findings = scan(args.root)

    if not findings and not stale:
        print(f"NUL scan clean: {len(tracked_files(args.root))} tracked files, no NUL bytes.")
        return 0

    for rel, offset, line_no, line in findings:
        print(f"{rel}:{line_no}: NUL byte at offset {offset}")
        # `repr` so the offending byte is visible as \x00 rather than
        # swallowed by the terminal — the point is to make it readable.
        print(f"    {line!r}")
    if findings:
        print()
        print(
            "A NUL byte makes git treat the file as binary: every diff of it renders as\n"
            '"Bin N -> M bytes" and stops being reviewable. Write the escape sequence\n'
            '("\\u0000", or String.fromCharCode(0)) instead of embedding the byte — same\n'
            "value at runtime, and the diff comes back. (Finding A6-F1, ruling D-123.2.)"
        )
    for pattern in stale:
        print(f"stale exemption: BINARY_PATHS pattern {pattern!r} matches no tracked file")
    return 1


if __name__ == "__main__":
    sys.exit(main())
