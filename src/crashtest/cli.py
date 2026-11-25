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


def _cmd_selftest(args: argparse.Namespace) -> int:
    from .selftest import check_all, check_one

    results = check_one(args.cheat) if args.cheat else check_all()
    by_cheat: dict[str, list] = {}
    for r in results:
        by_cheat.setdefault(r.cheat_id, []).append(r)

    failed = 0
    for cheat_id, checks in sorted(by_cheat.items()):
        bad = [c for c in checks if not c.ok]
        status = "PASS" if not bad else "FAIL"
        print(f"[{status}] {cheat_id}")
        for c in checks:
            mark = "ok" if c.ok else "XX"
            extra = f"  ({c.detail})" if c.detail else ""
            print(f"    {mark} {c.point:<18} expected={c.expected} reward={c.reward}{extra}")
        failed += len(bad)

    print()
    print(f"{len(by_cheat)} cheats checked, {failed} failing point(s).")
    return 0 if failed == 0 else 1


def _select_cheats(args: argparse.Namespace):
    from .registry import all_cheats, find_cheat

    if args.only:
        return [find_cheat(cid.strip()) for cid in args.only.split(",") if cid.strip()]
    cheats = all_cheats()
    if args.priority:
        cheats = [c for c in cheats if c.meta.priority == args.priority]
    return cheats


def _cmd_static(args: argparse.Namespace) -> int:
    from .runner import discover_tasks
    from .static import render_findings, scan_task_static

    tasks = discover_tasks(args.path)
    total = 0
    for t in tasks:
        findings = scan_task_static(t.path or args.path)
        if findings:
            print(f"== {t.id} ==")
            print(render_findings(findings))
            total += len(findings)
    print(f"\n{len(tasks)} task(s), {total} hint(s).")
    return 1 if total else 0


def _cmd_scan(args: argparse.Namespace) -> int:
    import os

    from .runner import (
        HarborHarness,
        ScanConfig,
        collect_pins,
        discover_tasks,
        run_scan,
        scan_dataset,
    )
    from .scorecard import build_scorecard, load_scorecard, write_scorecard

    if not args.path and not args.dataset:
        print("scan needs -p/--path or -d/--dataset", file=sys.stderr)
        return 2

    cheats = _select_cheats(args)
    cfg = ScanConfig(
        harbor_bin=args.harbor_bin,
        n_concurrent=args.concurrent,
        timeout_multiplier=args.timeout_multiplier,
        harbor_commit=args.harbor_commit,
        dataset_commit=args.dataset_commit,
        image_digest=args.image_digest,
        ablation=args.ablation,
        dry_run=args.dry_run,
    )
    harness = HarborHarness()
    pins = collect_pins(cfg)

    def _make_scorecard(controls, cells, mode):
        return build_scorecard(
            controls,
            cells,
            pins=pins,
            config={
                "mode": mode,
                "tasks": len(controls),
                "cheats": len(cheats),
                "ablation": cfg.ablation,
                "dry_run": cfg.dry_run,
            },
        )

    if args.path:
        # Path mode: one task directory at a time (what the CI Action uses).
        tasks = discover_tasks(args.path, dataset=args.dataset or "")
        if not tasks:
            print("no tasks found", file=sys.stderr)
            return 2
        controls, cells = run_scan(tasks, cheats, harness, cfg)
        mode = f"path:{args.path}"
    else:
        # Dataset mode: one Harbor run per agent/cheat over the whole dataset.
        if args.ablation:
            print("note: --ablation runs in path mode only; ignored for a dataset", file=sys.stderr)
        mode = f"dataset:{args.dataset}"

        resume_controls = resume_cells = None
        if args.resume and os.path.isfile(f"{args.out}.json"):
            prev = load_scorecard(f"{args.out}.json")
            resume_controls, resume_cells = prev.controls, prev.cells
            done = sorted({c.cheat_id for c in prev.cells})
            print(f"resuming from {args.out}.json ({len(done)} cheats already done)")

        # Flush the scorecard after controls and after each cheat, so a crash
        # mid-run keeps everything already computed (and --resume can continue).
        def _flush(controls, cells):
            write_scorecard(_make_scorecard(controls, cells, mode), args.out, sarif=args.sarif)

        controls, cells = scan_dataset(
            args.dataset,
            cheats,
            harness,
            cfg,
            on_update=_flush,
            resume_controls=resume_controls,
            resume_cells=resume_cells,
        )

    sc = _make_scorecard(controls, cells, mode)
    written = write_scorecard(sc, args.out, sarif=args.sarif)

    cc = sc.cell_counts()
    print(f"tasks: {len(controls)}  cheats: {len(cheats)}")
    print(
        f"controls: {sc.control_counts()}\n"
        f"cells: HOLE {cc['HOLE']} · FLAKY {cc['FLAKY-HOLE']} · "
        f"DEFENDED {cc['DEFENDED']} · N-A {cc['N-A']} · ERROR {cc['ERROR']}"
    )
    print("wrote: " + ", ".join(written))
    # Exit non-zero if any confirmed hole, so CI fails the gate.
    return 1 if sc.tasks_with_hole() else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="crashtest", description=__doc__)
    p.add_argument("--version", action="version", version=f"crashtest {__version__}")
    sub = p.add_subparsers(dest="command")

    p_list = sub.add_parser("list", help="list discovered cheats")
    p_list.set_defaults(func=_cmd_list)

    p_self = sub.add_parser(
        "selftest", help="validate cheats against their vuln/hardened fixtures (no Harbor)"
    )
    p_self.add_argument("cheat", nargs="?", help="a single cheat id (default: all)")
    p_self.set_defaults(func=_cmd_selftest)

    p_static = sub.add_parser(
        "static", help="fast no-Docker static hints over a task or directory of tasks"
    )
    p_static.add_argument("-p", "--path", required=True, help="task or directory of tasks")
    p_static.set_defaults(func=_cmd_static)

    p_scan = sub.add_parser("scan", help="run controls + cheats over a dataset or task path")
    p_scan.add_argument("-p", "--path", help="path to a task or a directory of tasks")
    p_scan.add_argument("-d", "--dataset", help="Harbor dataset id, e.g. terminal-bench@2.0")
    p_scan.add_argument("--only", help="comma-separated cheat ids to run")
    p_scan.add_argument("--priority", choices=["P0", "P1", "P2"], help="run only this priority")
    p_scan.add_argument("-o", "--out", default="scorecard", help="output path prefix")
    p_scan.add_argument("--sarif", action="store_true", help="also write a SARIF file")
    p_scan.add_argument("--ablation", action="store_true", help="rerun each HOLE under its defenses")
    p_scan.add_argument("--dry-run", action="store_true", help="print harbor commands, run nothing")
    p_scan.add_argument("--harbor-bin", default="harbor", help="harbor executable")
    p_scan.add_argument(
        "--concurrent", type=int, default=None,
        help="harbor --n-concurrent (default: harbor's own, 4). Set to your vCPU count.",
    )
    p_scan.add_argument(
        "--timeout-multiplier", type=float, default=None,
        help="harbor --timeout-multiplier (raise if heavy tasks time out)",
    )
    p_scan.add_argument(
        "--resume", action="store_true",
        help="dataset mode: reuse <out>.json, skip cheats already done",
    )
    p_scan.add_argument("--harbor-commit", help="pin: harbor commit/version")
    p_scan.add_argument("--dataset-commit", help="pin: dataset commit")
    p_scan.add_argument("--image-digest", help="pin: image digest")
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
