# Verification log — qnxcheck 0.1.0

Date: 2026-11-27 (WIB). Environment: Linux, Python 3.12.3, stdlib only.

## Test suite: 11/11 PASS

Run: `python3 tests/run_tests.py`

- buildfile: valid qemu x86_64 — PASS (0 findings)
- buildfile: valid shell (QNX docs `shell.bld` example) — PASS (0 findings)
- buildfile: valid rpi5 — PASS (0 findings)
- buildfile: all 17 bad fixtures fire their intended rule (B01–B17) — PASS
- c: good server clean — PASS (0 findings)
- c: good client clean (TimerTimeout arms MsgSend, C06 correctly skipped)
  — PASS (0 findings)
- c: bad client fires C02–C15 (all 14 rules) — PASS
- makefile: good clean — PASS (0 findings)
- makefile: bad fires M01–M05 — PASS
- dogfood: `qnxcheck init` skeletons (x86_64 + rpi5) pass
  `qnxcheck check` with 0 findings — PASS
- cli: JSON output parses, B01 present — PASS

## CLI smoke test

- `qnxcheck --version` → `qnxcheck 0.1.0`
- `qnxcheck check examples/qemu-x86_64` → 0 errors, exit 0
- `qnxcheck check examples/rpi5-aarch64` → 0 errors, exit 0
- `qnxcheck buildfile bad-B07-no-procnto.build` → B07 error, exit 2
- `qnxcheck c bad-client.c` → 14 rules (C02–C15), errors + warnings
- Whole-repo `qnxcheck check .` → 19 errors / 18 warnings / 1 info —
  all from the deliberately broken fixtures in `tests/fixtures/`
  (expected: the fixtures exist to prove the rules fire).

## What was verified locally (host only)

- mkifs buildfile grammar against the public QNX docs (attribute list,
  bootstrap/script structure, link/perms rules).
- QNX Neutrino API rules against the public QNX docs and the known
  message-passing / realtime semantics.
- The `init` skeleton is self-consistent: it passes the tool's own checks.

## Explicit limits (NOT verified — cannot be, from this machine)

- No QNX SDP 8.0 installed: download requires a myQNX account, which
  this agent cannot create. Therefore no `qcc` cross-compile, no `mkifs`
  run, and no QEMU boot of a real QNX 8.0 image was performed.
- The generated `system.build` files were validated as *text* (grammar +
  structure) only, not by running mkifs.
- The generated `hello.c` was validated as *source* (API rules) only,
  not compiled against QNX headers.
- Demo video not recorded (needs a screen capture; see
  `docs/DEMO_SCRIPT.md`).

## Known limitations

- The C checker is regex-based, not a full parser: heavily macro-ised
  code or unusual formatting can produce false positives/negatives.
  Every rule is documented with its rationale in `qnxcheck/ccheck.py`.
- On a malformed buildfile line (e.g. two bracket groups, B02), later
  checks can cascade extra findings for the same line (e.g. B13) —
  the primary error is still reported correctly.
- `qnxcheck c` caps findings at 5 per rule per file to avoid flooding
  the report on very broken files.
