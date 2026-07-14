-- Phase 1 MVP schema for "The Turning Point".
-- See ../../blueprint.md Section 5.2 (data layer) and Section 8 (Phase 1 plan).

create extension if not exists pgcrypto;
create extension if not exists vector;

create table if not exists channels (
    id           uuid primary key default gen_random_uuid(),
    name         text not null,
    niche        text not null,
    format_thesis text not null,
    created_at   timestamptz not null default now()
);

-- Case Sourcing agent's scored backlog (Section 8: "30+ candidate cases before
-- automation is worth building on top of it").
create table if not exists cases (
    id            uuid primary key default gen_random_uuid(),
    channel_id    uuid not null references channels(id) on delete cascade,
    title         text not null,
    jurisdiction  text,
    era           text,
    turning_point text,               -- the single beat the format is built around
    source_urls   jsonb not null default '[]',
    score         numeric,
    status        text not null default 'candidate'
                  check (status in ('candidate', 'selected', 'rejected', 'produced')),
    created_at    timestamptz not null default now()
);

create table if not exists videos (
    id                uuid primary key default gen_random_uuid(),
    channel_id        uuid not null references channels(id) on delete cascade,
    case_id           uuid references cases(id),
    title             text,
    status            text not null default 'sourced'
                      check (status in (
                          'sourced', 'researched', 'scripted', 'produced',
                          'in_review', 'rejected', 'approved', 'published'
                      )),
    script            text,
    voice_audio_path  text,
    assembled_video_path text,
    subtitle_path     text,
    youtube_video_id  text,
    published_at      timestamptz,
    created_at        timestamptz not null default now(),
    updated_at        timestamptz not null default now()
);

-- One row per agent invocation. This is the operational trace: what ran,
-- what it saw, what it produced, whether it failed.
create table if not exists agent_runs (
    id          uuid primary key default gen_random_uuid(),
    video_id    uuid not null references videos(id) on delete cascade,
    agent_name  text not null,
    status      text not null default 'running'
               check (status in ('running', 'succeeded', 'failed')),
    input       jsonb,
    output      jsonb,
    error       text,
    started_at  timestamptz not null default now(),
    finished_at timestamptz
);

-- One row per editorial/compliance judgment call. This is the audit trail
-- referenced throughout blueprint.md (Section 4.5, 4.6): evidence of genuine
-- editorial process, not just "the model said it was fine".
create table if not exists decisions (
    id          uuid primary key default gen_random_uuid(),
    video_id    uuid not null references videos(id) on delete cascade,
    agent_name  text not null,
    decision    text not null,
    rationale   text not null,
    confidence  numeric,
    created_at  timestamptz not null default now()
);

-- Originality & Angle agent's structural-similarity corpus (Section 4.2:
-- "embeddings of full script structure... across channel history"). In this
-- Phase 1 graph, Originality runs *before* Script Writer (see graph.py), so
-- what gets embedded here is the research brief's angle/thesis, not a
-- script — see agents/originality.py for why.
--
-- voyage-4 (1024-dim default) is this project's embedding model, confirmed
-- live 2026-07 against Voyage's current docs (their voyage-3 line is now
-- legacy). Update the vector(1024) dimension below if you change models or
-- tiers — voyage-4 also supports 256/512/2048 via Matryoshka learning.
create table if not exists angle_embeddings (
    id            uuid primary key default gen_random_uuid(),
    channel_id    uuid not null references channels(id) on delete cascade,
    video_id      uuid not null references videos(id) on delete cascade,
    case_id       uuid references cases(id),
    text_embedded text not null,
    embedding     vector(1024) not null,
    created_at    timestamptz not null default now()
);

create index if not exists idx_cases_channel on cases(channel_id);
create index if not exists idx_videos_channel on videos(channel_id);
create index if not exists idx_agent_runs_video on agent_runs(video_id);
create index if not exists idx_decisions_video on decisions(video_id);
create index if not exists idx_angle_embeddings_channel on angle_embeddings(channel_id);

-- No ivfflat/hnsw index on angle_embeddings.embedding yet: those need a
-- meaningful row count to tune (lists/m parameters) and a brute-force scan
-- over dozens-to-hundreds of rows is instant. Add one when the corpus
-- actually grows large enough for it to matter, not preemptively.
