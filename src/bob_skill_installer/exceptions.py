"""Centralized exception hierarchy.

Every failure mode the installer can hit is a subclass of :class:`InstallerError`
so callers (the CLI, tests, embedding code) can catch one type and still tell
*which* stage failed via ``isinstance`` checks. Each carries a stable
``exit_code`` used by the CLI.
"""

from __future__ import annotations


class InstallerError(Exception):
    """Base class for all installer failures."""

    exit_code: int = 1


class InvalidSourceError(InstallerError):
    """The supplied source URL could not be parsed into a known source type."""

    exit_code = 2


class FetchError(InstallerError):
    """Cloning a repository or downloading a ZIP failed."""

    exit_code = 3


class AnalysisError(InstallerError):
    """The fetched tree could not be analyzed (empty, unreadable, etc.)."""

    exit_code = 4


class FormatDetectionError(InstallerError):
    """No supported source skill format could be recognized."""

    exit_code = 5


class ConversionError(InstallerError):
    """Converting the source format into a Bob skill failed."""

    exit_code = 6


class ValidationFailedError(InstallerError):
    """The generated Bob skill failed structural/metadata validation."""

    exit_code = 7


class SecurityRejectedError(InstallerError):
    """A blocking security finding prevented installation."""

    exit_code = 8


class InstallError(InstallerError):
    """Writing the skill to its install target failed."""

    exit_code = 9
