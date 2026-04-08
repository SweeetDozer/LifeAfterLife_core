from collections.abc import Mapping
from typing import Final

from app.db.crud import crud
from app.services.graph_service import graph_service


PEER_RELATIONSHIP_TYPES: Final[frozenset[str]] = frozenset(
    {"spouse", "sibling", "friend"}
)
SUPPORTED_RELATIONSHIP_TYPES: Final[frozenset[str]] = (
    PEER_RELATIONSHIP_TYPES | frozenset({"parent"})
)


class RelationshipServiceError(Exception):
    pass


class RelationshipValidationError(RelationshipServiceError):
    pass


class RelationshipService:

    @staticmethod
    def _find_relation(relations, from_id, to_id, rel_type):
        for relation in relations:
            if (
                relation["from_person_id"] == from_id
                and relation["to_person_id"] == to_id
                and relation["relationship_type"] == rel_type
            ):
                return relation
        return None

    @staticmethod
    def _get_person_id(person: Mapping[str, object]) -> int:
        return int(person["id"])

    @staticmethod
    def _get_tree_id(person: Mapping[str, object]) -> int:
        return int(person["tree_id"])

    @staticmethod
    def _validate_person_context(
        from_person: Mapping[str, object],
        to_person: Mapping[str, object],
    ) -> int:
        from_id = RelationshipService._get_person_id(from_person)
        to_id = RelationshipService._get_person_id(to_person)
        if from_id == to_id:
            raise RelationshipValidationError("Cannot relate person to themselves")

        tree_id = RelationshipService._get_tree_id(from_person)
        if tree_id != RelationshipService._get_tree_id(to_person):
            raise RelationshipValidationError("Persons must belong to same tree")

        return tree_id

    @staticmethod
    def _validate_relationship_type(relationship_type: str) -> None:
        if relationship_type not in SUPPORTED_RELATIONSHIP_TYPES:
            raise RelationshipValidationError(
                f"Unsupported relationship type: {relationship_type}"
            )

    @staticmethod
    def _collect_conflicting_types(relations, relationship_type: str) -> list[str]:
        return sorted(
            {
                relation["relationship_type"]
                for relation in relations
                if relation["relationship_type"] != relationship_type
            }
        )

    @staticmethod
    def _shared_direct_parent_ids(
        first_ancestors: Mapping[int, int],
        second_ancestors: Mapping[int, int],
    ) -> set[int]:
        first_parents = {
            person_id for person_id, depth in first_ancestors.items() if depth == 1
        }
        second_parents = {
            person_id for person_id, depth in second_ancestors.items() if depth == 1
        }
        return first_parents & second_parents

    async def _get_lineage_context(self, tree_id, from_id, to_id, connection=None):
        from_ancestors = await graph_service.get_ancestors(
            tree_id,
            from_id,
            connection=connection,
        )
        to_ancestors = await graph_service.get_ancestors(
            tree_id,
            to_id,
            connection=connection,
        )
        return {
            "from_is_ancestor_of_to": from_id in to_ancestors,
            "to_is_ancestor_of_from": to_id in from_ancestors,
            "shared_direct_parent_ids": self._shared_direct_parent_ids(
                from_ancestors,
                to_ancestors,
            ),
        }

    @staticmethod
    def _raise_if_conflicting_pair_state(relations, relationship_type: str) -> None:
        conflicting_types = RelationshipService._collect_conflicting_types(
            relations,
            relationship_type,
        )
        if conflicting_types:
            existing = ", ".join(conflicting_types)
            raise RelationshipValidationError(
                "Cannot create relationship because pair already has "
                f"incompatible relationship(s): {existing}"
            )

    async def _ensure_parent_relationship_allowed(
        self,
        tree_id: int,
        from_id: int,
        to_id: int,
        connection=None,
    ) -> None:
        lineage = await self._get_lineage_context(
            tree_id,
            from_id,
            to_id,
            connection=connection,
        )
        if lineage["to_is_ancestor_of_from"]:
            raise RelationshipValidationError(
                "Parent relationship would create an ancestry cycle"
            )
        if lineage["from_is_ancestor_of_to"]:
            raise RelationshipValidationError(
                "Parent relationship is invalid: ancestor is already above descendant"
            )
        if lineage["shared_direct_parent_ids"]:
            raise RelationshipValidationError(
                "Parent relationship cannot be created between siblings"
            )

    async def _ensure_peer_relationship_allowed(
        self,
        tree_id: int,
        from_id: int,
        to_id: int,
        relationship_type: str,
        connection=None,
    ) -> None:
        if relationship_type == "friend":
            return

        lineage = await self._get_lineage_context(
            tree_id,
            from_id,
            to_id,
            connection=connection,
        )
        if lineage["from_is_ancestor_of_to"] or lineage["to_is_ancestor_of_from"]:
            raise RelationshipValidationError(
                f"{relationship_type.title()} relationship cannot connect "
                "ancestors and descendants"
            )
        if relationship_type == "spouse" and lineage["shared_direct_parent_ids"]:
            raise RelationshipValidationError(
                "Spouse relationship cannot be created between siblings"
            )

    async def _persist_relationship(
        self,
        tree_id: int,
        from_id: int,
        to_id: int,
        relationship_type: str,
        connection=None,
    ) -> int:
        relationship_id = await crud.create_relationship(
            tree_id,
            from_id,
            to_id,
            relationship_type,
            connection=connection,
        )
        if relationship_id is not None:
            return relationship_id

        pair_relations = await crud.get_pair_relationships(
            from_id,
            to_id,
            tree_id=tree_id,
            connection=connection,
        )
        relation = self._find_relation(
            pair_relations,
            from_id,
            to_id,
            relationship_type,
        )
        if relation:
            return relation["id"]

        raise RelationshipServiceError("Failed to persist relationship")

    async def create_relationship(
        self,
        *,
        from_person: Mapping[str, object],
        to_person: Mapping[str, object],
        relationship_type: str,
        connection=None,
    ) -> int:
        self._validate_relationship_type(relationship_type)
        tree_id = self._validate_person_context(from_person, to_person)
        from_id = self._get_person_id(from_person)
        to_id = self._get_person_id(to_person)

        pair_relations = await crud.get_pair_relationships(
            from_id,
            to_id,
            tree_id=tree_id,
            connection=connection,
        )
        self._raise_if_conflicting_pair_state(pair_relations, relationship_type)

        direct_relation = self._find_relation(
            pair_relations,
            from_id,
            to_id,
            relationship_type,
        )
        reverse_relation = self._find_relation(
            pair_relations,
            to_id,
            from_id,
            relationship_type,
        )

        if relationship_type == "parent":
            if direct_relation:
                raise RelationshipValidationError("Relationship already exists")
            if reverse_relation:
                raise RelationshipValidationError(
                    "Parent relationship cannot point in both directions"
                )

            await self._ensure_parent_relationship_allowed(
                tree_id,
                from_id,
                to_id,
                connection=connection,
            )
            return await self._persist_relationship(
                tree_id,
                from_id,
                to_id,
                relationship_type,
                connection=connection,
            )

        if direct_relation and reverse_relation:
            raise RelationshipValidationError("Relationship already exists")

        await self._ensure_peer_relationship_allowed(
            tree_id,
            from_id,
            to_id,
            relationship_type,
            connection=connection,
        )

        created_id = (
            direct_relation["id"]
            if direct_relation
            else await self._persist_relationship(
                tree_id,
                from_id,
                to_id,
                relationship_type,
                connection=connection,
            )
        )

        if reverse_relation is None:
            await self._persist_relationship(
                tree_id,
                to_id,
                from_id,
                relationship_type,
                connection=connection,
            )

        return created_id

    async def delete_relationship(
        self,
        *,
        relationship_id: int,
        connection=None,
    ) -> int:
        relationship = await crud.get_relationship(relationship_id, connection=connection)
        if not relationship:
            raise RelationshipValidationError("Relationship not found")

        pair_relations = await crud.get_pair_relationships(
            relationship["from_person_id"],
            relationship["to_person_id"],
            tree_id=relationship["tree_id"],
            connection=connection,
        )
        relationship_type = relationship["relationship_type"]
        relationship_ids_to_delete = {relationship_id}

        if relationship_type in PEER_RELATIONSHIP_TYPES:
            for pair_relation in pair_relations:
                if pair_relation["relationship_type"] == relationship_type:
                    relationship_ids_to_delete.add(pair_relation["id"])

        deleted_count = 0
        for current_relationship_id in relationship_ids_to_delete:
            deleted = await crud.delete_relationship(
                current_relationship_id,
                connection=connection,
            )
            if deleted:
                deleted_count += 1

        if deleted_count == 0:
            raise RelationshipServiceError("Failed to delete relationship")

        return deleted_count


relationship_service = RelationshipService()
