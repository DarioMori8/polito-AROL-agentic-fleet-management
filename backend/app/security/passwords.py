"""
Password hashing with scrypt.

scrypt is deliberately slow and memory-hard: every guess an attacker makes
against a stolen hash costs real CPU time and RAM. The per-user salt makes two
identical passwords produce different hashes, which defeats precomputed tables.
"""

import hashlib
import hmac
import secrets

# scrypt cost parameters. n (CPU/memory cost) must be a power of two;
# with r=8 the memory used is 128 * n * r bytes = 16 MiB per hash.
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_DKLEN = 64          # length of the derived key, in bytes
_SALT_BYTES = 16


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """
    Hash a password. Returns (hash_hex, salt_hex).

    With no salt a fresh random one is generated (provisioning a password);
    with a salt the same derivation is replayed (verifying a password).
    """
    salt_bytes = bytes.fromhex(salt) if salt is not None else secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt_bytes,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_DKLEN,
    )
    return digest.hex(), salt_bytes.hex()


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """
    Recompute the hash with the stored salt and compare.

    hmac.compare_digest takes the same time wherever the two strings first
    differ, so response time leaks nothing about how close a guess was.
    """
    candidate, _ = hash_password(password, salt)
    return hmac.compare_digest(candidate, password_hash)
