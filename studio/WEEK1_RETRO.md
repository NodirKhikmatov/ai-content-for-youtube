# Week 1 retrospective

blueprint.md Section 8, Day 7: "Write down every step that broke or felt
fragile; that list becomes week 2's priority order, not a pre-written
plan." This is that list — compiled from what actually happened across
Days 1–7, not from a template.

## The single biggest fact to act on first

**No live API key has been configured for any external service, ever, this
week** — not Anthropic, Tavily, Voyage, ElevenLabs, Kling, Deepgram,
Gemini, R2, or YouTube. `.env` in this project contains exactly two
values, both local ffmpeg binary paths, added to fix a system-dependency
gap (see below) — nothing that talks to a paid API has been exercised
against the real thing.

Everything that touches Postgres or ffmpeg has been verified for real. Everything
that touches an LLM or a media-generation vendor has only been verified
against **mocked** responses shaped by reading each SDK's actual installed
API surface (confirmed via `inspect.signature`, not guessed) — which
proves the orchestration logic is sound, but proves nothing about whether
the prompts actually produce parseable, useful output, or whether the
vendor API shapes assumed for Kling and Gemini are still current. That's a
real, open risk, not a formality.

**Week 2, priority zero: get one real API key (Anthropic is the cheapest
path — it unblocks Deep Research, Fact Checker, Storytelling, Script
Writer, and Compliance) and run one real case through the pipeline by
hand.** Everything below this line is worth fixing, but this is worth
doing first, because it's the only way to find out what a mocked test
can't show.

## What actually broke, in the order it happened

1. **Postgres `numeric` → `Decimal` isn't JSON-serializable** (Day 2).
   `json.dumps` on `agent_runs.output` blew up the moment a real score
   value flowed through it. Fixed with a `default=` handler — but it's a
   reminder that every `record_agent_run`/`record_decision` call is a
   potential serialization landmine as new data types get piped in.

2. **A test fixture silently consumed real backlog entries** (Day 2). The
   first draft of the Deep Research test fixture queried "top-scored
   candidate" instead of the specific case it had just inserted, because
   the synthetic case's deliberately-low score never actually won that
   query — it kept picking real cases (Bentley, Lizzie Borden, Miranda,
   Dreyfus, Scopes) instead. Caught by inspecting DB state after a test
   run, not by the test itself passing or failing. **Lesson: a passing
   test doesn't mean the test does what its name says.**

3. **`register_vector()` ordering bug** (Day 3): it needs the `vector`
   extension to already exist, which breaks on a fresh database's very
   first connection — the one that runs `CREATE EXTENSION vector`. Fixed
   with a narrow `except psycopg.ProgrammingError` around registration.

4. **pgvector's `<=>` needs an explicit `::vector` cast** (Day 3).
   Postgres can't infer the parameter type for a bare distance-operator
   query; without the cast it tried (and failed) to treat the parameter as
   a `double precision[]`.

5. **Two flaky tests from fixed/constant test vectors** (Day 3). Using
   `[0.5] * 1024` as a "prior angle" embedding collided with identical rows
   left behind by earlier runs of the same test against the persistent dev
   DB — similarity ties resolved to *some* matching row, not necessarily
   the one the test just inserted. Fixed with per-run random vectors.
   **Lesson: tests that mutate a persistent local dev DB need to assume
   they'll run more than once against the same data.**

6. **Local port collisions** (Day 1, recurring context through the week):
   5433 was already taken by another project's Docker container on this
   machine. Settled on 5434, documented everywhere it's referenced
   (docker-compose.yml, .env.example, config.py, README).

7. **Subtitle agent never created its working directory** (Day 5) — unlike
   every other media agent, which all called `.mkdir(parents=True,
   exist_ok=True)` before writing. Caught immediately by the real-ffmpeg
   test, not by a mock that would have papered over it.

8. **Plain `brew install ffmpeg` has no libass** (Day 5) — the `subtitles`
   burn-in filter doesn't exist in that build at all. Not a code bug, a
   missing system dependency; confirmed by reproducing the failure
   standalone before touching any project code. Fixed by installing
   `ffmpeg-full` (keg-only, deliberately *not* added to the global PATH —
   `FFMPEG_BINARY`/`FFPROBE_BINARY` are now configurable settings instead
   of a hardcoded binary name).

9. **A shell heredoc quoting failure while committing Day 5** — the commit
   message's apostrophes broke a `git commit -m "$(cat <<'EOF' ...)"`
   construction. Not a project bug, but worth noting as a process fragility:
   commit messages with contractions go through a temp file + `git commit
   -F` now, not an inline heredoc.

## What's known-incomplete, flagged rather than hidden

- **Video Generation's "one 5-second clip per beat, looped" pacing**
  (Day 5) satisfies "no dead air" but not "cut frequency" — a 10-minute
  video today would repeat the same 6 shots many times over. Needs either
  more clips generated per beat or an explicit cut-scheduling step.
- **`InMemorySaver`'s checkpointer is process-local** (Day 6) — a paused
  Quality Review can't be resumed by a separate later process invocation.
  `run_pipeline.py` works around this by handling a full run's interrupt
  and resume in one continuous execution. A durable checkpointer is the
  real fix, and not a coincidence that it's the same shape of gap Temporal
  was already scoped to close (blueprint.md roadmap, Phase 2+).
- **Vendor API surfaces verified only against documentation/training
  knowledge, not a live account**: Kling's endpoint and auth shape
  (`tools/video_gen.py`), the exact current "Gemini 3.1 Pro" model string
  (`tools/video_review.py`), and the current recommended Voyage embedding
  model (`tools/embeddings.py`) are all best-effort defaults with an
  explicit comment saying so. Anthropic's model ID (`claude-opus-4-8`) is
  the one exception — that came from confirmed session context, not a
  guess, and is the only vendor integration with that level of confidence
  going into Week 2.
- **mypy friction with langchain-anthropic's stubs**: `ChatAnthropic(model=...,
  api_key=...)` is stricter in the type stubs than in actual runtime
  validation (verified by hand — constructing it with a fake key works
  fine). Every Claude-based agent carries a documented `# type: ignore` for
  this rather than fighting a third-party stub. Not worth more effort than
  that, but worth knowing it's there.

## Week 2 priority order (derived from the above, not pre-written)

1. Configure `ANTHROPIC_API_KEY` and `TAVILY_API_KEY`; run Deep Research
   and Fact Checker against a real case. This is where prompt-shape and
   structured-output-parsing bugs will actually surface — nothing here has
   been checked against a real Claude response yet.
2. Same for `VOYAGE_API_KEY` (Originality), `ELEVENLABS_API_KEY` (Voice
   Synthesis), `DEEPGRAM_API_KEY` (Subtitle) — all lower-risk than Kling/
   Gemini since their SDK surfaces were confirmed against the installed
   package, not guessed.
3. `KLING_API_KEY` and `GEMINI_API_KEY` last, specifically because their
   integration code is the least verified — expect to actually need to fix
   `tools/video_gen.py` and `tools/video_review.py` against real API
   responses, not just add a key and have it work.
4. Once one full real run completes: address the clip-repetition pacing
   gap and evaluate whether `InMemorySaver` needs to become a durable
   checkpointer before doing a second real video, or whether it can wait
   for Phase 2's Temporal work as originally planned.
