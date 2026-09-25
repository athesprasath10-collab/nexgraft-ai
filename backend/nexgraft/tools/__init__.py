"""Tool registry: every module in this package exposes a TOOLS list."""

from __future__ import annotations

from .base import ToolInputError, ToolSpec, to_markdown
from .engineering import TOOLS as _ENGINEERING
from .literature import TOOLS as _LITERATURE
from .sequence import TOOLS as _SEQUENCE

TOOL_REGISTRY: dict[str, ToolSpec] = {t.id: t for t in (*_SEQUENCE, *_ENGINEERING, *_LITERATURE)}

__all__ = ["TOOL_REGISTRY", "ToolInputError", "ToolSpec", "to_markdown"]
