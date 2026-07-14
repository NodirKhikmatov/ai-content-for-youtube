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
- **Day 4** — Storytelling is real: a six-beat "hook → stakes → escalation →
  turning point → verdict → aftermath" sheet, with the hook's under-8-second
  rule enforced as an actual word-count check (one retry with an explicit
  trim instruction), not just a prompt ask. Script Writer is real: turns the
  beat sheet into narration prose, then validates the whole script against
  the 8-15 minute target the same way — one retry, trim or expand. Both
  raise on structurally bad output (a beat sheet missing a required beat, a
  missing beat sheet at all) rather than silently continuing. Shared pacing
  math lives in `pacing.py` so the two agents can't drift onto different
  assumptions about narration speed.

- **Day 5** — Voice Synthesis (ElevenLabs), Video Generation (Kling, one
  clip per beat), Video Assembly, and Subtitle are all real. Local disk
  (`media/{video_id}/`) is the canonical working store for the whole run —
  every ffmpeg step needs local files regardless, and there's no live R2
  credential to test an upload-as-gate design against — so R2 upload is
  best-effort persistence that degrades gracefully, not a blocking step.
  Video Assembly enforces its pacing rule for real (loop or trim the
  concatenated clips to match the narration's exact duration, verified with
  real ffmpeg against synthetic media, not mocked). Subtitle forced-aligns
  against the *assembled* video's actual audio (not the pre-mux narration
  file), computes word-error-rate, and only burns captions in when WER is
  low enough — otherwise it flags `needs_manual_correction` and leaves the
  un-captioned cut in place rather than publish-ready but wrong captions.

  **Known Phase 1 limitation, not fixed today:** one 5-second Kling clip per
  beat (6 total) gets looped to fill an 8-15 minute narration, which means
  long stretches of repeated visuals rather than frequent cuts — the "no
  dead air" half of Section 4.4's pacing rule is enforced (visuals always
  cover the full narration), but the "cut frequency" half isn't yet. Needs
  either more clips generated per beat or an explicit cut-scheduling step;
  flagged here rather than silently shipped as if it were solved.

  **Also surfaced today:** plain `brew install ffmpeg` has no libass, so the
  `subtitles` burn-in filter doesn't exist in it at all — needs
  `ffmpeg-full` (keg-only) pointed at via `FFMPEG_BINARY`/`FFPROBE_BINARY`.
  See "Manual steps" below.

Quality Review, Compliance, and Publishing are still Day 6–7 work — see
`blueprint.md` Section 8's build-order table.

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

pytest                 # 44 tests. Real: Case Sourcing (DB), all of
                        # test_ffmpeg_utils.py and most of Video Assembly/
                        # Subtitle (synthetic media via ffmpeg, no API keys
                        # needed for those). Mocked LLM/search/embeddings/
                        # ElevenLabs/Kling/Deepgram elsewhere. pacing.py and
                        # word_error_rate/words_to_srt are pure, no mocking.
```

## Layout

```
src/studio/
  config.py    settings, loaded from .env
  state.py     the PipelineState TypedDict every agent reads/writes
  db.py        Postgres connection helper + all queries (incl. pgvector)
  storage.py   Cloudflare R2 client (needs a bucket created by hand first)
  pacing.py    shared word-count <-> narration-seconds math
  graph.py     builds the LangGraph pipeline; owns the fact-checker
               hard-stop conditional edge
  tools/       external-API clients shared across agents (Tavily search,
               Voyage embeddings, ElevenLabs voice, Kling video, Deepgram
               transcription, shared ffmpeg subprocess helpers)
  agents/      one file per Phase 1 agent — see blueprint.md Section 4 for
               each agent's full spec (inputs/outputs/decision logic/failure
               handling). Everything through Subtitle has real logic now;
               Quality Review, Compliance, and Publishing are still stubs.
db/schema.sql  channels, cases, videos, agent_runs, decisions, angle_embeddings
scripts/
  init_db.py     applies schema.sql + seeds the one Phase 1 channel
  seed_cases.py  seeds the 30-case backlog with its scoring rubric
tests/
  test_graph.py           structural: compiles, all nodes present, routing
  test_case_sourcing.py   real (hits the dev DB, no external API)
  test_deep_research.py   mocked LLM + search
  test_fact_checker.py    mocked LLM + search; covers pass and hard-stop
  test_originality.py     mocked embeddings; covers pass, flag, and failure
  test_storytelling.py    mocked LLM; covers pass, hook retry, missing beat
  test_script_writer.py   mocked LLM; covers pass, pacing retry, missing input
  test_pacing.py          pure unit tests, no mocking
  test_ffmpeg_utils.py    real ffmpeg against synthetic media, no mocking
  test_voice_synthesis.py mocked ElevenLabs
  test_video_generation.py mocked Kling
  test_video_assembly.py  real ffmpeg against synthetic media; R2 mocked
  test_subtitle.py        mocked Deepgram; real ffmpeg for extract/burn-in
```

## Manual steps not automated here

These need your own accounts/credentials, so they're not something this
scaffold can do on its own:

- **Anthropic** (`ANTHROPIC_API_KEY`): Deep Research and Fact Checker.
- **Tavily** (`TAVILY_API_KEY`): the search grounding both of those use.
- **Voyage AI** (`VOYAGE_API_KEY`): Originality & Angle's embeddings. Verify
  the `voyage-3` model choice in `tools/embeddings.py` is still current —
  it's a Jan-2026-training-cutoff default, not a live lookup.
- **ElevenLabs** (`ELEVENLABS_API_KEY`): Voice Synthesis.
- **Kling** (`KLING_API_KEY`): Video Generation. `tools/video_gen.py`'s
  endpoint/auth shape is a best-effort default, not verified against a live
  account — check Kling's current API docs before trusting it.
- **Deepgram** (`DEEPGRAM_API_KEY`): Subtitle's forced transcription.
- **ffmpeg-full** (not the plain `ffmpeg` formula): `brew install
  ffmpeg-full`, then set `FFMPEG_BINARY`/`FFPROBE_BINARY` in `.env` to its
  keg path (default in `.env.example` assumes Homebrew on Apple Silicon —
  adjust for your machine). Plain `ffmpeg` has no libass, so caption
  burn-in silently has no filter to call.
- **Cloudflare R2**: create the bucket + API token in the dashboard, fill
  `R2_*` in `.env`. Optional in practice as of Day 5 — every media agent
  works entirely off local disk and just skips the upload (with a logged
  warning) when R2 isn't configured.
- **YouTube Data API**: create a project + OAuth client in Google Cloud
  Console, fill `YOUTUBE_CLIENT_ID`/`YOUTUBE_CLIENT_SECRET`. The OAuth
  consent flow that produces `YOUTUBE_REFRESH_TOKEN` is Day 7 work
  (publishing stays manual — YouTube Studio — until then, per the blueprint).
- **Anthropic, Tavily, Voyage, Gemini, OpenAI**: as described above.

## Deliberately not here yet

TikTok repurposing, multi-model LLM routing, Temporal, a second case in
flight simultaneously — deferred per `blueprint.md` Section 8's
"deliberately not in week 1" note. A single manual LangGraph run doesn't
need durable workflow yet.
