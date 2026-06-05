"""Typed domain models shared across every stage of the pipeline.

These pydantic models *are* the contract between modules: the GitHub layer emits
a :class:`ParsedSource`, the analyzer emits a :class:`RepoAnalysis`, converters
emit a :class:`BobSkill`, and so on. Keeping the data typed and validated at each
boundary is what makes the stages independently testable.
"""

from __future__ import annotations

import datetime as _dt
import re
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #


class SourceType(StrEnum):
    """Where the skill bytes come from."""

    GITHUB = "github"
    GITLAB = "gitlab"
    GIT = "git"
    ZIP = "zip"
    LOCAL = "local"


class SkillFormat(StrEnum):
    """Recognized third-party skill formats, plus sentinels."""

    CLAUDE = "claude"
    CURSOR = "cursor"
    WINDSURF = "windsurf"
    CLINE = "cline"
    ROOCODE = "roocode"
    OPENAI = "openai"
    GENERIC = "generic"
    UNKNOWN = "unknown"


class InstallScope(StrEnum):
    """Project-local vs. user-global install targets."""

    PROJECT = "project"
    GLOBAL = "global"


class Severity(StrEnum):
    """Shared severity scale for validation and security findings."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class InstallStatus(StrEnum):
    """Terminal status of an install attempt."""

    SUCCESS = "SUCCESS"
    SUCCESS_WITH_WARNINGS = "SUCCESS_WITH_WARNINGS"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


# --------------------------------------------------------------------------- #
# Source parsing
# --------------------------------------------------------------------------- #


class ParsedSource(BaseModel):
    """A normalized description of a user-supplied source URL."""

    model_config = ConfigDict(frozen=True)

    raw: str
    source_type: SourceType
    clone_url: str | None = None
    host: str | None = None
    owner: str | None = None
    repo: str | None = None
    ref: str | None = None
    subpath: str | None = None
    zip_url: str | None = None
    local_path: str | None = None

    @property
    def is_zip(self) -> bool:
        return self.source_type is SourceType.ZIP

    @property
    def slug(self) -> str:
        """Best-effort human slug for naming the working directory."""
        if self.repo:
            return self.repo
        if self.zip_url:
            return Path(self.zip_url).stem
        if self.local_path:
            return Path(self.local_path).name
        return "skill"


# --------------------------------------------------------------------------- #
# Repository analysis
# --------------------------------------------------------------------------- #


class FormatDetection(BaseModel):
    """One scored guess at the source format."""

    fmt: SkillFormat
    score: int
    evidence: list[str] = Field(default_factory=list)


class RepoAnalysis(BaseModel):
    """The result of walking a fetched tree."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    root: Path
    file_count: int
    text_files: list[Path] = Field(default_factory=list)
    markdown_files: list[Path] = Field(default_factory=list)
    script_files: list[Path] = Field(default_factory=list)
    detections: list[FormatDetection] = Field(default_factory=list)
    readme: Path | None = None

    @property
    def best_format(self) -> SkillFormat:
        if not self.detections:
            return SkillFormat.UNKNOWN
        return max(self.detections, key=lambda d: d.score).fmt


class ExtractedContent(BaseModel):
    """Normalized skill content lifted out of the source format."""

    role: str | None = None
    objective: str | None = None
    workflow: list[str] = Field(default_factory=list)
    instructions: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    mcp_references: list[str] = Field(default_factory=list)
    body_markdown: str = ""


# --------------------------------------------------------------------------- #
# Generated skill
# --------------------------------------------------------------------------- #

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Lowercase kebab-case slug safe for a directory name."""
    slug = _SLUG_RE.sub("-", value.strip().lower()).strip("-")
    return slug or "skill"


class SkillMetadata(BaseModel):
    """Frontmatter for a generated Bob ``SKILL.md``.

    Mirrors the spec's required block while staying compatible with the richer
    frontmatter real Bob skills use (extra keys are allowed downstream).
    """

    name: str
    description: str
    version: str = "0.1.0"
    source: str
    author: str = "unknown"
    converted_from: SkillFormat
    created_at: str = Field(
        default_factory=lambda: _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    @field_validator("name")
    @classmethod
    def _slug_name(cls, v: str) -> str:
        return slugify(v)

    @field_validator("description")
    @classmethod
    def _trim_description(cls, v: str) -> str:
        v = " ".join(v.split())
        return v if v else "Converted skill."


class GeneratedFile(BaseModel):
    """A non-SKILL.md file to write alongside the skill (docs/examples/etc.)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    relative_path: Path
    content: str


class BobSkill(BaseModel):
    """A complete, ready-to-install Bob skill."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    metadata: SkillMetadata
    skill_md: str
    files: list[GeneratedFile] = Field(default_factory=list)

    @property
    def name(self) -> str:
        return self.metadata.name


# --------------------------------------------------------------------------- #
# Validation & security
# --------------------------------------------------------------------------- #


class Finding(BaseModel):
    """A single validation or security finding."""

    severity: Severity
    category: str
    message: str
    location: str | None = None

    @property
    def is_blocking(self) -> bool:
        return self.severity in (Severity.HIGH, Severity.CRITICAL)


class ValidationResult(BaseModel):
    """Outcome of structural/metadata/link validation."""

    findings: list[Finding] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(f.is_blocking for f in self.findings)

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if not f.is_blocking]


class SecurityReport(BaseModel):
    """Outcome of the security scan over the *source* tree."""

    findings: list[Finding] = Field(default_factory=list)
    quarantined_scripts: list[str] = Field(default_factory=list)

    @property
    def blocking(self) -> list[Finding]:
        return [f for f in self.findings if f.is_blocking]

    @property
    def ok(self) -> bool:
        return not self.blocking


# --------------------------------------------------------------------------- #
# Install report
# --------------------------------------------------------------------------- #


class InstallReport(BaseModel):
    """The user-facing summary emitted at the end of a run."""

    status: InstallStatus
    skill_name: str
    version: str
    source: str
    converted_from: SkillFormat
    target: str | None = None
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
