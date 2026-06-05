"""Install generated skills and orchestrate the end-to-end pipeline."""

from __future__ import annotations

from bob_skill_installer.installer.installer import SkillInstaller, resolve_target
from bob_skill_installer.installer.pipeline import PipelineOptions, run_install

__all__ = ["PipelineOptions", "SkillInstaller", "resolve_target", "run_install"]
