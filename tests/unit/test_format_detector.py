"""Unit tests for format detection and repo analysis."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from bob_skill_installer.analyzer import analyze_repo, detect_formats
from bob_skill_installer.exceptions import AnalysisError
from bob_skill_installer.models import SkillFormat


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("claude", SkillFormat.CLAUDE),
        ("claude_tree", SkillFormat.CLAUDE),
        ("cursor", SkillFormat.CURSOR),
        ("windsurf", SkillFormat.WINDSURF),
        ("cline", SkillFormat.CLINE),
        ("roocode", SkillFormat.ROOCODE),
        ("openai", SkillFormat.OPENAI),
        ("generic", SkillFormat.GENERIC),
    ],
)
def test_best_format_detection(
    repo_factory: Callable[[str], Path], kind: str, expected: SkillFormat
) -> None:
    root = repo_factory(kind)
    detections = detect_formats(root)
    assert detections, f"no detection for {kind}"
    assert detections[0].fmt is expected
    assert detections[0].evidence


def test_detect_returns_sorted_desc(repo_factory: Callable[[str], Path]) -> None:
    root = repo_factory("claude")
    detections = detect_formats(root)
    scores = [d.score for d in detections]
    assert scores == sorted(scores, reverse=True)


def test_analyze_repo_inventory(repo_factory: Callable[[str], Path]) -> None:
    root = repo_factory("generic")
    analysis = analyze_repo(root)
    assert analysis.file_count >= 2
    assert analysis.readme is not None
    assert any(p.suffix == ".md" for p in analysis.markdown_files)
    assert analysis.best_format is SkillFormat.GENERIC


def test_analyze_repo_collects_scripts(repo_factory: Callable[[str], Path]) -> None:
    root = repo_factory("malicious")
    analysis = analyze_repo(root)
    assert any(p.name == "install.sh" for p in analysis.script_files)


def test_analyze_empty_dir_raises(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(AnalysisError):
        analyze_repo(empty)


def test_analyze_non_dir_raises(tmp_path: Path) -> None:
    f = tmp_path / "file.txt"
    f.write_text("x")
    with pytest.raises(AnalysisError):
        analyze_repo(f)


def test_unknown_when_no_markers(tmp_path: Path) -> None:
    root = tmp_path / "blank"
    root.mkdir()
    (root / "data.bin").write_bytes(b"\x00\x01")
    analysis = analyze_repo(root)
    assert analysis.best_format is SkillFormat.UNKNOWN
