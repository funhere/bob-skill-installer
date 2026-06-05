"""Fallback converter for generic prompt repositories (README + prompts/)."""

from __future__ import annotations

from pathlib import Path

from bob_skill_installer.converters.base import BaseConverter, dedupe_paths
from bob_skill_installer.models import RepoAnalysis, SkillFormat

_README_NAMES = ("README.md", "readme.md", "Readme.md")


class GenericConverter(BaseConverter):
    source_format = SkillFormat.GENERIC

    def primary_sources(self, analysis: RepoAnalysis) -> list[Path]:
        root = analysis.root
        sources: list[Path] = []
        if analysis.readme is not None:
            sources.append(analysis.readme)
        else:
            for name in _README_NAMES:
                candidate = root / name
                if candidate.is_file():
                    sources.append(candidate)
                    break
        prompts = root / "prompts"
        if prompts.is_dir():
            sources.extend(sorted(prompts.rglob("*.md")))
            sources.extend(sorted(prompts.rglob("*.txt")))
        # Absolute last resort: any markdown at all so the pipeline still yields
        # a skill rather than failing on an otherwise-unstructured repo.
        if not sources and analysis.markdown_files:
            sources.append(analysis.markdown_files[0])
        return dedupe_paths(sources)
