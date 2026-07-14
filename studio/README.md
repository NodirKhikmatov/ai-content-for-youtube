# studio — "The Turning Point"

Phase 1 MVP pipeline. Full context: [`../blueprint.md`](../blueprint.md) (or the
published artifact) — this scaffold implements Section 8 of that doc.

## What's here (Day 1)

A LangGraph skeleton with all 13 Phase 1 agents wired in as no-op stubs, a
Postgres schema, and the config/storage plumbing they'll need. No agent has
real logic yet — that's Days 2–7 (see `blueprint.md` Section 8's build-order
table). The point of Day 1 is that the chain compiles and runs end to end
before anything in it does real work.

## Setup

```bash
cd studio
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env   # fill in API keys as you reach the day that needs them

docker compose up -d   # local Postgres on localhost:5434 (isolated from any
                        # native Postgres, and from other projects' dev
                        # containers, already running on this machine)
python scripts/init_db.py

pytest                 # should pass: graph compiles, stub run doesn't raise
```

## Layout

```
src/studio/
  config.py    settings, loaded from .env
  state.py     the PipelineState TypedDict every agent reads/writes
  db.py        Postgres connection helper
  storage.py   Cloudflare R2 client (needs a bucket created by hand first)
  graph.py     builds the LangGraph pipeline from agents/
  agents/      one file per Phase 1 agent — see blueprint.md Section 4 for
               each agent's full spec (inputs/outputs/decision logic/failure
               handling); these files currently only log and pass state
               through
db/schema.sql  channels, cases, videos, agent_runs, decisions
scripts/init_db.py   applies schema.sql + seeds the one Phase 1 channel
tests/test_graph.py  Day 1 smoke test
```

## Manual steps not automated here

These need your own accounts/credentials, so they're not something this
scaffold can do on its own:

- **Cloudflare R2**: create the bucket + API token in the dashboard, fill
  `R2_*` in `.env`.
- **YouTube Data API**: create a project + OAuth client in Google Cloud
  Console, fill `YOUTUBE_CLIENT_ID`/`YOUTUBE_CLIENT_SECRET`. The OAuth
  consent flow that produces `YOUTUBE_REFRESH_TOKEN` is Day 7 work
  (publishing stays manual — YouTube Studio — until then, per the blueprint).
- **Claude / Gemini / OpenAI / ElevenLabs / Kling**: API keys from each
  vendor's own dashboard.

## Not in Day 1, on purpose

TikTok repurposing, multi-model LLM routing, Temporal, Qdrant/embeddings —
all deferred per `blueprint.md` Section 8's "deliberately not in week 1"
note. A single manual LangGraph run doesn't need durable workflow yet.
