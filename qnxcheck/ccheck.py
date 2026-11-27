"""Static checks for QNX Neutrino C source code.

Regex-based, comment- and string-aware analysis of one .c/.h file.
Each rule is documented with the QNX behaviour it guards against; rules
are deliberately conservative (they flag patterns, not intent) and every
finding carries a fix suggestion.

Rules:
  C01 error   QNX API used but <sys/neutrino.h> not included
  C02 warning ChannelCreate/ChannelCreate_r return value unchecked
  C03 warning ChannelCreate without matching ChannelDestroy
  C04 warning ConnectAttach without matching ConnectDetach
  C05 warning name_attach/name_open without matching detach/close
  C06 warning blocking MsgSend (no timeout) — consider TimerTimeout
  C07 warning pthread_create with default attributes in realtime code
  C08 error   non-async-signal-safe call inside an interrupt handler
  C09 warning InterruptAttach without matching InterruptDetach
  C10 warning port I/O (in*/out*, mmap_device_io) without ThreadCtl IO
  C11 error   Linux-only API not available on QNX Neutrino
  C12 warning fork() — prefer spawn() on QNX
  C13 warning MsgReceive in a function that never MsgReplies
  C14 info    sleep()/usleep() in realtime code — prefer nanosleep/delay
  C15 warning sched_setscheduler/SchedSet return value unchecked
"""

from __future__ import annotations

import re

from .report import Finding, Report

QNX_APIS = (
    "ChannelCreate", "ChannelCreate_r", "ChannelDestroy", "ConnectAttach",
    "ConnectDetach", "MsgSend", "MsgSendv", "MsgSendPulse", "MsgReceive",
    "MsgReceivev", "MsgReply", "MsgReplyv", "MsgDeliverEvent",
    "name_attach", "name_detach", "name_open", "name_close",
    "InterruptAttach", "InterruptAttachEvent", "InterruptDetach",
    "InterruptWait", "InterruptMask", "InterruptUnmask",
    "ThreadCtl", "SchedSet", "SchedGet", "pthread_create",
    "mmap_device_io", "mmap_device_memory", "procmgr_ability",
    "TimerTimeout", "TimerCreate", "ClockTime",
)

LINUX_ONLY_APIS = {
    "epoll_create": "epoll is Linux-only; use QNX ionotify() or a "
                    "pulse/event channel instead",
    "epoll_create1": "epoll is Linux-only; use QNX ionotify() or a "
                     "pulse/event channel instead",
    "inotify_init": "inotify is Linux-only; QNX has no inotify — poll "
                    "the path or use a resource manager",
    "inotify_init1": "inotify is Linux-only; QNX has no inotify — poll "
                     "the path or use a resource manager",
    "eventfd": "eventfd is Linux-only; use a QNX pulse (MsgSendPulse) "
               "instead",
    "signalfd": "signalfd is Linux-only; use sigwait() or a QNX pulse "
                "instead",
    "timerfd_create": "timerfd is Linux-only; use QNX TimerCreate() "
                      "instead",
}

# Functions that are not async-signal-safe: forbidden in interrupt handlers.
ISR_UNSAFE = ("printf", "fprintf", "sprintf", "snprintf", "malloc",
              "calloc", "realloc", "free", "puts", "fputs")

_PORT_IO_RE = re.compile(
    r"\b(in8|in16|in32|out8|out16|out32|mmap_device_io|mmap_device_memory)\s*\("
)

# Cap findings per rule per file so one bad file does not flood the report.
_MAX_PER_RULE = 5


def _strip_code(text: str) -> str:
    """Remove // and /* */ comments and string/char literals, keeping
    newlines and column positions (replaced by spaces)."""
    out = []
    i, n = 0, len(text)
    state = "code"  # code | linecomment | blockcomment | string | char
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if state == "code":
            if ch == "/" and nxt == "/":
                state = "linecomment"
                out.append("  ")
                i += 2
            elif ch == "/" and nxt == "*":
                state = "blockcomment"
                out.append("  ")
                i += 2
            elif ch == '"':
                state = "string"
                out.append(" ")
                i += 1
            elif ch == "'":
                state = "char"
                out.append(" ")
                i += 1
            else:
                out.append(ch)
                i += 1
        elif state == "linecomment":
            if ch == "\n":
                state = "code"
                out.append("\n")
            else:
                out.append(" ")
            i += 1
        elif state == "blockcomment":
            if ch == "*" and nxt == "/":
                state = "code"
                out.append("  ")
                i += 2
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
        elif state == "string":
            if ch == "\\":
                out.append("  ")
                i += 2
            elif ch == '"':
                state = "code"
                out.append(" ")
                i += 1
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
        else:  # char
            if ch == "\\":
                out.append("  ")
                i += 2
            elif ch == "'":
                state = "code"
                out.append(" ")
                i += 1
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
    return "".join(out)


def _line_no(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


_C_KEYWORDS = {
    "if", "else", "while", "for", "switch", "do", "return", "sizeof",
    "case", "default", "typedef", "struct", "union", "enum",
}


def _function_bodies(clean: str):
    """Yield (name, start_line, body_text, start_pos, end_pos) for
    top-level function definitions found by a simple brace-matching scan."""
    pattern = re.compile(
        r"(?:^|\n)\s*(?:[A-Za-z_][\w\s\*]*?)\b([A-Za-z_]\w*)\s*\([^;]*?\)\s*\{",
        re.MULTILINE)
    for m in pattern.finditer(clean):
        name = m.group(1)
        if name in _C_KEYWORDS:
            continue  # control-flow block, not a function definition
        prefix = clean[m.start():m.start(1)]
        if re.search(r"\b(if|while|for|switch)\b", prefix):
            continue  # e.g. `if (fork() == 0) {` — not a definition
        brace_pos = m.end() - 1
        depth = 0
        i = brace_pos
        while i < len(clean):
            if clean[i] == "{":
                depth += 1
            elif clean[i] == "}":
                depth -= 1
                if depth == 0:
                    yield (name, _line_no(clean, m.start()),
                           clean[brace_pos:i + 1], m.start(), i + 1)
                    break
            i += 1


def check_c_source(text: str, path: str) -> Report:
    report = Report()
    clean = _strip_code(text)
    per_rule_count: dict = {}

    def add(rule, severity, message, line, suggestion=""):
        per_rule_count[rule] = per_rule_count.get(rule, 0) + 1
        if per_rule_count[rule] > _MAX_PER_RULE:
            return
        report.add(Finding(rule, severity, message, path, line, suggestion))

    # C01: QNX API without <sys/neutrino.h>
    uses_qnx = any(re.search(rf"\b{re.escape(a)}\s*\(", clean)
                   for a in QNX_APIS)
    if uses_qnx and not re.search(r'#\s*include\s*<sys/neutrino\.h>',
                                  clean):
        add("C01", "error",
            "QNX Neutrino APIs are used but <sys/neutrino.h> is not "
            "included",
            1,
            "Add #include <sys/neutrino.h> (and <sys/netmgr.h> for "
            "name_attach/name_open).")

    # C11: Linux-only APIs
    for api, why in LINUX_ONLY_APIS.items():
        for m in re.finditer(rf"\b{re.escape(api)}\s*\(", clean):
            add("C11", "error",
                f"{api}() is not available on QNX Neutrino",
                _line_no(clean, m.start()), why)

    # C02: unchecked ChannelCreate / ChannelCreate_r
    for m in re.finditer(r"\b(ChannelCreate(?:_r)?)\s*\(", clean):
        line_start = clean.rfind("\n", 0, m.start()) + 1
        line_end = clean.find("\n", m.end())
        stmt = clean[line_start:line_end if line_end != -1 else len(clean)]
        stripped = stmt.strip()
        # OK if assigned, compared, returned, or inside an if/while.
        ok = bool(re.search(r"[=<>!]\s*$", clean[:m.start()].rstrip()[-3:])
                  or re.search(r"=\s*$", clean[max(0, m.start() - 40):m.start()])
                  or stripped.startswith(("if", "while", "return")))
        if not ok and re.match(r"^(ChannelCreate(?:_r)?)\s*\(.*\)\s*;$",
                               stripped):
            add("C02", "warning",
                f"{m.group(1)}() return value is not checked "
                "(channel id -1 means failure)",
                _line_no(clean, m.start()),
                "Assign it and check for -1, e.g. chid = ChannelCreate(0); "
                "if (chid == -1) { /* handle */ }")

    # C03/C04/C05/C09: lifecycle pairing (per file)
    pairs = [
        ("C03", "ChannelCreate", "ChannelDestroy",
         "channel created but never destroyed"),
        ("C04", "ConnectAttach", "ConnectDetach",
         "connection attached but never detached"),
        ("C05", "name_attach", "name_detach",
         "name attached but never detached"),
        ("C05", "name_open", "name_close",
         "name opened but never closed"),
        ("C09", "InterruptAttach", "InterruptDetach",
         "interrupt attached but never detached"),
    ]
    for rule, create, destroy, msg in pairs:
        n_create = len(re.findall(rf"\b{create}\s*\(", clean))
        n_destroy = len(re.findall(rf"\b{destroy}\s*\(", clean))
        if n_create > n_destroy:
            first = re.search(rf"\b{create}\s*\(", clean)
            line = _line_no(clean, first.start()) if first else 1
            add(rule, "warning",
                f"{create}() called {n_create}x but {destroy}() only "
                f"{n_destroy}x — {msg}",
                line,
                f"Pair every {create}() with {destroy}() on all exit "
                f"paths, including error paths.")

    # C06: blocking MsgSend without timeout. Skipped when the enclosing
    # function arms TimerTimeout before the call (the documented QNX way
    # to bound a MsgSend).
    spans = list(_function_bodies(clean))

    def _timeout_armed(pos: int) -> bool:
        for _name, _line, _body, start, end in spans:
            if start <= pos < end:
                return "TimerTimeout(" in clean[start:pos]
        return False

    for m in re.finditer(r"\bMsgSend\s*\(", clean):
        if _timeout_armed(m.start()):
            continue
        add("C06", "warning",
            "MsgSend() blocks forever if the server never replies",
            _line_no(clean, m.start()),
            "Arm a timeout first with TimerTimeout(CLOCK_REALTIME, "
            "_NTO_TIMEOUT_SEND, ...) or use MsgSendv with a timeout, "
            "so a dead server cannot hang the client.")

    # C07: pthread_create with default attributes in realtime code
    for m in re.finditer(r"\bpthread_create\s*\(\s*[^,]+,\s*NULL\s*,", clean):
        add("C07", "warning",
            "pthread_create() with NULL attributes: the thread runs with "
            "the default scheduling policy and priority",
            _line_no(clean, m.start()),
            "Set explicit attributes: pthread_attr_setschedpolicy(&attr, "
            "SCHED_FIFO) + pthread_attr_setschedparam() with a real-time "
            "priority, then pthread_create(&tid, &attr, ...).")

    # C10: port I/O without ThreadCtl(_NTO_TCTL_IO)
    if _PORT_IO_RE.search(clean) and not re.search(
            r"ThreadCtl\s*\(\s*_NTO_TCTL_IO", clean):
        m = _PORT_IO_RE.search(clean)
        add("C10", "warning",
            "port/device I/O used but ThreadCtl(_NTO_TCTL_IO) is never "
            "called in this file",
            _line_no(clean, m.start()),
            "Call ThreadCtl(_NTO_TCTL_IO, 0) once at startup to gain I/O "
            "privileges, and check its return value.")

    # C12: fork() — prefer spawn()
    for m in re.finditer(r"\bfork\s*\(", clean):
        add("C12", "warning",
            "fork() is available but expensive on QNX; spawn() is the "
            "native way to launch a process",
            _line_no(clean, m.start()),
            "Use spawn() / spawnp() with POSIX_SPAWN_* flags instead.")

    # C14: sleep/usleep in realtime code
    for m in re.finditer(r"\b(usleep|sleep)\s*\(", clean):
        add("C14", "info",
            f"{m.group(1)}() is not precise enough for real-time waits",
            _line_no(clean, m.start()),
            "Use nanosleep() or delay() for deterministic timing.")

    # C15: unchecked sched_setscheduler / SchedSet
    for m in re.finditer(r"\b(sched_setscheduler|SchedSet)\s*\(", clean):
        line_start = clean.rfind("\n", 0, m.start()) + 1
        line_end = clean.find("\n", m.end())
        stmt = clean[line_start:line_end if line_end != -1 else len(clean)].strip()
        if re.match(r"^(sched_setscheduler|SchedSet)\s*\(.*\)\s*;$", stmt):
            add("C15", "warning",
                f"{m.group(1)}() return value is not checked",
                _line_no(clean, m.start()),
                "Check for -1 and handle EPERM/EINVAL: a failed priority "
                "change silently leaves the thread at the wrong priority.")

    # C08: unsafe calls inside interrupt handlers.
    # InterruptAttach(intr, handler, area, flags, id) — the handler is the
    # SECOND argument. (InterruptAttachEvent takes a sigevent, no handler.)
    handlers = set()
    for m in re.finditer(
            r"\bInterruptAttach\s*\(\s*[^,]+,\s*([A-Za-z_]\w*)\s*,",
            clean):
        handlers.add(m.group(1))
    for name, start_line, body, _s, _e in _function_bodies(clean):
        if name not in handlers:
            continue
        for fn in ISR_UNSAFE:
            for m in re.finditer(rf"\b{fn}\s*\(", body):
                add("C08", "error",
                    f"{fn}() inside interrupt handler '{name}' is not "
                    f"async-signal-safe",
                    start_line + body[:m.start()].count("\n"),
                    "Interrupt handlers may only use async-signal-safe "
                    "calls; defer work to a thread via a pulse "
                    "(MsgSendPulse) instead.")

    # C13: MsgReceive without MsgReply in the same function
    for name, start_line, body, _s, _e in _function_bodies(clean):
        if re.search(r"\bMsgReceive\w*\s*\(", body) and not re.search(
                r"\bMsgReply\w*\s*\(", body):
            add("C13", "warning",
                f"function '{name}' calls MsgReceive() but never "
                f"MsgReply() — the sender will block forever",
                start_line,
                "Reply on every path, including error paths, or use "
                "MsgError() to unblock the sender with an error.")

    return report
