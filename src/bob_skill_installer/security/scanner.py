"""Static security scan over a fetched source tree.

The scanner never executes anything; it reads text and matches a curated set of
patterns. Findings at ``HIGH``/``CRITICAL`` are *blocking* — the pipeline raises
:class:`SecurityRejectedError` and nothing is installed. Lower-severity findings
become warnings on the install report.

Two guarantees from the spec are enforced here:
  * No executable scripts are ever copied automatically — every script file is
    quarantined (recorded, never carried into the generated skill).
  * Remote-exec / credential-harvest / MCP-auto-trust payloads are rejected.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from bob_skill_installer.logging_config import get_logger
from bob_skill_installer.models import Finding, RepoAnalysis, SecurityReport, Severity

_log = get_logger("security")


@dataclass(frozen=True)
class _Rule:
    pattern: re.Pattern[str]
    severity: Severity
    category: str
    message: str


def _ci(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


# Ordered roughly by how damaging the payload is. Patterns are intentionally
# conservative to keep false positives low (spec rule: "No false positives").
_RULES: tuple[_Rule, ...] = (
    _Rule(
        _ci(r"\b(curl|wget)\b[^\n|]*\|\s*(sudo\s+)?(ba|z)?sh\b"),
        Severity.CRITICAL,
        "remote-exec",
        "Pipe-to-shell install (curl|bash / wget|sh) detected.",
    ),
    _Rule(
        _ci(r"\b(ba|z)?sh\b\s*<\(\s*(curl|wget)\b"),
        Severity.CRITICAL,
        "remote-exec",
        "Process-substitution remote execution (sh <(curl ...)) detected.",
    ),
    _Rule(
        _ci(r"\beval\b\s*[\"']?\$\(\s*(curl|wget)\b"),
        Severity.CRITICAL,
        "remote-exec",
        "eval of remotely downloaded content detected.",
    ),
    _Rule(
        _ci(r"(iex|invoke-expression)\b[^\n]*(downloadstring|invoke-webrequest|net\.webclient)"),
        Severity.CRITICAL,
        "remote-exec",
        "PowerShell IEX download-and-run detected.",
    ),
    _Rule(
        _ci(r"\brm\s+-rf\s+(/|~|\$HOME)(\s|$)"),
        Severity.CRITICAL,
        "destructive-shell",
        "Destructive recursive delete of a root/home path detected.",
    ),
    _Rule(
        _ci(r"\b(cat|cp|scp|curl|nc|base64)\b[^\n]*(\.ssh/id_|\.aws/credentials|\.netrc|id_rsa)"),
        Severity.HIGH,
        "credential-harvesting",
        "Access to private keys / credential files detected.",
    ),
    _Rule(
        _ci(r"\b(printenv|env)\b[^\n]*\|\s*(curl|nc|wget)\b"),
        Severity.HIGH,
        "secret-exfiltration",
        "Environment variables piped to a network command detected.",
    ),
    _Rule(
        _ci(r"\bcurl\b[^\n]*(-d|--data)[^\n]*\$\{?[A-Z_]*(TOKEN|SECRET|KEY|PASSWORD)"),
        Severity.HIGH,
        "secret-exfiltration",
        "Secret-bearing environment variable posted over the network detected.",
    ),
    _Rule(
        _ci(r"\bmcp\b[^\n]*\b(install|add)\b[^\n]*(--yes|-y|--trust|--auto)"),
        Severity.HIGH,
        "mcp-auto-trust",
        "Automatic/unattended MCP server install detected.",
    ),
    _Rule(
        _ci(r"\"?(autoapprove|auto_trust|auto_approve)\"?\s*[:=]\s*true"),
        Severity.HIGH,
        "mcp-auto-trust",
        "MCP auto-approve/auto-trust flag enabled.",
    ),
    _Rule(
        _ci(r"\b(playwright|puppeteer|selenium)\b[^\n]*\.(launch|start|chromium|webkit)"),
        Severity.MEDIUM,
        "browser-automation",
        "Browser automation that may run without approval detected.",
    ),
)

# Files large enough to almost certainly be binaries/assets are skipped.
_MAX_SCAN_BYTES = 2 * 1024 * 1024


def _read_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > _MAX_SCAN_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:  # pragma: no cover - race on read
        return None


def scan_source(analysis: RepoAnalysis) -> SecurityReport:
    """Scan the analyzed tree and return a :class:`SecurityReport`."""
    findings: list[Finding] = []

    # Quarantine every script: it is recorded but never copied into the skill.
    quarantined = [str(p.relative_to(analysis.root)) for p in analysis.script_files]
    if quarantined:
        findings.append(
            Finding(
                severity=Severity.LOW,
                category="quarantined-scripts",
                message=(
                    f"{len(quarantined)} executable script(s) found; they will NOT be "
                    "copied into the installed skill."
                ),
                location=", ".join(quarantined[:10]) + (" ..." if len(quarantined) > 10 else ""),
            )
        )

    # Pattern scan over text + script file contents.
    scan_targets = {*analysis.text_files, *analysis.script_files}
    for path in sorted(scan_targets):
        content = _read_text(path)
        if not content:
            continue
        rel = str(path.relative_to(analysis.root))
        for line_no, line in enumerate(content.splitlines(), start=1):
            for rule in _RULES:
                if rule.pattern.search(line):
                    findings.append(
                        Finding(
                            severity=rule.severity,
                            category=rule.category,
                            message=rule.message,
                            location=f"{rel}:{line_no}",
                        )
                    )

    report = SecurityReport(findings=findings, quarantined_scripts=quarantined)
    if report.blocking:
        _log.warning("Security scan found %d blocking issue(s).", len(report.blocking))
    return report
