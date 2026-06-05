"""Fetch a :class:`ParsedSource` onto local disk.

The fetcher is the *only* network-touching component. It supports shallow git
clones (via GitPython) and ZIP downloads (via httpx), extracts into a managed
temp directory, and honors the subpath of ``/tree/<ref>/<sub>`` URLs by
returning the nested directory as the effective root.

Security posture: ZIP extraction is path-traversal-safe (entries escaping the
destination are refused), downloads are size-capped, and nothing is executed.
"""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path
from types import TracebackType

import httpx

from bob_skill_installer.exceptions import FetchError
from bob_skill_installer.logging_config import get_logger
from bob_skill_installer.models import ParsedSource, SourceType

_log = get_logger("github.fetcher")

#: Hard ceiling on downloaded/extracted bytes to blunt zip-bomb style payloads.
MAX_DOWNLOAD_BYTES = 512 * 1024 * 1024


class SourceFetcher:
    """Context manager that materializes a source tree and cleans it up.

    Usage::

        with SourceFetcher(parsed) as root:
            ...  # `root` is a Path to the working tree
    """

    def __init__(self, source: ParsedSource, *, depth: int = 1) -> None:
        self._source = source
        self._depth = depth
        self._tmp: Path | None = None

    def __enter__(self) -> Path:
        return self.fetch()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.cleanup()

    # -- public ------------------------------------------------------------- #

    def fetch(self) -> Path:
        """Materialize the source and return the effective root directory."""
        self._tmp = Path(tempfile.mkdtemp(prefix="bob-skill-"))
        try:
            if self._source.source_type is SourceType.LOCAL:
                root = self._fetch_local()
            elif self._source.is_zip:
                root = self._fetch_zip()
            else:
                root = self._fetch_git()
        except FetchError:
            self.cleanup()
            raise
        except Exception as exc:  # pragma: no cover - defensive wrap
            self.cleanup()
            raise FetchError(str(exc)) from exc
        return self._apply_subpath(root)

    def cleanup(self) -> None:
        if self._tmp and self._tmp.exists():
            shutil.rmtree(self._tmp, ignore_errors=True)
        self._tmp = None

    # -- local -------------------------------------------------------------- #

    def _fetch_local(self) -> Path:
        local = self._source.local_path
        if not local:
            raise FetchError("No local path resolved for local source.")
        src = Path(local)
        if not src.is_dir():
            raise FetchError(f"Local source is not a directory: {src}")
        assert self._tmp is not None
        dest = self._tmp / "repo"
        _log.info("Copying local source [bold]%s[/bold]", src)
        # Skip a top-level .git so we copy a working tree, not history.
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns(".git"))
        return dest

    # -- git ---------------------------------------------------------------- #

    def _fetch_git(self) -> Path:
        from git import GitCommandError, Repo  # lazy: keep import cost off the CLI startup

        clone_url = self._source.clone_url
        if not clone_url:
            raise FetchError("No clone URL resolved for git source.")
        assert self._tmp is not None
        dest = self._tmp / "repo"
        _log.info("Cloning [bold]%s[/bold] (depth=%d)", clone_url, self._depth)
        try:
            repo = Repo.clone_from(clone_url, dest, depth=self._depth)
            if self._source.ref:
                self._checkout_ref(repo, self._source.ref, clone_url)
        except GitCommandError as exc:
            raise FetchError(f"git clone failed for {clone_url}: {exc}") from exc
        return dest

    def _checkout_ref(self, repo: object, ref: str, clone_url: str) -> None:
        from git import GitCommandError

        try:
            # A shallow clone may not contain the ref; fetch it explicitly.
            repo.git.fetch("origin", ref, depth=self._depth)  # type: ignore[attr-defined]
            repo.git.checkout(ref)  # type: ignore[attr-defined]
        except GitCommandError as exc:
            raise FetchError(f"Could not check out ref {ref!r} from {clone_url}: {exc}") from exc

    # -- zip ---------------------------------------------------------------- #

    def _fetch_zip(self) -> Path:
        url = self._source.zip_url
        if not url:
            raise FetchError("No ZIP URL resolved for zip source.")
        assert self._tmp is not None
        archive = self._tmp / "download.zip"
        _log.info("Downloading ZIP [bold]%s[/bold]", url)
        self._download(url, archive)
        extract_dir = self._tmp / "extracted"
        extract_dir.mkdir()
        _safe_extract_zip(archive, extract_dir)
        return _collapse_single_dir(extract_dir)

    def _download(self, url: str, dest: Path) -> None:
        written = 0
        try:
            with httpx.stream("GET", url, follow_redirects=True, timeout=60.0) as resp:
                resp.raise_for_status()
                with dest.open("wb") as fh:
                    for chunk in resp.iter_bytes():
                        written += len(chunk)
                        if written > MAX_DOWNLOAD_BYTES:
                            raise FetchError(
                                f"Download exceeded {MAX_DOWNLOAD_BYTES} bytes; refusing."
                            )
                        fh.write(chunk)
        except httpx.HTTPError as exc:
            raise FetchError(f"Failed to download {url}: {exc}") from exc

    # -- subpath ------------------------------------------------------------ #

    def _apply_subpath(self, root: Path) -> Path:
        sub = self._source.subpath
        if not sub:
            return root
        candidate = (root / sub).resolve()
        if not str(candidate).startswith(str(root.resolve())):
            raise FetchError(f"Subpath {sub!r} escapes the repository root.")
        if not candidate.is_dir():
            raise FetchError(f"Subpath {sub!r} is not a directory in the source.")
        return candidate


# --------------------------------------------------------------------------- #
# ZIP helpers (module-level so they are unit-testable without the network)
# --------------------------------------------------------------------------- #


def _safe_extract_zip(archive: Path, dest: Path) -> None:
    """Extract ``archive`` into ``dest`` refusing path-traversal entries."""
    dest_root = dest.resolve()
    total = 0
    try:
        with zipfile.ZipFile(archive) as zf:
            for member in zf.infolist():
                target = (dest / member.filename).resolve()
                if not str(target).startswith(str(dest_root)):
                    raise FetchError(f"Unsafe path in ZIP: {member.filename!r}")
                total += member.file_size
                if total > MAX_DOWNLOAD_BYTES:
                    raise FetchError("ZIP expands beyond the size cap; refusing.")
            zf.extractall(dest)
    except zipfile.BadZipFile as exc:
        raise FetchError(f"Not a valid ZIP archive: {exc}") from exc


def _collapse_single_dir(extract_dir: Path) -> Path:
    """GitHub/GitLab ZIPs wrap everything in one top folder; unwrap it."""
    entries = [p for p in extract_dir.iterdir() if not p.name.startswith("__MACOSX")]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return extract_dir
