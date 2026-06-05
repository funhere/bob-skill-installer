"""Validate a generated :class:`BobSkill` before it is written to disk.

Checks, mapped to the spec:
  * **Structure** — a non-empty ``SKILL.md`` with YAML frontmatter exists.
  * **Metadata** — all required frontmatter fields are present and non-empty.
  * **Markdown** — no unterminated fenced code blocks; at least one heading.
  * **References** — relative internal links resolve to a generated file.

Blocking problems (missing SKILL.md, missing required metadata) are ``HIGH``;
everything else is a non-blocking warning so a slightly-imperfect skill still
installs with the issues surfaced on the report.
"""

from __future__ import annotations

import re

from bob_skill_installer.converters.extraction import parse_frontmatter
from bob_skill_installer.logging_config import get_logger
from bob_skill_installer.models import BobSkill, Finding, Severity, ValidationResult

_log = get_logger("validator")

_REQUIRED_FIELDS = ("name", "description", "version", "source", "converted_from", "created_at")
_HEADING_RE = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)
_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
_FENCE_RE = re.compile(r"^\s*```", re.MULTILINE)


def validate_skill(skill: BobSkill) -> ValidationResult:
    """Run all checks and return a :class:`ValidationResult`."""
    findings: list[Finding] = []

    body = skill.skill_md or ""
    if not body.strip():
        findings.append(
            Finding(severity=Severity.HIGH, category="structure", message="SKILL.md is empty.")
        )
        return ValidationResult(findings=findings)

    front, _ = parse_frontmatter(body)
    if not front:
        findings.append(
            Finding(
                severity=Severity.HIGH,
                category="structure",
                message="SKILL.md is missing YAML frontmatter.",
            )
        )
    else:
        for field in _REQUIRED_FIELDS:
            value = front.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                findings.append(
                    Finding(
                        severity=Severity.HIGH,
                        category="metadata",
                        message=f"Required metadata field '{field}' is missing or empty.",
                        location="SKILL.md",
                    )
                )

    if not _HEADING_RE.search(body):
        findings.append(
            Finding(
                severity=Severity.MEDIUM,
                category="markdown",
                message="SKILL.md has no Markdown heading.",
                location="SKILL.md",
            )
        )

    if len(_FENCE_RE.findall(body)) % 2 != 0:
        findings.append(
            Finding(
                severity=Severity.MEDIUM,
                category="markdown",
                message="Unterminated fenced code block in SKILL.md.",
                location="SKILL.md",
            )
        )

    findings.extend(_check_links(skill))

    result = ValidationResult(findings=findings)
    if not result.ok:
        _log.warning("Validation found %d blocking issue(s).", len(findings) - len(result.warnings))
    return result


def _check_links(skill: BobSkill) -> list[Finding]:
    """Flag relative links in SKILL.md that don't resolve to a generated file."""
    available = {str(f.relative_path).replace("\\", "/") for f in skill.files}
    available_dirs = {p.rsplit("/", 1)[0] for p in available if "/" in p}
    findings: list[Finding] = []
    for raw_target in _LINK_RE.findall(skill.skill_md):
        target = raw_target.split("#", 1)[0].strip()
        if not target or _is_external(target):
            continue
        normalized = target.rstrip("/")
        if normalized in available or normalized in available_dirs:
            continue
        # A bare "docs/" reference is fine whenever any docs file exists.
        if normalized and any(p.startswith(normalized) for p in available):
            continue
        findings.append(
            Finding(
                severity=Severity.LOW,
                category="references",
                message=f"Internal link target not found among generated files: {target!r}",
                location="SKILL.md",
            )
        )
    return findings


def _is_external(target: str) -> bool:
    return target.startswith(("http://", "https://", "mailto:", "#", "tel:"))
