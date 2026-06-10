"""Base converter: turns a :class:`RepoAnalysis` into a :class:`BobSkill`.

Concrete converters subclass this and only need to declare their
:attr:`source_format` and implement :meth:`primary_sources` (which markdown
documents carry the skill's intent). Everything else — extraction, metadata,
SKILL.md rendering, and copying *non-executable* reference material into
``docs/`` — is shared here so all formats produce a consistent Bob layout.
"""

from __future__ import annotations

import abc
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

import yaml
from jinja2 import Environment, PackageLoader, select_autoescape
from pydantic import BaseModel

from bob_skill_installer.converters.extraction import extract_content, parse_frontmatter
from bob_skill_installer.exceptions import ConversionError
from bob_skill_installer.logging_config import get_logger
from bob_skill_installer.models import (
    BobSkill,
    ExtractedContent,
    GeneratedFile,
    RepoAnalysis,
    SkillFormat,
    SkillMetadata,
    slugify,
)
from bob_skill_installer.security import is_sensitive_path

_log = get_logger("converter")

# Per-file ceiling for copied source material (keeps a stray large binary from
# bloating the installed skill). Larger files are skipped with a log note.
_MAX_FILE_BYTES = 8 * 1024 * 1024

# OS/editor junk we never carry into a clean skill.
_JUNK_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}


class ConversionContext(BaseModel):
    """Per-run overrides supplied by the CLI/pipeline."""

    source_url: str
    name_override: str | None = None
    author_override: str | None = None
    version_override: str | None = None
    #: Full-fidelity by default: every supporting file is preserved. Set these to
    #: drop executable scripts / secret files from the installed skill.
    exclude_scripts: bool = False
    exclude_secrets: bool = False


def _render_frontmatter(metadata: SkillMetadata) -> str:
    """Serialize metadata into a valid YAML frontmatter block.

    Values are emitted through ``yaml.safe_dump`` rather than string-templated, so
    fields containing YAML-special characters (a colon-space in a description, a
    leading ``#``, quotes, non-ASCII text, …) are quoted/escaped correctly and the
    generated ``SKILL.md`` always parses. ``converted_from`` is coerced to a plain
    string because PyYAML has no representer for the ``SkillFormat`` enum subclass.
    """
    data = {
        "name": metadata.name,
        "description": metadata.description,
        "version": str(metadata.version),
        "source": metadata.source,
        "author": metadata.author,
        "converted_from": metadata.converted_from.value,
        "created_at": metadata.created_at,
    }
    body = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"---\n{body}---\n"


def dedupe_paths(paths: Iterable[Path]) -> list[Path]:
    """Order-preserving de-duplication used by every converter's source list."""
    seen: set[Path] = set()
    out: list[Path] = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            out.append(path)
    return out


@lru_cache(maxsize=1)
def _jinja_env() -> Environment:
    return Environment(
        loader=PackageLoader("bob_skill_installer", "templates"),
        autoescape=select_autoescape(enabled_extensions=()),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


class BaseConverter(abc.ABC):
    """Shared conversion machinery."""

    #: The source format this converter handles.
    source_format: SkillFormat = SkillFormat.UNKNOWN

    @abc.abstractmethod
    def primary_sources(self, analysis: RepoAnalysis) -> list[Path]:
        """Return the markdown files that carry the skill's core intent."""

    def can_convert(self, analysis: RepoAnalysis) -> bool:
        return bool(self.primary_sources(analysis))

    # -- main entry point --------------------------------------------------- #

    def convert(self, analysis: RepoAnalysis, ctx: ConversionContext) -> BobSkill:
        sources = self.primary_sources(analysis)
        if not sources:
            raise ConversionError(
                f"{self.source_format.value}: no convertible source documents found."
            )
        documents = [self._read(p) for p in sources]
        documents = [d for d in documents if d.strip()]
        if not documents:
            raise ConversionError(f"{self.source_format.value}: source documents are empty.")

        content = extract_content(documents, fallback_objective="Converted skill.")
        metadata = self._build_metadata(analysis, ctx, sources[0])
        files = self._collect_files(
            analysis,
            sources,
            exclude_scripts=ctx.exclude_scripts,
            exclude_secrets=ctx.exclude_secrets,
        )
        skill_md = self._render(metadata, content, bundled_count=len(files))

        _log.info(
            "Converted [bold]%s[/bold] -> skill '%s' (%d bundled file(s))",
            self.source_format.value,
            metadata.name,
            len(files),
        )
        return BobSkill(metadata=metadata, skill_md=skill_md, files=files)

    # -- helpers ------------------------------------------------------------ #

    def _read(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:  # pragma: no cover - race on read
            raise ConversionError(f"Could not read {path}: {exc}") from exc

    def _build_metadata(
        self, analysis: RepoAnalysis, ctx: ConversionContext, primary: Path
    ) -> SkillMetadata:
        front, _ = parse_frontmatter(self._read(primary))
        name = (
            ctx.name_override
            or _as_str(front.get("name"))
            or _derive_name(analysis, ctx, primary)
        )
        description = _as_str(front.get("description")) or _first_line(self._read(primary))
        version = ctx.version_override or _as_str(front.get("version")) or "0.1.0"
        author = (
            ctx.author_override
            or _as_str(front.get("author"))
            or _authors_to_str(front.get("authors"))
            or "unknown"
        )
        return SkillMetadata(
            name=name,
            description=description or "Converted skill.",
            version=version,
            source=ctx.source_url,
            author=author,
            converted_from=self.source_format,
        )

    def _render(
        self, metadata: SkillMetadata, content: ExtractedContent, *, bundled_count: int
    ) -> str:
        template = _jinja_env().get_template("skill_md.j2")
        title = metadata.name.replace("-", " ").title()
        rendered = template.render(
            meta=metadata,
            content=content,
            title=title,
            bundled_count=bundled_count,
            frontmatter=_render_frontmatter(metadata),
        )
        # Collapse 3+ blank lines that the conditional template blocks can leave.
        while "\n\n\n" in rendered:
            rendered = rendered.replace("\n\n\n", "\n\n")
        return rendered

    def _collect_files(
        self,
        analysis: RepoAnalysis,
        sources: list[Path],
        *,
        exclude_scripts: bool,
        exclude_secrets: bool,
    ) -> list[GeneratedFile]:
        """Preserve every supporting source file at its **original** relative path.

        Full-fidelity by default: references, assets, data files, helper scripts,
        and config all land where the skill expects them, so internal links keep
        resolving. The primary document(s) consumed into ``SKILL.md`` are skipped
        to avoid duplication. ``exclude_scripts`` / ``exclude_secrets`` drop those
        categories when the caller asks. OS junk (``.DS_Store``) is never copied.
        """
        files: list[GeneratedFile] = []
        consumed = set(sources)
        scripts = set(analysis.script_files)
        for path in analysis.all_files:
            if path in consumed:
                continue
            if exclude_scripts and path in scripts:
                continue
            rel = path.relative_to(analysis.root)
            # Never let a crafted path escape the skill root.
            if rel.is_absolute() or ".." in rel.parts:
                continue
            if rel.name in _JUNK_NAMES:
                continue
            if exclude_secrets and is_sensitive_path(rel):
                continue
            try:
                if path.stat().st_size > _MAX_FILE_BYTES:
                    _log.debug("Skipping oversized file (> cap): %s", rel)
                    continue
                data = path.read_bytes()
            except OSError:  # pragma: no cover - race on read
                continue
            files.append(GeneratedFile.binary(rel, data))
        return files


# --------------------------------------------------------------------------- #
# Small pure helpers (module-level for testability)
# --------------------------------------------------------------------------- #


def _as_str(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _authors_to_str(value: object) -> str | None:
    if isinstance(value, list) and value:
        parts = [str(v) for v in value if v]
        return ", ".join(parts) if parts else None
    return _as_str(value)


def _first_line(text: str) -> str:
    _, body = parse_frontmatter(text)
    for line in body.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped and stripped != "---":
            return " ".join(stripped.split())[:200]
    return ""


def _derive_name(analysis: RepoAnalysis, ctx: ConversionContext, primary: Path) -> str:
    # Prefer the source repo/zip slug from the URL tail, else the primary file's
    # parent directory, else the file stem.
    from bob_skill_installer.github.url_parser import parse_source

    try:
        parsed = parse_source(ctx.source_url)
        if parsed.repo:
            return slugify(parsed.repo)
    except Exception:  # noqa: BLE001 - naming is best-effort
        pass
    if primary.parent != analysis.root:
        return slugify(primary.parent.name)
    return slugify(primary.stem if primary.stem.lower() != "readme" else analysis.root.name)
