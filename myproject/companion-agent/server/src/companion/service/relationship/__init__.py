"""关系状态（docs/relationship-state-design.md）。"""

from companion.service.relationship.model import (
    STAGE_ACQUAINTANCE, STAGE_CLOSE, STAGE_FAMILIAR, STAGE_INTIMATE, STAGE_STRANGER,
    Relationship, RelationshipSnapshot, decay_factor, delta_for, effective_warmth, render_relationship_block,
    snapshot, stage_of,
)
from companion.service.relationship.port import RelationshipStore
from companion.service.relationship.sql import SqlRelationshipStore

__all__ = [
    "Relationship", "RelationshipSnapshot", "RelationshipStore", "SqlRelationshipStore",
    "STAGE_STRANGER", "STAGE_ACQUAINTANCE", "STAGE_FAMILIAR", "STAGE_CLOSE", "STAGE_INTIMATE",
    "decay_factor", "delta_for", "effective_warmth", "stage_of", "snapshot", "render_relationship_block",
]
