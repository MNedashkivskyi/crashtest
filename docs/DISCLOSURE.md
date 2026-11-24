# Disclosure policy

crashtest finds holes in benchmark graders. That is dual-use, so the project runs
disclosure-first.

## Principles

- **Local only.** crashtest runs on public tasks on your own hardware. It never
  targets hosted leaderboards, submission endpoints or anyone's infrastructure.
- **Loud, not stealthy.** Every cheat identifies itself: the Harbor agent name is
  `crashtest` and each run writes `/logs/agent/crashtest.json` listing what it
  touched. The cheats are designed to be easy to detect, not to evade detection.
- **Known techniques.** The catalog implements *already-published* reward-hacking
  techniques (BenchJack; the CMU hacker–fixer work; the cited arXiv notes). Each
  cheat's `cheat.toml` carries a `credit` field where one applies.

## Process for a hole

1. **Report privately first.** Use GitHub private vulnerability reporting on the
   affected repo if enabled, otherwise email/DM the maintainers. For task-level
   holes also notify the dataset owner.
2. **Share repro + fix.** Send the one-command repro and a proposed patch.
3. **Hold payloads.** Per-task holes are published only after a fix merges or the
   agreed embargo (2–4 weeks) ends. Payloads for any genuinely *new* technique
   are withheld until fixed.

## What this repo will and won't contain

- It **will** contain regression cheats for techniques that are already public,
  and the fixes for them.
- It **will not** open public pull requests carrying exploit payloads against
  third-party benchmark repos ahead of disclosure. Proposed upstream changes live
  as drafts under `disclosure/` until the maintainer has them.

If you believe a cheat here enables misuse that outweighs its defensive value,
open an issue (or contact the maintainer privately) and it will be reconsidered.
