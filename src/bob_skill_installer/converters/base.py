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

_log = get_logger("converter")

# Files we copy into the generated skill's docs/ as reference material.
_DOC_EXTS = {".md", ".mdc", ".markdown", ".txt", ".rst"}
_MAX_DOC_BYTES = 1024 * 1024


class ConversionContext(BaseModel):
    """Per-run overrides supplied by the CLI/pipeline."""

    source_url: str
    name_override: str | None = None
    author_override: str | None = None
    version_override: str | None = None
    quarantined_scripts: list[str] = []


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
        files = self._collect_docs(analysis, sources)
        skill_md = self._render(metadata, content, has_docs=bool(files))

        _log.info(
            "Converted [bold]%s[/bold] -> skill '%s'", self.source_format.value, metadata.name
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

    def _render(self, metadata: SkillMetadata, content: ExtractedContent, *, has_docs: bool) -> str:
        template = _jinja_env().get_template("skill_md.j2")
        title = metadata.name.replace("-", " ").title()
        rendered = template.render(
            meta=metadata,
            content=content,
            title=title,
            has_docs=has_docs,
            frontmatter=_render_frontmatter(metadata),
        )
        # Collapse 3+ blank lines that the conditional template blocks can leave.
        while "\n\n\n" in rendered:
            rendered = rendered.replace("\n\n\n", "\n\n")
        return rendered

    def _collect_docs(self, analysis: RepoAnalysis, sources: list[Path]) -> list[GeneratedFile]:
        """Copy non-executable reference docs into ``docs/`` (scripts excluded)."""
        files: list[GeneratedFile] = []
        seen: set[Path] = set()
        for path in analysis.markdown_files:
            if path in sources or path in seen:
                continue
            if path.suffix.lower() not in _DOC_EXTS:
                continue
            try:
                if path.stat().st_size > _MAX_DOC_BYTES:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:  # pragma: no cover
                continue
            rel = path.relative_to(analysis.root)
            files.append(GeneratedFile(relative_path=Path("docs") / rel, content=text))
            seen.add(path)
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
