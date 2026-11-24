# Private vulnerability report — template

> Send via GitHub private vulnerability reporting (if enabled) or directly to the
> maintainers. One report per hole class. Withhold payloads for any genuinely new
> technique until a fix is merged or the embargo (2–4 weeks) ends.

**Affected project / repo:**
**Affected tasks (ids):**
**Cheat / hole class:** `cNN_...` (category: reward-channel / harness-hijack / toolchain / exit-code / leakage / weak-test)

## Summary
One paragraph: what a reward of 1 proves about the task's verification.

## Reproduction (deterministic, no LLM)
```
pip install "crashtest @ git+https://github.com/MNedashkivskyi/crashtest@<ref>"
pip install harbor
crashtest scan -p <task> --only cNN_... --ablation -o scorecard
```
Attach `scorecard.md` (controls VALID; the cell = HOLE 3/3) and `scorecard.json`.

## Marker / detectability
Every run leaves `/logs/agent/crashtest.json` and uses agent name `crashtest`.

## Proposed fix
Link the matching draft in `disclosure/` and the ablation row showing the defense
flips the cell to DEFENDED.

## Scope statement
Run locally on public tasks only. No hosted leaderboard or infrastructure was
touched.
