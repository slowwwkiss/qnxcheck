"""Shared finding model and report rendering for qnxcheck.

A Finding is one issue in one file. Severity: error / warning / info.
Exit codes: 0 = clean, 1 = warnings only, 2 = errors found.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class Finding:
    rule: str
    severity: str  # "error" | "warning" | "info"
    message: str
    path: str
    line: int = 0
    suggestion: str = ""

    def to_dict(self) -> dict:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "path": self.path,
            "line": self.line,
            "suggestion": self.suggestion,
        }


@dataclass
class Report:
    findings: list = field(default_factory=list)

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    def extend(self, findings) -> None:
        self.findings.extend(findings)

    @property
    def errors(self) -> int:
        return sum(1 for f in self.findings if f.severity == "error")

    @property
    def warnings(self) -> int:
        return sum(1 for f in self.findings if f.severity == "warning")

    @property
    def infos(self) -> int:
        return sum(1 for f in self.findings if f.severity == "info")

    @property
    def exit_code(self) -> int:
        if self.errors:
            return 2
        if self.warnings:
            return 1
        return 0

    def render_text(self) -> str:
        lines = []
        for f in sorted(self.findings, key=lambda x: (x.path, x.line, x.rule)):
            loc = f"{f.path}:{f.line}" if f.line else f.path
            lines.append(f"{loc}: {f.severity}: [{f.rule}] {f.message}")
            if f.suggestion:
                lines.append(f"    -> {f.suggestion}")
        lines.append(
            f"qnxcheck: {self.errors} error(s), {self.warnings} warning(s), "
            f"{self.infos} info note(s)"
        )
        return "\n".join(lines)

    def render_json(self) -> str:
        return json.dumps(
            {
                "summary": {
                    "errors": self.errors,
                    "warnings": self.warnings,
                    "infos": self.infos,
                },
                "findings": [f.to_dict() for f in self.findings],
            },
            indent=2,
        )
