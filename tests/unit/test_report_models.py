"""Unit tests for report rendering and model helpers."""

from __future__ import annotations

from pathlib import Path

from bob_skill_installer.models import (
    Finding,
    InstallReport,
    InstallStatus,
    RepoAnalysis,
    SecurityReport,
    Severity,
    SkillFormat,
    SkillMetadata,
    ValidationResult,
    slugify,
)
from bob_skill_installer.report import render_plaintext, render_report


def test_slugify() -> None:
    assert slugify("React Architect!") == "react-architect"
    assert slugify("  Multi   Space ") == "multi-space"
    assert slugify("---") == "skill"


def test_metadata_slugs_name_and_trims_description() -> None:
    meta = SkillMetadata(
        name="My Cool Skill",
        description="  lots   of   space  ",
        source="https://x",
        converted_from=SkillFormat.CLAUDE,
    )
    assert meta.name == "my-cool-skill"
    assert meta.description == "lots of space"
    assert meta.created_at.endswith("Z")


def test_metadata_empty_description_defaults() -> None:
    meta = SkillMetadata(
        name="x", description="   ", source="https://x", converted_from=SkillFormat.GENERIC
    )
    assert meta.description == "Converted skill."


def test_finding_blocking_flag() -> None:
    assert Finding(severity=Severity.HIGH, category="c", message="m").is_blocking
    assert not Finding(severity=Severity.LOW, category="c", message="m").is_blocking


def test_validation_result_ok_and_warnings() -> None:
    res = ValidationResult(
        findings=[
            Finding(severity=Severity.LOW, category="a", message="warn"),
            Finding(severity=Severity.HIGH, category="b", message="block"),
        ]
    )
    assert not res.ok
    assert len(res.warnings) == 1


def test_security_report_ok() -> None:
    assert SecurityReport().ok
    rep = SecurityReport(findings=[Finding(severity=Severity.CRITICAL, category="x", message="m")])
    assert not rep.ok
    assert rep.blocking


def test_repo_analysis_best_format_empty(tmp_path: Path) -> None:
    analysis = RepoAnalysis(root=tmp_path, file_count=0)
    assert analysis.best_format is SkillFormat.UNKNOWN


def test_render_plaintext_success() -> None:
    report = InstallReport(
        status=InstallStatus.SUCCESS,
        skill_name="demo",
        version="1.0.0",
        source="https://github.com/org/demo",
        converted_from=SkillFormat.CLAUDE,
        target=".bob/skills/demo",
    )
    text = render_plaintext(report)
    assert text.startswith("SUCCESS")
    assert "Skill: demo" in text
    assert "Warnings: None" in text


def test_render_plaintext_with_warnings_and_error() -> None:
    report = InstallReport(
        status=InstallStatus.FAILED,
        skill_name="demo",
        version="-",
        source="https://x",
        converted_from=SkillFormat.UNKNOWN,
        warnings=["w1", "w2"],
        error="boom",
    )
    text = render_plaintext(report)
    assert "- w1" in text and "- w2" in text
    assert "Error: boom" in text


def test_render_report_does_not_raise() -> None:
    report = InstallReport(
        status=InstallStatus.SUCCESS_WITH_WARNINGS,
        skill_name="demo",
        version="1.0.0",
        source="https://x",
        converted_from=SkillFormat.CURSOR,
        target=".bob/skills/demo",
        warnings=["heads up"],
    )
    render_report(report)  # smoke: should print without error
