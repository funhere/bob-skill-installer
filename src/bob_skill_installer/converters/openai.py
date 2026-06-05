"""Converter for OpenAI GPT instructions (instructions.md / prompt.md)."""

from __future__ import annotations

from pathlib import Path

from bob_skill_installer.converters.base import BaseConverter
from bob_skill_installer.models import RepoAnalysis, SkillFormat


class OpenAIConverter(BaseConverter):
    source_format = SkillFormat.OPENAI

    def primary_sources(self, analysis: RepoAnalysis) -> list[Path]:
        root = analysis.root
        sources: list[Path] = []
        for name in ("instructions.md", "prompt.md", "system_prompt.md", "system.md"):
            candidate = root / name
            if candidate.is_file():
                sources.append(candidate)
        return sources
