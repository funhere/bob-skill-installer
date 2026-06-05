"""Security scanning of the *source* tree before anything is installed."""

from __future__ import annotations

from bob_skill_installer.security.scanner import scan_source

__all__ = ["scan_source"]
