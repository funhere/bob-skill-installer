# Security model

Installing a third-party skill means running someone else's instructions inside
your agent. `bob-skill-installer` treats every source as untrusted and is
**safe-by-default**.

## Guarantees

1. **Nothing from the source is ever executed.** Not during fetch, analysis,
   scanning, conversion, or install. Scripts are read as text, never run.
2. **Full-fidelity by default, with explicit opt-outs.** The installer aims to
   produce a faithful 1:1 copy, so executable scripts and supporting files are
   preserved by default. `--no-scripts` drops scripts; `--no-secrets` drops
   secret files. Every script and secret bundled is reported as a warning so the
   result is never silent.
3. **Secrets are copied by default — and loudly flagged.** When a source contains
   secret files (`.env`, `*.pem`, `id_rsa`, credential files, …) they are copied
   and the report emits a `SECURITY:` warning telling the user not to publish the
   skill. Pass `--no-secrets` to exclude them (detection keeps template variants
   like `.env.example` / `*.pub`). The takeaway: **do not share a skill built
   without `--no-secrets` from an untrusted or secret-bearing source.**
4. **No MCP server is auto-installed or auto-trusted.** MCP references found in
   the source are surfaced in a `## MCP References` section for awareness only.
5. **A blocking finding stops the install.** The skill is never written; the
   report status is `REJECTED`.
6. **ZIP extraction is path-traversal-safe and size-capped.** Entries that would
   escape the destination are refused; total expansion is capped (zip-bomb
   defense). Subpaths that escape the repo root are refused.
7. **Local-first.** The only network calls are the clone/download of the source
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
| (script policy) | Scripts found; bundled by default or dropped via `--no-scripts` (reported by the pipeline) |
| (secret policy) | Secret files found; copied by default (with a `SECURITY:` warning) or dropped via `--no-secrets` |
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
