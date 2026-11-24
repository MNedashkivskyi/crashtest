"""crashtest — deterministic reward-integrity test kit for Harbor tasks.

Scripted cheats replace the AI agent, the task's own grader runs, and any cheat
that scores a reward of 1 (while both the no-op and oracle controls pass) marks
a hole in the task's verification. No LLM, no network, minutes per task.

This is defensive tooling: it exercises *already-public* reward-hacking
techniques (crediting BenchJack, the CMU hacker-fixer work and the cited arXiv
notes) against a task's grader so task authors can find and fix grading holes.
Every cheat leaves obvious markers (`/logs/agent/crashtest.json`, agent name
``crashtest``) and the suite never touches `/solution`.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
