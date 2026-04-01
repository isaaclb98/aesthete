# Changelog

## [0.1.0.0] - 2026-04-01

### Added

- `recommend.py` — LLM-powered recommendation engine. Reads liked/disliked items from text files, calls OpenAI, outputs ranked JSON recommendations grouped by media type.
- `prompts/recommend_system.md` — system prompt for the recommendation call.
- `tests/test_recommend.py` — unit tests for all core functions (13 tests, 2 integration tests skipped without API key).
- `requirements.txt` — Python dependencies (openai, python-dotenv).
