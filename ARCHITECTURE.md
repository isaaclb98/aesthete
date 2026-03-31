# Aesthete — Architecture

**Cross-media aesthetic recommendation engine built on embedding similarity and LLM reasoning.**

---

## Overview

Aesthete recommends media—films, books, music, games, art—based on a user's demonstrated taste profile, not their explicit genre preferences. It avoids boxing users into categories and surfaces recommendations that feel *discovered*, not predicted.

The core philosophy: **people respond to aesthetic properties, not metadata labels.** Two works can share zero surface attributes yet trigger the same taste satisfaction. Aesthete exploits this to surface recommendations that feel serendipitous while being deeply personalized.

---

## The Two Spaces

Aesthete operates across two distinct vector spaces, each serving a different function:

### Space 1: Content Embedding Space

Every item in Aesthete's corpus exists as a dense vector in a shared embedding space. This space is pre-computed and static (updated on corpus rebuilds).

Items cluster by deep aesthetic similarity—not genre, not modality, not creator. A slow-burn Tarkovsky film and a slow-burn ambient album might be nearest neighbors because the *quality of attention* they demand is similar. This is the emergent property of training on diverse textual data: the embedding captures dimensions humans don't consciously articulate.

Corpus items include:
- Films (text descriptions or reviews)
- Books (descriptions, literary criticism)
- Music (album descriptions, critical prose)
- Games (design analysis, tone descriptions)
- Visual art (formal analysis, critical context)

The embedding model must place all modalities in the same latent space, or use a shared textual representation for all media types.

### Space 2: User Taste Space

Computed per-user, dynamic, derived from their explicitly provided preferences.

A user does not map to a genre label. They map to a **taste vector**—a point in the content embedding space that represents "what this user responds to aesthetically." This vector is synthesized from their liked items, not averaged.

The synthesis method: LLM-generated taste description, then embedded. This outperforms naive centroid approaches because:
- It can hold contradictions (user likes X and Y for unrelated reasons)
- It weights reasons, not just items
- It produces coherent taste profiles even from eclectic input

---

## The Problem with Naive Similarity

A naive system finds items *like* what the user likes. This produces obvious recommendations: "You liked Dune → here's more sci-fi." The user could have found this themselves.

The interesting problem is finding items that:
1. Match the user's taste profile
2. Are NOT in their consumption history
3. Are NOT obvious genre matches

This requires more than vector proximity. Aesthete addresses this through:

### Negative Space Filtering

```
Candidate Score = 
  PROXIMITY to taste vector
  − PROXIMITY to disliked items
  − PROXIMITY to already-consumed items
```

The negative signals carve out the obvious, forcing the system toward genuine discovery. A user who likes *Blade Runner* shouldn't just get *Blade Runner 2049*—they should get works that share its *atmosphere of technological melancholy* without sharing its genre label.

### Compound Aesthetic Queries

The LLM can generate compound embedding queries that no hand-coded taxonomy expresses:
- "Works with the narrative ambiguity of A but the pacing of B"
- "Something that has the atmosphere of C but ends like D"
- "Media that subverts the expectations E establishes"

These queries are embedded and used for retrieval, capturing aesthetic relationships that don't map to keywords.

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
│  Synthesizes → coherent taste description (avoids genre)   │
│  Output: rich text taste profile                             │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  TASTE VECTOR (embed)                        │
│  Embed the taste description → Taste Vector (Space 2)        │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                STAGE 1: EMBEDDING RETRIEVAL                 │
│  Approximate nearest-neighbor search over corpus            │
│  (Space 1: Content Embedding Space)                          │
│  Filter: exclude consumed items, apply negative signals     │
│  Output: top-N candidates (hundreds)                         │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              STAGE 2: LLM REASONING (RE-RANK)                │
│  For each candidate:                                         │
│    - Does it genuinely match the taste profile?             │
│    - Is the match at the right level (not surface)?         │
│    - Any contradictions with explicitly disliked items?      │
│  Re-rank candidates by reasoned fit                          │
│  Output: top-M final recommendations (5-10)                 │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                      DELIVERY                                │
│  Each recommendation includes:                               │
│    - Item name/description                                   │
│    - Confidence score                                        │
│    - Explanation: which taste properties it satisfies       │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Components

### 1. Corpus

A curated, cross-media corpus of high-quality textual descriptions. Not the media itself—descriptions, reviews, critical analyses. The quality of recommendations depends heavily on corpus quality.

**Corpus size**: ~10,000–50,000 items across modalities. Quality over quantity; over 50k the retrieval-to-reasoning ratio degrades.

**Corpus rebuild**: Periodic, not continuous. Aesthete does not learn from user interactions by default (stateless). Rebuild cadence: monthly or on-demand.

**Corpus format**: Each item is a structured record:
```
{
  "id": "unique-id",
  "title": "Work Title",
  "type": "film|book|music|game|art",
  "description": "Rich textual description (~200-500 words)",
  "metadata": { ... } // optional: year, creator, etc.
}
```

The `description` field is the embedded content. It must capture aesthetic properties, not just plot summary. Guidelines for corpus curation are in CORPUS.md.

### 2. Embedding Engine

**Model**: Any capable embedding model that places diverse text in a shared latent space. Choice depends on the corpus and desired trade-off between quality and cost.

**Output**: 768–3072 dimensional dense vectors (model-dependent). All media types share the same embedding space.

**Indexing**: Approximate Nearest Neighbor (ANN) index (e.g., FAISS, Qdrant, Weaviate) for fast retrieval over the full corpus. Index rebuilt on corpus rebuild.

### 3. Taste Profiler

An LLM prompt that takes in the user's liked items and produces a structured taste profile.

**Input**: List of liked items (and optionally disliked items, with reasoning for why).

**Output**: A taste profile in prose, covering:
- 5–8 specific aesthetic properties the user responds to
- Contradictions or tensions in their taste
- Implicit preferences (what they seem to value even if not stated)
- What to avoid (from disliked items or negative signals)

**Prompt design principles**:
- Never mention genre labels as primary descriptors
- Focus on *how* media affects the user, not *what* it is
- Preserve contradictions rather than smoothing them
- Derive preferences from specific examples, don't assume

Sample output structure:
```
Taste Profile:
- Aesthetic Property 1: [description with evidence from liked items]
- Aesthetic Property 2: [description with evidence]
- ...
- Contradiction: [if applicable]
- Avoid: [what to steer clear of and why]
```

### 4. Retrieval & Ranking Pipeline

**Stage 1** — ANN search:
- Embed the taste description
- Query the index for nearest neighbors
- Exclude consumed items
- Apply negative filtering against disliked items (if provided)
- Return top 100-500 candidates

**Stage 2** — LLM re-ranking:
- For each candidate, prompt the LLM to assess fit against the taste profile
- Score candidates: strong match / moderate match / weak match
- For borderline candidates: explicit reasoning about why they may or may not fit
- Return top 5-10 final recommendations with explanations

---

## Anti-Stereotyping Measures

Aesthete explicitly avoids demographic inference and genre-label pigeonholing.

**Rules**:
1. Never infer preferences from user identity, assumed demographics, or cultural background
2. Taste profiles derive exclusively from explicitly provided likes/dislikes
3. Recommendations are justified by aesthetic properties, never by demographic patterns
4. Contradictions in taste are preserved, not resolved
5. Negative signals (dislikes) carry as much weight as positive signals
6. Thin profiles (few items) produce tentative recommendations; rich profiles produce confident ones

**Implementation**:
- Taste profiler prompt explicitly instructs: "Do not reason about genre or demographic similarity"
- Recommendation output requires explicit connection to taste properties, not labels
- Confidence calibration: low item count → low confidence, high → higher confidence

---

## Why Embeddings Capture Aesthetic Similarity

The honest answer: we don't fully know why large-scale text embeddings capture aesthetic similarity so effectively.

The dominant theory: during pre-training, the model develops rich internal representations that reflect every dimension along which texts relate—including aesthetic, tonal, philosophical dimensions that aren't consciously named in language but are embedded in the statistical structure of how texts cluster.

When searching by embedding proximity, you search across dozens of implicit axes simultaneously, most of which no hand-crafted taxonomy could capture. This is why semantically different works can be neighbors in embedding space: the embedding has learned to group works by what they *ask of* the viewer or reader, not just what they *are*.

This is the empirical foundation Aesthete exploits.

---

## Scope & Limitations

**What Aesthete does well**:
- Cross-modal recommendation (film ↔ literature ↔ music ↔ games)
- Non-obvious discovery (recommends against genre labels)
- Handles eclectic, contradictory taste
- Explains its reasoning

**What Aesthete does not do**:
- Learn from user feedback continuously (stateless by default)
- Handle real-time new media (corpus-bound)
- Guarantee coverage of niche or obscure works (corpus-dependent)
- Replace social recommendations (taste similarity between users is out of scope)

**Known failure modes**:
- Very small taste profiles (2-3 items) produce unreliable taste vectors
- Very contradictory taste (loves and hates nearly identical properties) may produce incoherent profiles
- Corpus quality is paramount: bad descriptions → bad recommendations

---

## Future Considerations (Out of Scope for v1)

- **Feedback loop**: Let users rate recommendations, incorporate signals back into taste profile
- **Social taste matching**: Find users with similar taste profiles and cross-recommend
- **Dynamic corpus**: Add new items continuously, not just on rebuilds
- **Comparative ranking**: Instead of "recommend X", ask "do you prefer A or B?" for richer signal
- **Multi-stage taste**: Coarse taste profile → refine with targeted questions

---

## File Structure

```
aesthete/
├── ARCHITECTURE.md         # This file
├── CORPUS.md              # Corpus curation guidelines
├── SPEC.md                # Detailed technical specification
├── README.md              # Project overview
├── data/
│   └── corpus/            # Corpus items (JSON or NDJSON)
├── src/
│   ├── embed.py           # Embedding pipeline
│   ├── index.py           # ANN index construction
│   ├── profile.py         # Taste profiler (LLM)
│   ├── retrieve.py        # Stage 1 retrieval
│   ├── rank.py            # Stage 2 re-ranking
│   └── main.py            # CLI entry point
├── prompts/
│   ├── taste_profiler.md  # System prompt for taste profiling
│   └── ranker.md          # System prompt for re-ranking
└── tests/
    └── ...
```

---

## Summary

Aesthete recommends by modeling *why* a user responds to media, not by matching labels. The two-space architecture (content embeddings + synthesized taste vectors) enables cross-modal discovery that feels serendipitous. The LLM does the hard reasoning work; the embedding index handles fast retrieval at scale.
