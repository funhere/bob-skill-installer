# Security model

Installing a third-party skill means running someone else's instructions inside
your agent. `bob-skill-installer` treats every source as untrusted and is
**safe-by-default**.

## Guarantees

1. **Nothing from the source is ever executed.** Not during fetch, analysis,
   scanning, conversion, or install. Scripts are read as text, never run.
2. **No executable scripts are copied into the installed skill.** Every script
   file (`.sh`, `.bash`, `.ps1`, `.py`, `.js`, … or any file with an exec bit) is
   *quarantined*: recorded in the report, excluded from the generated skill.
3. **No MCP server is auto-installed or auto-trusted.** MCP references found in
   the source are surfaced in a `## MCP References` section for awareness only.
4. **A blocking finding stops the install.** The skill is never written; the
   report status is `REJECTED`.
5. **ZIP extraction is path-traversal-safe and size-capped.** Entries that would
   escape the destination are refused; total expansion is capped (zip-bomb
   defense). Subpaths that escape the repo root are refused.
6. **Local-first.** The only network calls are the clone/download of the source
   the user explicitly asked for. No telemetry, no accounts, no API keys.

## What gets rejected (blocking)

The scanner ([`security/scanner.py`](../src/bob_skill_installer/security/scanner.py))
flags these as `HIGH`/`CRITICAL`, which block the install:

| Category | Examples |
|----------|----------|
| `remote-exec` | `curl … \| bash`, `wget … \| sh`, `bash <(curl …)`, `eval "$(curl …)"`, PowerShell `IEX (… DownloadString …)` |
| `destructive-shell` | `rm -rf /`, `rm -rf ~`, `rm -rf $HOME` |
| `credential-harvesting` | reading `~/.ssh/id_*`, `~/.aws/credentials`, `~/.netrc`, `id_rsa` |
| `secret-exfiltration` | `printenv \| curl`, posting `$*TOKEN/$*SECRET/$*KEY/$*PASSWORD` over the network |
| `mcp-auto-trust` | `mcp install … --yes`, `"autoApprove": true` |

## What gets warned (non-blocking)

These are surfaced on the report but do not stop the install:

| Category | Meaning |
|----------|---------|
| `browser-automation` | Headless browser launch (`puppeteer`/`playwright`/`selenium`) that may act without approval |
| `quarantined-scripts` | Scripts found and excluded from the installed skill |
| markdown / references | Cosmetic issues in the generated `SKILL.md` |

## Design choices

- **Conservative patterns, no false positives.** Rules match concrete dangerous
  *constructs* (a pipe to a shell, a secret posted to the network), not mere
  mentions of `curl` or `token`. This keeps the "every finding is reproducible"
  promise.
- **Scan the source, not the output.** Because the scan runs on the raw fetched
  tree before conversion, malicious content can never be laundered through the
  converter.
- **Defense in depth.** The Bob slash command also instructs the agent to
  manually reject the same categories and never run a repo's scripts "to see what
  they do" — so a gap in the static scanner is still caught by the operator.

## Reporting a gap

If you find a payload that should be blocked but isn't, add a failing test in
`tests/unit/test_security.py` and a rule in `_RULES`. Prefer a precise pattern
over a broad one.
