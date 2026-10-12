"""Copy the operational parts of my memory into this folder.

Usage, from any session with this repo attached:
    1. ArtifactData list collection='handoff' on the work log, with out_dir=<dump folder>
    2. python3 memory/backup.py <dump folder>/handoff
    3. commit and push

Only the docs in KEEP are copied. Personal context about the person I work with
(user, current, catalog, schedules, chapters) stays in the private database and
never goes into this public repo.
"""
import json
import sys
from pathlib import Path

KEEP = ("protocol", "lessons", "tools", "self")
HERE = Path(__file__).resolve().parent


def main(dump: str) -> None:
    src = Path(dump)
    for name in KEEP:
        f = src / f"{name}.json"
        if not f.exists():
            print(f"skip {name}: not in dump")
            continue
        doc = json.loads(f.read_text())
        doc = doc.get("data", doc) if isinstance(doc, dict) else doc
        (HERE / f"{name}.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        print(f"saved {name}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python3 memory/backup.py <folder with handoff/*.json>")
    main(sys.argv[1])
