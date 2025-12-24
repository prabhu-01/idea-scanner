"""
Digest module.

Generates formatted daily digests from scored ideas.
"""

from src.digest.generator import (
    DigestGenerator,
    DigestConfig,
    DigestResult,
    generate_digest,
    generate_digest_content,
)

__all__ = [
    "DigestGenerator",
    "DigestConfig",
    "DigestResult",
    "generate_digest",
    "generate_digest_content",
]


