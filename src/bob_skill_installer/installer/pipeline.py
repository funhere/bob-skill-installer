"""End-to-end orchestration: URL in, :class:`InstallReport` out.

Stage order mirrors the spec's analysis workflow:

    parse -> fetch -> analyze -> security scan -> convert -> validate -> install

A blocking *security* finding short-circuits to a ``REJECTED`` report and a
blocking *validation* finding to a ``FAILED`` report; both are returned (not
raised) so the caller always gets a structured result. Infrastructure failures
(bad URL, clone failure) raise the corresponding :class:`InstallerError` for the
CLI to map to an exit code.

Note: the richer model-driven repository summarization the spec attributes to
``anysearch`` happens in the Bob slash command *before* this code runs. This
pipeline is the deterministic, offline core that the command invokes once the
source has been understood.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from bob_skill_installer.analyzer import analyze_repo
from bob_skill_installer.converters import ConversionContext, convert
from bob_skill_installer.github import SourceFetcher, parse_source
from bob_skill_installer.installer.installer import SkillInstaller
from bob_skill_installer.logging_config import get_logger
from bob_skill_installer.models import (
    InstallReport,
    InstallScope,
    InstallStatus,
    SkillFormat,
)
from bob_skill_installer.security import scan_source
from bob_skill_installer.validators import validate_skill

_log = get_logger("pipeline")


class PipelineOptions(BaseModel):
    """Everything the pipeline needs for one install run."""

    source_url: str
    scope: InstallScope = InstallScope.PROJECT
    name: str | None = None
    author: str | None = None
    version: str | None = None
    overwrite: bool = False
    upgrade: bool = False
    exclude_scripts: bool = False
    exclude_secrets: bool = False
    project_root: Path | None = None
    dry_run: bool = False
    clone_depth: int = 1


def run_install(opts: PipelineOptions) -> InstallReport:
    """Run the full pipeline and return an :class:`InstallReport`."""
    parsed = parse_source(opts.source_url)
    _log.info("Source classified as [bold]%s[/bold]", parsed.source_type.value)

    with SourceFetcher(parsed, depth=opts.clone_depth) as root:
        analysis = analyze_repo(root)
        fmt = analysis.best_format

        # --- Security gate (over the raw source) --------------------------- #
        security = scan_source(analysis)
        if not security.ok:
            return InstallReport(
                status=InstallStatus.REJECTED,
                skill_name=opts.name or parsed.slug,
                version=opts.version or "—",
                source=opts.source_url,
                converted_from=fmt,
                warnings=[f.message for f in security.blocking],
                error="Installation blocked by security scan.",
            )

        warnings = [f.message for f in security.findings if not f.is_blocking]

        # --- File-inclusion policy (full-fidelity by default) -------------- #
        if security.scripts:
            n = len(security.scripts)
            if opts.exclude_scripts:
                warnings.append(f"{n} executable script(s) were excluded (--no-scripts).")
            else:
                warnings.append(
                    f"{n} executable script(s) were bundled (passed the security scan) — "
                    "review them before running. Use --no-scripts to exclude."
                )
        if security.sensitive_files:
            n = len(security.sensitive_files)
            if opts.exclude_secrets:
                warnings.append(f"{n} potential secret file(s) were excluded (--no-secrets).")
            else:
                warnings.append(
                    f"SECURITY: {n} potential secret file(s) (e.g. .env / keys) were COPIED "
                    "into the skill. Do NOT share or publish it. Use --no-secrets to exclude."
                )

        # --- Convert ------------------------------------------------------- #
        ctx = ConversionContext(
            source_url=opts.source_url,
            name_override=opts.name,
            author_override=opts.author,
            version_override=opts.version,
            exclude_scripts=opts.exclude_scripts,
            exclude_secrets=opts.exclude_secrets,
        )
        skill = convert(analysis, ctx)

        # --- Validate ------------------------------------------------------ #
        validation = validate_skill(skill)
        warnings.extend(f.message for f in validation.warnings)
        if not validation.ok:
            blocking = [f.message for f in validation.findings if f.is_blocking]
            return InstallReport(
                status=InstallStatus.FAILED,
                skill_name=skill.name,
                version=skill.metadata.version,
                source=opts.source_url,
                converted_from=fmt,
                warnings=warnings + blocking,
                error="Generated skill failed validation.",
            )

        # --- Install ------------------------------------------------------- #
        target = SkillInstaller().install(
            skill,
            opts.scope,
            project_root=opts.project_root,
            overwrite=opts.overwrite,
            upgrade=opts.upgrade,
            dry_run=opts.dry_run,
        )

    status = InstallStatus.SUCCESS_WITH_WARNINGS if warnings else InstallStatus.SUCCESS
    return InstallReport(
        status=status,
        skill_name=skill.name,
        version=skill.metadata.version,
        source=opts.source_url,
        converted_from=skill.metadata.converted_from,
        target=str(target),
        warnings=warnings,
    )


def _unknown_report(opts: PipelineOptions, message: str) -> InstallReport:  # pragma: no cover
    return InstallReport(
        status=InstallStatus.FAILED,
        skill_name=opts.name or "unknown",
        version=opts.version or "—",
        source=opts.source_url,
        converted_from=SkillFormat.UNKNOWN,
        error=message,
    )
