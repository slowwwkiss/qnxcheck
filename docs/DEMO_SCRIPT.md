# Demo video script — qnxcheck (< 3 minutes)

Record a terminal on the Linux host (the tool's intended device). No
voiceover needed if the terminal is readable; otherwise narrate the
commands below. Total target: ~2 minutes.

## Shot list (run in ~/workspace/qnx)

1. **Intro — what it is** (5 s)
   Show the README header, or just start typing:
   ```
   ./qnxcheck.sh --version
   # qnxcheck 0.1.0
   ```

2. **A correct project passes clean** (20 s)
   ```
   ./qnxcheck.sh check examples/qemu-x86_64
   # qnxcheck: 0 error(s), 0 warning(s), 0 info note(s)
   # qnxcheck: checked 1 buildfile(s), 1 C file(s), 1 makefile(s)
   ```

3. **A broken buildfile — the missing kernel** (30 s)
   ```
   ./qnxcheck.sh buildfile tests/fixtures/buildfiles/bad-B07-no-procnto.build
   # ...: error: [B07] bootstrap section has no procnto kernel line
   #     -> The QNX kernel (procnto, procnto-smp-instr, ...) must be the last bootstrap executable.
   # qnxcheck: 1 error(s), 0 warning(s), 0 info note(s)
   ```

4. **Broken C — real QNX pitfalls** (40 s)
   ```
   ./qnxcheck.sh c tests/fixtures/c/bad-client.c
   # ... [C06] MsgSend() blocks forever if the server never replies
   # ... [C08] printf() inside interrupt handler 'isr_handler' is not async-signal-safe
   # ... [C11] epoll_create() is not available on QNX Neutrino
   ```

5. **Generate a correct project** (20 s)
   ```
   ./qnxcheck.sh init --target rpi5 --dir /tmp/demo-rpi5
   ./qnxcheck.sh check /tmp/demo-rpi5
   # qnxcheck: 0 error(s), 0 warning(s), 0 info note(s)
   ```

6. **Outro** (5 s): show the repo + `docs/CODELAB.md`.

## Notes for the recording

- Terminal font large enough to read at 1080p.
- Keep the full commands visible; do not cut mid-output.
- The video must show the project functioning on the device it was built
  for — qnxcheck is a Linux host tool, so the Linux terminal IS the
  device. Say that in the description if needed.
- Upload to public YouTube, no copyrighted music.
