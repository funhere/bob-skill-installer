"""Map a detected :class:`SkillFormat` to the converter that handles it.

The registry tries the converter matching the analysis's best-scoring format
first, then falls back through the remaining converters by priority, and finally
to the generic converter — so a repo that *looks* like Cursor but only has a
usable README still converts.
"""

from __future__ import annotations

from bob_skill_installer.converters.base import BaseConverter, ConversionContext
from bob_skill_installer.converters.claude import ClaudeConverter
from bob_skill_installer.converters.cline import ClineConverter
from bob_skill_installer.converters.cursor import CursorConverter
from bob_skill_installer.converters.generic import GenericConverter
from bob_skill_installer.converters.openai import OpenAIConverter
from bob_skill_installer.converters.roocode import RooCodeConverter
from bob_skill_installer.converters.windsurf import WindsurfConverter
from bob_skill_installer.exceptions import ConversionError
from bob_skill_installer.models import BobSkill, RepoAnalysis, SkillFormat

# Priority order from the spec: Claude > Cursor > Windsurf > Cline > RooCode >
# OpenAI > Generic.
_CONVERTERS: list[BaseConverter] = [
    ClaudeConverter(),
    CursorConverter(),
    WindsurfConverter(),
    ClineConverter(),
    RooCodeConverter(),
    OpenAIConverter(),
    GenericConverter(),
]

_BY_FORMAT: dict[SkillFormat, BaseConverter] = {c.source_format: c for c in _CONVERTERS}


def get_converter(fmt: SkillFormat) -> BaseConverter | None:
    """Return the converter registered for ``fmt`` (or ``None``)."""
    return _BY_FORMAT.get(fmt)


def convert(analysis: RepoAnalysis, ctx: ConversionContext) -> BobSkill:
    """Convert ``analysis`` into a :class:`BobSkill`, choosing the best converter.

    Raises:
        ConversionError: if no converter (not even generic) can handle the tree.
    """
    ordered: list[BaseConverter] = []
    best = _BY_FORMAT.get(analysis.best_format)
    if best is not None:
        ordered.append(best)
    ordered.extend(c for c in _CONVERTERS if c not in ordered)

    errors: list[str] = []
    for converter in ordered:
        if converter.can_convert(analysis):
            try:
                return converter.convert(analysis, ctx)
            except ConversionError as exc:  # try the next candidate
                errors.append(str(exc))
                continue
    detail = "; ".join(errors) if errors else "no converter matched the source tree"
    raise ConversionError(f"Conversion failed: {detail}")
