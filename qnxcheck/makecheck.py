"""Checks for QNX recursive-makefile structure (common.mk based projects).

QNX projects are normally built with the recursive makefile system:
a Makefile that includes $(QNX_TARGET)/usr/include/mk/common.mk and
defines TARGET_CPU, USEFILE and INSTALLDIR. These checks catch the
structural mistakes that make a QNX project unbuildable with qcc/make.

Rules:
  M01 error   no common.mk include
  M02 warning TARGET_CPU not set
  M03 warning USEFILE not set
  M04 warning INSTALLDIR not set
  M05 info    no -Wall in compiler warning flags
"""

from __future__ import annotations

import re

from .report import Finding, Report

_COMMON_MK_RE = re.compile(r"include\s+.*common\.mk")
_ASSIGN_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*[:+?]?=",
                        re.MULTILINE)


def check_makefile(text: str, path: str) -> Report:
    report = Report()
    # findall returns the single captured group: the variable name.
    assigned = set(_ASSIGN_RE.findall(text))

    if not _COMMON_MK_RE.search(text):
        report.add(Finding(
            "M01", "error",
            "no 'include .../common.mk' found — this is not a QNX "
            "recursive makefile",
            path, 1,
            "Add: include $(QNX_TARGET)/usr/include/mk/common.mk at the "
            "end of the Makefile."))
    if "TARGET_CPU" not in assigned:
        report.add(Finding(
            "M02", "warning",
            "TARGET_CPU is not set (e.g. x86_64, aarch64le)",
            path, 1,
            "Set TARGET_CPU to the target architecture, e.g. "
            "TARGET_CPU = x86_64."))
    if "USEFILE" not in assigned:
        report.add(Finding(
            "M03", "warning",
            "USEFILE is not set — the binary will have no usage message",
            path, 1,
            "Set USEFILE to a file with the usage text, e.g. "
            "USEFILE = $(PROJECT_ROOT)/usage.txt."))
    if "INSTALLDIR" not in assigned:
        report.add(Finding(
            "M04", "warning",
            "INSTALLDIR is not set — 'make install' has nowhere to put "
            "the binary",
            path, 1,
            "Set INSTALLDIR, e.g. INSTALLDIR = usr/bin."))
    if not re.search(r"-W(all|extra)", text):
        report.add(Finding(
            "M05", "info",
            "no -Wall/-Wextra in compiler flags",
            path, 1,
            "Add EXTRA_CCOPTS += -Wall -Wextra to catch bugs at compile "
            "time."))
    return report
