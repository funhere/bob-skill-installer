# Architecture

`bob-skill-installer` is a linear pipeline of small, independently testable
stages. Each stage has one job, a typed input, and a typed output (the pydantic
models in [`models.py`](../src/bob_skill_installer/models.py)). Nothing reaches
across stages; the models *are* the contract.

```
                ┌──────────┐
   URL  ───────▶│  parse   │  github/url_parser.py      → ParsedSource
                └────┬─────┘
                     ▼
                ┌──────────┐
                │  fetch   │  github/fetcher.py          → working dir (Path)
                └────┬─────┘
                     ▼
                ┌──────────┐
                │ analyze  │  analyzer/                  → RepoAnalysis
                └────┬─────┘
                     ▼
                ┌──────────┐
                │ security │  security/scanner.py        → SecurityReport
                └────┬─────┘   (blocking finding ⇒ REJECTED, stop)
                     ▼
                ┌──────────┐
                │ convert  │  converters/                → BobSkill
                └────┬─────┘
                     ▼
                ┌──────────┐
                │ validate │  validators/                → ValidationResult
                └────┬─────┘   (blocking finding ⇒ FAILED, stop)
                     ▼
                ┌──────────┐
                │ install  │  installer/installer.py     → target Path
                └────┬─────┘
                     ▼
                ┌──────────┐
                │  report  │  report.py                  → InstallReport
                └──────────┘
```

The orchestration lives in
[`installer/pipeline.py`](../src/bob_skill_installer/installer/pipeline.py)
(`run_install`). The Typer CLI
([`cli/main.py`](../src/bob_skill_installer/cli/main.py)) and the IBM Bob slash
command (`.bob/commands/install-skill.md`) are two front-ends over that one
function.

## Why these boundaries

- **`ParsedSource` is pure data.** URL parsing is network-free, so every URL
  shape is a fast unit test. Only the fetcher touches the network.
- **The security scan runs on the raw source, before conversion.** A malicious
  repo is rejected before any of its content is transformed or written.
- **Converters share a base.** [`BaseConverter`](../src/bob_skill_installer/converters/base.py)
  owns extraction, metadata, SKILL.md rendering, and doc collection; each format
  subclass only answers "which files carry the intent?" via `primary_sources`.
  Adding a format is one small file plus a registry line.
- **The installer is atomic.** It stages into a temp dir and swaps into place, so
  a crash mid-write never leaves a half-installed skill. `--upgrade` keeps a
  one-shot `.bak`.

## Adding a new source format

1. Create `converters/<format>.py` with a `BaseConverter` subclass: set
   `source_format` and implement `primary_sources(analysis) -> list[Path]`.
2. Add detection markers in
   [`analyzer/format_detector.py`](../src/bob_skill_installer/analyzer/format_detector.py).
3. Register the converter in
   [`converters/registry.py`](../src/bob_skill_installer/converters/registry.py)
   (priority order matters — earlier wins ties).
4. Add a fixture builder in `tests/conftest.py` and a detection + conversion test.

## Relationship to `anysearch`

The spec's "understand the repository" step is performed by the **`anysearch`**
skill inside the Bob slash command, *before* this pipeline runs. `anysearch`
produces a human/agent-level summary used to sanity-check the conversion and pick
a good skill name. This Python core is the deterministic, offline engine that
does the actual fetch → convert → validate → install. Keeping the model-driven
summarization in the command and the deterministic transform in code means the
transform is fully reproducible and unit-tested.
