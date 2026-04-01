#!/usr/bin/env python3
"""
Aesthete — LLM-powered recommendation engine.
Reads liked items from a text file (format: "media_type: item_name"),
infers taste profile via GPT-4o, then generates proportional and cross-media recommendations.
"""

import argparse
import json
import os
import sys
from collections import OrderedDict
from pathlib import Path

from dotenv import load_dotenv

# Load API key from .env
load_dotenv()

INFERENCE_PROMPT_PATH = Path(__file__).parent / "prompts" / "infer_taste.md"
RECOMMENDATION_PROMPT_PATH = Path(__file__).parent / "prompts" / "recommend_system.md"
MAX_FILE_SIZE = 1024 * 1024  # 1 MB


def read_file(path: str) -> list[tuple[str, str]]:
    """
    Read a text file, one item per line, in "media_type: item_name" format.
    Returns list of (media_type, item_name) tuples.
    """
    with open(path, "r", encoding="utf-8") as f:
        if f.seek(0, 2) > MAX_FILE_SIZE:
            raise ValueError(f"File too large (max {MAX_FILE_SIZE} bytes): {path}")
        f.seek(0)
        items = []
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Split on first ": " to separate media_type from item name
            if ": " in line:
                media_type, item_name = line.split(": ", 1)
                items.append((media_type.strip(), item_name.strip()))
            else:
                # Bare item — treat as unknown type
                items.append(("unknown", line))
        return items


def _format_likes_for_prompt(likes: list[tuple[str, str]]) -> str:
    """Format typed likes as lines for prompt injection."""
    return "\n".join(f"{media_type}: {item}" for media_type, item in likes)


def _compute_proportions(likes: list[tuple[str, str]]) -> str:
    """Compute input proportions for the recommendation prompt."""
    total = len(likes)
    if total == 0:
        return "No input types recorded."
    type_counts: dict[str, int] = {}
    for media_type, _ in likes:
        type_counts[media_type] = type_counts.get(media_type, 0) + 1
    parts = []
    for media_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        pct = round(count / total * 100)
        parts.append(f"{pct}% {media_type} ({count} item{'s' if count > 1 else ''})")
    return ", ".join(parts)


def build_inference_prompt(likes: list[tuple[str, str]]) -> tuple[str, str]:
    """
    Build the system and user prompts for taste inference.
    Returns (system_prompt, user_prompt).
    """
    system_template = INFERENCE_PROMPT_PATH.read_text(encoding="utf-8")
    likes_str = _format_likes_for_prompt(likes)
    system_prompt = system_template
    user_prompt = f"Favourites:\n{likes_str}"
    return system_prompt, user_prompt


def build_recommendation_prompt(
    taste_analysis: dict, likes: list[tuple[str, str]]
) -> tuple[str, str]:
    """
    Build the system and user prompts for recommendation generation.
    Returns (system_prompt, user_prompt).
    """
    system_template = RECOMMENDATION_PROMPT_PATH.read_text(encoding="utf-8")
    likes_str = _format_likes_for_prompt(likes)
    proportions = _compute_proportions(likes)
    system_prompt = system_template.format(
        taste_analysis=json.dumps(taste_analysis, indent=2),
        likes=f"{likes_str}\n\nInput proportions: {proportions}",
    )
    user_prompt = "Generate recommendations that match the taste profile above."
    return system_prompt, user_prompt


def call_openai(system_prompt: str, user_prompt: str, model: str = "gpt-4o") -> str:
    """Call the OpenAI API and return the raw response text."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Create a .env file with OPENAI_API_KEY=sk-..."
        )

    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=30.0)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    if not response.choices:
        raise ValueError("OpenAI returned no choices")

    content = response.choices[0].message.content
    if content is None:
        raise ValueError("OpenAI returned an empty response (content is None)")

    return content


def infer_taste(likes: list[tuple[str, str]], model: str = "gpt-4o") -> dict:
    """
    Call the taste inference prompt and return the parsed taste analysis.
    """
    system_prompt, user_prompt = build_inference_prompt(likes)
    raw = call_openai(system_prompt, user_prompt, model)
    data = parse_response(raw)

    required_keys = {"core_dimensions", "resonant_qualities", "negative_space", "discovery_leverage"}
    if not required_keys.issubset(data.keys()):
        missing = required_keys - set(data.keys())
        raise ValueError(f"Taste inference missing required fields: {missing}")

    return data


def generate_recommendations(
    taste_analysis: dict, likes: list[tuple[str, str]], model: str = "gpt-4o"
) -> tuple[list[dict], list[dict]]:
    """
    Call the recommendation prompt with the pre-computed taste analysis.
    Returns (proportional_recommendations, cross_media_recommendations).
    """
    system_prompt, user_prompt = build_recommendation_prompt(taste_analysis, likes)
    raw = call_openai(system_prompt, user_prompt, model)
    data = parse_response(raw)

    proportional = data.get("proportional_recommendations", [])
    cross_media = data.get("cross_media_recommendations", [])

    if not proportional and not cross_media:
        raise ValueError("no recommendations in response")

    return proportional, cross_media


def parse_response(raw: str) -> dict:
    """
    Parse the API response text as JSON.
    Handles markdown-wrapped code blocks (e.g. ```json ... ```).
    """
    text = raw.strip()

    # Strip markdown code block wrapper if present
    if text.startswith("```"):
        lines = text.splitlines()
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip() == "```":
                lines = lines[1:i]
                break
        text = "\n".join(lines)

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        snippet = text[:200] + ("..." if len(text) > 200 else "")
        raise ValueError(f"Failed to parse JSON response: {e}\nSnippet: {snippet}")


def group_by_media_type(recommendations: list[dict]) -> OrderedDict[str, list[dict]]:
    """
    Group recommendations by media_type and assign rank within each group.
    Returns an OrderedDict[media_type, list[with rank field]].
    """
    groups: OrderedDict[str, list[dict]] = OrderedDict()
    for rec in recommendations:
        media_type = rec.get("media_type", "unknown")
        if media_type not in groups:
            groups[media_type] = []
        groups[media_type].append({**rec})

    for media_type, recs in groups.items():
        for i, rec in enumerate(recs, start=1):
            rec["rank"] = i

    return groups


def print_json(data: dict) -> None:
    """Print data as JSON to stdout."""
    print(json.dumps(data, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Aesthete — LLM recommendation engine")
    parser.add_argument(
        "--likes",
        required=True,
        help='Path to text file with liked items (one per line, format: "media_type: item_name")',
    )
    parser.add_argument(
        "--model",
        default="gpt-4o",
        help="OpenAI model to use (default: gpt-4o)",
    )
    args = parser.parse_args()

    # Read likes
    try:
        likes = read_file(args.likes)
    except FileNotFoundError:
        print(f"Error: file not found: {args.likes}", file=sys.stderr)
        sys.exit(1)
        return  # unreachable in normal execution; needed when sys.exit is mocked

    if not likes:
        raise ValueError("likes file is empty")

    # Step 1: infer taste
    try:
        taste_analysis = infer_taste(likes, args.model)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
        return  # unreachable in normal execution; needed when sys.exit is mocked

    # Step 2: generate recommendations
    try:
        proportional, cross_media = generate_recommendations(taste_analysis, likes, args.model)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
        return  # unreachable in normal execution; needed when sys.exit is mocked

    # Group proportional recs by media type
    grouped_proportional = group_by_media_type(proportional)
    print_json({
        "taste_analysis": taste_analysis,
        "proportional_recommendations": grouped_proportional,
        "cross_media_recommendations": cross_media,
    })


if __name__ == "__main__":
    main()
