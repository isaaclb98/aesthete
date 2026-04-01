#!/usr/bin/env python3
"""
Aesthete — LLM-powered recommendation engine.
Reads liked/disliked items from text files and prints ranked,
media-type-grouped recommendations from OpenAI.
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

SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "recommend_system.md"


def read_file(path: str) -> list[str]:
    """Read a text file, one item per line. Strip whitespace, filter empty lines."""
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def build_prompt(likes: list[str], dislikes: list[str] | None = None) -> tuple[str, str]:
    """
    Build the system and user prompts from the template.
    Returns (system_prompt, user_prompt).
    """
    system_template = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

    likes_str = ", ".join(likes)
    dislikes_str = ", ".join(dislikes) if dislikes else "none"

    system_prompt = system_template.format(likes=likes_str, dislikes=dislikes_str)

    user_prompt = f"Liked: {likes_str}\nDisliked: {dislikes_str}\nExclude these already-consumed items: none\n\nGenerate recommendations that match the taste profile above."
    return system_prompt, user_prompt


def call_openai(system_prompt: str, user_prompt: str, model: str = "gpt-4o") -> str:
    """Call the OpenAI API and return the raw response text."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Create a .env file with OPENAI_API_KEY=sk-..."
        )

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content


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
        groups[media_type].append(rec)

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
        "--dislikes",
        help="Path to text file with disliked items (one per line, optional)",
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

    if not likes:
        raise ValueError("likes file is empty")

    # Read dislikes (optional)
    dislikes = None
    if args.dislikes:
        try:
            dislikes = read_file(args.dislikes)
        except FileNotFoundError:
            # Skip dislikes if file is missing
            pass

    # Build prompt
    system_prompt, user_prompt = build_prompt(likes, dislikes)

    # Call API
    try:
        raw = call_openai(system_prompt, user_prompt, args.model)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Parse response
    try:
        data = parse_response(raw)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    recommendations = data.get("recommendations", [])
    if not recommendations:
        raise ValueError("no recommendations in response")

    # Group and print
    grouped = group_by_media_type(recommendations)
    print_json({"recommendations": grouped})


if __name__ == "__main__":
    main()
