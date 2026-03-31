# Aesthete — Architecture

**Aesthetic recommendation engine that exploits the knowledge already encoded in large language models.**

---

## Core Philosophy

Traditional recommendation systems require building and maintaining an external corpus—manually curated descriptions of films, books, music, and other media. Aesthete rejects this entirely. LLMs trained on vast corpora of human knowledge already contain rich, nuanced representations of aesthetic properties across every media type. Aesthete exploits this directly.

The system synthesizes a user's taste from their explicitly provided likes and dislikes, then queries an LLM to generate recommendations grounded in that taste profile. No embedding index, no corpus pipeline, no retrieval infrastructure—just the model's knowledge, unleashed by precise instruction.

---

## The Problem with Conventional Recommendations

Genre-label systems are blunt instruments. "You liked Dune → here's more sci-fi" requires no intelligence and delivers no discovery.

Even collaborative filtering (find users like you, recommend what they liked) stays within surface similarity. It finds the obvious. It doesn't find the *interesting*.

The real problem: **aesthetic properties are not taxonomic.** They don't map cleanly to genre labels, demographics, or any hand-crafted categorization. The things that make you respond to a film—its pacing, its visual philosophy, its relationship to silence, how it handles moral ambiguity—are emergent, cross-cutting, and difficult to articulate. LLMs learn these emergent properties implicitly from training data. Aesthete extracts them explicitly.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         INPUT                                │
│  User provides: liked items, disliked items (optional)       │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   TASTE PROFILER (LLM)                       │
│  Analyzes liked items → extracts aesthetic properties       │
│  Synthesizes → coherent taste description                   │
│  Output: structured taste profile                            │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              RECOMMENDATION ENGINE (LLM)                     │
│  Prompt: "Given this taste profile, generate 8-12            │
│  recommendations. For each: name, media type, why it         │
│  matches. Avoid items similar to these dislikes."           │
│  Output: ranked recommendations with reasoning              │
└─────────────────────────────────────────────────────────────┘
```

Two stages. Both use the same LLM. Both are stateless.

---

## Stage 1: Taste Profiler

The taste profiler transforms a list of liked (and optionally disliked) items into a structured aesthetic profile.

**Input**: List of items the user has enjoyed. Format is flexible—titles, descriptions, or just names. The more items provided, the richer the profile.

**Output**: A taste profile covering:
- **Aesthetic properties**: 5–8 specific dimensions the user responds to (e.g., "controlled ambiguity in moral situations," "visual density over visual clarity," "narratives that respect the viewer's time")
- **Positive signals**: What draws the user in, what they seek
- **Negative signals**: What pushes them away, what they actively avoid
- **Tensions**: Contradictions in their taste (they enjoy X and Y for seemingly opposite reasons)
- **Avoid list**: Explicit items or properties to exclude

**Principles**:
- Profile is expressed in terms of *aesthetic properties*, not genre labels
- Contradictions are preserved rather than resolved
- Preferences are derived from specific examples, not assumed
- The output feeds directly into the recommendation engine

Sample output structure:
```
Taste Profile:
- Aesthetic Property 1: [description with examples from liked items]
- Aesthetic Property 2: [description with examples]
- ...
- Avoid: [what to steer clear of and why]
```

---

## Stage 2: Recommendation Engine

The recommendation engine receives the taste profile and generates personalized recommendations.

**Input**: The taste profile + optional consumption history (items already experienced, to exclude)

**Output**: 8–12 recommendations, each with:
- Item name
- Media type (film, book, music, game, etc.)
- Explanation: which taste properties this item satisfies and why
- Confidence: high / medium / moderate (calibrated from profile richness)

**Prompt structure**:
```
You are a recommendation engine with deep knowledge of films, books, music,
games, and visual art across all cultures and eras.

Based on the following taste profile, generate 10 recommendations that
genuinely match the user's aesthetic properties. Do NOT recommend items
similar to the excluded list. Vary media types when appropriate.

Taste Profile:
{profile}

Exclude these already-consumed items:
{consumption_history}

Respond with JSON or structured markdown.
```

**Key constraints**:
- Explain *why* each recommendation matches—not just what it is
- Match at the level of aesthetic properties, not surface similarity
- Avoid items similar to explicitly disliked items (negative filtering)
- Prioritize genuine discovery over obvious matches

---

## Why This Works

LLMs encode vast amounts of aesthetic knowledge from training on reviews, criticism, analyses, wikis, forum discussions, and creative writing. This knowledge includes:

- **Cross-modal relationships**: Film critics compare films to novels; music reviewers invoke visual art; game critics use literary frameworks. This cross-pollination means the LLM learns aesthetic properties that transcend any single medium.
- **Emergent clustering**: Through training, the model develops rich internal representations that reflect aesthetic similarity along dozens of implicit dimensions—most of which no hand-crafted taxonomy captures.
- **Reasoning over retrieval**: Unlike embedding systems that find nearest neighbors, the LLM reasons about *why* an item matches. It can explain the relationship at the level of the taste profile, not just proximity in latent space.

The key insight: embedding-based retrieval is powerful because it exploits these emergent properties. But it requires a static corpus. Using the LLM directly achieves the same result without the corpus overhead—trading fast retrieval for rich reasoning.

---

## Anti-Stereotyping Rules

Aesthete explicitly prevents demographic inference and genre-label pigeonholing.

1. **No demographic inference**: Do not assume preferences based on user identity, assumed background, or cultural framing
2. **Explicit over implicit**: Only use what the user explicitly provides; do not fill gaps with assumptions
3. **Aesthetic over taxonomic**: Match on aesthetic properties, not genre labels or surface categories
4. **Preserve contradictions**: Don't resolve tensions in the taste profile—preserve them
5. **Negative signals carry weight**: Dislikes are as informative as likes; exclude them explicitly
6. **Confidence calibration**: Fewer input items → lower confidence; richer profile → higher confidence

---

## Scope & Limitations

**What Aesthete does well**:
- Leverages all knowledge in the LLM with no corpus maintenance
- Handles cross-modal recommendations (film ↔ literature ↔ music ↔ games)
- Explains reasoning in terms of taste properties
- Handles contradictory and eclectic taste
- Stateless—no feedback loop to maintain

**Limitations**:
- LLM knowledge is bounded by training cutoff (no real-time media awareness)
- Consistency varies by model and prompt quality
- No grounded retrieval—relies on model's memory of items
- Harder to verify coverage: how do you know what the model didn't consider?

**Failure modes**:
- Very few input items → unreliable taste profile
- LLM may confabulate (present plausible but inaccurate descriptions)
- Heavily contradicted taste may produce incoherent recommendations
- Model may default to obvious/highly-referenced items when uncertain

---

## Future Considerations

- **Hybrid approach**: Use embeddings for initial candidate retrieval, LLM for reasoning—combines speed with depth
- **Feedback loop**: Let users rate recommendations; incorporate signals to refine taste profile
- **Coverage verification**: Adversarial prompting to check what the model didn't consider
- **Comparative ranking**: "Do you prefer A or B?" interactions for richer taste learning
- **Multi-model routing**: Route to specialized models for different media types

---

## File Structure

```
aesthete/
├── ARCHITECTURE.md    # This file
├── SPEC.md            # Technical specification, prompt designs
├── README.md          # Project overview
├── src/
│   ├── profile.py     # Taste profiler (LLM call)
│   ├── recommend.py   # Recommendation engine (LLM call)
│   └── main.py        # CLI entry point
├── prompts/
│   ├── taste_profiler.md   # System prompt for taste profiling
│   └── recommend.md        # System prompt for recommendations
└── tests/
    └── ...
```

---

## Summary

Aesthete is a two-stage LLM pipeline: synthesize a taste profile from user preferences, then query the LLM directly for recommendations that match those properties. No corpus. No embedding infrastructure. The LLM's training knowledge is the knowledge base.

The design prioritizes reasoning over retrieval, aesthetic matching over label matching, and discovery over the obvious.