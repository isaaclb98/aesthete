"""
Aesthete web UI — Flask app wrapping the recommendation engine.
"""

import os

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, session
from flask_session import Session

# Load .env before anything else
load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = "app_session"

# Ensure session dir exists
os.makedirs("app_session", exist_ok=True)

Session(app)

# Import the recommendation functions directly from recommend.py
from recommend import (
    generate_recommendations,
    group_by_media_type,
    infer_taste,
)


MEDIA_TYPES = ["film", "book", "music", "tv", "game"]


@app.route("/")
def index():
    items = session.get("items", [])
    return render_template(
        "index.html",
        items=items,
        taste_analysis=None,
        proportional=[],
        cross_media=[],
        error=None,
        media_types=MEDIA_TYPES,
    )


@app.route("/add_item", methods=["POST"])
def add_item():
    media_type = request.form.get("media_type", "").strip()
    item_name = request.form.get("item_name", "").strip()

    if not item_name:
        return redirect_with_error("Item name cannot be empty.")

    items = session.get("items", [])
    items.append((media_type, item_name))
    session["items"] = items

    return redirect("/")


@app.route("/remove_item/<int:index>", methods=["POST"])
def remove_item(index):
    items = session.get("items", [])
    if 0 <= index < len(items):
        items.pop(index)
        session["items"] = items
    return redirect("/")


@app.route("/recommend", methods=["POST"])
def recommend():
    items = session.get("items", [])

    if not items:
        return redirect_with_error("Add some items to your list first.")

    model = os.environ.get("MODEL", "gpt-4o")

    try:
        taste_analysis = infer_taste(items, model)
    except Exception as e:
        return render_template(
            "index.html",
            items=items,
            taste_analysis=None,
            proportional=[],
            cross_media=[],
            error=f"OpenAI API error: {e}",
            media_types=MEDIA_TYPES,
        )

    try:
        proportional_raw, cross_media = generate_recommendations(taste_analysis, items, model)
    except Exception as e:
        return render_template(
            "index.html",
            items=items,
            taste_analysis=taste_analysis,
            proportional=[],
            cross_media=[],
            error=f"OpenAI API error: {e}",
            media_types=MEDIA_TYPES,
        )

    proportional = group_by_media_type(proportional_raw)

    session["taste_analysis"] = taste_analysis

    return render_template(
        "index.html",
        items=items,
        taste_analysis=taste_analysis,
        proportional=proportional,
        cross_media=cross_media,
        error=None,
        media_types=MEDIA_TYPES,
    )


@app.route("/clear", methods=["POST"])
def clear():
    session["items"] = []
    return redirect("/")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def redirect_with_error(msg: str):
    items = session.get("items", [])
    return render_template(
        "index.html",
        items=items,
        taste_analysis=None,
        proportional=[],
        cross_media=[],
        error=msg,
        media_types=MEDIA_TYPES,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
