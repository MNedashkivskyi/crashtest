# harbor lint: new static rules for shared-verifier grading holes

**Target:** `harbor-framework/harbor` (`harbor lint`)
**Mirrors (crashtest):** the `crashtest static` rules
**Risk to merge:** low — additive lint rules.

## Proposed rules

1. **verify-time-download** — `test.sh` fetches/installs the toolchain at verify
   time (`curl`/`wget`, `astral.sh`, `uvx`, `pip install`). Correlates with
   `c05_path_shim`, `c06_uvx_trojan`. Fix: install at image build; offline verifier.
2. **pytest-no-isolation** — pytest invoked without `--noconftest` /
   `--confcutdir` / `--rootdir` and without `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`.
   Correlates with `c03`, `c04`, `c07`, `c08`.
3. **reward-from-exit-code** — reward derived from the pytest exit code (`$?`,
   `&&`/`||`) rather than a parsed JUnit/CTRF report. Correlates with `c09`, `c11`.
4. **build-runs-agent-code** — `pip install -e .` / `python setup.py` on the
   agent repo before tests. Correlates with `c10`.
5. **git-history-shipped** — a `.git` with objects reachable only via
   tags/reflog/remotes ships in the task image. Correlates with `c12`.

crashtest already implements these as `crashtest static`; this PR ports them to
`harbor lint` as the authoritative home (crashtest keeps them only as a fast local
hint). Each rule should carry the same fix text and a pointer to the dynamic cheat
that proves it.

## Validation

Run `harbor lint` on a known-vulnerable task and confirm each rule fires; run on a
hardened task and confirm it does not.
