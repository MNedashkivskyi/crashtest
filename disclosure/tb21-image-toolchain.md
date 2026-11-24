# Terminal-Bench 2.1: install uv/pytest at image build and/or convert to separate mode

**Target:** `terminal-bench-2-1`
**Closes (crashtest):** `c05_path_shim`, `c06_uvx_trojan` (toolchain hijack); reduces exposure to the harness-hijack family.
**Risk to merge:** medium — touches task images.

## Problem (from the spec's survey of 89 tasks on `main`, 2026-11-24)

- 0/89 use a separate verifier.
- 81/89 install uv from astral.sh **at verify time**; 82/89 use curl; 88/89 run
  pytest. Verify-time toolchain fetch is hijackable (C05/C06).

## Proposed change

1. Move `uv`/`pytest` installation into the image build (pin versions), so the
   verifier never fetches a toolchain the agent could have shimmed.
2. Where feasible, convert tasks to separate-verifier mode.

Attach the crashtest matrix as proof, per task, before/after.

## Validation

```
crashtest scan -p tasks/<task> --priority P0 --ablation
```

Expect `c05_path_shim` / `c06_uvx_trojan` to flip HOLE → DEFENDED after the image
change, and the artifact variants (c04a/c07a/c12a) to guide the separate-mode
conversion where it is applied.
