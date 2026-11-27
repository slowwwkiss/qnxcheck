# qnxcheck — host-side static analysis for QNX 8.0 projects

`qnxcheck` is a developer tool that runs **on the Linux host** and validates
QNX 8.0 project files **before** they ever reach a target. It catches the
mistakes that make QNX images fail to boot, servers hang, and drivers
misbehave — without needing QNX SDP 8.0 installed.

Built for the **QNX Global Hackathon 2026**, category **Developer Tooling &
Host Tools** (Best of Developer Tooling & Host Tools: $4,000).

## What it checks

| Command | What it validates | Rules |
|---|---|---|
| `qnxcheck buildfile <file.build>` | mkifs buildfile grammar, attributes, bootstrap/script sections, image paths | B01–B17 |
| `qnxcheck c <file.c>...` | QNX Neutrino C API usage: channels, connections, names, message passing, interrupts, realtime threads, port I/O, Linux-only APIs | C01–C15 |
| `qnxcheck makefile <Makefile>` | QNX recursive-makefile structure (common.mk, TARGET_CPU, USEFILE, INSTALLDIR) | M01–M05 |
| `qnxcheck check <dir>` | All of the above, auto-detected per file | — |
| `qnxcheck init --target x86_64\|rpi5` | Generate a correct QNX 8.0 project skeleton (passes `qnxcheck check` clean) | — |

Every finding carries a severity (`error` / `warning` / `info`), a rule code,
a line number, and a fix suggestion. Output is human-readable text or
`--format json`. Exit codes: `0` clean, `1` warnings only, `2` errors found.

## Requirements

- Python 3.10+ (tested on 3.12.3), **stdlib only — zero dependencies**
- No QNX toolchain needed: qnxcheck runs on the Linux host
- To actually *build* the generated skeleton for a target you need
  QNX SDP 8.0 (free for non-commercial use via QNX Everywhere)

## Quick start

```sh
# Validate a whole project
./qnxcheck.sh check examples/qemu-x86_64

# Validate one buildfile
./qnxcheck.sh buildfile system.build

# Check C sources (Neutrino API pitfalls)
./qnxcheck.sh c src/*.c

# Generate a correct skeleton (x86_64 QEMU or Raspberry Pi 5)
./qnxcheck.sh init --target x86_64 --dir my-qnx-app
./qnxcheck.sh check my-qnx-app
```

Example output:

```
tests/fixtures/buildfiles/bad-B07-no-procnto.build:2: error: [B07] bootstrap section has no procnto kernel line
    -> The QNX kernel (procnto, procnto-smp-instr, ...) must be the last bootstrap executable.
qnxcheck: 1 error(s), 0 warning(s), 0 info note(s)
```

## Why this matters for QNX

A QNX system image is assembled by `mkifs` from a buildfile. One wrong
attribute, a missing kernel line, or a script command whose binary was never
included, and the image fails to boot — on hardware you may not have on your
desk. On the target side, QNX's message-passing model is powerful but
unforgiving: an unchecked `ChannelCreate`, a `MsgSend` with no timeout, or a
`printf` inside an interrupt handler can hang or crash a safety-critical
system. `qnxcheck` finds these on the host, in seconds, before the image is
ever built.

## Rules reference

**Buildfile (B)** — grammar from the public QNX Utilities Reference
(`mkifs`) and the "Buildfile syntax" chapter of Building Embedded Systems:

- B01 unknown attribute · B02 attributes split across two bracket groups ·
  B03 empty attribute value · B04 unbalanced inline-file braces ·
  B05 missing bootstrap section · B06 missing `[+script]` section ·
  B07 procnto missing / not last in bootstrap · B08 bootstrap does not
  start with a `startup-*` binary · B09 duplicate in-image path ·
  B10 non-executable file in `/proc/boot` · B11 malformed perms/uid/gid/
  address value · B12 `[type=link]` without `target = source` ·
  B13 script command not included in the image · B14 `+raw` + `+compress`
  together · B15 unknown target architecture/protocol ·
  B16 comment `#` glued to a command · B17 multiple bootstrap/script sections

**C (C)** — QNX Neutrino Programmer's Guide / C Library Reference:

- C01 QNX API used without `<sys/neutrino.h>` · C02 unchecked
  `ChannelCreate` · C03 `ChannelCreate` without `ChannelDestroy` ·
  C04 `ConnectAttach` without `ConnectDetach` · C05 `name_attach`/
  `name_open` without detach/close · C06 blocking `MsgSend` without a
  `TimerTimeout` · C07 `pthread_create` with default attributes in
  realtime code · C08 non-async-signal-safe call in an interrupt handler ·
  C09 `InterruptAttach` without `InterruptDetach` · C10 port I/O without
  `ThreadCtl(_NTO_TCTL_IO)` · C11 Linux-only API (epoll, inotify, eventfd…)
  · C12 `fork()` (prefer `spawn()`) · C13 `MsgReceive` without `MsgReply`
  · C14 `sleep()`/`usleep()` in realtime code · C15 unchecked
  `sched_setscheduler`/`SchedSet`

**Makefile (M)** — QNX recursive makefile system:

- M01 no `common.mk` include · M02 `TARGET_CPU` not set ·
  M03 `USEFILE` not set · M04 `INSTALLDIR` not set ·
  M05 no `-Wall`/`-Wextra`

## QNX connection (for the judges)

qnxcheck is a **host-based developer tool** as defined in the hackathon
rules §4(2): it runs on Linux and its entire functionality is "specifically
intended to build, analyze, test … software for QNX 8.0". The buildfile
validator implements the documented mkifs grammar; the C checker encodes
QNX Neutrino message-passing, resource-manager and realtime rules; the
`init` command generates buildfiles and QNX C code that are valid by
construction. QNX version targeted: **QNX SDP 8.0**. Targets covered:
**x86_64 QEMU (multiboot)** and **aarch64 Raspberry Pi 5 (ELF)**.
Toolchain for the generated code: QNX SDP 8.0 `qcc` (host tool itself needs
only Python 3.10+).

## Development

```sh
python3 tests/run_tests.py   # stdlib-only test suite (11 tests)
```

The suite includes fixtures taken from the public QNX documentation
(`valid-shell.build` is the documented `shell.bld` example) and a bad
fixture per rule, plus dogfooding: every skeleton `qnxcheck init`
generates must pass `qnxcheck check` with zero findings.

## Tutorial

`docs/CODELAB.md` is a step-by-step tutorial, "Validate your first QNX 8.0
image buildfile with qnxcheck" (also the entry for the Best Codelab /
Tutorial bonus prize).

## License

MIT — see `LICENSE`.
