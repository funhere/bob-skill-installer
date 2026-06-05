# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] - 2026-06-02

### Added

- `/install-skill` IBM Bob slash command (`.bob/commands/install-skill.md`) with
  a confirm-first flow, `anysearch`-driven repository understanding, and a
  blocking security gate.
- `install-skill` CLI (Typer) and embeddable pipeline:
  `parse → fetch → analyze → security-scan → convert → validate → install →
  report`.
- Source support: GitHub, GitLab, generic Git, direct ZIP URL, and local
  directory paths (for offline use and testing).
- Format converters: Claude, Cursor, Windsurf, Cline, RooCode, OpenAI GPT, and a
  generic prompt-repository fallback.
- Static security scanner: rejects pipe-to-shell installs, remote-exec,
  credential/secret exfiltration, destructive shell, and MCP auto-trust;
  quarantines all executable scripts (never copied into the installed skill).
- Skill validator: structure, required metadata, markdown, and internal-link
  checks.
- Atomic, reversible installer with `--force` overwrite and `--upgrade`
  (keeps a `.bak`).
- Rich + plain-text install report.
- Test suite (unit + integration) with ≥90% coverage; `mypy --strict` and `ruff`
  clean.
- Documentation: `README.md`, `docs/architecture.md`, `docs/security.md`, and
  runnable examples.
