"""Integration tests: the full pipeline, offline via a patched fetcher."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from bob_skill_installer.installer import PipelineOptions, run_install
from bob_skill_installer.models import InstallScope, InstallStatus, SkillFormat

pytestmark = pytest.mark.integration


def _opts(tmp_path: Path, url: str = "https://github.com/org/sample", **kw: object) -> PipelineOptions:
    return PipelineOptions(source_url=url, project_root=tmp_path, **kw)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("kind", "fmt"),
    [
        ("claude", SkillFormat.CLAUDE),
        ("cursor", SkillFormat.CURSOR),
        ("generic", SkillFormat.GENERIC),
        ("openai", SkillFormat.OPENAI),
    ],
)
def test_install_each_format(
    tmp_path: Path,
    repo_factory: Callable[[str], Path],
    patch_fetcher: Callable[[Path], None],
    kind: str,
    fmt: SkillFormat,
) -> None:
    patch_fetcher(repo_factory(kind))
    report = run_install(_opts(tmp_path))
    assert report.status in (InstallStatus.SUCCESS, InstallStatus.SUCCESS_WITH_WARNINGS)
    assert report.converted_from is fmt
    installed = Path(report.target)
    assert (installed / "SKILL.md").is_file()
    assert installed.parent == tmp_path / ".bob" / "skills"


def test_malicious_repo_is_rejected(
    tmp_path: Path,
    repo_factory: Callable[[str], Path],
    patch_fetcher: Callable[[Path], None],
) -> None:
    patch_fetcher(repo_factory("malicious"))
    report = run_install(_opts(tmp_path))
    assert report.status is InstallStatus.REJECTED
    assert report.target is None
    assert report.warnings  # carries the blocking reasons
    # nothing was written
    assert not (tmp_path / ".bob" / "skills").exists()


def test_global_scope(
    tmp_path: Path,
    repo_factory: Callable[[str], Path],
    patch_fetcher: Callable[[Path], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    patch_fetcher(repo_factory("claude"))
    report = run_install(_opts(tmp_path, scope=InstallScope.GLOBAL))
    assert Path(report.target) == home / ".bob" / "skills" / "react-architect"


def test_overwrite_existing(
    tmp_path: Path,
    repo_factory: Callable[[str], Path],
    patch_fetcher: Callable[[Path], None],
) -> None:
    patch_fetcher(repo_factory("claude"))
    first = run_install(_opts(tmp_path))
    assert first.status in (InstallStatus.SUCCESS, InstallStatus.SUCCESS_WITH_WARNINGS)
    # Re-install without force -> InstallError surfaces from the installer.
    from bob_skill_installer.exceptions import InstallError

    with pytest.raises(InstallError):
        run_install(_opts(tmp_path))
    # With force it succeeds.
    again = run_install(_opts(tmp_path, overwrite=True))
    assert again.status in (InstallStatus.SUCCESS, InstallStatus.SUCCESS_WITH_WARNINGS)


def test_dry_run_does_not_write(
    tmp_path: Path,
    repo_factory: Callable[[str], Path],
    patch_fetcher: Callable[[Path], None],
) -> None:
    patch_fetcher(repo_factory("generic"))
    report = run_install(_opts(tmp_path, dry_run=True))
    assert report.status in (InstallStatus.SUCCESS, InstallStatus.SUCCESS_WITH_WARNINGS)
    assert not Path(report.target).exists()


def test_warnings_propagate_to_report(
    tmp_path: Path,
    patch_fetcher: Callable[[Path], None],
) -> None:
    # A repo containing a harmless script triggers the script-bundled warning.
    root = tmp_path / "src"
    root.mkdir()
    (root / "CLAUDE.md").write_text(
        "---\nname: t\ndescription: d\n---\n# T\n## Objective\nx\n"
    )
    (root / "helper.py").write_text("print('hi')\n")
    patch_fetcher(root)
    report = run_install(_opts(tmp_path))
    assert report.status is InstallStatus.SUCCESS_WITH_WARNINGS
    assert any("script" in w.lower() for w in report.warnings)


def test_secrets_copied_by_default_with_security_warning(
    tmp_path: Path,
    patch_fetcher: Callable[[Path], None],
) -> None:
    root = tmp_path / "src"
    root.mkdir()
    (root / "CLAUDE.md").write_text(
        "---\nname: t\ndescription: d\n---\n# T\n## Objective\nx\n"
    )
    (root / ".env").write_text("TOKEN=secret\n")
    patch_fetcher(root)
    report = run_install(_opts(tmp_path))
    installed = Path(report.target)
    assert (installed / ".env").is_file()  # full fidelity by default
    assert any(w.startswith("SECURITY:") for w in report.warnings)


def test_no_scripts_no_secrets_exclude(
    tmp_path: Path,
    patch_fetcher: Callable[[Path], None],
) -> None:
    root = tmp_path / "src"
    (root / "scripts").mkdir(parents=True)
    (root / "CLAUDE.md").write_text(
        "---\nname: t\ndescription: d\n---\n# T\n## Objective\nx\n"
    )
    (root / "scripts" / "run.sh").write_text("#!/bin/sh\necho hi\n")
    (root / ".env").write_text("TOKEN=secret\n")
    patch_fetcher(root)
    report = run_install(_opts(tmp_path, exclude_scripts=True, exclude_secrets=True))
    installed = Path(report.target)
    assert not (installed / ".env").exists()
    assert not (installed / "scripts" / "run.sh").exists()
