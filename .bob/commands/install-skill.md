---
name: install-skill
description: Download, analyze, convert, validate, and install a third-party open-source AI skill into IBM Bob. Supports GitHub/GitLab/git repositories and direct ZIP URLs; converts Claude, Cursor, Windsurf, Cline, RooCode, OpenAI-GPT, and generic prompt formats into IBM Bob skills.
version: 0.1.0
allowed-tools: Bash, Read, Write, AskUserQuestion
arguments:
  - name: source
    description: Source URL (GitHub/GitLab/git repository or .zip).
    required: true
  - name: scope
    description: --global (~/.bob/skills) or --project (./.bob/skills, default).
    required: false
---

# /install-skill

Install a third-party AI skill into IBM Bob from a public Git repository or ZIP.

```text
/install-skill https://github.com/example/react-skill
/install-skill https://github.com/example/react-skill --global
/install-skill https://github.com/example/react-skill --project   # default
```

This command never executes remote code, never auto-trusts an MCP server, and
never copies executable scripts into the installed skill. It converts the source
into a valid IBM Bob skill, validates it, and installs it after the security
gate passes.

---

## Workflow

Follow these steps in order. Do **not** skip the confirmation or the security
gate.

### Step 1 — Parse the invocation

From the user's message extract:

- **`source`** — the first URL argument.
- **`scope`** — `--global` → `~/.bob/skills/`; otherwise `--project` →
  `<project>/.bob/skills/` (the default).

If no URL is present, ask the user for one and stop.

### Step 2 — Confirm with the user (confirm-first)

Before cloning or writing anything, confirm with `AskUserQuestion`:

1. The **source URL**.
2. The **install target** (resolved `.bob/skills/<name>/` path + scope).
3. Whether to **overwrite** if a skill of that name already exists.

Do not proceed until confirmed.

### Step 3 — Understand the repository with `anysearch`

Invoke the **`anysearch`** skill to summarize the source before conversion. Ask
it to extract, from the repository:

- A one-paragraph repository summary.
- The skill's **role / objective / workflow / instructions / constraints**.
- Any **example** usages.
- Referenced **tools** and **MCP servers** (for awareness only — never install
  them).
- Candidate **skill metadata** (name, description, version, author).

Use this understanding to sanity-check the automated conversion in Step 5 and to
choose a good `--name` if the repo's own name is poor.

### Step 4 — Security review (blocking)

The installer runs a static security scan automatically, but you must also
**reject** the install if you observe any of the following and report why:

- `curl … | bash`, `wget … | sh`, or any pipe-to-shell install.
- Remote executable payloads, `eval "$(curl …)"`, PowerShell `IEX (… DownloadString …)`.
- Credential harvesting / token / secret / `.ssh` / `.aws` exfiltration.
- Browser automation that runs without approval.
- Any MCP server auto-install or auto-trust.
- Destructive shell (`rm -rf /`, `rm -rf ~`).

Never run any script found in the repository to "see what it does."

### Step 5 — Convert, validate, and install

Run the bundled CLI, which performs fetch → analyze → security-scan → convert →
validate → install atomically:

```bash
install-skill "<source>" <--global|--project> [--name <name>] [--force] [--no-scripts] [--no-secrets]
```

- Add `--force` only if the user approved overwrite in Step 2.
- The install is **full-fidelity by default**: all supporting files — references,
  assets, data, **and executable scripts** — are preserved at their original
  paths. Add `--no-scripts` to drop scripts.
- **Secret files (`.env`, keys, credentials) are copied by default.** If the user
  intends to share or publish the skill, pass `--no-secrets`. Surface the report's
  `SECURITY:` warning whenever secrets were bundled.
- Add `--dry-run` first if the user wants a preview; it runs every stage except
  the final write.
- If the CLI is not on PATH, run it from this project with
  `uv run install-skill "<source>" …` (or `python -m bob_skill_installer.cli.main …`).

The CLI exits non-zero on rejection (8), validation failure (7), or other
errors; surface the printed report verbatim.

### Step 6 — Report

Present the installation report to the user:

```text
SUCCESS
Skill: react-architect
Version: 0.1.0
Source: https://github.com/example/react-skill
Converted From: claude
Installed To: .bob/skills/react-architect
Warnings: None
```

If the status is `REJECTED` or `FAILED`, explain the blocking findings and what
the user can do (e.g. install a different skill, or open the source so they can
review the flagged lines themselves). Do not retry with reduced security.

---

## Generated skill layout

```text
.bob/skills/<name>/
├── SKILL.md        # frontmatter: name, description, version, source,
│                   #              author, converted_from, created_at
├── docs/           # original source material, preserved for reference
├── examples/
├── templates/
└── assets/
```

## Supported sources & formats

| Sources (priority) | Formats (priority) |
|--------------------|--------------------|
| GitHub repo        | Claude (`CLAUDE.md`, `skills/`, `SKILL.md`) |
| GitLab repo        | Cursor (`.mdc`, `.cursor/rules`, `.cursorrules`) |
| Generic Git        | Windsurf (`.windsurf`, `.windsurfrules`) |
| Direct `.zip` URL  | Cline (`.clinerules`, `.cline`) |
|                    | RooCode (`.roomodes`, `.roo`) |
|                    | OpenAI GPT (`instructions.md`, `prompt.md`) |
|                    | Generic prompt repo (`README.md`, `prompts/`) |
