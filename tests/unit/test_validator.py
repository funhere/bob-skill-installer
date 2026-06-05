"""Unit tests for skill validation."""

from __future__ import annotations

from pathlib import Path

from bob_skill_installer.models import BobSkill, GeneratedFile, SkillFormat, SkillMetadata
from bob_skill_installer.validators import validate_skill

_GOOD_MD = """---
name: demo
description: A demo skill.
version: 0.1.0
source: https://github.com/org/demo
author: tester
converted_from: claude
created_at: 2026-01-01T00:00:00Z
---

# Demo

## Objective
Do the thing.

See [`docs/`](docs/) for more.
"""


def _skill(md: str, files: list[GeneratedFile] | None = None) -> BobSkill:
    meta = SkillMetadata(
        name="demo",
        description="A demo skill.",
        source="https://github.com/org/demo",
        converted_from=SkillFormat.CLAUDE,
    )
    return BobSkill(metadata=meta, skill_md=md, files=files or [])


def test_valid_skill_passes() -> None:
    files = [GeneratedFile(relative_path=Path("docs/README.md"), content="x")]
    result = validate_skill(_skill(_GOOD_MD, files))
    assert result.ok
    assert result.warnings == []


def test_empty_skill_md_blocks() -> None:
    result = validate_skill(_skill(""))
    assert not result.ok
    assert any(f.category == "structure" for f in result.findings)


def test_missing_frontmatter_blocks() -> None:
    result = validate_skill(_skill("# No frontmatter\n\n## Objective\nx\n"))
    assert not result.ok


def test_missing_required_field_blocks() -> None:
    md = _GOOD_MD.replace("version: 0.1.0\n", "")
    result = validate_skill(_skill(md))
    assert not result.ok
    assert any("version" in f.message for f in result.findings)


def test_unterminated_code_fence_warns() -> None:
    md = _GOOD_MD + "\n```python\nprint(1)\n"
    result = validate_skill(_skill(md, [GeneratedFile(relative_path=Path("docs/x.md"), content="x")]))
    assert result.ok  # non-blocking
    assert any(f.category == "markdown" for f in result.warnings)


def test_no_heading_warns() -> None:
    md = (
        "---\nname: demo\ndescription: d\nversion: 0.1.0\n"
        "source: https://x\nauthor: t\nconverted_from: claude\n"
        "created_at: 2026-01-01T00:00:00Z\n---\n\nPlain body with no markdown headings.\n"
    )
    result = validate_skill(_skill(md, [GeneratedFile(relative_path=Path("docs/x.md"), content="x")]))
    assert any(f.category == "markdown" for f in result.warnings)


def test_broken_internal_link_warns() -> None:
    md = _GOOD_MD.replace("[`docs/`](docs/)", "[missing](docs/missing.md)")
    result = validate_skill(_skill(md))  # no files -> link unresolved
    assert result.ok
    assert any(f.category == "references" for f in result.warnings)


def test_external_links_ignored() -> None:
    md = _GOOD_MD.replace("[`docs/`](docs/)", "[site](https://example.com)")
    result = validate_skill(_skill(md))
    assert not any(f.category == "references" for f in result.findings)
