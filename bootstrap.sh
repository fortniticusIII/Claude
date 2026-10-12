#!/usr/bin/env bash
# Set up Claude's research kit in a fresh session, then check every source.
#   git clone --depth 1 https://github.com/fortniticusIII/claude /home/claude/claude   # public; no add_repo needed to read
#   bash /home/claude/claude/bootstrap.sh            # add --no-test to skip the live check
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
PKGS="trafilatura feedparser pyarrow duckdb"

if ! python3 -c "import trafilatura, feedparser, pyarrow, duckdb" 2>/dev/null; then
  # The registries sit on NO_PROXY, and direct DNS can fail; route them through the proxy instead.
  NP=$(echo "${NO_PROXY:-}" | tr ',' '\n' | grep -vE '^(pypi.org|files.pythonhosted.org|registry.npmjs.org)$' | paste -sd,)
  pip install -q --break-system-packages $PKGS 2>/dev/null \
    || NO_PROXY=$NP no_proxy=$NP pip install -q --break-system-packages $PKGS 2>&1 | grep -v "^WARNING" \
    || echo "pip failed: kit still works, but web.page falls back to plain BeautifulSoup text"
fi

# Shell egress check: the open web needs the user's Capabilities setting (see the work log lessons).
if curl -sS -o /dev/null --max-time 10 https://example.com 2>/dev/null; then
  echo "open web: reachable from the shell"
else
  echo "open web: NOT reachable from the shell. Use WebFetch/WebSearch; GitHub still works."
fi

if [ "${1:-}" != "--no-test" ]; then
  (cd "$HERE" && python3 -m kit.selftest)
fi
echo
echo "Ready:  import sys; sys.path.insert(0, '$HERE'); import kit; kit.help()"
