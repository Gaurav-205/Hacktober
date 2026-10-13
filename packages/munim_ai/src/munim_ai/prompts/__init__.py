"""Prompt files with a version header (docs/AI_SPEC.md section 4).

Each file starts with `prompt_version: N` and a `---` line. The version is saved with every
read and is part of the replay key, so changing a prompt means bumping its version and
re-running the evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from importlib import resources

from munim_ai.schemas import FieldSpec, compact_schema

__all__ = ["Prompt", "extraction_prompt", "load", "reread_prompt", "strict_suffix"]


@dataclass(frozen=True)
class Prompt:
    version: str
    text: str


@cache
def load(name: str) -> Prompt:
    raw = resources.files("munim_ai.prompts").joinpath(name).read_text(encoding="utf-8")
    header, sep, body = raw.partition("\n---\n")
    if not sep or not header.startswith("prompt_version:"):
        raise ValueError(f"prompt file {name} has no 'prompt_version: N' header")
    return Prompt(version=header.split(":", 1)[1].strip(), text=body.strip())


def extraction_prompt(kind: str) -> Prompt:
    """The system prompt for reading one paper, with the JSON shape filled in."""
    prompt = load(f"{kind}.system.md")
    return Prompt(prompt.version, prompt.text.replace("{schema}", compact_schema(kind)))


def reread_prompt(spec: FieldSpec) -> Prompt:
    """The single-field prompt. It gives the field's format, never the value read before."""
    prompt = load("reread.system.md")
    text = prompt.text.replace("{field_label}", spec.label).replace(
        "{format_hint}", spec.format_hint
    )
    return Prompt(prompt.version, "\n".join(line for line in text.splitlines() if line.strip()))


def strict_suffix() -> str:
    return load("strict_suffix.md").text


USER_TURN = {
    "invoice": "Read this tax invoice.",
    "challan": "Read this delivery challan.",
    "po": "Read this purchase order.",
}
