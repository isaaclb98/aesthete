# Plan: Aesthete — Two-Call LLM Recommendation Architecture

## What changed

v1 was a single API call — the model inferred taste and generated recs simultaneously, which produced shallow surface-similarity matches. v1.1 separates into two calls:

1. **Taste inference call** — model analyses the likes list and articulates core aesthetic dimensions, resonant qualities, negative space, and discovery leverage
2. **Recommendation call** — model generates recs guided by the articulated taste profile, not raw item similarity

Dislikes were removed entirely (too high a cognitive burden on users to articulate what they hate).

## File structure

```
aesthete/
├── recommend.py              # CLI + two-call flow
├── prompts/
│   ├── infer_taste.md         # Taste inference prompt (call 1)
│   └── recommend_system.md    # Recommendation prompt (call 2)
└── tests/
    └── test_recommend.py      # 23 tests
```

## Data flow

```
recommend.py
  │
  ├── argparse → reads --likes (no --dislikes)
  │
  ├── read_file() → strip lines, filter empty, return list[str]
  │
  ├── infer_taste(likes)
  │   ├── build_inference_prompt(likes) → (system, user)
  │   ├── call_openai(system, user)
  │   └── parse_response(raw) → taste_analysis dict
  │
  ├── generate_recommendations(taste_analysis, likes)
  │   ├── build_recommendation_prompt(taste_analysis, likes) → (system, user)
  │   ├── call_openai(system, user)
  │   ├── parse_response(raw)
  │   └── returns list[dict]
  │
  ├── group_by_media_type(recommendations) → OrderedDict
  │
  └── print_json({taste_analysis, recommendations})
```

## Output format

```json
{
  "taste_analysis": {
    "core_dimensions": ["..."],
    "resonant_qualities": ["..."],
    "negative_space": ["..."],
    "discovery_leverage": "..."
  },
  "recommendations": {
    "film": [{"rank": 1, "name": "...", "media_type": "film", "reason": "...", "confidence": "high"}],
    "book": [...],
    ...
  }
}
```

## NOT in scope

- Chatbot-style taste elicitation (deferred)
- Dislikes input
- Weights
- Streaming
- Caching
- Any web UI
