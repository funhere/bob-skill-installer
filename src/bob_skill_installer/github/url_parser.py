"""Parse user-supplied source URLs into a normalized :class:`ParsedSource`.

Priority order (per spec): GitHub > GitLab > generic Git > direct ZIP. The
parser is pure and network-free so it is trivially unit-testable; the fetcher is
the only piece that touches the network.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from bob_skill_installer.exceptions import InvalidSourceError
from bob_skill_installer.models import ParsedSource, SourceType

_GITHUB_HOSTS = {"github.com", "www.github.com"}
_GITLAB_HOSTS = {"gitlab.com", "www.gitlab.com"}


def _strip_git_suffix(value: str) -> str:
    return value[:-4] if value.endswith(".git") else value


def _parse_forge(url: str, host: str, source_type: SourceType) -> ParsedSource:
    """Parse a github.com / gitlab.com style URL.

    Handles the three documented shapes:
      * ``/owner/repo``
      * ``/owner/repo/tree/<ref>/<subpath...>``  (also ``/blob/`` and GitLab ``/-/tree/``)
      * ``/owner/repo/releases/download/<tag>/<asset>.zip`` -> treated as a ZIP
    """
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        raise InvalidSourceError(f"Could not find owner/repo in URL: {url!r}")

    owner, repo = parts[0], _strip_git_suffix(parts[1])
    rest = parts[2:]

    # Release asset -> ZIP path wins regardless of forge.
    if rest and rest[0] == "releases" and url.endswith(".zip"):
        return ParsedSource(
            raw=url,
            source_type=SourceType.ZIP,
            host=host,
            owner=owner,
            repo=repo,
            zip_url=url,
        )

    ref: str | None = None
    subpath: str | None = None
    # GitLab nests tree/blob under a "-" segment: /owner/repo/-/tree/<ref>/<path>
    if rest and rest[0] == "-":
        rest = rest[1:]
    if rest and rest[0] in ("tree", "blob"):
        if len(rest) >= 2:
            ref = rest[1]
        if len(rest) >= 3:
            subpath = "/".join(rest[2:])

    clone_url = f"https://{host}/{owner}/{repo}.git"
    return ParsedSource(
        raw=url,
        source_type=source_type,
        clone_url=clone_url,
        host=host,
        owner=owner,
        repo=repo,
        ref=ref,
        subpath=subpath,
    )


def parse_source(url: str) -> ParsedSource:
    """Classify ``url`` and return a :class:`ParsedSource`.

    Raises:
        InvalidSourceError: if the URL is empty or uses an unsupported scheme.
    """
    if not url or not url.strip():
        raise InvalidSourceError("Source URL is empty.")
    url = url.strip()

    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    host = (parsed.netloc or "").lower()

    # Direct ZIP download (any host) takes the ZIP path.
    if url.lower().endswith(".zip"):
        return ParsedSource(raw=url, source_type=SourceType.ZIP, host=host or None, zip_url=url)

    if host in _GITHUB_HOSTS:
        return _parse_forge(url, "github.com", SourceType.GITHUB)
    if host in _GITLAB_HOSTS:
        return _parse_forge(url, "gitlab.com", SourceType.GITLAB)

    # Generic git: explicit .git, git+ scheme, or ssh-style git@host:owner/repo.
    if scheme in ("http", "https") and url.endswith(".git"):
        return ParsedSource(raw=url, source_type=SourceType.GIT, host=host or None, clone_url=url)
    if scheme.startswith("git"):
        return ParsedSource(raw=url, source_type=SourceType.GIT, host=host or None, clone_url=url)
    if url.startswith("git@") and ":" in url:
        return ParsedSource(raw=url, source_type=SourceType.GIT, clone_url=url)

    # Local filesystem directory (convenient for offline examples and testing).
    if not scheme:
        candidate = Path(url).expanduser()
        if candidate.is_dir():
            return ParsedSource(
                raw=url, source_type=SourceType.LOCAL, local_path=str(candidate.resolve())
            )

    raise InvalidSourceError(
        f"Unsupported source: {url!r}. Expected a GitHub/GitLab/git URL, a .zip link, "
        "or a local directory path."
    )
