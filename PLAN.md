# Plan: Aesthete v1 — Single-File LLM Recommendation Script

## What we're building

A Python script (`recommend.py`) that reads liked/disliked items from text files and prints ranked, media-type-grouped recommendations from OpenAI. Single API call. JSON stdout.

## File structure

```
aesthete/
├── recommend.py        # Single script — CLI + API + prompt + output
├── prompts/
│   └── recommend_system.md   # System prompt for the recommendation call
└── tests/
    └── test_recommend.py     # Unit tests
```

## Data flow

```
recommend.py
  │
  ├── argparse → reads --likes, --dislikes (optional)
  │
  ├── read_file() → strip lines, filter empty, return list[str]
  │
  ├── build_prompt(likes, dislikes) → inject into system prompt template
  │
  ├── call_openai(prompt) → client.chat.completions.create()
  │
  ├── parse_response(raw) → json.loads() with fallback for markdown code blocks
  │
  ├── group_by_media_type(recommendations) → OrderedDict[media_type, list]
  │
  └── print_json(grouped) → json.dumps → stdout
```

## Prompt design

System prompt (prompts/recommend_system.md):
- Role: recommendation engine with deep cross-media knowledge
- Input: liked items, disliked items (optional)
- Task: generate 8-12 recommendations matching aesthetic properties
- Output format: JSON with fields: `name`, `media_type`, `reason`, `confidence`
- Constraint: do not recommend items similar to disliked list
- Constraint: vary media types appropriately

User prompt:
```
Liked: {comma-separated likes}
Disliked: {comma-separated dislikes or "none"}
Exclude these already-consumed items: none

Generate recommendations...
```

## API integration

- Package: `openai` (pip install openai)
- API: `client.chat.completions.create(model="gpt-4o", messages=[...])`
- No streaming for v1 — wait for full response
- No retries — fail fast on error, raise exception

## CLI

```bash
python recommend.py --likes likes.txt [--dislikes dislikes.txt] [--model gpt-4o]
```

- `--likes`: required, path to text file (one item per line)
- `--dislikes`: optional, path to text file (one item per line)
- `--model`: optional, defaults to gpt-4o

## Error handling

| Scenario | Behavior |
|----------|----------|
| Missing --likes file | exit with error message |
| --dislikes file missing | skip dislikes, proceed |
| API error (auth, rate limit, timeout) | raise RuntimeError with message, exit 1 |
| JSON parse failure | raise ValueError with snippet, exit 1 |
| Empty likes file | raise ValueError("likes file is empty"), exit 1 |
| No recommendations returned | raise ValueError("no recommendations in response"), exit 1 |

## Output format

```json
{
  "recommendations": {
    "film": [
      {"rank": 1, "name": "...", "media_type": "film", "reason": "...", "confidence": "high"}
    ],
    "book": [...],
    "music": [...],
    "game": [...]
  }
}
```

## Test coverage

**Test file:** `tests/test_recommend.py`

### Unit tests (no API calls needed)

1. `read_file()` — normal case, strips whitespace, filters empty lines
2. `read_file()` — file not found → raises FileNotFoundError
3. `read_file()` — empty file → returns []
4. `build_prompt()` — includes likes, excludes dislikes when present
5. `build_prompt()` — omits dislikes section when dislikes empty
6. `parse_response()` — valid JSON → returns dict
7. `parse_response()` — markdown code block wrapper → strips and parses
8. `parse_response()` — invalid JSON → raises ValueError
9. `group_by_media_type()` — correctly groups and assigns rank within group
10. `group_by_media_type()` — empty list → returns empty groups

### Integration tests (require API key, skipped if not set)

11. `test_full_run_with_likes_only` — end-to-end with --likes only
12. `test_full_run_with_likes_and_dislikes` — end-to-end with both files

**Coverage diagram:**

```
CODE PATH COVERAGE
===========================
[+] recommend.py
    │
    ├── read_file()
    │   ├── [TESTED] Normal file with items — test_read_file
    │   ├── [TESTED] File not found — test_read_file_not_found
    │   └── [TESTED] Empty file — test_read_file_empty
    │
    ├── build_prompt()
    │   ├── [TESTED] Likes only — test_build_prompt_likes_only
    │   └── [TESTED] Likes + dislikes — test_build_prompt_with_dislikes
    │
    ├── call_openai()
    │   └── [GAP] API error propagation — no test (would need mock)
    │
    ├── parse_response()
    │   ├── [TESTED] Plain JSON — test_parse_response
    │   ├── [TESTED] Markdown code block — test_parse_response_markdown
    │   └── [TESTED] Invalid JSON — test_parse_response_invalid
    │
    ├── group_by_media_type()
    │   ├── [TESTED] Normal grouping — test_group_by_media_type
    │   └── [TESTED] Empty input — test_group_by_media_type_empty
    │
    └── main()
        ├── [TESTED] Missing likes file — test_main_missing_likes
        └── [TESTED] Empty likes file — test_main_empty_likes

USER FLOW COVERAGE
===========================
[+] CLI invocation
    ├── [TESTED] --likes only — test_full_run_likes_only (integration, skipped without API key)
    └── [TESTED] --likes --dislikes — test_full_run_likes_dislikes (integration, skipped without API key)

─────────────────────────────────
COVERAGE: 10/11 paths tested (91%)
  Code paths: 9/10 (90%)
  User flows: 1/1 (100%) + 1 integration
QUALITY:  ★★★: 8  ★★: 1  ★: 1
GAPS: 1 path (API error propagation — low priority, fail-fast behavior is implicit)
─────────────────────────────────
```

## NOT in scope

- `--experienced` flag (deferred to future — user will provide feedback on results)
- Separate taste profiler stage (v2)
- Streaming responses
- Caching
- Prompt variations / A/B testing
- Any web UI

## What already exists

- ARCHITECTURE.md: documents the vision and philosophy — reused for context
- No implementation code exists

## Open questions resolved

- [x] --experienced: NOT in v1 — defer to future feedback mechanism
- [x] Media type tagging in input: NOT in v1 — LLM infers from context
- [x] --dislikes: optional CLI arg

## Failure modes

| Codepath | Failure mode | Test? | Error handling? | Silent? |
|----------|-------------|-------|-----------------|---------|
| read_file() | File not found | YES | YES (raises) | NO |
| read_file() | Empty likes file | YES | YES (raises) | NO |
| call_openai() | Auth failure / rate limit | NO | YES (raises RuntimeError) | NO |
| parse_response() | Invalid JSON from model | NO | YES (raises ValueError) | NO |
| parse_response() | Empty recommendations | NO | YES (raises ValueError) | NO |

**Critical gap:** parse_response() has no test for invalid JSON from model — would need to mock the API response.

## Implementation order

1. `prompts/recommend_system.md` — write the system prompt first (independent)
2. `recommend.py` — implement in this order: read_file, build_prompt, parse_response, group_by_media_type, call_openai, main
3. `tests/test_recommend.py` — write tests alongside implementation
4. Manual test with real preferences

## Parallelization

Sequential — all steps touch the same primary module (`recommend.py`). No parallelization opportunity.

## Next step

Run `/ship` to implement and push.
