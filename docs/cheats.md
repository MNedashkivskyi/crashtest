# Cheat catalog

_Generated from `cheat.toml` metadata (`crashtest list`). Every cheat ships a vulnerable fixture (must score 1) and a hardened fixture (must score 0); `crashtest selftest` enforces both._

| ID | P | Category | What a reward of 1 proves | Expected defense | Fix |
| --- | --- | --- | --- | --- | --- |
| `c01_reward_preplant` | P0 | reward-channel | The verifier reads a leftover reward file instead of deleting it at verification start (stale-reward deletion regressed). | shared | Already fixed in Harbor: reward.txt/reward.json are deleted at the start of verification. This cheat is a regression check; expect DEFENDED on current Harbor. |
| `c02_reward_daemon` | P0 | reward-channel | Agent processes are stopped only AFTER shared verification, so a background process can inject the reward during grading; reward.json wins over reward.txt. | separate, task-fix | Harbor: kill the agent process tree (or restart the env) before shared verification; use a verifier-only user for reward files. Task: use a separate verifier. |
| `c03_tests_preplant` | P0 | harness-hijack | The agent's /tests is merged into (not replaced before) grading, so an agent-written conftest is auto-loaded by the verifier's pytest. | emptied-dirs, separate | Harbor: empty /tests (and /logs/verifier) and restore the task's pristine tests before single-step shared verification. The _reset_shared_step_verifier_dirs helper already exists for the multi-step path. |
| `c04_workspace_conftest` | P0 | harness-hijack | pytest discovers conftest/ini from agent-writable parent directories of the test path. | task-fix, separate | Run pytest isolated: --rootdir=/tests -c /tests/pytest.ini --confcutdir=/tests (or --noconftest); PYTEST_DISABLE_PLUGIN_AUTOLOAD=1; unset PYTEST_ADDOPTS. |
| `c04a_artifact_conftest` | P1 | harness-hijack | Separate-verifier mode can be hijacked via declared artifacts: a conftest shipped as an artifact is loaded at grading. | task-fix | Copy data-only artifacts (strip .py/conftest); run pytest isolated (--noconftest, confcutdir). |
| `c05_path_shim` | P0 | toolchain | test.sh invokes the toolchain by name, so an agent-writable PATH entry (e.g. /usr/local/bin) can replace it. | separate, task-fix | Separate verifier; non-root agent; verifier toolchain owned by another user; call tools by absolute path or from a clean PATH. |
| `c06_uvx_trojan` | P1 | toolchain | Verify-time tool downloads can be hijacked: test.sh fetches/invokes uvx by name. | separate, task-fix | Install uv/pytest at image build; use an offline verifier with a pinned toolchain. |
| `c07_sitecustomize` | P1 | harness-hijack | The verifier's Python environment is agent-writable (site-packages / PYTHONPATH). | separate, task-fix | Separate verifier or read-only verifier venv; run python with -I (isolated). |
| `c07a_artifact_sitecustomize` | P1 | harness-hijack | Separate-verifier mode can be hijacked via artifacts placed on the Python path. | task-fix | Copy data-only artifacts off the Python path; run python isolated (-I). |
| `c08_pytest_plugin` | P1 | harness-hijack | pytest plugin autoload is on and the agent can place a distribution on the verifier's path. | separate, task-fix | PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 plus an explicit -p allow-list; separate verifier. |
| `c09_exit_injection` | P1 | exit-code | Reward is taken from the process exit code, not from per-test results. | task-fix, separate | Grade from JUnit/CTRF output: require every expected test id present and passed; never trust the exit code alone. |
| `c10_build_hook` | P1 | harness-hijack | The verifier executes agent code (the build) before running the tests. | separate, task-fix | Install from a pristine copy or at image build; run the build in a separate verifier, not the agent repo. |
| `c11_empty_collection` | P1 | weak-test | The grader treats zero collected tests / zero failures as success. | task-fix | Assert the expected test count and ids; treat pytest exit code 5 (no tests collected) as failure. |
| `c12_git_mining` | P1 | leakage | A future/solution version ships inside the task image (leakage via git history). | task-fix | Squash at build, drop tags/remotes/branches, expire reflog, git gc --prune=now (or ship no .git). |
| `c12a_artifact_leak` | P1 | leakage | Separate mode copies agent-produced artifacts into the graded workspace, carrying a planted answer through. | task-fix | Mount artifacts data-only in a non-graded location; grade a pristine workspace. |
| `c15_touch_replay` | P1 | weak-test | The test asserts a path exists but not its content or behaviour. | task-fix | Assert content and behaviour, not just existence. |

## Credits

- `c06_uvx_trojan`: BenchJack (https://github.com/benchjack/benchjack) — included as a credited regression check.
