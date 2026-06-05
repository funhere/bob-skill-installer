"""bob-skill-installer.

Download, analyze, convert, validate, and install third-party open-source AI
skills into IBM Bob. The public surface is intentionally small; orchestration
lives in :mod:`bob_skill_installer.installer.pipeline` and the Typer CLI in
:mod:`bob_skill_installer.cli.main`.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
