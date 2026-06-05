"""Converter for Windsurf rules (.windsurfrules / .windsurf/)."""

from __future__ import annotations

from pathlib import Path

from bob_skill_installer.converters.base import BaseConverter, dedupe_paths
from bob_skill_installer.models import RepoAnalysis, SkillFormat


class WindsurfConverter(BaseConverter):
    source_format = SkillFormat.WINDSURF

    def primary_sources(self, analysis: RepoAnalysis) -> list[Path]:
        root = analysis.root
        sources: list[Path] = []
        rules = root / ".windsurfrules"
        if rules.is_file():
            sources.append(rules)
        windsurf_dir = root / ".windsurf"
        if windsurf_dir.is_dir():
            sources.extend(sorted(windsurf_dir.rglob("*.md")))
            sources.extend(sorted(windsurf_dir.rglob("*.mdc")))
        elif windsurf_dir.is_file():
            sources.append(windsurf_dir)
        return dedupe_paths(sources)
