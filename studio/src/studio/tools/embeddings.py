"""Voyage AI embeddings — the Originality & Angle agent's structural-
similarity tool. Anthropic has no first-party embedding endpoint; Voyage is
the standard pairing for a Claude-centric stack.

Model choice note: voyage-3 (1024-dim) is this project's default as of its
Jan-2026 training cutoff. Verify that's still Voyage's current recommended
model at https://docs.voyageai.com/docs/embeddings before trusting this
live — if you change models, update db/schema.sql's angle_embeddings
vector(1024) column to match the new dimension.
"""

import voyageai

from studio.config import settings

MODEL = "voyage-3"
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
