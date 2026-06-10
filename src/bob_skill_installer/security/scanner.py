"""Static security scan over a fetched source tree.

The scanner never executes anything; it reads text and matches a curated set of
patterns. Findings at ``HIGH``/``CRITICAL`` are *blocking* — the pipeline raises
:class:`SecurityRejectedError` and nothing is installed. Lower-severity findings
become warnings on the install report.

What the scanner guarantees:
  * Remote-exec / credential-harvest / destructive-shell / MCP-auto-trust
    payloads are detected and *block* the install (nothing is written).
  * Scripts and secret files are inventoried so the pipeline can report exactly
    what was copied or excluded. The copy decision itself is install-policy
    (``--no-scripts`` / ``--no-secrets``), not a security verdict.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from bob_skill_installer.logging_config import get_logger
from bob_skill_installer.models import Finding, RepoAnalysis, SecurityReport, Severity

_log = get_logger("security")

# -- Sensitive file policy (shared with the converter so secrets are both
#    reported here and excluded from the installed skill) ------------------- #
# fmt: off
_SENSITIVE_NAMES = {
    ".netrc", ".npmrc", ".pypirc", ".htpasswd", ".pgpass",
    "credentials", ".git-credentials", "secrets.yaml", "secrets.yml",
}
_SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".keystore", ".jks"}
_PRIVATE_KEY_STEMS = {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}
_ENV_ALLOW_SUFFIXES = (".example", ".sample", ".template", ".dist", ".md")
# fmt: on


def is_sensitive_path(rel: Path) -> bool:
    """True for files that may carry secrets and must never be copied.

    Allows obvious *template* variants (``.env.example``, ``*.pub``) so a skill's
    documented placeholders survive while real credentials do not.
    """
    name = rel.name
    low = name.lower()
    if low == ".env":
        return True
    if low.startswith(".env.") and not low.endswith(_ENV_ALLOW_SUFFIXES):
        return True
    if name in _SENSITIVE_NAMES:
        return True
    if rel.suffix.lower() in _SENSITIVE_SUFFIXES:
        return True
    if name.endswith(".pub"):  # public keys are safe
        return False
    return any(name == stem or name.startswith(stem + ".") for stem in _PRIVATE_KEY_STEMS)


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
    """Scan the analyzed tree and return a :class:`SecurityReport`.

    Scripts and secret files are inventoried (and script/text content is
    pattern-scanned for blocking payloads). Whether those files are ultimately
    copied is an *install-policy* decision made downstream (``--no-scripts`` /
    ``--no-secrets``), so this scanner stays policy-free and only reports facts.
    """
    findings: list[Finding] = []

    # Inventory scripts and secret-bearing files. Whether they are copied is an
    # install-policy decision the pipeline makes; the scanner only reports facts.
    scripts = [str(p.relative_to(analysis.root)) for p in analysis.script_files]
    sensitive = [
        str(p.relative_to(analysis.root))
        for p in analysis.all_files
        if is_sensitive_path(p.relative_to(analysis.root))
    ]

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

    report = SecurityReport(findings=findings, scripts=scripts, sensitive_files=sensitive)
    if report.blocking:
        _log.warning("Security scan found %d blocking issue(s).", len(report.blocking))
    return report
