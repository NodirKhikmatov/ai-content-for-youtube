"""Voyage AI embeddings — the Originality & Angle agent's structural-
similarity tool. Anthropic has no first-party embedding endpoint; Voyage is
the standard pairing for a Claude-centric stack.

Model choice note: this project originally defaulted to voyage-3 (its
Jan-2026 training cutoff's current model) but Voyage shipped the voyage-4
family (nano/lite/standard/large, shared embedding space) that same month,
which made voyage-3 legacy almost immediately — confirmed live against
https://docs.voyageai.com/docs/embeddings (2026-07). voyage-4 (the
balanced/standard tier, not -lite or -large) is the direct swap-in
replacement and keeps the same 1024-dim default, so db/schema.sql's
angle_embeddings vector(1024) column needs no migration. Re-verify at that
URL if this stops being current — re-check EMBEDDING_DIMENSION too if you
switch tiers, since voyage-4 supports 256/512/1024/2048 via Matryoshka
learning rather than one fixed size per model.
"""

import voyageai

from studio.config import settings

MODEL = "voyage-4"
EMBEDDING_DIMENSION = 1024


def embed_text(text: str) -> list[float]:
    if not settings.voyage_api_key:
        raise RuntimeError(
            "VOYAGE_API_KEY missing — Originality & Angle needs it to check a "
            "new video's angle against the channel's own history. Get a key "
            "at voyageai.com and add it to .env."
        )
    client = voyageai.Client(api_key=settings.voyage_api_key)
    result = client.embed([text], model=MODEL, input_type="document")
    return list(result.embeddings[0])
