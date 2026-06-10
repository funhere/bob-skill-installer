"""Typer CLI: ``install-skill <url> [--global|--project] [...]``.

This is the programmatic counterpart to the IBM Bob ``/install-skill`` slash
command. The slash command (see ``.bob/commands/install-skill.md``) handles the
conversational confirm-first flow and the ``anysearch`` repository summarization;
this CLI runs the deterministic pipeline and prints the install report.
"""

from __future__ import annotations

import logging
from pathlib import Path

import typer

from bob_skill_installer import __version__
from bob_skill_installer.exceptions import InstallerError
from bob_skill_installer.installer import PipelineOptions, run_install
from bob_skill_installer.logging_config import configure
from bob_skill_installer.models import InstallReport, InstallScope, InstallStatus, SkillFormat
from bob_skill_installer.report import render_plaintext, render_report

app = typer.Typer(
    add_completion=False,
    help="Download, convert, validate, and install third-party AI skills into IBM Bob.",
)

_FAILURE_EXIT = {InstallStatus.REJECTED: 8, InstallStatus.FAILED: 7}


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"bob-skill-installer {__version__}")
        raise typer.Exit()


@app.command()
def install(  # noqa: PLR0913 - a CLI surface legitimately has many flags
    ctx: typer.Context,
    url: str | None = typer.Argument(None, help="Source URL (GitHub/GitLab/git/.zip)."),
    global_: bool = typer.Option(
        False, "--global", "-g", help="Install to ~/.bob/skills (user-global)."
    ),
    project: bool = typer.Option(
        False, "--project", "-p", help="Install to ./.bob/skills (default)."
    ),
    name: str | None = typer.Option(None, "--name", help="Override the skill name."),
    author: str | None = typer.Option(None, "--author", help="Override the skill author."),
    version: str | None = typer.Option(None, "--skill-version", help="Override skill version."),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite an existing skill."),
    upgrade: bool = typer.Option(
        False, "--upgrade", "-u", help="Replace an existing skill, keeping a .bak."
    ),
    no_scripts: bool = typer.Option(
        False, "--no-scripts", help="Exclude the source's executable scripts (included by default)."
    ),
    no_secrets: bool = typer.Option(
        False, "--no-secrets", help="Exclude secret files like .env / keys (included by default)."
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Run every stage but do not write."),
    json_out: bool = typer.Option(False, "--json", help="Emit the report as plain text on stdout."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging."),
    log_file: Path | None = typer.Option(None, "--log-file", help="Also write logs to a file."),
    _version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show version and exit."
    ),
) -> None:
    if url is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()

    configure(level=logging.DEBUG if verbose else logging.INFO, log_file=log_file, quiet=json_out)

    if global_ and project:
        typer.secho("Choose only one of --global / --project.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    scope = InstallScope.GLOBAL if global_ else InstallScope.PROJECT

    opts = PipelineOptions(
        source_url=url,
        scope=scope,
        name=name,
        author=author,
        version=version,
        overwrite=force,
        upgrade=upgrade,
        exclude_scripts=no_scripts,
        exclude_secrets=no_secrets,
        dry_run=dry_run,
    )

    try:
        report = run_install(opts)
    except InstallerError as exc:
        report = InstallReport(
            status=InstallStatus.FAILED,
            skill_name=name or "unknown",
            version=version or "—",
            source=url,
            converted_from=SkillFormat.UNKNOWN,
            error=str(exc),
        )
        _emit(report, json_out)
        raise typer.Exit(code=exc.exit_code) from exc

    _emit(report, json_out)
    raise typer.Exit(code=_FAILURE_EXIT.get(report.status, 0))


def _emit(report: InstallReport, json_out: bool) -> None:
    if json_out:
        typer.echo(render_plaintext(report))
    else:
        render_report(report)


if __name__ == "__main__":  # pragma: no cover
    app()
