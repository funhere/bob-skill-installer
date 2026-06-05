"""Converter for Cline skills (.clinerules / .cline)."""

from __future__ import annotations

from pathlib import Path

from bob_skill_installer.converters.base import BaseConverter, dedupe_paths
from bob_skill_installer.models import RepoAnalysis, SkillFormat


class ClineConverter(BaseConverter):
    source_format = SkillFormat.CLINE

    def primary_sources(self, analysis: RepoAnalysis) -> list[Path]:
        root = analysis.root
        sources: list[Path] = []
        for name in (".clinerules", ".cline"):
            target = root / name
            if target.is_file():
                sources.append(target)
            elif target.is_dir():
                sources.extend(sorted(target.rglob("*.md")))
                sources.extend(sorted(target.rglob("*.txt")))
        return dedupe_paths(sources)
