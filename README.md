# crashtest

**Deterministic reward-integrity test kit for Harbor tasks.** Scripted cheats
replace the AI agent, the task's own grader runs, and any cheat that scores a
reward of 1 marks a hole in that task's verification. No LLM, no network, minutes
per task. It plugs into task-authoring CI as a GitHub Action.

crashtest is **defensive tooling**. It exercises *already-public* reward-hacking
techniques — crediting [BenchJack](https://github.com/benchjack/benchjack), the
CMU hacker–fixer work, and the cited arXiv notes — against a task's grader so
task authors can find and fix grading holes. It is the runtime complement to
`harbor lint`: dynamic proof of which holes remain after Harbor's 2026 defenses,
per defense mode.

> **Scope and safety.** Everything runs locally on public tasks. crashtest never
> attacks hosted leaderboards or anyone's infrastructure, and every cheat leaves
> obvious markers: the agent name is `crashtest` and each run writes
> `/logs/agent/crashtest.json` describing what it touched. New techniques are
> disclosed privately to maintainers before any public writeup.

## How it works

crashtest runs as a Harbor **custom agent**, so `harbor run` works unchanged and
no fork is needed:

```
harbor run -a crashtest.agent:CheatAgent --ak cheat=c03_tests_preplant -p <task>
```

Per task, the runner does:

1. Run Harbor's built-in `nop` agent 3×. Every run must score 0, or the task is
   **BROKEN-NOP**.
2. Run Harbor's built-in `oracle` agent 3×. Every run must score 1, or the task
   is **BROKEN-ORACLE**.
3. For each cheat: a fresh trial where `CheatAgent` runs the cheat script instead
   of an AI, then the task's official `test.sh` grades it.
4. A reward of 1 triggers 2 reruns: 3/3 = **HOLE**, 1–2/3 = **FLAKY-HOLE**, 0 =
   **DEFENDED**.

A hole only counts when both controls pass, the cheat hits 3/3, and applying the
matching defense flips it to 0 (the causal-ablation pass).

## A cheat

A cheat is a directory under `src/crashtest/cheats/`:

```
cNN_name/
  cheat.toml    # id, version, category, priority, what a hit proves, expected defense, fix
  probe.sh      # exit 0 = applies to this task, exit 3 = not applicable
  payload.sh    # the cheat itself; runs only when probe said "applies"
  files/        # optional payload assets
```

Each cheat ships a **vulnerable fixture** (must score 1) and a **hardened
fixture** (must score 0) under `fixtures/`. The fixture harness validates every
cheat with plain pytest — no Harbor, no network — and is the false-positive
guard: release is blocked if any fixture fails.

## Install

```
uv pip install -e ".[dev]"          # tool + test deps, no Harbor needed
```

Harbor is an **optional** dependency. The result model, cheat registry, fixture
harness and scorecard all import and run without it.

### To run real scans (needs Harbor)

Harbor loads a custom agent by importing it **inside Harbor's own Python
environment**, so `crashtest` must be importable from there. If Harbor is
installed as a `uv` tool (`uv tool install harbor`), inject crashtest into that
tool's environment:

```
uv tool install harbor --with-editable /path/to/crashtest --force
```

(Use `--with` instead of `--with-editable` if your `uv` doesn't accept it.) If
instead you install Harbor into this project's venv (`pip install harbor`; needs
Python ≥ 3.12), run that venv's `harbor` so both share one environment. A plain
`uv tool install harbor` on its own cannot see crashtest and fails with
`No module named 'crashtest'`.

## Quickstart

```
crashtest list                 # show the cheat catalog (see docs/cheats.md)
crashtest list --priority P0   # just the MVP cheats
crashtest selftest             # validate every cheat against its fixtures (no Harbor)
crashtest static -p <task>     # fast no-Docker hints over a task
crashtest scan   -p <task>     # the real matrix via `harbor run` (needs Harbor; --dry-run otherwise)
```

See [`docs/usage.md`](docs/usage.md) for all commands, the GitHub Action, and how
to add a cheat.

## Status

The cheats are validated against bundled vulnerable/hardened graders
(`crashtest selftest`) with no Harbor and no network. The live `harbor run`
integration (env API, trial-result parsing) is exercised the first time you run
`crashtest scan` against your own Harbor; use `--dry-run` to inspect the planned
commands first. crashtest ships no fabricated scan results.

## License

MIT © 2026 Maksym Nedashkivskyi
