"""Image understanding through an optional local Ollama vision model.

The image is converted into a detailed text description, which then flows into
the normal orchestration pipeline like any other input.
"""

from __future__ import annotations

import base64

from ..llm.ollama import OllamaClient, OllamaError

VISION_PROMPT = (
    "Describe this image in detail for a technical assistant. Transcribe any visible text, labels, numbers, "
    "axes, table contents, circuit components, chemical or biological sequences exactly. Describe diagrams, "
    "charts and objects factually. Do not guess at anything you cannot see."
)

INSTALL_HINT = (
    "No vision model is installed, so images cannot be read yet. Install one with Ollama, e.g. "
    "`ollama pull qwen2.5vl:3b` (≈3.2 GB) or the lighter `ollama pull moondream` (≈1.7 GB), then try again."
)


class VisionUnavailable(RuntimeError):
    pass


async def describe_image(client: OllamaClient, data: bytes, hint: str = "") -> tuple[str, str]:
    model = await client.resolve_vision_model()
    if not model:
        raise VisionUnavailable(INSTALL_HINT)
    prompt = VISION_PROMPT + (f"\nThe user says: {hint}" if hint else "")
    try:
        text = await client.describe_image(model, base64.b64encode(data).decode(), prompt)
    except OllamaError as exc:
        raise VisionUnavailable(str(exc)) from exc
    return model, text
