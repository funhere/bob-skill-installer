"""Converter for Cursor rules (.mdc / .cursorrules / .cursor/rules)."""

from __future__ import annotations

from pathlib import Path

from bob_skill_installer.converters.base import BaseConverter, dedupe_paths
from bob_skill_installer.models import RepoAnalysis, SkillFormat


class CursorConverter(BaseConverter):
    source_format = SkillFormat.CURSOR

    def primary_sources(self, analysis: RepoAnalysis) -> list[Path]:
        root = analysis.root
        sources: list[Path] = []
        legacy = root / ".cursorrules"
        if legacy.is_file():
            sources.append(legacy)
        sources.extend(sorted(root.glob(".cursor/rules/**/*.mdc")))
        sources.extend(sorted(root.glob(".cursor/rules/**/*.md")))
        sources.extend(sorted(p for p in root.rglob("*.mdc") if ".cursor" not in p.parts))
        return dedupe_paths(sources)
