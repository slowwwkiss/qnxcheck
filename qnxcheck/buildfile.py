"""mkifs buildfile parser and validator for QNX 8.0.

Grammar (from the public QNX Utilities Reference, mkifs, and the
"Buildfile syntax" chapter of Building Embedded Systems):

- Each line is: [attributes] file_specification  (either part optional)
- ``#`` starts a comment, and there must be a space between a buildfile
  command and the ``#``.
- Attributes are one bracket group per line: boolean ``+name`` / ``-name``
  or value ``name=value`` (no spaces around ``=``). All attributes for a
  line go inside the SAME pair of brackets.
- An attribute group on a line by itself ("sticky") applies to all
  following files until changed.
- Inline files: ``[attrs] name = { ... }`` — e.g. the bootstrap section
  ``[virtual=x86_64,multiboot] boot = { startup-x86 ... procnto }`` and the
  startup script ``[+script] .script = { ... }``.
- ``[type=link] target = source`` creates an in-image symbolic link.
- ``target = source`` (no type) copies a host file into the image at target.

This module never runs mkifs (mkifs license-checks against a QNX license
and needs SDP 8.0); it validates the buildfile text only.
"""

from __future__ import annotations

import re

from .report import Finding, Report

# Boolean attributes documented for mkifs (QNX 7.1+ / 8.0 docs).
BOOL_ATTRS = {
    "autolink", "bigendian", "littleendian", "compress", "followlink",
    "keeplinked", "optional", "raw", "script", "include",
}
# Value attributes documented for mkifs (QNX 7.1+ / 8.0 docs).
VALUE_ATTRS = {
    "cd", "chain", "code", "data", "dperms", "filter", "gid", "image",
    "linker", "module", "perms", "physical", "prefix", "ram", "search",
    "type", "uid", "virtual", "drop", "keepsection",
}
KNOWN_ATTRS = BOOL_ATTRS | VALUE_ATTRS

KNOWN_ARCHS = {
    "x86_64", "aarch64le", "armle-v7", "armle", "armbe", "armv7",
    "ppcbe", "ppcle", "mipsbe", "mipsle", "shle", "shbe", "x86",
}
KNOWN_PROTOCOLS = {"elf", "multiboot", "srec", "raw", "binary"}

# Commands that are built into the QNX startup script language / procnto.
SCRIPT_BUILTINS = {
    "display_msg", "reopen", "waitfor", "procmgr_symlink", "procmgr_daemon",
    "seedres", "mount", "umount", "echo", "sleep", "rm", "ln", "cp",
    "export", "SYSNAME", "PATH", "LD_LIBRARY_PATH",
}
# Common QNX utility prefixes that legitimately appear in .script.
SCRIPT_UTILITY_PREFIXES = (
    "devc-", "devb-", "io-", "fs-", "slogger", "pipe", "mqueue", "pps",
    "screen", "drm-", "usb", "cam-", "i2c-", "spi-", "gpio-", "netmanager",
    "dhcp", "ifconfig", "route", "telnetd", "ftpd", "sshd", "random",
    "seed", "procnto",
)
# A line inside [+script] that is an assignment (VAR=value) is not a command.
_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")
# octal perms like 0755 / 0644, or symbolic like +r,+x / +x / -w
_OCTAL_PERMS_RE = re.compile(r"^0?[0-7]{3,4}$")
_SYMBOLIC_PERMS_RE = re.compile(r"^[+-][rwxst]{1,4}(,[+-][rwxst]{1,4})*$")
_HEX_RE = re.compile(r"^0[xX][0-9a-fA-F]+$")


class _Line:
    __slots__ = ("no", "raw", "attrs", "spec", "comment_bad")

    def __init__(self, no, raw, attrs, spec, comment_bad):
        self.no = no
        self.raw = raw
        self.attrs = attrs  # list of (name, value_or_None) or None
        self.spec = spec    # file specification text ("" if none)
        self.comment_bad = comment_bad  # "#" attached to a token, no space


def _split_comment(text: str):
    """Return (code, comment_bad). A '#' starts a comment only when it is
    at the start of the line or preceded by whitespace. A '#' glued to a
    token is flagged (docs require a space before '#')."""
    for i, ch in enumerate(text):
        if ch == "#":
            if i == 0 or text[i - 1] in " \t":
                return text[:i], False
            return text, True  # '#' attached to a token
    return text, False


def _parse_attrs(group: str, line_no: int, path: str, report: Report):
    """Parse the inside of one [...] group. Returns list of (name, value)."""
    attrs = []
    for tok in group.split():
        if tok.startswith(("+", "-")):
            name = tok[1:]
            if name not in BOOL_ATTRS:
                report.add(Finding(
                    "B01", "error",
                    f"unknown boolean attribute '{tok}'",
                    path, line_no,
                    "Remove it or check the mkifs attribute list in the "
                    "QNX Utilities Reference."))
            attrs.append((name, tok.startswith("+")))
        elif "=" in tok:
            name, value = tok.split("=", 1)
            if name not in VALUE_ATTRS:
                report.add(Finding(
                    "B01", "error",
                    f"unknown value attribute '{name}'",
                    path, line_no,
                    "Remove it or check the mkifs attribute list in the "
                    "QNX Utilities Reference."))
            elif value == "":
                report.add(Finding(
                    "B03", "error",
                    f"attribute '{name}' has an empty value",
                    path, line_no,
                    f"Give '{name}' a value, e.g. [type=link]."))
            attrs.append((name, value))
        else:
            report.add(Finding(
                "B01", "error",
                f"unrecognised attribute token '{tok}'",
                path, line_no,
                "Attributes are +name / -name or name=value, all inside "
                "one pair of brackets."))
            attrs.append((tok, None))
    return attrs


def _validate_attr_values(attrs, line_no, path, report):
    """Value-format checks for the attributes on one line."""
    for name, value in attrs:
        if not isinstance(value, str):
            continue  # boolean attribute: no value to validate
        if name in ("perms", "dperms"):
            if not (_OCTAL_PERMS_RE.match(value)
                    or _SYMBOLIC_PERMS_RE.match(value)):
                report.add(Finding(
                    "B11", "warning",
                    f"{name} value '{value}' is neither octal (e.g. 0755) "
                    f"nor symbolic (e.g. +r,+x)",
                    path, line_no,
                    "Use an octal mode like perms=0755 or symbolic "
                    "perms=+r,+x."))
        elif name in ("uid", "gid"):
            if not (value.isdigit() or value.startswith("$")
                    or re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", value)):
                report.add(Finding(
                    "B11", "warning",
                    f"{name} value '{value}' is not a number, name or "
                    f"$VARIABLE",
                    path, line_no, "Use a numeric id, e.g. uid=0."))
        elif name in ("image", "physical", "ram", "chain"):
            if not _HEX_RE.match(value):
                report.add(Finding(
                    "B11", "warning",
                    f"{name} value '{value}' is not a hex address/size "
                    f"(0x...)",
                    path, line_no,
                    f"Use a hex value, e.g. {name}=0x400000."))
        elif name == "virtual":
            if _HEX_RE.match(value):
                continue  # virtual=0xADDR placement form
            parts = value.split(",")
            arch = parts[0]
            if arch not in KNOWN_ARCHS:
                report.add(Finding(
                    "B15", "error",
                    f"unknown target architecture '{arch}' in "
                    f"virtual={value}",
                    path, line_no,
                    "Use a documented arch, e.g. virtual=x86_64,multiboot "
                    "or virtual=aarch64le,elf."))
            elif len(parts) > 1 and parts[1] not in KNOWN_PROTOCOLS:
                report.add(Finding(
                    "B15", "warning",
                    f"unknown boot protocol '{parts[1]}' in "
                    f"virtual={value}",
                    path, line_no,
                    "Use elf, multiboot, srec, raw or binary."))


def parse_buildfile(text: str, path: str) -> Report:
    """Parse and validate a mkifs buildfile. Returns a Report."""
    report = Report()
    lines: list[_Line] = []
    for no, raw in enumerate(text.splitlines(), 1):
        code, comment_bad = _split_comment(raw)
        code = code.rstrip()
        if comment_bad:
            report.add(Finding(
                "B16", "warning",
                "comment '#' is glued to a command with no space before it",
                path, no,
                "Put a space between the command and '#'; mkifs ignores "
                "text after '#' only when separated by a space."))
        attrs = None
        spec = code.strip()
        # A bracket group must come first on the line.
        if spec.startswith("["):
            end = spec.find("]")
            if end == -1:
                report.add(Finding(
                    "B02", "error",
                    "unclosed '[' attribute group",
                    path, no, "Close the attribute group with ']'."))
                lines.append(_Line(no, raw, [], spec, comment_bad))
                continue
            group = spec[1:end]
            attrs = _parse_attrs(group, no, path, report)
            _validate_attr_values(attrs, no, path, report)
            rest = spec[end + 1:].strip()
            if rest.startswith("["):
                report.add(Finding(
                    "B02", "error",
                    "attributes split across two bracket groups on one line",
                    path, no,
                    "Combine all attributes in one pair of brackets, "
                    "e.g. [uid=0 gid=0 perms=0755] file."))
            spec = rest
        lines.append(_Line(no, raw, attrs, spec, comment_bad))

    # ---- structural analysis ----
    sticky: dict = {}          # sticky attributes from bare [attrs] lines
    targets: dict = {}         # in-image target path -> line no
    included: set = set()      # basenames of files included in the image
    inline_stack: list = []    # (name, line_no, attrs) of open inline files
    bootstrap = None           # (line_no, [content lines]) of bootstrap
    script = None              # (line_no, [content lines]) of +script
    bootstrap_count = 0
    script_count = 0

    def effective_attrs(line_attrs):
        eff = dict(sticky)
        if line_attrs:
            for name, value in line_attrs:
                eff[name] = value
        return eff

    for ln in lines:
        spec = ln.spec
        # bare attribute line -> sticky for subsequent files
        if ln.attrs is not None and not spec:
            for name, value in ln.attrs:
                sticky[name] = value
            continue
        if not spec:
            continue
        # inline file close
        if spec == "}":
            if not inline_stack:
                report.add(Finding(
                    "B04", "error", "stray '}' with no open inline file",
                    path, ln.no, "Remove it or open an inline file first."))
            else:
                inline_stack.pop()
            continue
        # inline file open:  name = {
        m = re.match(r"^(\S+)\s*=\s*\{$", spec)
        if m:
            name = m.group(1)
            eff = effective_attrs(ln.attrs)
            inline_stack.append((name, ln.no, eff))
            if "virtual" in eff:
                bootstrap_count += 1
                bootstrap = (ln.no, [])
            if eff.get("script") is True:
                script_count += 1
                script = (ln.no, [])
            continue
        # content lines inside an inline file
        if inline_stack:
            top_name, _, _ = inline_stack[-1]
            if bootstrap is not None and bootstrap[0] == inline_stack[-1][1]:
                bootstrap[1].append((ln.no, spec))
            if script is not None and script[0] == inline_stack[-1][1]:
                script[1].append((ln.no, spec))
            continue
        # ---- plain file entry ----
        eff = effective_attrs(ln.attrs)
        # target = source form
        if "=" in spec and not spec.startswith("="):
            target, _, source = spec.partition("=")
            target = target.strip()
            source = source.strip()
        else:
            target, source = spec, spec
        # type=link must have target = source
        if eff.get("type") == "link" and "=" not in spec:
            report.add(Finding(
                "B12", "error",
                f"[type=link] entry '{spec}' has no 'target = source'",
                path, ln.no,
                "Write it as [type=link] /dev/console=/dev/ser1."))
        # duplicate in-image target
        if target in targets:
            report.add(Finding(
                "B09", "error",
                f"in-image path '{target}' is included twice "
                f"(also on line {targets[target]})",
                path, ln.no,
                "Each path may appear once in the image; remove one entry."))
        else:
            targets[target] = ln.no
        included.add(target.split("/")[-1])
        included.add(source.split("/")[-1])
        # +raw and +compress together make no sense
        has_raw = _attr_on(ln.attrs, sticky, "raw")
        has_compress = _attr_on(ln.attrs, sticky, "compress")
        if has_raw and has_compress:
            report.add(Finding(
                "B14", "info",
                f"'{target}' is both +raw and +compress; +raw files are "
                f"not processed, so compression has no effect",
                path, ln.no,
                "Drop +compress for raw data files."))
        # executables in /proc/boot should be executable
        if target.startswith("/proc/boot/"):
            perms = eff.get("perms")
            if perms is not None:
                ok = False
                if _OCTAL_PERMS_RE.match(perms):
                    ok = int(perms, 8) & 0o111 != 0
                elif _SYMBOLIC_PERMS_RE.match(perms):
                    ok = "+x" in perms
                if not ok:
                    report.add(Finding(
                        "B10", "warning",
                        f"'{target}' in /proc/boot has non-executable "
                        f"perms={perms}",
                        path, ln.no,
                        "Executables in /proc/boot need the execute bit, "
                        "e.g. perms=0755."))

    # unclosed inline files
    for name, no, _ in inline_stack:
        report.add(Finding(
            "B04", "error",
            f"inline file '{name}' opened on line {no} is never closed",
            path, no, "Close the inline file with '}' on its own line."))

    # bootstrap / script presence and content
    if bootstrap_count == 0:
        report.add(Finding(
            "B05", "error",
            "no bootstrap section: a buildfile needs one inline file "
            "with a [virtual=<arch>,<protocol>] attribute",
            path, 0,
            "Add e.g. [virtual=x86_64,multiboot] boot = { startup-x86 "
            "PATH=/proc/boot procnto-smp-instr }."))
    elif bootstrap_count > 1:
        report.add(Finding(
            "B17", "error",
            f"{bootstrap_count} bootstrap sections found; a buildfile has "
            f"exactly one",
            path, 0, "Keep a single [virtual=...] bootstrap section."))
    if script_count == 0:
        report.add(Finding(
            "B06", "error",
            "no [+script] section: the image needs a startup script",
            path, 0,
            "Add e.g. [+script] .script = { display_msg Booting "
            "reopen ... }."))
    elif script_count > 1:
        report.add(Finding(
            "B17", "error",
            f"{script_count} [+script] sections found; a buildfile has "
            f"exactly one",
            path, 0, "Keep a single [+script] section."))

    if bootstrap is not None:
        # Sequence of commands in the bootstrap section. A line may carry
        # VAR=value assignments before the command, e.g.
        # "PATH=/proc/boot procnto-smp-instr" — the command is procnto.
        seq = [(_command_name(s), no) for no, s in bootstrap[1]]
        seq = [(cmd, no) for cmd, no in seq if cmd]
        if seq:
            if not seq[0][0].startswith("startup-"):
                report.add(Finding(
                    "B08", "error",
                    f"bootstrap section starts with '{seq[0][0]}', not a "
                    f"startup-* binary",
                    path, seq[0][1],
                    "The first bootstrap executable must be the startup "
                    "binary (e.g. startup-x86), it receives control first."))
            if not any(cmd.startswith("procnto") for cmd, _ in seq):
                report.add(Finding(
                    "B07", "error",
                    "bootstrap section has no procnto kernel line",
                    path, bootstrap[0],
                    "The QNX kernel (procnto, procnto-smp-instr, ...) must "
                    "be the last bootstrap executable."))
            elif not seq[-1][0].startswith("procnto"):
                report.add(Finding(
                    "B07", "error",
                    f"bootstrap section ends with '{seq[-1][0]}', not "
                    f"procnto",
                    path, seq[-1][1],
                    "procnto must be the last item in the bootstrap "
                    "section; the kernel starts the init script."))

    if script is not None:
        for no, spec in script[1]:
            cmd = _command_name(spec)
            if not cmd or cmd in SCRIPT_BUILTINS:
                continue
            if cmd.rstrip("&") in SCRIPT_BUILTINS:
                continue
            base = cmd.split("/")[-1]
            if base in included:
                continue
            if any(base.startswith(p) for p in SCRIPT_UTILITY_PREFIXES):
                continue
            report.add(Finding(
                "B13", "warning",
                f"script runs '{cmd}' but it is not included in the image",
                path, no,
                "Add the binary to the buildfile or remove the command; "
                "the script will fail at boot otherwise."))

    return report


def _command_name(spec: str) -> str:
    """First non-assignment token of a line, e.g. 'procnto-smp-instr'
    for 'PATH=/proc/boot procnto-smp-instr'. Returns '' if there is none."""
    for tok in spec.split():
        if _ASSIGN_RE.match(tok):
            continue
        return tok
    return ""


def _attr_on(line_attrs, sticky, name) -> bool:
    """True if a boolean attribute is on, from the line or sticky attrs."""
    if line_attrs:
        for n, v in line_attrs:
            if n == name:
                return bool(v)
    return sticky.get(name) is True
