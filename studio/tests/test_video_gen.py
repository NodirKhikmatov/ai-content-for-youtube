"""tools/video_gen.py auth test — pure, no network. Covers the JWT this
project generates for Kling (access-key/secret-key pair, not a static
bearer token — see KLING_API_KEY -> KLING_ACCESS_KEY/KLING_SECRET_KEY
migration) and KlingBackend's fail-fast on missing credentials.
"""

import jwt
import pytest

from studio.tools import video_gen


def test_kling_jwt_has_expected_claims():
    token = video_gen._kling_jwt("my-access-key", "my-secret-key")

    decoded = jwt.decode(token, "my-secret-key", algorithms=["HS256"])
    assert decoded["iss"] == "my-access-key"
    assert decoded["exp"] > decoded["nbf"]


def test_kling_jwt_rejects_wrong_secret():
    token = video_gen._kling_jwt("my-access-key", "my-secret-key")

    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(token, "wrong-secret", algorithms=["HS256"])


def test_backend_requires_both_credentials(monkeypatch):
    monkeypatch.setattr(video_gen.settings, "kling_access_key", None)
    monkeypatch.setattr(video_gen.settings, "kling_secret_key", "secret-only")

    with pytest.raises(RuntimeError, match="KLING_ACCESS_KEY"):
        video_gen.KlingBackend()
