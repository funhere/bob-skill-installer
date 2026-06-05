# Examples

Self-contained sample sources you can convert locally, plus what the result
looks like.

## Try it against a local source

The installer accepts any git-cloneable location, including a local path, so you
can convert the bundled sample without a network round-trip:

```bash
# From the repo root, with the package installed (uv pip install -e ".[dev]")
install-skill "$(pwd)/examples/sample-claude-skill" --project --name demo-architect
```

> Note: a bare local path is convenient for trying things out. The everyday flow
> is a real URL, e.g. `install-skill https://github.com/org/repo`.

This will:

1. Clone the sample into a temp dir.
2. Detect it as a **Claude** skill (`CLAUDE.md` present).
3. Scan it — clean, nothing blocking.
4. Convert it into a Bob skill.
5. Install it to `./.bob/skills/demo-architect/`.
6. Print the install report.

## Samples

| Directory | Format detected | Notes |
|-----------|-----------------|-------|
| [`sample-claude-skill/`](sample-claude-skill/) | Claude | `CLAUDE.md` with role/objective/workflow/constraints |
| [`sample-cursor-skill/`](sample-cursor-skill/) | Cursor | `.cursorrules` + a `.mdc` rule |

## Expected report

```text
SUCCESS
Skill: demo-architect
Version: 1.0.0
Source: /…/examples/sample-claude-skill
Converted From: claude
Installed To: .bob/skills/demo-architect
Warnings: None
```
