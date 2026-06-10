"""Walk a fetched tree into a :class:`RepoAnalysis`.

This is deliberately deterministic and offline. The richer, model-driven
repository *summarization* (prompt/workflow extraction) is performed by the
``anysearch`` skill from inside the Bob slash command before this code runs;
here we collect the concrete file inventory the converters need.
"""

from __future__ import annotations

from pathlib import Path

from bob_skill_installer.analyzer.format_detector import detect_formats
from bob_skill_installer.exceptions import AnalysisError
from bob_skill_installer.logging_config import get_logger
from bob_skill_installer.models import RepoAnalysis

_log = get_logger("analyzer")

_IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".idea"}
_TEXT_EXTS = {
    ".md", ".mdc", ".markdown", ".txt", ".rst", ".yaml", ".yml", ".json", ".toml", ".cfg",
}
_MARKDOWN_EXTS = {".md", ".mdc", ".markdown"}
_SCRIPT_EXTS = {".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd", ".py", ".js", ".rb", ".pl"}
_README_NAMES = ("README.md", "readme.md", "Readme.md", "README.markdown")


def _is_ignored(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    return any(part in _IGNORE_DIRS for part in rel.parts)


def analyze_repo(root: Path) -> RepoAnalysis:
    """Inventory ``root`` and attach format detections.

    Raises:
        AnalysisError: if ``root`` is not a directory or contains no files.
    """
    if not root.is_dir():
        raise AnalysisError(f"Analysis root is not a directory: {root}")

    all_files: list[Path] = []
    text_files: list[Path] = []
    markdown_files: list[Path] = []
    script_files: list[Path] = []

    for path in sorted(root.rglob("*")):
        if path.is_dir() or _is_ignored(path, root):
            continue
        all_files.append(path)
        suffix = path.suffix.lower()
        if suffix in _TEXT_EXTS:
            text_files.append(path)
        if suffix in _MARKDOWN_EXTS:
            markdown_files.append(path)
        if suffix in _SCRIPT_EXTS or _is_executable(path):
            script_files.append(path)

    file_count = len(all_files)
    if file_count == 0:
        raise AnalysisError(f"Source tree {root} is empty.")

    readme = next((root / name for name in _README_NAMES if (root / name).exists()), None)
    detections = detect_formats(root)

    analysis = RepoAnalysis(
        root=root,
        file_count=file_count,
        all_files=all_files,
        text_files=text_files,
        markdown_files=markdown_files,
        script_files=script_files,
        detections=detections,
        readme=readme,
    )
    _log.info(
        "Analyzed %d files; best format: [bold]%s[/bold]",
        file_count,
        analysis.best_format.value,
    )
    return analysis


def _is_executable(path: Path) -> bool:
    try:
        return path.stat().st_mode & 0o111 != 0
    except OSError:  # pragma: no cover - race on stat
        return False
