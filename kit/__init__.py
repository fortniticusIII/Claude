"""Claude's research kit. Start of any session:

    git clone --depth 1 https://github.com/fortniticusIII/claude ~/claude   (if not already there)
    bash ~/claude/bootstrap.sh                                               (installs extras, runs selftest)
    import sys; sys.path.insert(0, "/home/claude/claude"); import kit; kit.help()

Modules: http (polite cached fetch + source ledger), web (page/PDF/table text), scholar (papers),
data (official statistics), lookup (reference databases), qa (check a page before publishing).
"""
from . import http  # noqa: F401

__version__ = "1.0"


def help() -> None:  # noqa: A001
    import importlib
    for m in ("web", "scholar", "data", "lookup", "qa", "http"):
        mod = importlib.import_module(f"kit.{m}")
        print(f"== kit.{m}\n{(mod.__doc__ or '').strip()}\n")


def sources(only=None) -> str:
    """Markdown Sources list of everything fetched in this Python session."""
    return http.sources_md(only=only)
