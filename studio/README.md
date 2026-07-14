# studio — "The Turning Point"

Phase 1 MVP pipeline. Full context: [`../blueprint.md`](../blueprint.md) (or the
published artifact) — this scaffold implements Section 8 of that doc. See
[`WEEK1_RETRO.md`](WEEK1_RETRO.md) for what actually broke building it and
what Week 2 should do first.

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

- **Day 6** — Quality Review and Compliance are real, and both are now
  actual graph-level gates (Quality Review → END on rejection, Compliance →
  END on rejection), matching Fact Checker's Day 3 hard-stop precedent
  rather than returning flags nobody routes on. Quality Review's human gate
  is a genuine LangGraph `interrupt()`: the auto-pass threshold is
  deliberately strict (avg ≥ 0.95, every dimension ≥ 0.85), and anything
  below it actually pauses the graph and waits for a real decision, resumed
  via `scripts/run_pipeline.py`'s `Command(resume=...)` — tested against
  the real interrupt/resume cycle (with the Gemini call mocked), not just
  the agent function called directly. Compliance's rubric is built from
  YouTube's own inauthentic/reused/low-value/limited-ads policy language
  (blueprint.md Section 1.1) and is the first agent to actually write to
  the `decisions` audit-trail table the schema has carried since Day 1.

  **Known Phase 1 limitation:** the human-in-the-loop checkpointer
  (`InMemorySaver`) only survives within one process — a paused run can't
  be resumed by a separate later process invocation. That's why
  `run_pipeline.py` both starts a run and handles its own interrupt/resume
  in one continuous execution rather than being a "resume anytime" CLI. A
  durable checkpointer is the natural fix, and not a coincidence that it's
  the same shape of problem Temporal was scoped to solve (blueprint.md
  roadmap, Phase 2+) — not built here.

- **Day 7** — Publishing is real, scoped exactly as blueprint.md Section 8
  specifies: it does **not** call the YouTube Data API. It prepares a
  manual-publish checklist (video path, captions, a suggested title/
  description drawn from the research brief) and leaves the video ready
  for a human to upload through YouTube Studio. `scripts/mark_published.py`
  is the honest counterpart — a separate, deliberately manual step that
  records the actual publish only after a human confirms it happened;
  verified by actually running it against a real seeded video, not just
  unit-tested.

  **The plan's literal Day 7 task — "publish video #1" — could not
  literally happen**: no live API key has been configured for anything
  this week, so no real video has ever been produced end to end. See
  [`WEEK1_RETRO.md`](WEEK1_RETRO.md) for the full accounting of what broke,
  what's still unverified, and what Week 2 should do first (spoiler: get
  one real API key before anything else).

All 13 Phase 1 agents now have real logic. Phase 2 is next — see
`blueprint.md` Section 7's roadmap.

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

pytest                 # 59 tests. Real: Case Sourcing and Publishing (DB),
                        # all of test_ffmpeg_utils.py and most of Video
                        # Assembly/Subtitle (synthetic media via ffmpeg, no
                        # API keys needed), and Quality Review's actual
                        # interrupt/resume cycle (real LangGraph checkpointer,
                        # only the Gemini call is mocked). Mocked LLM/search/
                        # embeddings/ElevenLabs/Kling/Deepgram elsewhere.
                        # pacing.py and word_error_rate/words_to_srt are pure.
```

## Layout

```
src/studio/
  config.py    settings, loaded from .env
  state.py     the PipelineState TypedDict every agent reads/writes
  db.py        Postgres connection helper + all queries (incl. pgvector)
  storage.py   Cloudflare R2 client (needs a bucket created by hand first)
  pacing.py    shared word-count <-> narration-seconds math
  graph.py     builds the LangGraph pipeline; owns all three hard-stop
               conditional edges and the InMemorySaver checkpointer
  tools/       external-API clients shared across agents (Tavily search,
               Voyage embeddings, ElevenLabs voice, Kling video, Deepgram
               transcription, Gemini video review, shared ffmpeg helpers)
  agents/      one file per Phase 1 agent — see blueprint.md Section 4 for
               each agent's full spec (inputs/outputs/decision logic/failure
               handling). All 13 have real logic as of Day 7.
db/schema.sql  channels, cases, videos, agent_runs, decisions, angle_embeddings
scripts/
  init_db.py       applies schema.sql + seeds the one Phase 1 channel
  seed_cases.py    seeds the 30-case backlog with its scoring rubric
  run_pipeline.py  runs a full video end to end, handling Quality Review's
                   human-in-the-loop interrupt interactively
  mark_published.py records an actual manual YouTube upload after the fact
tests/
  test_graph.py           structural: compiles, all nodes present, all routing
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
  test_quality_review.py  real interrupt/resume cycle; Gemini call mocked
  test_compliance.py      mocked LLM; verifies decisions table rows
  test_publishing.py      real (DB only, no external API)
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
- **Gemini** (`GEMINI_API_KEY`): Quality Review's video-understanding
  judge. `tools/video_review.py`'s model name ("gemini-3-pro") is a
  best-effort default — verify against Google's current model list.
- **ffmpeg-full** (not the plain `ffmpeg` formula): `brew install
  ffmpeg-full`, then set `FFMPEG_BINARY`/`FFPROBE_BINARY` in `.env` to its
  keg path (default in `.env.example` assumes Homebrew on Apple Silicon —
  adjust for your machine). Plain `ffmpeg` has no libass, so caption
  burn-in silently has no filter to call.
- **Cloudflare R2**: create the bucket + API token in the dashboard, fill
  `R2_*` in `.env`. Optional in practice as of Day 5 — every media agent
  works entirely off local disk and just skips the upload (with a logged
  warning) when R2 isn't configured.
- **YouTube**: no API credentials needed for Phase 1 — Publishing
  deliberately stays manual (YouTube Studio) per blueprint.md Section 8.
  `YOUTUBE_CLIENT_ID`/`YOUTUBE_CLIENT_SECRET`/the OAuth consent flow are
  Phase 2 work, whenever the write path actually gets automated.

## Deliberately not here yet

TikTok repurposing, multi-model LLM routing, Temporal, a second case in
flight simultaneously — deferred per `blueprint.md` Section 8's
"deliberately not in week 1" note. A single manual LangGraph run doesn't
need durable workflow yet.
