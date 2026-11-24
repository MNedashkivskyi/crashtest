# Using crashtest

## Commands

```
crashtest list [--priority P0]        # the cheat catalog
crashtest selftest [CHEAT]            # validate cheats against their fixtures (no Harbor)
crashtest static -p <path>           # fast no-Docker hints over a task / dir of tasks
crashtest scan   -p <path> [opts]    # the real matrix: controls + cheats via `harbor run`
```

### `scan` options

| flag | meaning |
| --- | --- |
| `-p/--path` | a task dir, or a directory of task dirs |
| `-d/--dataset` | a Harbor dataset id (task enumeration is a week-1 item; prefer `-p`) |
| `--priority P0\|P1\|P2` | run only cheats of this priority |
| `--only c03_tests_preplant,c05_path_shim` | run specific cheats |
| `--ablation` | rerun each HOLE under its expected defenses (builds the defense matrix) |
| `--sarif` | also write `scorecard.sarif` for code-scanning |
| `--dry-run` | print the `harbor run` commands, run nothing (works with no Harbor) |
| `--harbor-commit/--dataset-commit/--image-digest` | determinism pins for the scorecard header |

`scan` exits non-zero if any confirmed **HOLE** is found, so CI can gate on it.

### Outputs

- `scorecard.json` — versioned machine record (controls, cells, pins).
- `scorecard.md` — pins header, controls summary, task×cheat matrix, per-task fix list.
- `scorecard.sarif` — optional, one result per hole for GitHub code scanning.

## In CI (GitHub Action)

```yaml
# .github/workflows/crashtest.yml in a task repo
name: crashtest
on:
  pull_request:
    paths: ["tasks/**"]
jobs:
  crashtest:
    runs-on: ubuntu-latest
    permissions:
      security-events: write   # for the SARIF upload
    steps:
      - uses: actions/checkout@v4
      - uses: MNedashkivskyi/crashtest/action@master
        with:
          tasks-path: tasks
          priority: P0
```

With Harbor unavailable the Action automatically falls back to `--dry-run` (it
validates the plan rather than grading).

## Adding a cheat

A cheat is a directory under `src/crashtest/cheats/<id>/`:

```
cheat.toml    # id, version, category, priority, proves, expected_defense, fix, preconditions
probe.sh      # exit 0 = applies to this task, exit 3 = not applicable
payload.sh    # the cheat; runs only when probe said "applies"
files/        # optional payload assets
```

Then add the two fixtures under `fixtures/`:

```
fixtures/vuln-<id>/      grade.sh (+ tests/, optional setup.sh)   # grader WITH the hole
fixtures/hardened-<id>/  grade.sh (+ tests/, optional setup.sh)   # grader with the FIX
```

Rules the harness enforces (`crashtest selftest`):

- **vuln, no payload → reward 0** — the fixture task must genuinely fail when nobody cheats.
- **vuln, payload → reward 1** — the cheat works.
- **hardened, payload → reward 0** — the matching fix stops it.

Payloads must target real absolute paths **by default** but honour the
`CRASHTEST_*` overrides so the harness can sandbox them:

| env var | default | meaning |
| --- | --- | --- |
| `CRASHTEST_TESTS_DIR` | `/tests` | the verifier's test tree |
| `CRASHTEST_VERIFIER_LOG_DIR` | `/logs/verifier` | where reward files live |
| `CRASHTEST_BIN_DIR` | `/usr/local/bin` | agent-writable PATH dir |
| `CRASHTEST_WORKDIR` | `$PWD` | the agent workspace |
| `CRASHTEST_REPO_ROOT` | `$CRASHTEST_WORKDIR` | the repo root |
| `CRASHTEST_FS_ROOT` | `/` | filesystem root (for `/`-level plants) |
| `CRASHTEST_SITE_DIR` | an on-path site dir | agent-writable Python site |
| `CRASHTEST_ARTIFACT_DIR` | a declared artifact path | for artifact-variant cheats |
| `CRASHTEST_CLEAN_PATH` | — | a PATH without the agent shim dir (for hardened graders) |

`grade.sh` prints `REWARD=<0|1>` as its last line.
