# Plan: Aesthete — Typed Input, Proportional + Cross-Media Recs

## What changed

v0.2.0 had a two-call architecture with raw item input (no media types) and a single grouped recommendations output. This version introduces:

**Input format:** `media_type: item_name` per line. Any media type is valid — K-pop, opera, anime, whatever the user actually listens to. No fixed enum.

**Proportional recommendations:** Within the media types the user listed. The model uses input proportions as a soft guide (80% films in input → lean toward more film recs). Reflects where the user's aesthetic attention lives.

**Cross-media recommendations:** 2-4 recommendations in media types the user did NOT mention. Genuine left-field discoveries — the model uses discovery_leverage to find things the user would love but never considered.

**Output structure:**
```json
{
  "taste_analysis": { ... },
  "proportional_recommendations": {
    "film": [{rank, name, media_type, reason, confidence}],
    "music": [...]
  },
  "cross_media_recommendations": [{rank, name, media_type, reason, confidence}]
}
```

## File structure

```
aesthete/
├── recommend.py              # CLI + two-call flow
├── prompts/
│   ├── infer_taste.md         # Taste inference prompt (call 1)
│   └── recommend_system.md    # Recommendation prompt (call 2)
└── tests/
    └── test_recommend.py      # 25 tests
```

## Data flow

```
recommend.py
  │
  ├── argparse → reads --likes (no --dislikes)
  │
  ├── read_file() → parses "media_type: item_name" lines, returns list[(type, name)]
  │
  ├── infer_taste(likes) → taste_analysis dict
  │
  ├── generate_recommendations(taste_analysis, likes)
  │   → returns (proportional_recommendations, cross_media_recommendations)
  │
  ├── group_by_media_type(proportional_recommendations) → OrderedDict
  │
  └── print_json({taste_analysis, proportional_recommendations, cross_media_recommendations})
```

## Input format examples

```
film: The Godfather
film: Parasite
music: Blonde
k-pop: BTS
opera: Carmen
game: Factorio
```

Bare items (no `media_type:` prefix) default to `unknown` type.

## NOT in scope

- Chatbot-style taste elicitation (deferred)
- Dislikes input
- Weights
- Streaming
- Caching
- Any web UI
