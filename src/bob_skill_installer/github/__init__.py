"""Source acquisition: parse a URL and fetch its bytes onto disk."""

from __future__ import annotations

from bob_skill_installer.github.fetcher import SourceFetcher
from bob_skill_installer.github.url_parser import parse_source

__all__ = ["SourceFetcher", "parse_source"]
