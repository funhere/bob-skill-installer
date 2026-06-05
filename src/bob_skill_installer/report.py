"""Build and render the installation report.

Two renderings are offered: a rich panel for interactive terminals and a plain
text block that matches the spec's example layout (used for ``--no-color`` and
for copy-paste into issues/PRs).
"""

from __future__ import annotations

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from bob_skill_installer.logging_config import console
from bob_skill_installer.models import InstallReport, InstallStatus

_STATUS_STYLE = {
    InstallStatus.SUCCESS: "bold green",
    InstallStatus.SUCCESS_WITH_WARNINGS: "bold yellow",
    InstallStatus.FAILED: "bold red",
    InstallStatus.REJECTED: "bold red",
}


def render_report(report: InstallReport) -> None:
    """Print ``report`` as a rich panel to the shared console."""
    style = _STATUS_STYLE.get(report.status, "bold")
    table = Table.grid(padding=(0, 2))
    table.add_column(justify="right", style="dim")
    table.add_column()
    table.add_row("Status", Text(report.status.value, style=style))
    table.add_row("Skill", report.skill_name)
    table.add_row("Version", report.version)
    table.add_row("Source", report.source)
    table.add_row("Converted From", report.converted_from.value)
    table.add_row("Installed To", report.target or "—")
    if report.warnings:
        table.add_row("Warnings", "\n".join(f"• {w}" for w in report.warnings))
    else:
        table.add_row("Warnings", "None")
    if report.error:
        table.add_row("Error", Text(report.error, style="red"))
    console.print(Panel(table, title="Installation Report", border_style=style))


def render_plaintext(report: InstallReport) -> str:
    """Return the spec-style plain-text report."""
    lines = [
        report.status.value,
        f"Skill: {report.skill_name}",
        f"Version: {report.version}",
        f"Source: {report.source}",
        f"Converted From: {report.converted_from.value}",
        f"Installed To: {report.target or '-'}",
    ]
    if report.warnings:
        lines.append("Warnings:")
        lines.extend(f"  - {w}" for w in report.warnings)
    else:
        lines.append("Warnings: None")
    if report.error:
        lines.append(f"Error: {report.error}")
    return "\n".join(lines)
