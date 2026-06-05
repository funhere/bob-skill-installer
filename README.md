# bob-skill-installer

> Download, analyze, convert, validate, and install third-party open-source AI
> skills into **IBM Bob** — with one command.

`bob-skill-installer` powers the IBM Bob `/install-skill` slash command. Point it
at a public Git repository or a ZIP, and it fetches the source, recognizes its
format (Claude, Cursor, Windsurf, Cline, RooCode, OpenAI-GPT, or a generic prompt
repo), converts it into a valid IBM Bob skill, runs a static security scan,
validates the result, and installs it into `.bob/skills/`.

It is **local-first and safe-by-default**: it never executes remote code, never
auto-trusts an MCP server, and never copies executable scripts into the
installed skill.

---

## Quickstart

```bash
# Install the tool (editable, with dev extras)
uv pip install -e ".[dev]"

# Install a skill into the current project (./.bob/skills)
install-skill https://github.com/example/react-skill

# Install globally (~/.bob/skills)
install-skill https://github.com/example/react-skill --global

# Preview without writing anything
install-skill https://github.com/example/react-skill --dry-run
```

From inside IBM Bob, use the slash command instead:

```text
/install-skill https://github.com/example/react-skill --global
```

## CLI reference

```text
install-skill <url> [options]

  -g, --global          Install to ~/.bob/skills (user-global)
  -p, --project         Install to ./.bob/skills (default)
      --name TEXT       Override the generated skill name
      --author TEXT     Override the skill author
      --skill-version   Override the skill version
  -f, --force           Overwrite an existing skill
  -u, --upgrade         Replace an existing skill, keeping a .bak
      --dry-run         Run every stage but do not write
      --json            Emit the report as plain text on stdout
  -v, --verbose         Debug logging
      --log-file PATH   Also write logs to a rotating file
      --version         Show version and exit
```


<img width="958" height="975" alt="image" src="https://github.com/user-attachments/assets/23596bed-1277-4afc-a3fe-4bd5db53672f" />

<img width="583" height="477" alt="image" src="https://github.com/user-attachments/assets/d7e2e2a7-627e-4de8-a469-4c67075f16a3" />


<img width="572" height="838" alt="image" src="https://github.com/user-attachments/assets/e219a347-02ad-4936-a96a-00dff374f463" />

<img width="567" height="601" alt="image" src="https://github.com/user-attachments/assets/94ee1dec-df3c-43db-ba85-5dbf6c42fc03" />

<img width="556" height="535" alt="image" src="https://github.com/user-attachments/assets/09e30ccb-a1fa-4368-8d5a-8099a4ac7b8c" />

<img width="234" height="250" alt="image" src="https://github.com/user-attachments/assets/e0742cf5-5902-4963-b63c-e3a1f0f09c44" />


### Exit codes

| Code | Meaning                         |
|------|---------------------------------|
| 0    | Success (with or without warnings) |
| 2    | Invalid source URL / bad flags  |
| 3    | Fetch (clone/download) failed   |
| 7    | Generated skill failed validation |
| 8    | Rejected by the security scan   |

## How it works

```text
parse → fetch → analyze → security-scan → convert → validate → install → report
```

Each stage is an independently testable module under `src/bob_skill_installer/`:

| Stage      | Module            | Responsibility |
|------------|-------------------|----------------|
| parse      | `github/url_parser.py` | Classify GitHub/GitLab/git/ZIP URLs |
| fetch      | `github/fetcher.py`    | Shallow clone or safe ZIP extract |
| analyze    | `analyzer/`            | Walk the tree, score the format |
| security   | `security/scanner.py`  | Reject dangerous payloads, quarantine scripts |
| convert    | `converters/`          | Format-specific → Bob `SKILL.md` |
| validate   | `validators/`          | Structure, metadata, markdown, links |
| install    | `installer/installer.py` | Atomic write to the scope target |
| report     | `report.py`            | Rich + plain-text install report |

See [`docs/architecture.md`](docs/architecture.md) for the full design and
[`docs/security.md`](docs/security.md) for the threat model.

## Generated skill layout

```text
.bob/skills/<name>/
├── SKILL.md        # name, description, version, source, author,
│                   # converted_from, created_at (+ converted body)
├── docs/           # original source material, preserved
├── examples/
├── templates/
└── assets/
```

## Supported sources & formats

**Sources** (priority order): GitHub → GitLab → generic Git → direct `.zip` URL.

**Formats** (priority order): Claude → Cursor → Windsurf → Cline → RooCode →
OpenAI GPT → generic prompt repository.

## Development

```bash
uv pip install -e ".[dev]"
uv run pytest                 # run the suite
uv run pytest --cov           # with coverage
uv run mypy src               # type-check
uv run ruff check .           # lint
```

