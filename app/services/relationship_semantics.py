from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class RelationshipDefinition:
    type_key: str
    axis: str
    nature: str
    reciprocity: str
    kinship_priority: int


RELATIONSHIP_DEFINITIONS: Final[dict[str, RelationshipDefinition]] = {
    "parent": RelationshipDefinition(
        type_key="parent",
        axis="vertical",
        # Current schema stores only a generic parent edge. We treat it as the
        # default biological/blood lineage until a richer nature field exists.
        nature="biological",
        reciprocity="directed",
        kinship_priority=0,
    ),
    "sibling": RelationshipDefinition(
        type_key="sibling",
        axis="collateral",
        nature="biological",
        reciprocity="peer",
        kinship_priority=1,
    ),
    "spouse": RelationshipDefinition(
        type_key="spouse",
        axis="affinal",
        nature="affinal",
        reciprocity="peer",
        kinship_priority=3,
    ),
    "friend": RelationshipDefinition(
        type_key="friend",
        axis="social",
        nature="social",
        reciprocity="peer",
        kinship_priority=4,
    ),
}


def get_relationship_definition(relationship_type: str) -> RelationshipDefinition | None:
    return RELATIONSHIP_DEFINITIONS.get(relationship_type)


def supported_relationship_types() -> frozenset[str]:
    return frozenset(RELATIONSHIP_DEFINITIONS)


def peer_relationship_types() -> frozenset[str]:
    return frozenset(
        relationship_type
        for relationship_type, definition in RELATIONSHIP_DEFINITIONS.items()
        if definition.reciprocity == "peer"
    )


def blood_relationship_types() -> frozenset[str]:
    return frozenset(
        relationship_type
        for relationship_type, definition in RELATIONSHIP_DEFINITIONS.items()
        if definition.nature == "biological"
    )


def relationship_priority(relationship_type: str) -> int:
    definition = get_relationship_definition(relationship_type)
    if definition is None:
        return 999
    return definition.kinship_priority
