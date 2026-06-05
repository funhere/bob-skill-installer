"""Unit tests for the source fetcher (no real network)."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

import pytest

from bob_skill_installer.exceptions import FetchError
from bob_skill_installer.github.fetcher import (
    SourceFetcher,
    _collapse_single_dir,
    _safe_extract_zip,
)
from bob_skill_installer.models import ParsedSource, SourceType


def test_safe_extract_normal_zip(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("hello")
    archive = tmp_path / "a.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.write(src / "a.txt", "a.txt")
    dest = tmp_path / "out"
    dest.mkdir()
    _safe_extract_zip(archive, dest)
    assert (dest / "a.txt").read_text() == "hello"


def test_safe_extract_rejects_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../evil.txt", "pwn")
    dest = tmp_path / "out"
    dest.mkdir()
    with pytest.raises(FetchError):
        _safe_extract_zip(archive, dest)


def test_safe_extract_bad_zip(tmp_path: Path) -> None:
    archive = tmp_path / "bad.zip"
    archive.write_text("not a zip")
    dest = tmp_path / "out"
    dest.mkdir()
    with pytest.raises(FetchError):
        _safe_extract_zip(archive, dest)


def test_collapse_single_dir(tmp_path: Path) -> None:
    extract = tmp_path / "extract"
    inner = extract / "repo-main"
    inner.mkdir(parents=True)
    (inner / "f.txt").write_text("x")
    assert _collapse_single_dir(extract) == inner


def test_collapse_keeps_multi_entry(tmp_path: Path) -> None:
    extract = tmp_path / "extract"
    extract.mkdir()
    (extract / "a.txt").write_text("a")
    (extract / "b.txt").write_text("b")
    assert _collapse_single_dir(extract) == extract


def test_fetch_zip_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Build a github-style wrapped zip.
    src = tmp_path / "payload"
    (src / "repo-main").mkdir(parents=True)
    (src / "repo-main" / "CLAUDE.md").write_text("# skill")
    archive = tmp_path / "skill.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for p in src.rglob("*"):
            if p.is_file():
                zf.write(p, str(p.relative_to(src)))

    def fake_download(self: SourceFetcher, url: str, dest: Path) -> None:
        shutil.copy(archive, dest)

    monkeypatch.setattr(SourceFetcher, "_download", fake_download)
    source = ParsedSource(raw="x", source_type=SourceType.ZIP, zip_url="https://x/skill.zip")
    with SourceFetcher(source) as root:
        assert (root / "CLAUDE.md").read_text() == "# skill"
        captured = root
    # cleanup removed the temp tree
    assert not captured.exists()


def test_apply_subpath_ok(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "skills" / "writer").mkdir(parents=True)
    source = ParsedSource(
        raw="x", source_type=SourceType.GITHUB, subpath="skills/writer"
    )
    fetcher = SourceFetcher(source)
    assert fetcher._apply_subpath(root) == root / "skills" / "writer"


def test_apply_subpath_escape_rejected(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    source = ParsedSource(raw="x", source_type=SourceType.GITHUB, subpath="../escape")
    fetcher = SourceFetcher(source)
    with pytest.raises(FetchError):
        fetcher._apply_subpath(root)


def test_apply_subpath_missing_dir(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    source = ParsedSource(raw="x", source_type=SourceType.GITHUB, subpath="nope")
    fetcher = SourceFetcher(source)
    with pytest.raises(FetchError):
        fetcher._apply_subpath(root)


def test_zip_without_url_raises(tmp_path: Path) -> None:
    source = ParsedSource(raw="x", source_type=SourceType.ZIP)
    with pytest.raises(FetchError):
        SourceFetcher(source).fetch()


def test_git_without_clone_url_raises() -> None:
    source = ParsedSource(raw="x", source_type=SourceType.GIT)
    with pytest.raises(FetchError):
        SourceFetcher(source).fetch()


def test_fetch_local_copies_tree_without_git(tmp_path: Path) -> None:
    src = tmp_path / "skill"
    (src / ".git").mkdir(parents=True)
    (src / ".git" / "config").write_text("[core]\n")
    (src / "CLAUDE.md").write_text("# skill", encoding="utf-8")
    source = ParsedSource(
        raw=str(src), source_type=SourceType.LOCAL, local_path=str(src)
    )
    with SourceFetcher(source) as root:
        assert (root / "CLAUDE.md").read_text() == "# skill"
        assert not (root / ".git").exists()  # history excluded
        captured = root
    assert not captured.exists()


def test_fetch_local_missing_path_raises() -> None:
    source = ParsedSource(raw="x", source_type=SourceType.LOCAL)
    with pytest.raises(FetchError):
        SourceFetcher(source).fetch()


def test_fetch_git_success_with_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    import git

    calls: dict[str, bool] = {}

    class _FakeGit:
        def fetch(self, *_a: object, **_k: object) -> None:
            calls["fetch"] = True

        def checkout(self, *_a: object, **_k: object) -> None:
            calls["checkout"] = True

    class _FakeRepo:
        def __init__(self) -> None:
            self.git = _FakeGit()

    def fake_clone(url: str, dest: str, depth: int = 1) -> _FakeRepo:
        Path(dest).mkdir(parents=True)
        (Path(dest) / "CLAUDE.md").write_text("# skill", encoding="utf-8")
        return _FakeRepo()

    monkeypatch.setattr(git.Repo, "clone_from", staticmethod(fake_clone))
    source = ParsedSource(
        raw="x",
        source_type=SourceType.GITHUB,
        clone_url="https://github.com/o/r.git",
        ref="main",
    )
    with SourceFetcher(source) as root:
        assert (root / "CLAUDE.md").exists()
    assert calls.get("checkout")


def test_fetch_git_clone_failure_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import git

    def boom(url: str, dest: str, depth: int = 1) -> None:
        raise git.GitCommandError("clone", 128)

    monkeypatch.setattr(git.Repo, "clone_from", staticmethod(boom))
    source = ParsedSource(
        raw="x", source_type=SourceType.GIT, clone_url="https://x/r.git"
    )
    with pytest.raises(FetchError):
        SourceFetcher(source).fetch()


def test_fetch_git_checkout_failure_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import git

    class _FakeGit:
        def fetch(self, *_a: object, **_k: object) -> None:
            raise git.GitCommandError("fetch", 1)

        def checkout(self, *_a: object, **_k: object) -> None: ...

    class _FakeRepo:
        def __init__(self) -> None:
            self.git = _FakeGit()

    def fake_clone(url: str, dest: str, depth: int = 1) -> _FakeRepo:
        Path(dest).mkdir(parents=True)
        return _FakeRepo()

    monkeypatch.setattr(git.Repo, "clone_from", staticmethod(fake_clone))
    source = ParsedSource(
        raw="x", source_type=SourceType.GIT, clone_url="https://x/r.git", ref="nope"
    )
    with pytest.raises(FetchError):
        SourceFetcher(source).fetch()
