# Codelab: Validate your first QNX 8.0 image buildfile with qnxcheck

**What you will learn:** how to catch the buildfile mistakes that stop a
QNX 8.0 image from booting — using a free host tool, before you ever touch
a target. No QNX toolchain, no hardware, no account needed. Time: ~15 min.

**You need:** a Linux machine with Python 3.10+ (no other dependencies).

---

## 1. Get qnxcheck

```sh
git clone https://github.com/slowwwkiss/qnxcheck.git
cd qnxcheck
./qnxcheck.sh --version
# qnxcheck 0.1.0
```

## 2. Look at a correct buildfile

QNX builds an OS image with `mkifs` from a **buildfile**. Open the example
for x86_64 QEMU:

```sh
cat examples/qemu-x86_64/system.build
```

```text
[image=0x400000]
[virtual=x86_64,multiboot] boot = {
    startup-x86 -D 8250
    PATH=/proc/boot procnto-smp-instr
}
[+script] .script = {
    display_msg "Hello from QNX 8.0"
    procmgr_symlink ../../proc/boot/libc.so.6 /usr/lib/ldqnx.so.2
    reopen
    hello &
}
[type=link] /usr/lib/ldqnx.so.2=/proc/boot/libc.so.6
libc.so.6
[uid=0 gid=0 perms=0755] /proc/boot/hello = hello
```

Three parts: a **bootstrap** section (`[virtual=...]`) that starts the
hardware and the kernel, a **script** section (`[+script]`) that runs after
the kernel starts, and a list of **files** to put in the image. Validate it:

```sh
./qnxcheck.sh buildfile examples/qemu-x86_64/system.build
# qnxcheck: 0 error(s), 0 warning(s), 0 info note(s)
```

## 3. Break it on purpose — the missing kernel

Delete the kernel line and see what happens. Copy the example and remove
`PATH=/proc/boot procnto-smp-instr`:

```sh
cp examples/qemu-x86_64/system.build /tmp/broken.build
# edit /tmp/broken.build: delete the procnto line
./qnxcheck.sh buildfile /tmp/broken.build
```

```text
/tmp/broken.build:2: error: [B07] bootstrap section has no procnto kernel line
    -> The QNX kernel (procnto, procnto-smp-instr, ...) must be the last bootstrap executable.
qnxcheck: 1 error(s), 0 warning(s), 0 info note(s)
```

Without `procnto` there is no kernel to run — the image would never boot.
`qnxcheck` exits with code `2` on errors, so you can gate it in CI.

## 4. Three more classic mistakes

Try each one in `/tmp/broken.build` and read the suggestion:

| Mistake | What qnxcheck says |
|---|---|
| `[uid=0] [gid=0] file` — attributes in two bracket groups | `B02: attributes split across two bracket groups` — combine them: `[uid=0 gid=0] file` |
| `hello &` in the script, but `hello` never listed as a file | `B13: script runs 'hello' but it is not included in the image` |
| `[type=link] /dev/console` with no target | `B12: [type=link] entry has no 'target = source'` |

Fix each one and re-run until the report is clean.

## 5. Check the C code too

The example server uses QNX message passing (`name_attach` +
`MsgReceive`/`MsgReply`). Check it:

```sh
./qnxcheck.sh c examples/qemu-x86_64/src/hello.c
# qnxcheck: 0 error(s), 0 warning(s), 0 info note(s)
```

Now look at a deliberately broken client and see what a real QNX bug
looks like:

```sh
./qnxcheck.sh c tests/fixtures/c/bad-client.c
```

You will see, among others: an unchecked `ChannelCreate` (C02), a
`MsgSend` with no timeout that blocks forever if the server dies (C06),
`printf` inside an interrupt handler (C08 — not async-signal-safe), and
`epoll_create` (C11 — epoll does not exist on QNX Neutrino). Each finding
tells you how to fix it.

## 6. Generate your own correct project

```sh
./qnxcheck.sh init --target rpi5 --dir my-qnx-app
./qnxcheck.sh check my-qnx-app
# qnxcheck: 0 error(s), 0 warning(s), 0 info note(s)
```

You now have a valid QNX 8.0 skeleton for Raspberry Pi 5: buildfile,
server source, and Makefile. Build it for real with QNX SDP 8.0 (free for
non-commercial use via QNX Everywhere):

```sh
cd my-qnx-app
make                    # cross-compile hello for aarch64le
mkifs system.build system.ifs
```

## 7. Put it in CI

```yaml
# .github/workflows/qnxcheck.yml
- name: Validate QNX project
  run: |
    python3 -m qnxcheck check .
```

Exit code `2` on errors, `1` on warnings, `0` when clean.

## What you learned

- A QNX buildfile has three parts: bootstrap, script, file list — and
  `qnxcheck` verifies the structure mkifs expects.
- The kernel (`procnto`) must be the last bootstrap executable; the first
  must be a `startup-*` binary.
- QNX message passing has strict pairing rules (create/destroy,
  attach/detach, receive/reply) that a host-side checker can enforce.
- You can validate all of this on a Linux host with zero QNX toolchain —
  and catch the bugs before the image is built.
