"""Command-line interface for qnxcheck."""

from __future__ import annotations

import argparse
import os
import sys

from . import __version__
from .buildfile import parse_buildfile
from .ccheck import check_c_source
from .init import TARGETS, generate
from .makecheck import check_makefile
from .report import Report


def _read(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _emit(report: Report, fmt: str) -> int:
    if fmt == "json":
        print(report.render_json())
    else:
        print(report.render_text())
    return report.exit_code


def _cmd_buildfile(args) -> int:
    report = parse_buildfile(_read(args.file), args.file)
    return _emit(report, args.format)


def _cmd_c(args) -> int:
    report = Report()
    for path in args.files:
        report.extend(check_c_source(_read(path), path).findings)
    return _emit(report, args.format)


def _cmd_makefile(args) -> int:
    report = check_makefile(_read(args.file), args.file)
    return _emit(report, args.format)


def _cmd_check(args) -> int:
    report = Report()
    checked = {"buildfile": 0, "c": 0, "makefile": 0}
    for root, _dirs, files in os.walk(args.dir):
        for name in sorted(files):
            path = os.path.join(root, name)
            if name.endswith((".build", ".bld")):
                report.extend(
                    parse_buildfile(_read(path), path).findings)
                checked["buildfile"] += 1
            elif name.endswith((".c", ".h")):
                report.extend(
                    check_c_source(_read(path), path).findings)
                checked["c"] += 1
            elif name in ("Makefile", "makefile", "common.mk") or \
                    name.endswith(".mk"):
                report.extend(
                    check_makefile(_read(path), path).findings)
                checked["makefile"] += 1
    total = sum(checked.values())
    if total == 0:
        print(f"qnxcheck: nothing to check in {args.dir}")
        return 0
    code = _emit(report, args.format)
    print(f"qnxcheck: checked {checked['buildfile']} buildfile(s), "
          f"{checked['c']} C file(s), {checked['makefile']} makefile(s)")
    return code


def _cmd_init(args) -> int:
    try:
        written = generate(args.target, args.name, args.dir)
    except ValueError as exc:
        print(f"qnxcheck: {exc}", file=sys.stderr)
        return 3
    print(f"qnxcheck: wrote {len(written)} file(s) to {args.dir}:")
    for rel in written:
        print(f"  {rel}")
    print("Validate it with: qnxcheck check " + args.dir)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="qnxcheck",
        description="Host-side static analysis and validation toolkit "
                    "for QNX 8.0 projects. Runs on Linux; no QNX toolchain "
                    "needed.")
    p.add_argument("--version", action="version",
                   version=f"qnxcheck {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    pb = sub.add_parser("buildfile",
                        help="validate a mkifs buildfile (.build)")
    pb.add_argument("file")
    pb.add_argument("--format", choices=("text", "json"), default="text")
    pb.set_defaults(func=_cmd_buildfile)

    pc = sub.add_parser("c", help="check QNX Neutrino C source files")
    pc.add_argument("files", nargs="+")
    pc.add_argument("--format", choices=("text", "json"), default="text")
    pc.set_defaults(func=_cmd_c)

    pm = sub.add_parser("makefile",
                        help="check a QNX recursive makefile")
    pm.add_argument("file")
    pm.add_argument("--format", choices=("text", "json"), default="text")
    pm.set_defaults(func=_cmd_makefile)

    pk = sub.add_parser("check",
                        help="run all applicable checks on a project "
                             "directory")
    pk.add_argument("dir", nargs="?", default=".")
    pk.add_argument("--format", choices=("text", "json"), default="text")
    pk.set_defaults(func=_cmd_check)

    pi = sub.add_parser("init",
                        help="generate a correct QNX 8.0 project skeleton")
    pi.add_argument("--target", choices=sorted(TARGETS), default="x86_64")
    pi.add_argument("--name", default="qnx-hello")
    pi.add_argument("--dir", default=".")
    pi.set_defaults(func=_cmd_init)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
