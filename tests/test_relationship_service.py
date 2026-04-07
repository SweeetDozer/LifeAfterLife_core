import unittest
from unittest.mock import AsyncMock, patch

from app.services.relationship_service import (
    RelationshipService,
    RelationshipValidationError,
)


class RelationshipServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = RelationshipService()
        self.from_person = {"id": 1, "tree_id": 10}
        self.to_person = {"id": 2, "tree_id": 10}

    async def test_parent_rejects_existing_ancestor_chain(self):
        with (
            patch("app.services.relationship_service.crud") as crud_mock,
            patch("app.services.relationship_service.graph_service") as graph_mock,
        ):
            crud_mock.get_pair_relationships = AsyncMock(return_value=[])
            crud_mock.create_relationship = AsyncMock()
            graph_mock.get_ancestors = AsyncMock(
                side_effect=[
                    {1: 0},
                    {2: 0, 1: 2},
                ]
            )

            with self.assertRaisesRegex(
                RelationshipValidationError,
                "ancestor is already above descendant",
            ):
                await self.service.create_relationship(
                    from_person=self.from_person,
                    to_person=self.to_person,
                    relationship_type="parent",
                )

            crud_mock.create_relationship.assert_not_awaited()

    async def test_sibling_rejects_ancestor_descendant_pair(self):
        with (
            patch("app.services.relationship_service.crud") as crud_mock,
            patch("app.services.relationship_service.graph_service") as graph_mock,
        ):
            crud_mock.get_pair_relationships = AsyncMock(return_value=[])
            crud_mock.create_relationship = AsyncMock()
            graph_mock.get_ancestors = AsyncMock(
                side_effect=[
                    {1: 0, 2: 1},
                    {2: 0},
                ]
            )

            with self.assertRaisesRegex(
                RelationshipValidationError,
                "Sibling relationship cannot connect ancestors and descendants",
            ):
                await self.service.create_relationship(
                    from_person=self.from_person,
                    to_person=self.to_person,
                    relationship_type="sibling",
                )

            crud_mock.create_relationship.assert_not_awaited()

    async def test_spouse_rejects_siblings_inferred_from_shared_parent(self):
        with (
            patch("app.services.relationship_service.crud") as crud_mock,
            patch("app.services.relationship_service.graph_service") as graph_mock,
        ):
            crud_mock.get_pair_relationships = AsyncMock(return_value=[])
            crud_mock.create_relationship = AsyncMock()
            graph_mock.get_ancestors = AsyncMock(
                side_effect=[
                    {1: 0, 99: 1},
                    {2: 0, 99: 1},
                ]
            )

            with self.assertRaisesRegex(
                RelationshipValidationError,
                "Spouse relationship cannot be created between siblings",
            ):
                await self.service.create_relationship(
                    from_person=self.from_person,
                    to_person=self.to_person,
                    relationship_type="spouse",
                )

            crud_mock.create_relationship.assert_not_awaited()

    async def test_peer_relationship_repairs_missing_reverse_link(self):
        pair_relations = [
            {
                "id": 41,
                "tree_id": 10,
                "from_person_id": 1,
                "to_person_id": 2,
                "relationship_type": "spouse",
            }
        ]

        with (
            patch("app.services.relationship_service.crud") as crud_mock,
            patch("app.services.relationship_service.graph_service") as graph_mock,
        ):
            crud_mock.get_pair_relationships = AsyncMock(return_value=pair_relations)
            crud_mock.create_relationship = AsyncMock(return_value=42)
            graph_mock.get_ancestors = AsyncMock(
                side_effect=[
                    {1: 0},
                    {2: 0},
                ]
            )

            relationship_id = await self.service.create_relationship(
                from_person=self.from_person,
                to_person=self.to_person,
                relationship_type="spouse",
            )

            self.assertEqual(relationship_id, 41)
            crud_mock.create_relationship.assert_awaited_once_with(
                10,
                2,
                1,
                "spouse",
                connection=None,
            )

    async def test_rejects_incompatible_pair_relationship_type(self):
        pair_relations = [
            {
                "id": 7,
                "tree_id": 10,
                "from_person_id": 1,
                "to_person_id": 2,
                "relationship_type": "friend",
            }
        ]

        with (
            patch("app.services.relationship_service.crud") as crud_mock,
            patch("app.services.relationship_service.graph_service") as graph_mock,
        ):
            crud_mock.get_pair_relationships = AsyncMock(return_value=pair_relations)
            crud_mock.create_relationship = AsyncMock()
            graph_mock.get_ancestors = AsyncMock()

            with self.assertRaisesRegex(
                RelationshipValidationError,
                "incompatible relationship",
            ):
                await self.service.create_relationship(
                    from_person=self.from_person,
                    to_person=self.to_person,
                    relationship_type="sibling",
                )

            graph_mock.get_ancestors.assert_not_awaited()
            crud_mock.create_relationship.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
