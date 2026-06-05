"""Repository analysis: walk a tree and classify its skill format."""

from __future__ import annotations

from bob_skill_installer.analyzer.format_detector import detect_formats
from bob_skill_installer.analyzer.repo_analyzer import analyze_repo

__all__ = ["analyze_repo", "detect_formats"]
