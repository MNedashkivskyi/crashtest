# Campaign: 2027-01 TB 2.1

The planned public scan. `config.yaml` is the recipe (datasets, sampling, pins,
whether ablation runs). Results go in `scorecard.md` here (the `results/` dir with
raw per-trial JSON is git-ignored — regenerate it).

## Run it

```
# one dataset / path at a time, pinning determinism
crashtest scan -p <tb21-checkout>/tasks \
  --priority P0 --ablation --sarif \
  --harbor-commit <sha> --dataset-commit <sha> \
  -o scorecard
```

Then commit the resulting `scorecard.md` next to this file.

## Report (fill after the run)

- % tasks where controls fail (no-op passes or oracle fails)
- % valid tasks with ≥1 HOLE, overall and by category
- hit rate per cheat
- defense matrix: shared vs separate vs emptied-dirs vs task-fix
- residual holes after converting sample tasks to separate mode
- median scan time per task; cost per 1k tasks

**Nothing here is published until the disclosure in [`../../disclosure/`](../../disclosure/)
has run.** crashtest ships no fabricated numbers; this file stays empty of results
until a real scan fills it.
