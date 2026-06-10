"""Unit tests for converters and the converter registry."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from bob_skill_installer.analyzer import analyze_repo
from bob_skill_installer.converters import ConversionContext, convert, get_converter
from bob_skill_installer.converters.extraction import parse_frontmatter
from bob_skill_installer.exceptions import ConversionError
from bob_skill_installer.models import SkillFormat

_ALL = ["claude", "cursor", "windsurf", "cline", "roocode", "openai", "generic"]


def _convert(root: Path, url: str = "https://github.com/org/sample") -> object:
    analysis = analyze_repo(root)
    return convert(analysis, ConversionContext(source_url=url))


@pytest.mark.parametrize("kind", _ALL)
def test_each_format_converts(repo_factory: Callable[[str], Path], kind: str) -> None:
    skill = _convert(repo_factory(kind))
    assert skill.skill_md.startswith("---")
    front, _ = parse_frontmatter(skill.skill_md)
    for field in ("name", "description", "version", "source", "converted_from", "created_at"):
        assert field in front and str(front[field]).strip()


def test_claude_metadata_from_frontmatter(repo_factory: Callable[[str], Path]) -> None:
    skill = _convert(repo_factory("claude"))
    assert skill.metadata.name == "react-architect"
    assert skill.metadata.version == "2.1.0"
    assert skill.metadata.author == "Jane Dev"
    assert skill.metadata.converted_from is SkillFormat.CLAUDE


def test_name_override_wins(repo_factory: Callable[[str], Path]) -> None:
    analysis = analyze_repo(repo_factory("claude"))
    skill = convert(
        analysis,
        ConversionContext(source_url="https://github.com/org/sample", name_override="My Skill"),
    )
    assert skill.metadata.name == "my-skill"


def test_name_derived_from_repo_when_no_frontmatter_name(
    repo_factory: Callable[[str], Path],
) -> None:
    skill = _convert(repo_factory("generic"), url="https://github.com/org/prompt-pack")
    assert skill.metadata.name == "prompt-pack"


def test_files_preserved_at_original_paths(
    repo_factory: Callable[[str], Path],
) -> None:
    skill = _convert(repo_factory("claude"))
    paths = {str(f.relative_path) for f in skill.files}
    # README is bundled at its ORIGINAL path (not buried under docs/).
    assert "README.md" in paths
    assert not any(p.startswith("docs/") for p in paths)
    # The primary CLAUDE.md was consumed into SKILL.md, not duplicated.
    assert "CLAUDE.md" not in paths


def test_scripts_included_by_default_excluded_on_opt_out(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    (root / "CLAUDE.md").write_text(
        "---\nname: s\ndescription: d\n---\n# S\n## Objective\nx\n", encoding="utf-8"
    )
    (root / "scripts" / "run.sh").write_text("#!/bin/sh\necho hi\n", encoding="utf-8")
    (root / "data.json").write_text('{"k": 1}', encoding="utf-8")
    analysis = analyze_repo(root)
    url = "https://github.com/org/s"

    default_skill = convert(analysis, ConversionContext(source_url=url))
    default_paths = {str(f.relative_path) for f in default_skill.files}
    assert "data.json" in default_paths  # non-markdown asset preserved
    assert "scripts/run.sh" in default_paths  # script bundled by default

    no_scripts = convert(
        analysis, ConversionContext(source_url=url, exclude_scripts=True)
    )
    paths = {str(f.relative_path) for f in no_scripts.files}
    assert "scripts/run.sh" not in paths  # excluded on opt-out
    assert "data.json" in paths  # other files still preserved


def test_secret_files_included_by_default_excluded_on_opt_out(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "CLAUDE.md").write_text(
        "---\nname: s\ndescription: d\n---\n# S\n## Objective\nx\n", encoding="utf-8"
    )
    (root / ".env").write_text("API_KEY=supersecret\n", encoding="utf-8")
    (root / "server.pem").write_text("-----BEGIN PRIVATE KEY-----\n", encoding="utf-8")
    analysis = analyze_repo(root)
    url = "https://github.com/org/s"

    default_skill = convert(analysis, ConversionContext(source_url=url))
    default_paths = {str(f.relative_path) for f in default_skill.files}
    assert ".env" in default_paths  # full fidelity: secrets copied by default
    assert "server.pem" in default_paths

    no_secrets = convert(analysis, ConversionContext(source_url=url, exclude_secrets=True))
    paths = {str(f.relative_path) for f in no_secrets.files}
    assert ".env" not in paths  # excluded on opt-out
    assert "server.pem" not in paths


def test_binary_assets_preserved_intact(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "CLAUDE.md").write_text(
        "---\nname: s\ndescription: d\n---\n# S\n## Objective\nx\n", encoding="utf-8"
    )
    png = b"\x89PNG\r\n\x1a\n\x00\x01\x02\x03\xff\xfe"
    (root / "logo.png").write_bytes(png)
    skill = _convert(root)
    asset = next(f for f in skill.files if str(f.relative_path) == "logo.png")
    assert asset.data == png  # bytes preserved exactly, not mangled as text


def test_author_override(repo_factory: Callable[[str], Path]) -> None:
    analysis = analyze_repo(repo_factory("openai"))
    skill = convert(
        analysis,
        ConversionContext(source_url="https://github.com/org/x", author_override="ACME"),
    )
    assert skill.metadata.author == "ACME"


def test_registry_lookup() -> None:
    assert get_converter(SkillFormat.CLAUDE) is not None
    assert get_converter(SkillFormat.UNKNOWN) is None


def test_convert_falls_back_to_generic(tmp_path: Path) -> None:
    # A repo that detects as nothing special but has a README still converts.
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("# Tool\n\nDoes things.\n")
    skill = _convert(root)
    assert skill.metadata.converted_from is SkillFormat.GENERIC


@pytest.mark.parametrize(
    "description",
    [
        "Code review: find bugs, smells, and risks",  # colon-space breaks naive YAML
        "# starts with a hash",
        'has "double" quotes',
        "日本語の説明: ローカルで動作",  # non-ASCII + colon
        "ends with a colon:",
    ],
)
def test_frontmatter_is_valid_yaml_for_special_descriptions(
    tmp_path: Path, description: str
) -> None:
    """Regression: metadata with YAML-special chars must still parse.

    Previously the frontmatter was string-templated, so a description containing
    a colon-space produced invalid YAML and validation reported "missing
    frontmatter". The frontmatter is now serialized via yaml.safe_dump.
    """
    root = tmp_path / "repo"
    root.mkdir()
    (root / "CLAUDE.md").write_text(
        f"---\nname: special\ndescription: {description!r}\nversion: 1.0.0\n---\n"
        "# Special\n## Objective\nDo work.\n",
        encoding="utf-8",
    )
    skill = _convert(root)
    front, _ = parse_frontmatter(skill.skill_md)
    assert front, "generated frontmatter failed to parse"
    assert front["description"] == description
    from bob_skill_installer.validators import validate_skill

    assert validate_skill(skill).ok


def test_convert_raises_when_unconvertible(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "data.json").write_text("{}")  # no markdown, nothing to convert
    analysis = analyze_repo(root)
    with pytest.raises(ConversionError):
        convert(analysis, ConversionContext(source_url="https://github.com/org/x"))
