"""Make the stripped copy of wire/collect.py that the scheduled Wire collector carries in its prompt.

Scheduled sessions refuse to run code cloned from GitHub ("Code from External", Oct 19, 2026), so the
collector task holds the program itself. Run this after editing collect.py, test the copy against a
live dump next to collect.py (their writes.json must match), then paste the copy and its sha256 into
the task prompt with update_trigger.

    python3 -m wire.inline OUT.py      # writes the copy, prints its size and sha256
"""
import hashlib
import re
import sys
from pathlib import Path

SRC = Path(__file__).with_name("collect.py")
HEADER = "# The Wire collector (inline copy of wire/collect.py, Oct 19 2026). Usage: python3 collect.py DUMP OUT\n"


def stripped(src: str) -> str:
    body = src.split('"""', 2)[2]                                   # drop the module docstring
    body = re.sub(r'\n    """.*?"""', "", body, flags=re.S)         # drop function docstrings
    body = re.sub(r"    try:\n        import feedparser.*?    except ImportError:\n        pass\n", "", body, flags=re.S)
    lines = []
    for line in body.split("\n"):
        if line.strip().startswith("#"):
            continue
        lines.append(re.sub(r"\s{2,}#\s.*$", "", line).rstrip())
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip() + "\n"
    return HEADER + body


if __name__ == "__main__":
    out = stripped(SRC.read_text())
    Path(sys.argv[1]).write_text(out)
    print(len(out), "bytes; sha256", hashlib.sha256(out.encode()).hexdigest())
