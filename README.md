# bob-skill-installer

> **One command. Any skill. Into IBM Bob.**

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-141%20passed-brightgreen.svg)]()
[![Coverage](https://img.shields.io/badge/coverage-92%25-brightgreen.svg)]()
[![mypy: strict](https://img.shields.io/badge/mypy-strict-blue.svg)]()
[![ruff](https://img.shields.io/badge/ruff-passing-blue.svg)]()

[日本語](README.ja.md) | [中文](README.zh.md)

---

`bob-skill-installer` powers the IBM Bob `/install-skill` slash command.  
Point it at a public GitHub/GitLab/Git repository or a ZIP URL, and it automatically fetches, analyzes, converts, validates, and installs the skill into IBM Bob — with zero manual steps.

```bash
install-skill https://github.com/obra/superpowers --project
```

That's it.

---

## Features

- **Universal source support** — GitHub, GitLab, generic Git, direct ZIP, local directory
- **Format converters** — Claude, Cursor, Windsurf, Cline, RooCode, OpenAI GPT, generic prompt repos
- **Full-fidelity install** — every file preserved at its original path, binary-safe
- **Security gate** — blocks `curl | bash`, credential exfiltration, destructive shell, MCP auto-trust before anything is written
- **Atomic install** — staged write + swap; `--upgrade` keeps a `.bak`; no half-written skills on crash
- **IBM Bob slash command** — confirm-first conversational flow with `anysearch`-powered repo understanding
- **Enterprise-grade quality** — `mypy --strict`, `ruff`, 141 tests, 92% coverage

---

## Quickstart

### Prerequisites

- Python 3.12 or higher
- [`uv`](https://docs.astral.sh/uv/) (recommended) or `pip`
- Git (for cloning remote repositories)

### Install

```bash
git clone https://github.com/funhere/bob-skill-installer
cd bob-skill-installer
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

### Your first skill

```bash
# Install into the current project (./.bob/skills/)
install-skill https://github.com/obra/superpowers

# Install globally (~/.bob/skills/)
install-skill https://github.com/obra/superpowers --global

# Preview everything without writing to disk
install-skill https://github.com/obra/superpowers --dry-run

# From inside IBM Bob (slash command)
/install-skill https://github.com/obra/superpowers --project
```

---

## How It Works

The pipeline runs 8 independent, typed stages:

```
      URL
       │
       ▼
┌──────────────┐
│    parse     │  Classify the source URL → ParsedSource
└──────┬───────┘
       ▼
┌──────────────┐
│    fetch     │  Shallow git clone or safe ZIP extract → local dir
└──────┬───────┘
       ▼
┌──────────────┐
│   analyze    │  Walk the file tree, score the format → RepoAnalysis
└──────┬───────┘
       ▼
┌──────────────┐
│   security   │  Static pattern scan → SecurityReport
└──────┬───────┘   REJECTED here → nothing is installed
       ▼
┌──────────────┐
│   convert    │  Format-specific → BobSkill + SKILL.md
└──────┬───────┘
       ▼
┌──────────────┐
│   validate   │  Structure · metadata · markdown · links
└──────┬───────┘   FAILED here → nothing is installed
       ▼
┌──────────────┐
│   install    │  Atomic staged write → skill directory
└──────┬───────┘
       ▼
┌──────────────┐
│   report     │  Rich panel or plain-text summary
└──────────────┘
```

Each stage has a typed Pydantic model as its contract — independently testable, independently replaceable.

| Stage | Module | Responsibility |
|---|---|---|
| parse | `github/url_parser.py` | URL → `ParsedSource` |
| fetch | `github/fetcher.py` | clone / ZIP / local copy |
| analyze | `analyzer/` | file inventory + format scoring |
| security | `security/scanner.py` | pattern scan, inventory scripts & secrets |
| convert | `converters/` | 7 format converters + Jinja2 template |
| validate | `validators/` | structure, metadata, markdown, links |
| install | `installer/installer.py` | atomic write, `--force` / `--upgrade` |
| report | `report.py` | Rich + plain-text report |

---

## Supported Sources & Formats

### Sources (priority order)

| Source | Example |
|---|---|
| GitHub repository | `https://github.com/org/repo` |
| GitHub subtree | `https://github.com/org/repo/tree/main/skills/writer` |
| GitLab repository | `https://gitlab.com/org/repo` |
| Generic Git | `https://git.example.com/repo.git` |
| Direct ZIP URL | `https://example.com/skill.zip` |
| Local directory | `./examples/sample-claude-skill` |

### Formats (priority order)

| Format | Detection markers |
|---|---|
| **Claude** | `CLAUDE.md`, `SKILL.md`, `.claude/skills/` |
| **Cursor** | `.cursorrules`, `.cursor/rules/*.mdc` |
| **Windsurf** | `.windsurfrules`, `.windsurf/` |
| **Cline** | `.clinerules`, `.cline/` |
| **RooCode** | `.roomodes`, `.roo/` |
| **OpenAI GPT** | `instructions.md`, `prompt.md` |
| **Generic** | `README.md`, `prompts/` |

Format detection is evidence-based: multiple markers contribute weighted scores, so mixed repos always resolve to the best match.

---

## Generated Skill Layout

```text
.bob/skills/<name>/
├── SKILL.md           ← converted skill (YAML frontmatter + Markdown body)
├── docs/              ← Bob conventional scaffold
├── examples/
├── templates/
├── assets/
├── <original files>   ← every source file preserved at its original path
└── scripts/           ← included by default; use --no-scripts to drop
```

**Full-fidelity by default.** Every file from the source — including scripts, `.env`, configuration, images, and data — is preserved at its original relative path so the skill stays intact and internal links keep resolving.

> ⚠️ **Secrets notice:** If the source contains a real `.env` or private key, it will be copied by default. The report emits a prominent `SECURITY:` warning. Use `--no-secrets` for any skill you intend to share or publish.

### Generated `SKILL.md` example

```yaml
---
name: react-architect
description: 'Expert React architecture: patterns, state management, and performance.'
version: 2.1.0
source: https://github.com/org/react-skill
author: Jane Dev
converted_from: claude
created_at: 2026-06-02T09:01:07Z
---

# React Architect

## Role
You are a senior React architect who reviews component design.

## Objective
Help engineers structure scalable React applications.

## Workflow
1. Inspect the component tree
2. Identify state-management smells
3. Propose the minimal refactor

## Constraints
- Do not recommend class components
- Avoid premature memoization
```

Frontmatter is serialized with `yaml.safe_dump`, so descriptions containing colons, quotes, or non-ASCII characters are always valid YAML.

---

## Security Model

The security scanner runs **before** any conversion or installation. A single blocking finding causes an immediate `REJECTED` — nothing is written.

### What gets blocked (install stops)

| Category | Examples |
|---|---|
| `remote-exec` | `curl … \| bash`, `wget … \| sh`, `bash <(curl …)`, `eval "$(curl …)"` |
| `remote-exec` | PowerShell `IEX (… DownloadString …)` |
| `destructive-shell` | `rm -rf /`, `rm -rf ~`, `rm -rf $HOME` |
| `credential-harvesting` | Reading `~/.ssh/id_*`, `~/.aws/credentials`, `id_rsa` |
| `secret-exfiltration` | `printenv \| curl`, posting `$TOKEN`/`$SECRET` over the network |
| `mcp-auto-trust` | `mcp install … --yes`, `"autoApprove": true` |

### What gets warned (install continues)

| Category | Meaning |
|---|---|
| `browser-automation` | Headless browser launch without explicit approval |
| script policy | Scripts bundled (default) or excluded (`--no-scripts`) |
| secret policy | Secret files bundled with `SECURITY:` warning, or excluded (`--no-secrets`) |

Nothing from the source is ever executed. Scripts are read as text, never run.

---

## CLI Reference

```text
install-skill [URL] [OPTIONS]
```

| Option | Short | Default | Description |
|---|---|---|---|
| `--global` | `-g` | — | Install to `~/.bob/skills/` |
| `--project` | `-p` | ✓ | Install to `./.bob/skills/` |
| `--name TEXT` | | derived | Override the skill name (slug) |
| `--author TEXT` | | from source | Override the author |
| `--skill-version TEXT` | | from source | Override the version |
| `--force` | `-f` | — | Overwrite an existing skill |
| `--upgrade` | `-u` | — | Replace skill, keeping a `.bak` |
| `--no-scripts` | | — | Exclude executable scripts |
| `--no-secrets` | | — | Exclude `.env` / key files |
| `--dry-run` | | — | Run all stages but do not write |
| `--json` | | — | Plain-text report (no Rich colors) |
| `--verbose` | `-v` | — | Debug logging |
| `--log-file PATH` | | — | Also write logs to a rotating file |
| `--version` | | — | Show version and exit |

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Success (with or without warnings) |
| `2` | Invalid source URL or conflicting flags |
| `3` | Fetch failed (clone error, network, bad ZIP) |
| `7` | Generated skill failed validation |
| `8` | Rejected by the security scan |

### Real operation use cases
<img width="1454" height="275" alt="image" src="https://github.com/user-attachments/assets/3e43f00a-ffb2-4d9e-ad53-64856bf52f3e" />
...
<img width="1323" height="220" alt="image" src="https://github.com/user-attachments/assets/a343c664-b551-4dea-8425-65f81f27ff82" />
...
<img width="1454" height="270" alt="image" src="https://github.com/user-attachments/assets/8e039b0f-dade-42f7-aa81-468e8a21f781" />
...
<img width="277" height="668" alt="image" src="https://github.com/user-attachments/assets/f351f014-3c9a-4e4c-ac56-63f6d7d0d3e2" />


---

## IBM Bob Slash Command

The `/install-skill` Bob slash command (`.bob/commands/install-skill.md`) wraps the CLI with a conversational confirm-first flow:

1. **Parse** — extract URL and scope from the user message
2. **Confirm** — ask the user to approve source, target, and overwrite policy
3. **Understand** — invoke `anysearch` to summarize the repository
4. **Security review** — agent checks for obvious red flags before the scan
5. **Convert & install** — call the CLI
6. **Report** — surface the install report to the user

```text
/install-skill https://github.com/org/react-skill --project
/install-skill https://github.com/org/react-skill --global --no-secrets
```

### 実行レポートの例
<img width="606" height="787" alt="image" src="https://github.com/user-attachments/assets/a79f44c6-eba9-49cd-96b9-52467497700d" />

```text
┌─────────────────┐
│ install-skill   │
│ mcp-builder     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ mcp-builder     │
│ Skill実行       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ slack_mcp       │
│ MCP生成         │
└─────────────────┘
```
先ほどインストールした mcp-builder Skill を呼び出し、slack_mcp を生成します。

<img width="588" height="683" alt="image" src="https://github.com/user-attachments/assets/157f8d72-2b02-4635-8679-d3b3dfb85253" />
...
<img width="561" height="631" alt="image" src="https://github.com/user-attachments/assets/ca7da473-1eac-46cd-8859-e1ea08f6f826" />


---

## Project Structure

```text
bob-skill-installer/
├── src/bob_skill_installer/
│   ├── models.py              ← shared Pydantic models (pipeline contract)
│   ├── exceptions.py          ← typed exception hierarchy with exit_codes
│   ├── logging_config.py      ← Rich-based logging (console + rotating file)
│   ├── report.py              ← Rich panel + plain-text install report
│   ├── github/                ← URL parsing + git clone / ZIP fetch / local copy
│   ├── analyzer/              ← file tree walk + evidence-scored format detection
│   ├── converters/            ← 7 format converters + Jinja2 SKILL.md template
│   ├── security/              ← pattern scanner + sensitive-file detection
│   ├── validators/            ← structure / metadata / markdown / link checks
│   ├── installer/             ← atomic install + 8-stage pipeline orchestration
│   ├── templates/             ← skill_md.j2 Jinja2 template
│   └── cli/                   ← Typer CLI
├── tests/
│   ├── unit/                  ← 9 unit test files
│   └── integration/           ← 2 integration test files (offline, patched fetcher)
├── .bob/
│   ├── commands/install-skill.md  ← Bob slash command definition
│   └── skills/                    ← project-scope install target
├── docs/
│   ├── architecture.md
│   └── security.md
└── examples/
    ├── sample-claude-skill/
    └── sample-cursor-skill/
```

---

## anysearch Setup

[`anysearch`](https://github.com/anysearch-ai/anysearch-skill) is the real-time search skill that powers Step 3 of the slash command — it fetches and summarizes the target repository so the agent can understand its intent before conversion. **It is pre-installed** in `.bob/skills/anysearch/` and requires only an API key to activate.

### Get an API key

Visit **<https://anysearch.com/console/api-keys>** to sign up and create a free API key.

### Configure the key

**Option A — `.env` file (recommended for projects)**

```bash
cp .bob/skills/anysearch/.env.example .bob/skills/anysearch/.env
# Edit the file and set:
# ANYSEARCH_API_KEY=<your_api_key_here>
```

**Option B — environment variable (recommended for CI / global use)**

```bash
# Linux / macOS
export ANYSEARCH_API_KEY=<your_api_key_here>

# Windows CMD
set ANYSEARCH_API_KEY=<your_api_key_here>

# Windows PowerShell
$env:ANYSEARCH_API_KEY="<your_api_key_here>"
```

**Option C — CLI flag (one-off)**

```bash
install-skill https://github.com/org/skill --project
# anysearch picks up --api_key if passed through the slash command
```

> **Key priority order:** `--api_key` CLI flag › `.env` file › environment variable › anonymous (rate-limited)

Anonymous access is available without a key but subject to lower rate limits. For regular use, a free API key is strongly recommended.

For more details, see the [anysearch-skill repository](https://github.com/anysearch-ai/anysearch-skill).

---

## Development

```bash
# Install with dev extras
uv pip install -e ".[dev]"

# Run tests
uv run pytest

# Run tests with coverage report
uv run pytest --cov

# Type-check (strict)
uv run mypy src

# Lint
uv run ruff check .

# Try the bundled example (no network needed)
install-skill ./examples/sample-claude-skill --name demo-architect
```

### Quality metrics

| Metric | Value |
|---|---|
| Tests | 141 passing |
| Coverage | 92% |
| Type checking | `mypy --strict` — clean |
| Linting | `ruff` — clean |
| Python | 3.12+ |

---

## License

[Apache-2.0](LICENSE) — Copyright 2026 bob-skill-installer contributors.

---

## Related

- [`docs/architecture.md`](docs/architecture.md) — full pipeline design
- [`docs/security.md`](docs/security.md) — threat model and guarantees
- [`docs/blog-note.md`](docs/blog-note.md) — technical deep-dive (Japanese)
- [anysearch-skill](https://github.com/anysearch-ai/anysearch-skill) — real-time search skill (pre-installed dependency)
- [IBM Bob documentation](https://bob.ibm.com/)


---

## Disclaimer

This project may facilitate the discovery or installation of third-party Skills.

Users are responsible for reviewing the security, privacy, licensing, and compliance implications of any Skill before use. Always verify that a Skill complies with your organization's security policies, governance requirements, and applicable license terms.

The project maintainers assume no responsibility for any third-party content, code, or services.
