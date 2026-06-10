"""Security scanning of the *source* tree before anything is installed."""

from __future__ import annotations

from bob_skill_installer.security.scanner import is_sensitive_path, scan_source

__all__ = ["is_sensitive_path", "scan_source"]
