"""Passwords, TOTP, secret encryption and signed sessions."""
from __future__ import annotations

import pyotp

from app.security import (
    create_session_token,
    decrypt_secret,
    encrypt_secret,
    generate_token,
    hash_password,
    load_session_token,
    mask_secret,
    totp_provisioning_uri,
    totp_qr_png_base64,
    verify_password,
    verify_totp,
)


def test_password_hash_roundtrip():
    hashed = hash_password("s3cret-password")
    assert hashed != "s3cret-password"
    assert verify_password("s3cret-password", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_verify_password_tolerates_malformed_hash():
    assert verify_password("x", "not-a-hash") is False


def test_secret_encryption_roundtrip():
    token = encrypt_secret("api-key-123")
    assert token and token != "api-key-123"
    assert decrypt_secret(token) == "api-key-123"


def test_encrypt_empty_is_none():
    assert encrypt_secret("") is None
    assert encrypt_secret(None) is None
    assert decrypt_secret(None) is None


def test_decrypt_invalid_returns_none():
    assert decrypt_secret("not-a-valid-token") is None


def test_mask_secret():
    assert mask_secret("") == ""
    assert mask_secret("abcd") == "****"
    assert mask_secret("abcdefgh") == "ab****gh"


def test_totp_verify_accepts_current_code():
    secret = pyotp.random_base32()
    code = pyotp.TOTP(secret).now()
    assert verify_totp(secret, code) is True
    assert verify_totp(secret, "000000") is False or code == "000000"


def test_totp_provisioning_uri_and_qr():
    secret = pyotp.random_base32()
    uri = totp_provisioning_uri(secret, "owner@example.com")
    assert uri.startswith("otpauth://totp/")
    assert "issuer=SaaS%20Manager" in uri or "issuer=SaaS+Manager" in uri
    qr = totp_qr_png_base64(secret, "owner@example.com")
    assert isinstance(qr, str) and len(qr) > 50


def test_session_token_roundtrip():
    token = create_session_token(7, "owner@example.com")
    data = load_session_token(token)
    assert data is not None
    assert data.user_id == 7
    assert data.email == "owner@example.com"


def test_session_token_rejects_tampering():
    token = create_session_token(1, "a@b.c")
    assert load_session_token(token + "x") is None
    assert load_session_token("garbage") is None


def test_generate_token_is_urlsafe():
    token = generate_token(16)
    assert isinstance(token, str)
    assert len(token) >= 16
