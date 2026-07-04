"""
Password hashing and reset-token generation. Uses only the standard library
(hashlib's PBKDF2-HMAC-SHA256 + secrets) so the project doesn't need a new
dependency for something security-sensitive that's easy to get wrong.
"""
import hashlib
import hmac
import secrets

PBKDF2_ITERATIONS = 260_000
TOKEN_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
TOKEN_LENGTH = 8


def hash_password(password: str, salt: str = None) -> tuple:
    """Returns (hash_hex, salt_hex). Pass an existing salt to verify against it."""
    salt_bytes = bytes.fromhex(salt) if salt else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, PBKDF2_ITERATIONS)
    return digest.hex(), salt_bytes.hex()


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    candidate_hash, _ = hash_password(password, salt)
    return hmac.compare_digest(candidate_hash, password_hash)


def generate_reset_token() -> str:
    """A random 8-character alphanumeric token, generated with a
    cryptographically secure source (not `random`)."""
    return "".join(secrets.choice(TOKEN_ALPHABET) for _ in range(TOKEN_LENGTH))
