# -*- coding: utf-8 -*-
"""Final Terra semantic hash contract for snapshot v2."""
from __future__ import annotations

import hashlib

from hsr_battle_agent.battle_sandbox.canonical_v2 import canonical_v2_bytes
from hsr_battle_agent.battle_sandbox.snapshot_v2 import TerraSnapshotV2

__all__ = [
    "SEMANTIC_HASH_V2_ALGORITHM",
    "SEMANTIC_HASH_V2_DOMAIN",
    "SemanticHashV2Error",
    "semantic_hash_v2",
]

SEMANTIC_HASH_V2_ALGORITHM = "SHA-256"
SEMANTIC_HASH_V2_DOMAIN = b"hsr-battle-agent:terra-semantic-hash:v2\x00"


class SemanticHashV2Error(ValueError):
    """Raised when a non-snapshot is offered as Terra semantic state."""


def semantic_hash_v2(snapshot: TerraSnapshotV2) -> str:
    """Hash every decision-affecting component of a validated Terra snapshot.

    The snapshot contains the complete state aggregate (stores, pending and
    opaque data, revision/sequences, allocator and complete RNG state) plus
    evidence/profile/rule identity.  Accepting only ``TerraSnapshotV2`` avoids
    accidentally hashing an incomplete arbitrary dictionary.
    """
    if not isinstance(snapshot, TerraSnapshotV2):
        raise SemanticHashV2Error(
            "semantic_hash_v2 requires a validated TerraSnapshotV2"
        )
    digest = hashlib.sha256()
    digest.update(SEMANTIC_HASH_V2_DOMAIN)
    digest.update(canonical_v2_bytes(snapshot.to_dict()))
    return digest.hexdigest()
