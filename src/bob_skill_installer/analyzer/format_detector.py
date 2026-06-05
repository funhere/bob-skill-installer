"""Classify a fetched tree into a known source skill format.

Detection is evidence-based and additive: each marker contributes a score and a
human-readable reason, so the install report can explain *why* a format was
chosen. ``GENERIC`` carries a small baseline whenever a README exists so a bare
prompt repository still converts instead of failing as ``UNKNOWN``.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from bob_skill_installer.models import FormatDetection, SkillFormat

# Directories we never descend into when probing for markers.
_IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}


def _iter_dirs(root: Path) -> list[str]:
    return [p.name for p in root.iterdir() if p.is_dir()]


def _has_ext(root: Path, ext: str) -> bool:
    return any(p.suffix == ext for p in root.rglob(f"*{ext}") if _not_ignored(p, root))


def _not_ignored(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    return not any(part in _IGNORE_DIRS for part in rel.parts)


def _exists(root: Path, name: str) -> bool:
    return (root / name).exists()


def detect_formats(root: Path) -> list[FormatDetection]:
    """Return scored format guesses, highest score first."""
    scores: dict[SkillFormat, int] = defaultdict(int)
    evidence: dict[SkillFormat, list[str]] = defaultdict(list)

    def add(fmt: SkillFormat, score: int, reason: str) -> None:
        scores[fmt] += score
        evidence[fmt].append(reason)

    top_dirs = set(_iter_dirs(root))

    # -- Claude -------------------------------------------------------------- #
    if _exists(root, "CLAUDE.md"):
        add(SkillFormat.CLAUDE, 4, "CLAUDE.md present")
    if ".claude" in top_dirs or (root / ".claude" / "skills").exists():
        add(SkillFormat.CLAUDE, 4, ".claude/ directory present")
    if (root / "skills").is_dir() and any(root.glob("skills/**/SKILL.md")):
        add(SkillFormat.CLAUDE, 3, "skills/ tree with SKILL.md")
    if _exists(root, "SKILL.md"):
        add(SkillFormat.CLAUDE, 2, "top-level SKILL.md present")

    # -- Cursor -------------------------------------------------------------- #
    if (root / ".cursor" / "rules").exists():
        add(SkillFormat.CURSOR, 4, ".cursor/rules present")
    if _exists(root, ".cursorrules"):
        add(SkillFormat.CURSOR, 3, ".cursorrules present")
    if _has_ext(root, ".mdc"):
        add(SkillFormat.CURSOR, 4, ".mdc rule files present")

    # -- Windsurf ------------------------------------------------------------ #
    if ".windsurf" in top_dirs or _exists(root, ".windsurf"):
        add(SkillFormat.WINDSURF, 4, ".windsurf present")
    if _exists(root, ".windsurfrules"):
        add(SkillFormat.WINDSURF, 3, ".windsurfrules present")

    # -- Cline --------------------------------------------------------------- #
    if _exists(root, ".clinerules") or (root / ".clinerules").is_dir():
        add(SkillFormat.CLINE, 4, ".clinerules present")
    if ".cline" in top_dirs or _exists(root, ".cline"):
        add(SkillFormat.CLINE, 3, ".cline present")

    # -- RooCode ------------------------------------------------------------- #
    if _exists(root, ".roomodes"):
        add(SkillFormat.ROOCODE, 4, ".roomodes present")
    if ".roo" in top_dirs or _exists(root, ".roo"):
        add(SkillFormat.ROOCODE, 3, ".roo present")

    # -- OpenAI / GPT -------------------------------------------------------- #
    if _exists(root, "instructions.md"):
        add(SkillFormat.OPENAI, 3, "instructions.md present")
    if _exists(root, "prompt.md"):
        add(SkillFormat.OPENAI, 3, "prompt.md present")
    if _exists(root, "system_prompt.md"):
        add(SkillFormat.OPENAI, 2, "system_prompt.md present")

    # -- Generic prompt repo (fallback baseline) ----------------------------- #
    if (root / "prompts").is_dir():
        add(SkillFormat.GENERIC, 3, "prompts/ directory present")
    if _exists(root, "README.md") or _exists(root, "readme.md"):
        add(SkillFormat.GENERIC, 1, "README.md present (generic baseline)")

    detections = [
        FormatDetection(fmt=fmt, score=score, evidence=evidence[fmt])
        for fmt, score in scores.items()
    ]
    detections.sort(key=lambda d: d.score, reverse=True)
    return detections
