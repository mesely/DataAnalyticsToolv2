"""The NUL-byte guard (finding A6-F1, ruling D-123.2).

Two things are tested, and the split matters. The first is the *estate*:
this repository, right now, has no tracked file git would call binary —
that is the fix's acceptance test, and it runs on every commit. The rest
is the *scanner*: that it actually finds a NUL when one is there, that it
looks past git's 8 KB heuristic, and that it will not sit quietly on a
stale exemption. A guard nobody has watched fail is a guard nobody knows
works.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tools import nul_scan

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def scratch_repo(tmp_path: Path) -> Path:
    """A git repo with one tracked text file, for the scanner's own tests."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "clean.ts").write_text('const sep = "\\u0000";\n')
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    return tmp_path


# -- the estate ------------------------------------------------------------


def test_no_tracked_file_in_this_repo_carries_a_nul_byte():
    findings = nul_scan.scan(REPO_ROOT)
    assert findings == [], (
        "these tracked files contain NUL bytes and so diff as "
        f"'Bin N -> M bytes': {[f[0] for f in findings]}"
    )


def test_the_three_files_the_finding_named_are_text_again():
    # Named explicitly rather than left to the sweep above: A6-F1 is about
    # these three, and a future exemption that re-hid them should fail a
    # test that says their names out loud.
    for rel in ("core/src/setup.ts", "core/src/ratelimit.ts", "core/src/visibility.ts"):
        data = (REPO_ROOT / rel).read_bytes()
        assert b"\0" not in data, f"{rel} is binary to git again"
        # The escape is what replaced the byte; if it is gone, the
        # separator was rewritten rather than escaped, which is a
        # behaviour change this test should not let pass silently.
        assert "\\u0000" in data.decode("utf-8")


def test_the_scan_covers_what_git_tracks_and_not_the_working_junk():
    tracked = nul_scan.tracked_files(REPO_ROOT)
    assert "core/src/visibility.ts" in tracked
    # node_modules and the build output are full of real binaries and are
    # not tracked; a directory walk would have swept them in and the
    # guard would have had to grow exemptions for things git never saw.
    assert not any(p.startswith("core/node_modules/") for p in tracked)
    assert not any(p.startswith(".venv/") for p in tracked)


# -- the scanner -----------------------------------------------------------


def test_a_nul_is_found_and_reported_with_its_line(scratch_repo: Path):
    (scratch_repo / "bad.ts").write_bytes(b'const a = 1;\nconst sep = "\x00";\n')
    subprocess.run(["git", "add", "-A"], cwd=scratch_repo, check=True)

    findings = nul_scan.scan(scratch_repo)

    assert len(findings) == 1
    rel, offset, line_no, line = findings[0]
    assert rel == "bad.ts"
    assert line_no == 2
    assert offset == 26
    assert "const sep" in line


def test_a_nul_past_gits_8kb_heuristic_is_still_caught(scratch_repo: Path):
    # git only sniffs the first 8000 bytes, so this file diffs as text
    # today and turns binary the moment somebody adds a line above it.
    # The guard is on the property, not on today's rendering.
    padding = b"// filler\n" * 900
    assert len(padding) > 8000
    (scratch_repo / "late.ts").write_bytes(padding + b'const sep = "\x00";\n')
    subprocess.run(["git", "add", "-A"], cwd=scratch_repo, check=True)

    findings = nul_scan.scan(scratch_repo)
    assert [f[0] for f in findings] == ["late.ts"]


def test_an_untracked_file_is_not_the_guards_business(scratch_repo: Path):
    (scratch_repo / "scratch.bin").write_bytes(b"\x00\x01\x02")
    assert nul_scan.scan(scratch_repo) == []


def test_an_exemption_suppresses_its_file_and_only_its_file(
    scratch_repo: Path, monkeypatch: pytest.MonkeyPatch
):
    (scratch_repo / "logo.png").write_bytes(b"\x89PNG\x00\x00")
    (scratch_repo / "bad.ts").write_bytes(b'const sep = "\x00";\n')
    subprocess.run(["git", "add", "-A"], cwd=scratch_repo, check=True)
    monkeypatch.setattr(nul_scan, "BINARY_PATHS", ("*.png",))

    assert [f[0] for f in nul_scan.scan(scratch_repo)] == ["bad.ts"]


def test_a_stale_exemption_is_itself_a_failure(
    scratch_repo: Path, monkeypatch: pytest.MonkeyPatch
):
    # An allowlist entry for a file that no longer exists is how a guard
    # rots into a formality: it survives the deletion of what it excused
    # and is there to excuse the next thing.
    monkeypatch.setattr(nul_scan, "BINARY_PATHS", ("assets/logo.png",))

    assert nul_scan.stale_exemptions(scratch_repo) == ["assets/logo.png"]
    assert nul_scan.main(["--root", str(scratch_repo)]) == 1


def test_the_shipped_allowlist_contains_only_named_real_images():
    # AW-7 permits actual UI/brand images, never source files or wildcard exemptions.
    assert nul_scan.BINARY_PATHS
    for name in nul_scan.BINARY_PATHS:
        assert not any(c in name for c in "*?[")
        assert name.endswith((".png", ".jpeg"))
        raw = (REPO_ROOT / name).read_bytes()
        assert raw.startswith(b"\x89PNG\r\n\x1a\n") if name.endswith(".png") else raw.startswith(b"\xff\xd8\xff")


def test_the_cli_exits_nonzero_and_names_the_file(
    scratch_repo: Path, capsys: pytest.CaptureFixture[str]
):
    (scratch_repo / "bad.ts").write_bytes(b'const sep = "\x00";\n')
    subprocess.run(["git", "add", "-A"], cwd=scratch_repo, check=True)

    code = nul_scan.main(["--root", str(scratch_repo)])
    out = capsys.readouterr().out

    assert code == 1
    assert "bad.ts:1" in out
    # It says what to do, not just what is wrong: the fix is the escape.
    assert "\\u0000" in out


def test_the_cli_passes_on_this_repo(capsys: pytest.CaptureFixture[str]):
    assert nul_scan.main(["--root", str(REPO_ROOT)]) == 0
    assert "clean" in capsys.readouterr().out
