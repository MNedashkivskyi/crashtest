# Harbor: kill the agent process tree (or restart the env) before shared verification

**Target:** `harbor-framework/harbor`
**Closes (crashtest):** `c02_reward_daemon`
**Risk to merge:** medium — open an issue first; it changes lifecycle behaviour.

## Problem

In single-step shared mode the agent environment is stopped only **after** shared
verification. A detached agent process (`setsid`/`nohup`) therefore survives into
grading and can inject the reward while the verifier runs — e.g. wait for the
verifier's `reward.txt`, then write `reward.json = {"reward": 1}` (which is
preferred over `reward.txt`).

## Proposed change

Before the shared verifier runs, terminate the agent process tree (or restart /
recreate the environment for the verifier). Make it opt-in first, default later.

Sketch (finalize against live source):

```python
# src/harbor/trial/single_step.py, before the shared verifier
if self._is_shared_verifier and self._kill_agent_before_verify:   # new opt-in
    self._terminate_agent_process_tree()   # SIGTERM the agent session, then SIGKILL
```

Complementary hardening: run the verifier's reward-file writes as a verifier-only
user so an agent-owned process cannot overwrite them.

## Validation

```
crashtest scan -p <task> --only c02_reward_daemon --ablation
```

Before: HOLE. After (flag on): DEFENDED. Attach before/after `scorecard.md`.

## Notes / to pin at disclosure

- First confirm the week-1 question: do `setsid` children of the agent actually
  survive until the verifier runs? (docs/open-questions.md)
- Flag name and default; whether a full env restart is cheaper/safer than a
  targeted process-tree kill.
