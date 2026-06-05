"""Format-agnostic content extraction from Markdown.

Converters feed one or more source markdown documents in here and get back a
normalized :class:`ExtractedContent` (role / objective / workflow / instructions
/ constraints / examples / tools / MCP references). The heuristics are heading-
and list-driven so they degrade gracefully on loosely structured prompt repos.
"""

from __future__ import annotations

import re

import yaml

from bob_skill_installer.models import ExtractedContent

_FRONTMATTER_RE = re.compile(r"^[﻿\s]*---[ \t]*\n(.*?)\n---[ \t]*\n", re.DOTALL)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")
_MCP_RE = re.compile(r"\b(mcp[\w./-]*|model[- ]context[- ]protocol)\b", re.IGNORECASE)

# Heading keyword -> target field.
_SECTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "role": ("role", "you are", "persona", "identity", "who you are"),
    "objective": ("objective", "goal", "purpose", "overview", "summary", "about", "mission"),
    "workflow": ("workflow", "steps", "process", "procedure", "pipeline", "how it works"),
    "instructions": (
        "instruction", "rule", "guideline", "how to", "usage", "behavior", "best practice",
    ),
    "constraints": (
        "constraint", "limitation", "do not", "don't", "avoid", "restriction", "anti-pattern",
    ),
    "examples": ("example", "demo", "sample"),
    "tools": ("tool", "command", "capabilit", "function", "skill"),
}


def parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    """Split optional YAML frontmatter from a document body."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}, text
    if not isinstance(data, dict):
        return {}, text
    return data, text[match.end():]


def split_sections(markdown: str) -> list[tuple[str, str]]:
    """Split markdown into ``(heading_title, body)`` pairs.

    Content before the first heading is returned under an empty title.
    """
    sections: list[tuple[str, str]] = []
    current_title = ""
    current_lines: list[str] = []
    for line in markdown.splitlines():
        heading = _HEADING_RE.match(line)
        if heading:
            sections.append((current_title, "\n".join(current_lines).strip()))
            current_title = heading.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)
    sections.append((current_title, "\n".join(current_lines).strip()))
    return [(t, b) for t, b in sections if t or b]


def _classify(title: str) -> str | None:
    low = title.lower()
    for field, keywords in _SECTION_KEYWORDS.items():
        if any(kw in low for kw in keywords):
            return field
    return None


def _list_items(body: str) -> list[str]:
    items: list[str] = []
    for line in body.splitlines():
        m = _LIST_RE.match(line)
        if m:
            items.append(m.group(1).strip())
    return items


def _first_paragraph(text: str) -> str:
    for block in re.split(r"\n\s*\n", text.strip()):
        cleaned = block.strip()
        if cleaned and not cleaned.startswith("#"):
            return " ".join(cleaned.split())
    return ""


def extract_content(documents: list[str], *, fallback_objective: str = "") -> ExtractedContent:
    """Merge one or more markdown documents into :class:`ExtractedContent`."""
    content = ExtractedContent()
    merged_body: list[str] = []

    for raw in documents:
        _, body = parse_frontmatter(raw)
        merged_body.append(body.strip())
        for title, section_body in split_sections(body):
            field = _classify(title)
            if field == "role" and not content.role:
                content.role = _first_paragraph(section_body) or section_body.strip()
            elif field == "objective" and not content.objective:
                content.objective = _first_paragraph(section_body) or section_body.strip()
            elif field == "workflow":
                content.workflow.extend(_list_items(section_body))
            elif field == "instructions":
                content.instructions.extend(_list_items(section_body))
            elif field == "constraints":
                content.constraints.extend(_list_items(section_body))
            elif field == "tools":
                content.tools.extend(_list_items(section_body))
            elif field == "examples" and section_body:
                content.examples.append(section_body.strip())

    content.body_markdown = "\n\n".join(b for b in merged_body if b).strip()

    if not content.objective:
        content.objective = (
            _first_paragraph(content.body_markdown) or fallback_objective or "Converted skill."
        )

    # MCP references across the whole corpus, de-duplicated, order-preserving.
    seen: set[str] = set()
    for ref in _MCP_RE.findall(content.body_markdown):
        token = ref if isinstance(ref, str) else ref[0]
        key = token.lower()
        if key not in seen:
            seen.add(key)
            content.mcp_references.append(token)

    # De-dupe list fields while preserving order.
    content.workflow = _dedupe(content.workflow)
    content.instructions = _dedupe(content.instructions)
    content.constraints = _dedupe(content.constraints)
    content.tools = _dedupe(content.tools)
    return content


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out
