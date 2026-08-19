"""Tests for Multi-User Authentication, Password Hashing, Sessions, and User Profiles."""

import pytest

from studio import db
from studio.tools.auth import (
    create_session_token,
    hash_password,
    verify_password,
    verify_session_token,
)


def test_password_hashing_and_verification():
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert "$" in hashed
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_session_token_lifecycle():
    user_id = "123e4567-e89b-12d3-a456-426614174000"
    token = create_session_token(user_id)

    assert token is not None
    verified_id = verify_session_token(token)
    assert verified_id == user_id

    # Tampered token fails
    tampered_token = token + "tampered"
    assert verify_session_token(tampered_token) is None
    assert verify_session_token("invalid_format") is None


def test_user_creation_and_lookup():
    email = f"test_user_{pytest.importorskip('uuid').uuid4()}@example.com"
    pw_hash = hash_password("mypassword")

    user = db.create_user(email, pw_hash, "Test User")
    assert user["email"] == email
    assert user["full_name"] == "Test User"

    fetched = db.get_user_by_email(email)
    assert fetched is not None
    assert fetched["id"] == user["id"]

    # Test settings update
    db.update_user_settings(user["id"], {"anthropic_api_key": "sk-test-123"})
    updated = db.get_user_by_id(user["id"])
    assert updated is not None
    assert updated["settings"].get("anthropic_api_key") == "sk-test-123"
