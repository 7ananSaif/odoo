"""Cryptography helpers: password hashing, 2FA (TOTP), secret encryption, sessions."""
from __future__ import annotations

import base64
import io
import secrets
import time
from dataclasses import dataclass

import pyotp
import qrcode
from cryptography.fernet import Fernet, InvalidToken
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from passlib.context import CryptContext

from app.config import settings

# Argon2id is the default and strongest scheme.
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

_serializer = URLSafeTimedSerializer(secret_key=settings.secret_key, salt="saas-manager-session")
_fernet: Fernet | None = None


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------
def hash_password(plain: str) -> str:
    """Hash a password with Argon2."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against its hash (constant time)."""
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:  # noqa: BLE001 - malformed hash
        return False


# ---------------------------------------------------------------------------
# Two-factor authentication (TOTP)
# ---------------------------------------------------------------------------
def generate_totp_secret() -> str:
    """Return a new base32 TOTP secret."""
    return pyotp.random_base32()


def totp_provisioning_uri(secret: str, account: str) -> str:
    """Return the otpauth:// URI to enroll an authenticator app."""
    return pyotp.TOTP(secret).provisioning_uri(name=account, issuer_name="SaaS Manager")


def verify_totp(secret: str, code: str, valid_window: int = 1) -> bool:
    """Verify a 6-digit TOTP code, tolerating a +/- one-step clock drift."""
    if not secret or not code:
        return False
    clean = code.strip().replace(" ", "")
    return pyotp.TOTP(secret).verify(clean, valid_window=valid_window)


def totp_qr_png_base64(secret: str, account: str) -> str:
    """Render the enrolment QR code as a base64 PNG data payload."""
    uri = totp_provisioning_uri(secret, account)
    img = qrcode.make(uri)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


# ---------------------------------------------------------------------------
# Secret encryption (Fernet)
# ---------------------------------------------------------------------------
def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        if not settings.secrets_key:
            raise RuntimeError("SECRETS_KEY is not configured; cannot encrypt/decrypt secrets.")
        _fernet = Fernet(settings.secrets_key.encode())
    return _fernet


def encrypt_secret(plain: str | None) -> str | None:
    """Encrypt a secret for at-rest storage. Returns None for empty input."""
    if plain is None or plain == "":
        return None
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_secret(token: str | None) -> str | None:
    """Decrypt a stored secret. Returns None if empty/unreadable."""
    if not token:
        return None
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return None


def mask_secret(value: str | None) -> str:
    """Return a display-safe masked value."""
    if not value:
        return ""
    if len(value) <= 4:
        return "****"
    return f"{value[:2]}****{value[-2:]}"


# ---------------------------------------------------------------------------
# Signed session cookies
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SessionData:
    """Minimal data carried in the signed cookie."""

    user_id: int
    email: str


def create_session_token(user_id: int, email: str) -> str:
    """Sign a small payload to store in the session cookie."""
    return _serializer.dumps({"uid": user_id, "email": email})


def load_session_token(token: str) -> SessionData | None:
    """Verify and load a session cookie, or None when invalid/expired."""
    max_age = settings.session_max_age_minutes * 60
    try:
        data = _serializer.loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    return SessionData(user_id=int(data["uid"]), email=str(data["email"]))


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------
def generate_token(length: int = 32) -> str:
    """Return a URL-safe random token."""
    return secrets.token_urlsafe(length)


def now_ts() -> int:
    """Current unix timestamp (helper for signed payloads)."""
    return int(time.time())
