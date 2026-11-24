"""Cheat discovery.

Cheats are loaded from two places:

  1. The built-in catalog shipped in ``crashtest/cheats/`` (one directory per
     cheat).
  2. Any directory advertised by a ``crashtest.cheats`` entry point, so third
     parties can ship extra cheats without forking.

The registry is intentionally lazy and filesystem-driven: adding a cheat is
"drop a directory with a cheat.toml", nothing to register in code.
"""

from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache
from importlib import resources
from importlib.metadata import entry_points
from pathlib import Path

from .cheatspec import Cheat, load_cheat

CHEATS_PACKAGE = "crashtest.cheats"


def _builtin_cheats_dir() -> Path:
    """Filesystem path to the shipped cheats directory."""
    # resources.files works whether crashtest is a source checkout or an
    # installed wheel.
    return Path(str(resources.files(CHEATS_PACKAGE)))


def _entrypoint_dirs() -> list[Path]:
    dirs: list[Path] = []
    try:
        eps = entry_points(group="crashtest.cheats")
    except TypeError:  # pragma: no cover - very old importlib.metadata
        eps = entry_points().get("crashtest.cheats", [])  # type: ignore[assignment]
    for ep in eps:
        try:
            loaded = ep.load()
        except Exception:  # pragma: no cover
            continue
        p = Path(str(loaded))
        if p.is_dir():
            dirs.append(p)
    return dirs


def _iter_cheat_dirs() -> Iterable[Path]:
    seen: set[str] = set()
    roots = [_builtin_cheats_dir(), *_entrypoint_dirs()]
    for root in roots:
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if child.is_dir() and (child / "cheat.toml").is_file():
                if child.name in seen:
                    continue
                seen.add(child.name)
                yield child


@lru_cache(maxsize=1)
def _load_all() -> dict[str, Cheat]:
    cheats: dict[str, Cheat] = {}
    for d in _iter_cheat_dirs():
        cheat = load_cheat(d)
        cheats[cheat.id] = cheat
    return cheats


def all_cheats() -> list[Cheat]:
    """Every discovered cheat, sorted by id."""
    return [c for _, c in sorted(_load_all().items())]


def cheats_by_priority(priority: str) -> list[Cheat]:
    return [c for c in all_cheats() if c.meta.priority == priority]


def find_cheat(cheat_id: str) -> Cheat:
    cheats = _load_all()
    if cheat_id not in cheats:
        known = ", ".join(sorted(cheats)) or "(none found)"
        raise KeyError(f"unknown cheat {cheat_id!r}. Known cheats: {known}")
    return cheats[cheat_id]


def reset_cache() -> None:
    """Drop the discovery cache (tests that add cheats on disk call this)."""
    _load_all.cache_clear()
