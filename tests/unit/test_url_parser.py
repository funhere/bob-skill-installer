"""Unit tests for source URL parsing."""

from __future__ import annotations

import pytest

from bob_skill_installer.exceptions import InvalidSourceError
from bob_skill_installer.github import parse_source
from bob_skill_installer.models import SourceType


def test_plain_github_repo() -> None:
    p = parse_source("https://github.com/org/repo")
    assert p.source_type is SourceType.GITHUB
    assert p.owner == "org"
    assert p.repo == "repo"
    assert p.clone_url == "https://github.com/org/repo.git"
    assert p.ref is None and p.subpath is None
    assert not p.is_zip


def test_github_strips_git_suffix() -> None:
    p = parse_source("https://github.com/org/repo.git")
    assert p.repo == "repo"
    assert p.source_type is SourceType.GITHUB


def test_github_tree_with_subpath() -> None:
    p = parse_source("https://github.com/org/repo/tree/main/skills/writer")
    assert p.ref == "main"
    assert p.subpath == "skills/writer"


def test_github_blob_ref() -> None:
    p = parse_source("https://github.com/org/repo/blob/dev/path/to/file")
    assert p.ref == "dev"
    assert p.subpath == "path/to/file"


def test_github_release_zip_is_zip() -> None:
    url = "https://github.com/org/repo/releases/download/v1.0/skill.zip"
    p = parse_source(url)
    assert p.source_type is SourceType.ZIP
    assert p.zip_url == url
    assert p.is_zip


def test_gitlab_tree_with_dash_segment() -> None:
    p = parse_source("https://gitlab.com/org/repo/-/tree/main/sub")
    assert p.source_type is SourceType.GITLAB
    assert p.ref == "main"
    assert p.subpath == "sub"
    assert p.clone_url == "https://gitlab.com/org/repo.git"


def test_direct_zip_url() -> None:
    p = parse_source("https://example.com/downloads/skill.zip")
    assert p.source_type is SourceType.ZIP
    assert p.zip_url.endswith("skill.zip")


def test_generic_git_https() -> None:
    p = parse_source("https://git.example.com/team/skill.git")
    assert p.source_type is SourceType.GIT
    assert p.clone_url.endswith("skill.git")


def test_generic_git_scheme() -> None:
    p = parse_source("git+https://host/team/skill")
    assert p.source_type is SourceType.GIT


def test_ssh_style_git() -> None:
    p = parse_source("git@github.com:org/repo.git")
    assert p.source_type is SourceType.GIT
    assert p.clone_url == "git@github.com:org/repo.git"


def test_slug_property() -> None:
    assert parse_source("https://github.com/org/cool-skill").slug == "cool-skill"
    assert parse_source("https://example.com/x/my-skill.zip").slug == "my-skill"


def test_local_directory(tmp_path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "skill").mkdir()
    p = parse_source(str(tmp_path / "skill"))
    assert p.source_type is SourceType.LOCAL
    assert p.local_path.endswith("skill")
    assert p.slug == "skill"


@pytest.mark.parametrize("bad", ["", "   ", "ftp://example.com/x", "not a url", "https://"])
def test_invalid_sources_raise(bad: str) -> None:
    with pytest.raises(InvalidSourceError):
        parse_source(bad)


def test_github_missing_repo_raises() -> None:
    with pytest.raises(InvalidSourceError):
        parse_source("https://github.com/justowner")
