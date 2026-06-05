"""Integration tests for the Typer CLI, offline via a patched fetcher."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bob_skill_installer import __version__
from bob_skill_installer.cli import app

pytestmark = pytest.mark.integration

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_no_args_shows_help() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "install-skill" in result.stdout.lower() or "Usage" in result.stdout


def test_project_install_success(
    tmp_path: Path,
    repo_factory: Callable[[str], Path],
    patch_fetcher: Callable[[Path], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    patch_fetcher(repo_factory("claude"))
    result = runner.invoke(app, ["https://github.com/org/react", "--json"])
    assert result.exit_code == 0
    assert "SUCCESS" in result.stdout
    assert (tmp_path / ".bob" / "skills" / "react-architect" / "SKILL.md").is_file()


def test_rejected_returns_exit_8(
    tmp_path: Path,
    repo_factory: Callable[[str], Path],
    patch_fetcher: Callable[[Path], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    patch_fetcher(repo_factory("malicious"))
    result = runner.invoke(app, ["https://github.com/org/evil", "--json"])
    assert result.exit_code == 8
    assert "REJECTED" in result.stdout


def test_conflicting_scopes_error(monkeypatch: pytest.MonkeyPatch) -> None:
    result = runner.invoke(app, ["https://github.com/org/x", "--global", "--project"])
    assert result.exit_code == 2


def test_invalid_url_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    # parse_source fails before any fetch; InvalidSourceError -> exit 2.
    result = runner.invoke(app, ["not-a-valid-url"])
    assert result.exit_code == 2


def test_dry_run_writes_nothing(
    tmp_path: Path,
    repo_factory: Callable[[str], Path],
    patch_fetcher: Callable[[Path], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    patch_fetcher(repo_factory("generic"))
    result = runner.invoke(app, ["https://github.com/org/prompts", "--dry-run", "--json"])
    assert result.exit_code == 0
    assert not (tmp_path / ".bob" / "skills" / "prompts").exists()


def test_name_override_via_cli(
    tmp_path: Path,
    repo_factory: Callable[[str], Path],
    patch_fetcher: Callable[[Path], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    patch_fetcher(repo_factory("generic"))
    result = runner.invoke(
        app, ["https://github.com/org/x", "--name", "Custom Name", "--json"]
    )
    assert result.exit_code == 0
    assert (tmp_path / ".bob" / "skills" / "custom-name" / "SKILL.md").is_file()
