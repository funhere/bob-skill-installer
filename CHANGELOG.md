# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed

- Frontmatter is now serialized with `yaml.safe_dump`, so skills whose metadata
  contains YAML-special characters (a colon-space in a description, a leading
  `#`, quotes, non-ASCII text) no longer produce an invalid `SKILL.md` that
  failed validation as "missing frontmatter".
- **Faithful file preservation.** Conversion previously copied only markdown
  (buried under `docs/` with mangled paths) and silently dropped every other
  file. All supporting files are now preserved at their **original relative
  paths**, binary-safe, so skills install intact and internal links resolve.

### Changed

- **Full-fidelity by default.** Executable scripts and secret files are now
  preserved by default to produce a faithful 1:1 copy. Use `--no-scripts` /
  `--no-secrets` to drop them. When secrets are bundled the report emits a
  `SECURITY:` warning advising against publishing the skill. The blocking
  security scan (`curl | bash`, exfiltration, MCP auto-trust, …) still runs and
  rejects actively malicious sources regardless of these flags.

### Added

- `--no-scripts` and `--no-secrets` opt-out flags.
- Secret-file detection (`.env`, `*.pem`, `*.key`, `id_rsa`, `.netrc`, `.npmrc`,
  credential files, … with template variants like `.env.example` / `*.pub`
  recognized) used for the `--no-secrets` filter and the copy-warning.

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
