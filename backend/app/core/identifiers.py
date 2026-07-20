"""
app/core/identifiers.py — Utilities for deterministic ID generation and source hashing.
"""
import hashlib

def generate_id(*parts: any) -> str:
    """Generate a deterministic ID from string parts."""
    raw = "::".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

def compute_source_hash(filepath: str) -> str:
    """Compute SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()
