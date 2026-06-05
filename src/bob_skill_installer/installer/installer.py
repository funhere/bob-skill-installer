"""Write a validated :class:`BobSkill` to its install target.

Targets follow the spec:
  * project scope -> ``<project_root>/.bob/skills/<name>``
  * global scope  -> ``~/.bob/skills/<name>``

Writes are staged in a sibling temp directory and swapped into place so a failed
write never leaves a half-installed skill. An existing skill is only replaced
when ``overwrite`` or ``upgrade`` is set; ``upgrade`` keeps a one-shot ``.bak``
of the previous version.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from bob_skill_installer.exceptions import InstallError
from bob_skill_installer.logging_config import get_logger
from bob_skill_installer.models import BobSkill, InstallScope

_log = get_logger("installer")

# Standard Bob skill scaffold directories created for every install.
_SCAFFOLD_DIRS = ("docs", "examples", "templates", "assets")


def resolve_target(scope: InstallScope, name: str, project_root: Path | None = None) -> Path:
    """Resolve the absolute install directory for ``name`` under ``scope``."""
    if scope is InstallScope.GLOBAL:
        base = Path.home() / ".bob" / "skills"
    else:
        root = project_root or Path.cwd()
        base = root / ".bob" / "skills"
    return base / name


class SkillInstaller:
    """Writes skills onto disk with atomic, reversible semantics."""

    def install(
        self,
        skill: BobSkill,
        scope: InstallScope,
        *,
        project_root: Path | None = None,
        overwrite: bool = False,
        upgrade: bool = False,
        dry_run: bool = False,
    ) -> Path:
        target = resolve_target(scope, skill.name, project_root)

        if target.exists() and not (overwrite or upgrade):
            raise InstallError(
                f"Skill already installed at {target}. "
                "Re-run with --force to overwrite or --upgrade to replace it."
            )

        if dry_run:
            _log.info("[dry-run] Would install '%s' to %s", skill.name, target)
            return target

        target.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".bob-stage-", dir=target.parent))
        try:
            self._materialize(skill, staging)
            self._swap_into_place(staging, target, upgrade=upgrade)
        except Exception as exc:
            shutil.rmtree(staging, ignore_errors=True)
            if isinstance(exc, InstallError):
                raise
            raise InstallError(f"Failed to install '{skill.name}': {exc}") from exc

        _log.info("Installed [bold green]%s[/bold green] -> %s", skill.name, target)
        return target

    # -- internals ---------------------------------------------------------- #

    def _materialize(self, skill: BobSkill, staging: Path) -> None:
        for sub in _SCAFFOLD_DIRS:
            (staging / sub).mkdir(parents=True, exist_ok=True)

        (staging / "SKILL.md").write_text(skill.skill_md, encoding="utf-8")

        for gen in skill.files:
            dest = (staging / gen.relative_path).resolve()
            if not str(dest).startswith(str(staging.resolve())):
                raise InstallError(f"Generated file escapes skill root: {gen.relative_path}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(gen.content, encoding="utf-8")

        # Keep empty scaffold dirs present in version control / archives.
        for sub in _SCAFFOLD_DIRS:
            d = staging / sub
            if not any(d.iterdir()):
                (d / ".gitkeep").write_text("", encoding="utf-8")

    def _swap_into_place(self, staging: Path, target: Path, *, upgrade: bool) -> None:
        backup: Path | None = None
        if target.exists():
            if upgrade:
                backup = target.with_name(target.name + ".bak")
                if backup.exists():
                    shutil.rmtree(backup)
                target.rename(backup)
            else:  # overwrite
                shutil.rmtree(target)
        try:
            staging.rename(target)
        except OSError:
            # Cross-device or non-atomic FS: fall back to a copy.
            shutil.copytree(staging, target)
            shutil.rmtree(staging, ignore_errors=True)
        if backup is not None:
            shutil.rmtree(backup, ignore_errors=True)
