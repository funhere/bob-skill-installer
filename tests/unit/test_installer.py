"""Unit tests for the on-disk installer."""

from __future__ import annotations

from pathlib import Path

import pytest

from bob_skill_installer.exceptions import InstallError
from bob_skill_installer.installer import SkillInstaller, resolve_target
from bob_skill_installer.models import (
    BobSkill,
    GeneratedFile,
    InstallScope,
    SkillFormat,
    SkillMetadata,
)


def _skill(name: str = "demo", version: str = "0.1.0") -> BobSkill:
    meta = SkillMetadata(
        name=name,
        description="A demo.",
        version=version,
        source="https://github.com/org/demo",
        converted_from=SkillFormat.CLAUDE,
    )
    md = f"---\nname: {name}\n---\n# {name}\n"
    return BobSkill(
        metadata=meta,
        skill_md=md,
        files=[GeneratedFile(relative_path=Path("docs/README.md"), content="hi")],
    )


def test_resolve_target_project(tmp_path: Path) -> None:
    target = resolve_target(InstallScope.PROJECT, "demo", project_root=tmp_path)
    assert target == tmp_path / ".bob" / "skills" / "demo"


def test_resolve_target_global() -> None:
    target = resolve_target(InstallScope.GLOBAL, "demo")
    assert target == Path.home() / ".bob" / "skills" / "demo"


def test_project_install_writes_scaffold(tmp_path: Path) -> None:
    target = SkillInstaller().install(_skill(), InstallScope.PROJECT, project_root=tmp_path)
    assert (target / "SKILL.md").is_file()
    for sub in ("docs", "examples", "templates", "assets"):
        assert (target / sub).is_dir()
    assert (target / "docs" / "README.md").read_text() == "hi"
    # empty scaffold dirs get a .gitkeep
    assert (target / "examples" / ".gitkeep").is_file()


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    target = SkillInstaller().install(
        _skill(), InstallScope.PROJECT, project_root=tmp_path, dry_run=True
    )
    assert not target.exists()


def test_existing_without_force_raises(tmp_path: Path) -> None:
    inst = SkillInstaller()
    inst.install(_skill(), InstallScope.PROJECT, project_root=tmp_path)
    with pytest.raises(InstallError):
        inst.install(_skill(), InstallScope.PROJECT, project_root=tmp_path)


def test_overwrite_replaces(tmp_path: Path) -> None:
    inst = SkillInstaller()
    inst.install(_skill(version="0.1.0"), InstallScope.PROJECT, project_root=tmp_path)
    target = inst.install(
        _skill(version="0.2.0"), InstallScope.PROJECT, project_root=tmp_path, overwrite=True
    )
    assert "name: demo" in (target / "SKILL.md").read_text()


def test_upgrade_replaces_and_cleans_backup(tmp_path: Path) -> None:
    inst = SkillInstaller()
    inst.install(_skill(version="0.1.0"), InstallScope.PROJECT, project_root=tmp_path)
    target = inst.install(
        _skill(version="0.2.0"), InstallScope.PROJECT, project_root=tmp_path, upgrade=True
    )
    assert target.exists()
    assert not target.with_name("demo.bak").exists()
