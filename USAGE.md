# Aesthete — Usage Guide

## What it does

Aesthete infers your taste from things you like, then recommends new things you'd genuinely enjoy. It learns what resonates with you — not just more of the same, but proportional picks within your types and left-field discoveries across media you haven't mentioned.

## Quick start

```bash
# 1. Install dependencies
python3 -m venv venv
source venv/bin/activate        # on Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env — add your OPENAI_API_KEY and FLASK_SECRET_KEY

# 3. Run
flask run --host=0.0.0.0 --port=5000
# Or: python app.py

# 4. Open
open http://localhost:5000
```

## Using the web UI

**Add items** — Enter a name (e.g. "The Godfather") and pick or type a type (e.g. "film"), then click Add. The item appears in your list.

**Get recommendations** — Click "Get Recommendations". Aesthete runs two LLM calls:
1. Infers your taste profile from your item list
2. Generates proportional and cross-media recommendations based on that profile

**Remove items** — Click "remove" next to any item to drop it from your list.

**Clear all** — Click the "Clear" button in the header to start fresh.

## Item format

Items are typed: a media type and a name per item. The form has a text field with suggestions for the type. Suggested types:

```
film  book  music  tv  game
```

You can type any custom type not in the list — Aesthete accepts any string.

## What the output means

**Taste Analysis** — A description of your taste across four dimensions:
- **Core dimensions** — the thematic and stylistic threads running through your picks
- **Resonant qualities** — what specifically draws you to the things you like
- **Negative space** — what doesn't appeal to you, and why
- **Discovery leverage** — where Aesthete has room to surprise you

**Proportional Recommendations** — Items grouped by media type, respecting the proportions of your input list. If half your list is films, roughly half your recommendations will be films.

**Cross-Media Discoveries** — 2-4 recommendations in media types you haven't mentioned. These are the left-field finds: Factorio players getting a supply chain book, film noir fans getting a 1940s radio drama.

## CLI (unchanged)

The command-line tool still works and is importable:

```bash
python recommend.py --likes likes.txt
```

The Flask app imports `infer_taste()` and `generate_recommendations()` from `recommend.py` — they are the same functions.

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | — | Your OpenAI API key |
| `FLASK_SECRET_KEY` | Yes | `dev-secret-change-me` | Session signing key — generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `MODEL` | No | `gpt-4o` | OpenAI model to use |

## Deploying

The app is gunicorn-compatible and stateless aside from session files:

```bash
gunicorn app:app
```

For production, mount `app_session/` as a persistent volume, or switch to Redis:

```bash
SESSION_TYPE=redis SESSION_REDIS_URL=redis://localhost:6379 gunicorn app:app
```

Required environment variables for production: `OPENAI_API_KEY`, `FLASK_SECRET_KEY`.
