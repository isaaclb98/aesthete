#!/usr/bin/env python3
"""
Aesthete — LLM-powered recommendation engine.
Reads liked items from a text file, infers taste profile via GPT-4o,
then generates ranked, media-type-grouped recommendations.
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


def read_file(path: str) -> list[str]:
    """Read a text file, one item per line. Strip whitespace, filter empty lines."""
    with open(path, "r", encoding="utf-8") as f:
        if f.seek(0, 2) > MAX_FILE_SIZE:
            raise ValueError(f"File too large (max {MAX_FILE_SIZE} bytes): {path}")
        f.seek(0)
        return [line.strip() for line in f if line.strip()]


def _json_escape(items: list[str]) -> str:
    """Join items as a JSON-raw string, stripped of surrounding quotes."""
    return ", ".join(json.dumps(item)[1:-1] for item in items)


def build_inference_prompt(likes: list[str]) -> tuple[str, str]:
    """
    Build the system and user prompts for taste inference.
    Returns (system_prompt, user_prompt).
    """
    system_template = INFERENCE_PROMPT_PATH.read_text(encoding="utf-8")
    likes_str = _json_escape(likes)
    system_prompt = system_template
    user_prompt = f"Favourites:\n{likes_str}"
    return system_prompt, user_prompt


def build_recommendation_prompt(taste_analysis: dict, likes: list[str]) -> tuple[str, str]:
    """
    Build the system and user prompts for recommendation generation.
    Returns (system_prompt, user_prompt).
    """
    system_template = RECOMMENDATION_PROMPT_PATH.read_text(encoding="utf-8")
    likes_str = _json_escape(likes)
    system_prompt = system_template.format(
        taste_analysis=json.dumps(taste_analysis, indent=2),
        likes=likes_str,
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


def infer_taste(likes: list[str], model: str = "gpt-4o") -> dict:
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
    taste_analysis: dict, likes: list[str], model: str = "gpt-4o"
) -> list[dict]:
    """
    Call the recommendation prompt with the pre-computed taste analysis.
    Returns a list of recommendation dicts.
    """
    system_prompt, user_prompt = build_recommendation_prompt(taste_analysis, likes)
    raw = call_openai(system_prompt, user_prompt, model)
    data = parse_response(raw)

    recommendations = data.get("recommendations", [])
    if not recommendations:
        raise ValueError("no recommendations in response")

    return recommendations


def parse_response(raw: str) -> dict:
    """
    Parse the API response text as JSON.
    Handles markdown-wrapped code blocks (e.g. ```json ... ```).
    """
    text = raw.strip()

    # Strip markdown code block wrapper if present
    if text.startswith("```"):
        # Remove the first line (```json or ```) and trailing ```
        lines = text.splitlines()
        # Find the last ``` line
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
        help="Path to text file with liked items (one per line)",
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
        recommendations = generate_recommendations(taste_analysis, likes, args.model)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
        return  # unreachable in normal execution; needed when sys.exit is mocked

    # Group and print
    grouped = group_by_media_type(recommendations)
    print_json({"taste_analysis": taste_analysis, "recommendations": grouped})


if __name__ == "__main__":
    main()
