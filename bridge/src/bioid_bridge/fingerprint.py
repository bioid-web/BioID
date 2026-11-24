"""Content fingerprints for attach_data and access agreements.

The chain stores a 32-byte SHA-256 fingerprint next to an off-chain document.
A plain hash of a guessable document (a consent-form template with a few
fields filled in, a short agreement, a small CSV) can be confirmed by anyone
who hashes candidate documents and compares. For those documents use a salted
fingerprint: HMAC-SHA256 with a random 32-byte salt kept off-chain beside the
document. Whoever is allowed to see the document gets the salt with it and can
verify; nobody else can test guesses.

Large public datasets (sequence files, images) need no salt: anyone should be
able to check them, and they cannot be guessed.

Never put personal data in the document name, URI or data_type. Losing the
salt makes the fingerprint unverifiable, so store it with the same durability
as the document (see docs/durability.md).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

SALT_BYTES = 32


def new_salt() -> bytes:
    """A fresh random salt. Store it off-chain with the document, never on-chain."""
    return secrets.token_bytes(SALT_BYTES)


def fingerprint(content: bytes, salt: bytes | None = None) -> str:
    """64 hex characters: SHA-256 of the content, or HMAC-SHA256 keyed with the salt."""
    if salt is None:
        return hashlib.sha256(content).hexdigest()
    if len(salt) < 16:
        raise ValueError("a salt must be at least 16 random bytes")
    return hmac.new(salt, content, hashlib.sha256).hexdigest()


def verify(content: bytes, expected_hex: str, salt: bytes | None = None) -> bool:
    """Constant-time check of a document against the fingerprint on-chain."""
    return hmac.compare_digest(fingerprint(content, salt), expected_hex.lower())
