# Week-1 spike runbook

The spike exists to turn "read the Harbor source" into "ran it once." Until it is
done, `crashtest scan` builds plausible `harbor run` commands and parses a *guessed*
trial-JSON shape, and two cheats (C02, C03) rest on unverified assumptions. The
spike pins all of that and records a go/pivot decision.

Budget it at a few focused hours. Everything here runs **locally on public tasks**;
nothing is published.

## 0. Prerequisites

You need a machine crashtest's own sandbox is not: Linux with **Docker** running,
Python ≥ 3.11, and ~20–30 GB free disk for images. Then:

```
git clone https://github.com/MNedashkivskyi/crashtest && cd crashtest
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pip install harbor            # confirm the real package/import name; fix pyproject if it differs
crashtest list               # 16 cheats
crashtest selftest           # 16 pass, 0 failing points — the tool is sane before Harbor
```

If `pip install harbor` fails or the import name differs, that is finding #1 — note
the correct name and update the `harbor` extra in `pyproject.toml` and the Action.

## 1. Controls on the sample, and locate the trial JSON

Run the built-in agents by hand first, on the smallest dataset, so you see Harbor's
real output layout:

```
harbor run -a nop    --dataset terminal-bench-sample@2.0
harbor run -a oracle --dataset terminal-bench-sample@2.0
```

Capture, for the go/pivot notes:
- the exact `-a` spec that selects nop and oracle (is it `nop`/`oracle`, or a module
  path? update `ScanConfig.nop_agent`/`oracle_agent` if needed);
- where results landed — the job directory and the **trial JSON** filename;
- one trial JSON's structure (which key holds the reward: `reward`? `score`?
  nested?);
- rough per-task wall time and image size.

This directly pins two seams in `src/crashtest/runner.py::HarborHarness`:
`find_trial_json` (the path/glob) and `extract_reward` (the key). Adjust them to the
real shape and re-run — `harbor run ... -a nop` through crashtest should now parse a
0, and oracle a 1.

Also confirm the output flag: the runner passes `-o <jobdir>`. If `harbor run` uses
a different flag (or none, writing to a fixed location), fix `build_command` and
`find_trial_json` together.

## 2. Pin the env API (the `CheatAgent` ↔ Harbor seam)

`src/crashtest/agent.py::_adapt_env` guesses the env object's method names
(`exec`/`run`, `upload_dir`/`upload`, `write_file`). Verify them with a throwaway
probe agent — drop this in the repo root as `probe_agent.py`:

```python
# probe_agent.py — prints the env's surface, then no-ops. Delete after the spike.
try:
    from harbor.agents import BaseAgent          # fix the import if step 1 showed another path
except Exception:
    BaseAgent = object

class ProbeAgent(BaseAgent):
    def name(self): return "probe"
    def version(self): return "0"
    def setup(self, env): pass
    def run(self, instruction, env, context=None):
        import json
        info = {
            "env_type": type(env).__name__,
            "attrs": [a for a in dir(env) if not a.startswith("__")],
        }
        print("PROBE " + json.dumps(info))
        return {}
```

```
harbor run -a probe_agent:ProbeAgent --dataset terminal-bench-sample@2.0
```

Read the `PROBE {...}` line. Map the real method names into `_adapt_env` and delete
the guessing (and the TODO). Confirm: which method runs a shell command and what it
returns (tuple vs object — `_normalize_exec_result` already handles both), which
uploads a directory, and whether there is a file-write method or you must write via
`exec`.

Also settle the default **agent user** on TB images here (`whoami` via the probe's
`run`): root or not decides whether the `/usr/local/bin` shim (C05) and
site-packages writes (C07) even apply.

## 3. First real cheat trial

With the two seams pinned, run a cheat through crashtest against one sample task:

```
crashtest scan -p <path-to-one-sample-task> --only c05_path_shim --priority P0 -o /tmp/sc
cat /tmp/sc.md
```

Expect controls VALID and a cell verdict. A HOLE here is a real finding; DEFENDED is
also a real result. If you get ERROR, the seams from steps 1–2 are still off — fix
and repeat. Confirm `/logs/agent/crashtest.json` (the honesty marker) is written.

## 4. Test the two load-bearing assumptions by hand

These decide whether C02 and C03 (and one upstream PR each) stand:

**C03 — does an uploaded `/tests` merge or replace?** Run
`crashtest scan --only c03_tests_preplant` on a sample task. HOLE ⇒ the agent's
`/tests` is merged into grading (assumption holds, PR `harbor-empty-shared-dirs`
applies). DEFENDED ⇒ Harbor already replaces/empties it — note *where* in the source
and revisit BenchJack's "protects `/tests/`" remark.

**C02 — do detached agent processes survive into grading?** Run
`crashtest scan --only c02_reward_daemon`. HOLE ⇒ the `setsid` daemon outlived the
agent phase (assumption holds, PR `harbor-kill-agent-procs` applies). DEFENDED ⇒
Harbor already stops the process tree before shared verify — good for Harbor, note
it and drop that PR.

## 5. Timings, disk, go/pivot

From the runs above, record: per-task wall time, image pull size, and the compute the
spec estimated (≈1.7k trials for a full TB run). Decide:

- **Go** if the seams pinned cleanly and at least one of C01–C05 is a live HOLE on the
  sample, or the controls/leakage probes already produce usable numbers.
- **Pivot** (per the spec's risk row) if Harbor has already closed C02/C03: shift the
  headline to the artifact variants (C04a/C07a/C12a) plus weak-test and leakage rates.
  A clean negative result on Harbor's defenses is itself publishable.

## 6. Write it down

Update `docs/open-questions.md`: tick the items you confirmed, record the answers
(env API, trial path, agent user, C02/C03 outcomes), and delete the guessing in
`agent.py`/`runner.py` that the spike made unnecessary. Commit that as its own PR so
the "unverified" surface shrinks visibly. Then the first real campaign
(`campaigns/2027-01-tb21/`) can run.

Delete `probe_agent.py` when done — it is spike scaffolding, not part of the tool.
