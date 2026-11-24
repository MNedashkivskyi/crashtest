# Harbor: empty `/tests` and `/logs/verifier` before single-step shared verification

**Target:** `harbor-framework/harbor`
**Closes (crashtest):** `c03_tests_preplant`, and contributes to `c01_reward_preplant`
**Risk to merge:** low — the cleanup helper already exists for the multi-step path.

## Problem

In single-step **shared** mode the agent and the verifier share a filesystem.
`/tests` and `/logs/verifier` are **not** reset between the agent run and the
shared verifier, so the agent can leave behind:

- a `/tests/conftest.py` that the verifier's pytest auto-loads (forces passes);
- reward files in `/logs/verifier` that a reward read may pick up.

The multi-step path already resets these via `_reset_shared_step_verifier_dirs`
(in `src/harbor/trial/trial.py`); the single-step shared path
(`src/harbor/trial/single_step.py`) does not call it.

NeMo Gym empties `/tests` and `/logs/verifier` in shared mode, for comparison.

## Proposed change

Call the existing reset helper on the single-step shared path, immediately before
the shared verifier runs and after the agent environment has produced its result,
then restore the task's pristine `/tests` from the task definition.

Sketch (finalize against live source):

```python
# src/harbor/trial/single_step.py, just before invoking the shared verifier
if self._is_shared_verifier:
    self._reset_shared_step_verifier_dirs()   # already used by the multi-step path
    self._restore_pristine_tests()            # re-copy the task's own /tests
```

## Validation

```
crashtest scan -p <task> --only c03_tests_preplant --ablation
```

Before: `c03_tests_preplant` = HOLE. After: DEFENDED, with the ablation row showing
`emptied-dirs: closes`. Attach the before/after `scorecard.md`.

## Notes / to pin at disclosure

- Exact helper name/signature and where pristine tests are sourced from.
- Whether `/logs/verifier` emptying interacts with the reward-file deletion that
  already happens at verification start (avoid double-work / ordering bugs).
