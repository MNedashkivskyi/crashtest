# Upstream change drafts (disclosure-staged)

These are **drafts**, staged here deliberately. They are *not* open pull requests
against `harbor-framework/harbor`, `terminal-bench-2-1`, or any dataset repo.

Why staged and not opened:

1. **Disclosure first.** Per [`../docs/DISCLOSURE.md`](../docs/DISCLOSURE.md), task-
   level holes and any new technique go to maintainers privately before anything
   public. Opening a public PR that carries a working grader-bypass ahead of a fix
   is exactly what the embargo exists to prevent.
2. **Not our repos to merge.** These changes belong to their projects. crashtest's
   job is to hand maintainers a clean repro, a scorecard, and a proposed patch —
   then they decide.

Each file below is a proposed change written against the files named in the
project spec. **Line numbers and exact diffs are intentionally not pinned**: they
must be finalized against the live source at disclosure time (a week-1 item), and
this repo has not executed Harbor. Treat them as the body of the PR/issue to open
*after* the maintainer acknowledges.

| draft | target | risk-to-merge |
| --- | --- | --- |
| [`harbor-empty-shared-dirs.md`](harbor-empty-shared-dirs.md) | harbor-framework/harbor | low (helper already exists) |
| [`harbor-kill-agent-procs.md`](harbor-kill-agent-procs.md) | harbor-framework/harbor | medium (open an issue first) |
| [`harbor-lint-rules.md`](harbor-lint-rules.md) | harbor-framework/harbor | low |
| [`tb21-image-toolchain.md`](tb21-image-toolchain.md) | terminal-bench-2-1 | medium |
| [`report-template.md`](report-template.md) | (private report body) | — |

Order to pursue, most-likely-to-merge first: empty-shared-dirs, lint rules,
kill-agent-procs (issue first), tb21 toolchain, then dataset repos adopting the
Action.
