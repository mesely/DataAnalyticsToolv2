"""Verify upstream attribution without overwriting domain adaptations (network, optional)."""

from pathlib import Path
import hashlib, json, urllib.request


def main():
    ledger = json.loads(
        (Path(__file__).resolve().parent / "SOURCE_LEDGER.json").read_text()
    )
    for item in ledger:
        url = f"https://raw.githubusercontent.com/{item['source_repo']}/{item['source_commit']}/{item['source_path']}"
        raw = urllib.request.urlopen(url, timeout=30).read()
        if hashlib.sha256(raw).hexdigest() != item["source_sha256"]:
            raise ValueError("Source hash mismatch: " + item["source_path"])
    print(f"{len(ledger)} pinned source files verified; adapted files untouched.")


if __name__ == "__main__":
    main()
