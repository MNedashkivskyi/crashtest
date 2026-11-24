# Open questions / not yet verified

crashtest's design was read from Harbor's source and docs on 2026-11-24. The
items below were **read, not executed**. They must be confirmed against a live
Harbor (the week-1 spike) before any scan numbers are published. Until then the
code is written against the documented interfaces with clearly marked fallbacks.

## Blocking (decide go/pivot in week 1)

- [ ] **C02 — daemon survival.** Do `setsid`/`nohup` children of the agent run
      survive until the shared verifier runs? The spec claims the agent env is
      stopped only *after* shared verification.
- [ ] **C03 — `/tests` merge vs replace.** Does an uploaded `/tests` merge into
      the existing one, or replace it? crashtest's C03 assumes merge.
- [ ] Why does BenchJack's writeup say Harbor "protects `/tests/`"? C03 may
      already be blocked somewhere we haven't found.

## Harness shape (needed by the agent + runner)

- [ ] Exact import path of Harbor's `BaseAgent` (agent.py tries several).
- [ ] The env object's method names: exec/run, upload_dir/upload, write_file.
      `agent.py::_adapt_env` guesses; pin and delete the guessing.
- [ ] Trial result JSON path and job-directory layout (needed by the runner's
      `TrialResult.model_validate_json` parse).
- [ ] Default agent user on Terminal-Bench images (root or not?) — decides
      whether `/usr/local/bin` shims (C05) and site-packages writes (C07) apply.
- [ ] Harbor Hub name for Terminal-Bench 2.1.
- [ ] Trial timings and image sizes (for the compute estimate).

## Later

- [ ] Whether C17 (uv cache poisoning) works at all.
- [ ] Whether private vulnerability reporting is enabled on `harbor-framework/harbor`.
- [ ] Contents of `harbor/rewardhackbench` and `islo-labs/reward-hack-bench`.

Each cheat's `cheat.toml` records its own preconditions; a cheat whose
precondition is unmet reports **N-A**, not DEFENDED.
