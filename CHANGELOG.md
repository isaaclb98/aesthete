# Changelog

## [0.3.0.0] - 2026-04-01

### Changed

- `recommend.py` — input format changed to `media_type: item_name` per line. Any media type is valid (k-pop, opera, anime, etc. — no fixed enum). Bare items default to `unknown` type.
- `recommend.py` — output now has `proportional_recommendations` (within input types, matching input proportions softly) and `cross_media_recommendations` (2-4 genuine left-field discoveries in unmentioned types).
- `prompts/recommend_system.md` — updated to generate both proportional and cross-media recommendations. Removes fixed `media_type` enum restriction.

### Added

- `_compute_proportions()` — computes input type distribution for the recommendation prompt.
- `cross_media_recommendations` output section — out-of-left-field recs in unmentioned media types, driven by `discovery_leverage`.
- 25 tests total (up from 23) — new tests for typed input parsing and dual-output structure.

## [0.2.0.0] - 2026-04-01

### Changed

- `recommend.py` — two-call architecture: taste inference call first, then recommendation call. Produces richer recs guided by articulated taste dimensions rather than surface similarity.
- `prompts/recommend_system.md` — updated to accept pre-computed taste_analysis, removed dislikes support, targets 20-30 recs per call.
- `--dislikes` CLI argument removed — dislikes were a high-cognitive-burden input for users.

### Added

- `prompts/infer_taste.md` — taste inference prompt. Articulates core aesthetic dimensions, resonant qualities, negative space, and discovery leverage from the likes list.
