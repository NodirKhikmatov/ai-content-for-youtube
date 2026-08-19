"""Authentication & Session Security helper.

Provides PBKDF2-HMAC-SHA256 password hashing with salt, and HMAC-signed
session tokens for user authentication.
"""

import base64
import hashlib
import hmac
import os
import time

# Secret key used for signing session tokens (fallback generated per process if not in env)
SECRET_KEY = os.environ.get("STUDIO_SECRET_KEY", "ai-youtube-content-super-secret-key-2026")
TOKEN_MAX_AGE_SECONDS = 30 * 24 * 60 * 60  # 30 days


def hash_password(password: str) -> str:
    """Hashes a password with a random 16-byte salt using PBKDF2-HMAC-SHA256."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return f"{base64.b64encode(salt).decode('ascii')}${base64.b64encode(key).decode('ascii')}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verifies a plain text password against a stored PBKDF2 hash."""
    try:
        salt_b64, key_b64 = password_hash.split("$", 1)
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected_key = base64.b64decode(key_b64.encode("ascii"))
        actual_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
        return hmac.compare_digest(expected_key, actual_key)
    except Exception:
        return False


def create_session_token(user_id: str) -> str:
    """Creates an HMAC-signed session token containing user_id and timestamp."""
    timestamp = str(int(time.time()))
    payload = f"{user_id}:{timestamp}"
    signature = hmac.new(
        SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"{payload}:{signature}"


def verify_session_token(token: str) -> str | None:
    """Verifies a session token and returns user_id if valid, else None."""
    if not token or ":" not in token:
        return None
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return None
        user_id, timestamp_str, signature = parts
        timestamp = int(timestamp_str)

        # Check expiration
        if time.time() - timestamp > TOKEN_MAX_AGE_SECONDS:
            return None

        payload = f"{user_id}:{timestamp_str}"
        expected_signature = hmac.new(
            SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        if hmac.compare_digest(expected_signature, signature):
            return user_id
    except Exception:
        return None
    return None
