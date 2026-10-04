"""License material is returned once; only its digest is retained."""
import hashlib
import secrets


def generate_key() -> str:
    return 'CLASTIO-' + secrets.token_hex(16).upper()

def key_digest(key: str) -> str:
    return hashlib.sha256(key.strip().upper().encode()).hexdigest()
