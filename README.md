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
> disclosed privately to maintainers before any public writeup. See
> [`docs/DISCLOSURE.md`](docs/DISCLOSURE.md).

## How it works

crashtest runs as a Harbor **custom agent**, so `harbor run` works unchanged and
no fork is needed:

```
harbor run -a crashtest.agent:CheatAgent --ak cheat=c03_tests_preplant -p <task>
```

Per task, the runner (lands with PR3) does:

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
uv pip install -e ".[dev,harbor]"   # add this on a machine where you run scans
```

Harbor is an **optional** dependency. The result model, cheat registry, fixture
harness and scorecard all import and run without it.

## Quickstart

```
crashtest list                 # show the cheat catalog
crashtest list --priority P0   # just the MVP cheats
# crashtest scan -p <task>     # full matrix (runner lands with PR3)
```

## Status

This repo is being built up PR by PR against the project spec. Several behaviours
the spec depends on have been read from Harbor's source but **not yet executed
against a live Harbor** (env API shape, whether an uploaded `/tests` merges,
whether `setsid` children survive into grading). Those are tracked in
[`docs/open-questions.md`](docs/open-questions.md) and must be confirmed before
any scan numbers are published. crashtest does not ship fabricated scan results.

## License

MIT © 2026 Maksym Nedashkivskyi
