"""Converter for Claude skills (CLAUDE.md / skills/ / SKILL.md)."""

from __future__ import annotations

from pathlib import Path

from bob_skill_installer.converters.base import BaseConverter, dedupe_paths
from bob_skill_installer.models import RepoAnalysis, SkillFormat


class ClaudeConverter(BaseConverter):
    source_format = SkillFormat.CLAUDE

    def primary_sources(self, analysis: RepoAnalysis) -> list[Path]:
        root = analysis.root
        sources: list[Path] = []
        for name in ("SKILL.md", "CLAUDE.md"):
            candidate = root / name
            if candidate.is_file():
                sources.append(candidate)
        # Nested skill definitions, e.g. skills/<name>/SKILL.md.
        sources.extend(sorted(root.glob("skills/**/SKILL.md")))
        sources.extend(sorted(root.glob(".claude/skills/**/SKILL.md")))
        return dedupe_paths(sources)
