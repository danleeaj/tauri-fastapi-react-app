# Prompts for subtitle translation API

import json


def get_translation_prompt(
    target_language: str,
    context_before: list[dict],
    texts_to_translate: list[dict],
    context_after: list[dict]
) -> str:
    """Generate the translation prompt for subtitle batches."""
    return f"""Translate subtitle dialogue to {target_language}.

CONTEXT (PREVIOUS - DO NOT TRANSLATE):
{json.dumps(context_before, indent=2) if context_before else "None"}

INPUT TO TRANSLATE:
{json.dumps(texts_to_translate, indent=2)}

CONTEXT (NEXT - DO NOT TRANSLATE):
{json.dumps(context_after, indent=2) if context_after else "None"}

INSTRUCTIONS:
- ONLY translate the subtitles in "INPUT TO TRANSLATE"
- Use context for dialogue continuity
- Preserve line breaks (\\n)
- Keep translations concise

OUTPUT (JSON):
[{{"id": 1, "text": "translated"}}]
"""
