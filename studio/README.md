# studio — "The Turning Point"

Phase 1 MVP pipeline. Full context: [`../blueprint.md`](../blueprint.md) (or the
published artifact) — this scaffold implements Section 8 of that doc.

## Status

Following `blueprint.md` Section 8's day-by-day build order:

- **Day 1** — LangGraph skeleton, Postgres schema, all 13 Phase 1 agents wired
  in (started as no-op stubs).
- **Day 2** — Case Sourcing is real (DB-only, no external API): a 30-case
  backlog scored by a rubric that penalizes sensitivity harder than it
  rewards drama. Deep Research is real: two-pass Claude + Tavily research
  (gather, then a dedicated disconfirming-evidence pass).
- **Day 3** — Fact Checker is real: one consolidated verification pass per
  case, and its hard-stop is a genuine graph-level conditional edge (routes
  straight to `END`, not just a flag). Originality & Angle is real: Voyage
  embeddings of each video's research angle, checked against the channel's
  own history via pgvector cosine similarity; it degrades to a
  human-review flag on any failure rather than raising.

Storytelling, Script Writer, Voice Synthesis, Video Generation, Video
Assembly, Subtitle, Quality Review, Compliance, and Publishing are still Day
4–7 work — see `blueprint.md` Section 8's build-order table.

## Setup

```bash
cd studio
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env   # fill in API keys as you reach the day that needs them

docker compose up -d   # local Postgres (pgvector-enabled) on localhost:5434,
                        # isolated from any native Postgres and other
                        # projects' dev containers already on this machine
python scripts/init_db.py
python scripts/seed_cases.py

pytest                 # 13 tests: structural + Case Sourcing (real, hits the
                        # dev DB) + Deep Research/Fact Checker/Originality
                        # (mocked LLM/search/embeddings — no live keys needed)
```

## Layout

```
src/studio/
  config.py    settings, loaded from .env
  state.py     the PipelineState TypedDict every agent reads/writes
  db.py        Postgres connection helper + all queries (incl. pgvector)
  storage.py   Cloudflare R2 client (needs a bucket created by hand first)
  graph.py     builds the LangGraph pipeline; owns the fact-checker
               hard-stop conditional edge
  tools/       external-API clients shared across agents (Tavily search,
               Voyage embeddings)
  agents/      one file per Phase 1 agent — see blueprint.md Section 4 for
               each agent's full spec (inputs/outputs/decision logic/failure
               handling). case_sourcing, deep_research, fact_checker, and
               originality have real logic; the rest are still stubs.
db/schema.sql  channels, cases, videos, agent_runs, decisions, angle_embeddings
scripts/
  init_db.py     applies schema.sql + seeds the one Phase 1 channel
  seed_cases.py  seeds the 30-case backlog with its scoring rubric
tests/
  test_graph.py          structural: compiles, all nodes present, routing
  test_case_sourcing.py  real (hits the dev DB, no external API)
  test_deep_research.py  mocked LLM + search
  test_fact_checker.py   mocked LLM + search; covers pass and hard-stop
  test_originality.py    mocked embeddings; covers pass, flag, and failure
```

## Manual steps not automated here

These need your own accounts/credentials, so they're not something this
scaffold can do on its own:

- **Anthropic** (`ANTHROPIC_API_KEY`): Deep Research and Fact Checker.
- **Tavily** (`TAVILY_API_KEY`): the search grounding both of those use.
- **Voyage AI** (`VOYAGE_API_KEY`): Originality & Angle's embeddings. Verify
  the `voyage-3` model choice in `tools/embeddings.py` is still current —
  it's a Jan-2026-training-cutoff default, not a live lookup.
- **Cloudflare R2**: create the bucket + API token in the dashboard, fill
  `R2_*` in `.env`.
- **YouTube Data API**: create a project + OAuth client in Google Cloud
  Console, fill `YOUTUBE_CLIENT_ID`/`YOUTUBE_CLIENT_SECRET`. The OAuth
  consent flow that produces `YOUTUBE_REFRESH_TOKEN` is Day 7 work
  (publishing stays manual — YouTube Studio — until then, per the blueprint).
- **Gemini / OpenAI / ElevenLabs / Kling**: API keys from each vendor's own
  dashboard, needed starting Day 4–5.

## Deliberately not here yet

TikTok repurposing, multi-model LLM routing, Temporal, a second case in
flight simultaneously — deferred per `blueprint.md` Section 8's
"deliberately not in week 1" note. A single manual LangGraph run doesn't
need durable workflow yet.
