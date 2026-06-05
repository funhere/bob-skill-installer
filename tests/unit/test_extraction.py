"""Unit tests for markdown content extraction."""

from __future__ import annotations

from bob_skill_installer.converters.extraction import (
    extract_content,
    parse_frontmatter,
    split_sections,
)


def test_parse_frontmatter_basic() -> None:
    text = "---\nname: x\nversion: 1.0\n---\n\n# Body\n"
    front, body = parse_frontmatter(text)
    assert front == {"name": "x", "version": 1.0}
    assert body.strip() == "# Body"


def test_parse_frontmatter_tolerates_leading_whitespace() -> None:
    text = "\n\n---\nname: y\n---\nbody"
    front, _ = parse_frontmatter(text)
    assert front["name"] == "y"


def test_parse_frontmatter_none() -> None:
    front, body = parse_frontmatter("# No frontmatter\ntext")
    assert front == {}
    assert body.startswith("# No frontmatter")


def test_parse_frontmatter_invalid_yaml() -> None:
    front, _ = parse_frontmatter("---\n: : :\nfoo bar\n---\nbody")
    assert front == {}


def test_split_sections() -> None:
    md = "intro\n\n# A\nbody a\n\n## B\nbody b"
    sections = split_sections(md)
    titles = [t for t, _ in sections]
    assert "A" in titles and "B" in titles


def test_extract_classifies_sections() -> None:
    doc = (
        "# Skill\n"
        "## Role\nYou are a helper.\n"
        "## Objective\nDo good work.\n"
        "## Workflow\n- step one\n- step two\n"
        "## Instructions\n- be precise\n"
        "## Constraints\n- never guess\n"
        "## Tools\n- ripgrep\n"
        "## Examples\n```py\nprint(1)\n```\n"
    )
    content = extract_content([doc])
    assert content.role == "You are a helper."
    assert content.objective == "Do good work."
    assert content.workflow == ["step one", "step two"]
    assert content.instructions == ["be precise"]
    assert content.constraints == ["never guess"]
    assert content.tools == ["ripgrep"]
    assert content.examples and "print(1)" in content.examples[0]


def test_extract_objective_fallback_to_first_paragraph() -> None:
    content = extract_content(["# Title\n\nThis is the intro paragraph.\n\nMore."])
    assert content.objective == "This is the intro paragraph."


def test_extract_dedupes_and_finds_mcp() -> None:
    doc = (
        "## Workflow\n- a\n- a\n- b\n"
        "Uses the mcp-server and model-context-protocol bridge. Also MCP-Server again.\n"
    )
    content = extract_content([doc])
    assert content.workflow == ["a", "b"]
    # Case-insensitive de-dup keeps first spelling only.
    assert any(ref.lower().startswith("mcp") for ref in content.mcp_references)
    lowered = [r.lower() for r in content.mcp_references]
    assert len(lowered) == len(set(lowered))


def test_extract_merges_multiple_documents() -> None:
    content = extract_content(["## Objective\nOne.", "## Workflow\n- x"])
    assert content.objective == "One."
    assert content.workflow == ["x"]
