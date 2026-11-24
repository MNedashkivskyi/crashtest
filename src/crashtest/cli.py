"""crashtest command-line interface.

PR1 ships ``list`` and ``version``. ``scan`` (the matrix runner that drives
``harbor run``) arrives with the runner in a later PR; it is stubbed here with a
clear message so the entry point is valid from day one.
"""

from __future__ import annotations

import argparse
import sys

from . import __version__


def _cmd_list(args: argparse.Namespace) -> int:
    from .registry import all_cheats

    cheats = all_cheats()
    if not cheats:
        print("No cheats found. (The catalog ships from PR2 onward.)")
        return 0
    width = max(len(c.id) for c in cheats)
    for c in cheats:
        m = c.meta
        print(f"{c.id:<{width}}  {m.priority}  {m.category:<15}  {m.summary}")
    return 0


def _cmd_scan(args: argparse.Namespace) -> int:
    try:
        from .runner import run_scan  # noqa: F401
    except Exception:
        print(
            "crashtest scan is not available yet in this build "
            "(the runner lands in a later PR).",
            file=sys.stderr,
        )
        return 2
    return run_scan(args)  # pragma: no cover - wired up with the runner


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="crashtest", description=__doc__)
    p.add_argument("--version", action="version", version=f"crashtest {__version__}")
    sub = p.add_subparsers(dest="command")

    p_list = sub.add_parser("list", help="list discovered cheats")
    p_list.set_defaults(func=_cmd_list)

    p_scan = sub.add_parser("scan", help="run controls + cheats over a dataset or task path")
    p_scan.add_argument("-p", "--path", help="path to a task or a directory of tasks")
    p_scan.add_argument("-d", "--dataset", help="Harbor dataset id, e.g. terminal-bench@2.0")
    p_scan.add_argument("--only", help="comma-separated cheat ids to run")
    p_scan.add_argument("--priority", help="run only cheats of this priority (P0/P1/P2)")
    p_scan.add_argument("-o", "--out", default="scorecard", help="output path prefix")
    p_scan.set_defaults(func=_cmd_scan)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
