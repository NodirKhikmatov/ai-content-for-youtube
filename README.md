# ai-content-for-youtube — "The Turning Point"

An AI-assisted pipeline for producing narrated, documentary-style
long-form YouTube videos, built around a deliberate human-in-the-loop
checkpoint rather than full automation — see
[`blueprint.md`](blueprint.md) (or [`blueprint.html`](blueprint.html))
for the full strategic and technical rationale, including why "fully
autonomous" is the wrong target given YouTube's inauthentic-content
policy.

## Layout

- [`blueprint.md`](blueprint.md) / [`blueprint.html`](blueprint.html) —
  the strategy and architecture doc: platform research, the 13-agent
  pipeline design, and the Phase 1 build order.
- [`studio/`](studio/) — the Phase 1 MVP implementation of that
  blueprint (LangGraph pipeline, Postgres, all agents). See
  [`studio/README.md`](studio/README.md) for setup and current status.
