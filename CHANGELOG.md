# Changelog

## [0.2.0.0] - 2026-04-01

### Changed

- `recommend.py` — two-call architecture: taste inference call first, then recommendation call. Produces richer recs guided by articulated taste dimensions rather than surface similarity.
- `prompts/recommend_system.md` — updated to accept pre-computed taste_analysis, removed dislikes support, targets 20-30 recs per call.
- `--dislikes` CLI argument removed — dislikes were a high-cognitive-burden input for users.

### Added

- `prompts/infer_taste.md` — taste inference prompt. Articulates core aesthetic dimensions, resonant qualities, negative space, and discovery leverage from the likes list.
- 23 tests total (up from 20) — new tests for `infer_taste`, `generate_recommendations`, and the two-call `main()` flow.
