"""Converter for RooCode modes (.roomodes / .roo)."""

from __future__ import annotations

from pathlib import Path

from bob_skill_installer.converters.base import BaseConverter, dedupe_paths
from bob_skill_installer.models import RepoAnalysis, SkillFormat


class RooCodeConverter(BaseConverter):
    source_format = SkillFormat.ROOCODE

    def primary_sources(self, analysis: RepoAnalysis) -> list[Path]:
        root = analysis.root
        sources: list[Path] = []
        # .roomodes is typically YAML/JSON describing modes; treat as text input.
        modes = root / ".roomodes"
        if modes.is_file():
            sources.append(modes)
        roo_dir = root / ".roo"
        if roo_dir.is_dir():
            for ext in ("*.md", "*.markdown", "*.txt", "*.yaml", "*.yml"):
                sources.extend(sorted(roo_dir.rglob(ext)))
        elif roo_dir.is_file():
            sources.append(roo_dir)
        return dedupe_paths(sources)
