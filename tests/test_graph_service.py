import unittest
from unittest.mock import AsyncMock, patch

from app.services.graph_service import GraphService


class GraphServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = GraphService()

    async def test_build_graph_skips_invalid_rows_and_deduplicates_neighbors(self):
        relations = [
            {
                "from_person_id": 1,
                "to_person_id": 2,
                "relationship_type": "parent",
            },
            {
                "from_person_id": "1",
                "to_person_id": "2",
                "relationship_type": "parent",
            },
            {
                "from_person_id": 2,
                "to_person_id": 1,
                "relationship_type": "spouse",
            },
            {
                "from_person_id": 1,
                "to_person_id": 4,
                "relationship_type": " friend ",
            },
            {
                "from_person_id": 3,
                "to_person_id": 3,
                "relationship_type": "friend",
            },
            {
                "from_person_id": 4,
                "to_person_id": None,
                "relationship_type": "sibling",
            },
            {
                "from_person_id": "broken",
                "to_person_id": 5,
                "relationship_type": "parent",
            },
        ]

        with patch("app.services.graph_service.crud") as crud_mock:
            crud_mock.get_tree_relationships = AsyncMock(return_value=relations)

            graph = await self.service.build_graph(tree_id=10)

        self.assertEqual(
            graph,
            {
                1: [2, 4],
                2: [1],
                4: [1],
            },
        )

    async def test_find_path_details_returns_directional_step_metadata(self):
        relations = [
            {
                "from_person_id": 1,
                "to_person_id": 2,
                "relationship_type": "parent",
            },
            {
                "from_person_id": 2,
                "to_person_id": 3,
                "relationship_type": "spouse",
            },
            {
                "from_person_id": 3,
                "to_person_id": 2,
                "relationship_type": "spouse",
            },
        ]

        with patch("app.services.graph_service.crud") as crud_mock:
            crud_mock.get_tree_relationships = AsyncMock(return_value=relations)

            path_details = await self.service.find_path_details(
                tree_id=10,
                start_id=2,
                end_id=1,
            )

        self.assertEqual(path_details["path"], [2, 1])
        self.assertEqual(
            path_details["steps"],
            [
                {
                    "from_person_id": 2,
                    "to_person_id": 1,
                    "direct_relationship_types": [],
                    "reverse_relationship_types": ["parent"],
                }
            ],
        )

    async def test_find_lca_is_deterministic_when_multiple_common_ancestors_exist(self):
        relations = [
            {
                "from_person_id": 10,
                "to_person_id": 1,
                "relationship_type": "parent",
            },
            {
                "from_person_id": 11,
                "to_person_id": 1,
                "relationship_type": "parent",
            },
            {
                "from_person_id": 10,
                "to_person_id": 2,
                "relationship_type": "parent",
            },
            {
                "from_person_id": 11,
                "to_person_id": 2,
                "relationship_type": "parent",
            },
        ]

        with patch("app.services.graph_service.crud") as crud_mock:
            crud_mock.get_tree_relationships = AsyncMock(return_value=relations)

            lca = await self.service.find_lca(tree_id=10, p1=1, p2=2)

        self.assertEqual(lca, 10)

    async def test_find_path_details_short_circuits_on_invalid_person_id(self):
        with patch("app.services.graph_service.crud") as crud_mock:
            crud_mock.get_tree_relationships = AsyncMock()

            path_details = await self.service.find_path_details(
                tree_id=10,
                start_id=None,
                end_id=2,
            )

        self.assertIsNone(path_details)
        crud_mock.get_tree_relationships.assert_not_awaited()

    async def test_find_path_details_keeps_sorted_relationship_types_for_same_edge(self):
        relations = [
            {
                "from_person_id": 1,
                "to_person_id": 2,
                "relationship_type": " spouse ",
            },
            {
                "from_person_id": 1,
                "to_person_id": 2,
                "relationship_type": "friend",
            },
            {
                "from_person_id": 2,
                "to_person_id": 1,
                "relationship_type": "sibling",
            },
        ]

        with patch("app.services.graph_service.crud") as crud_mock:
            crud_mock.get_tree_relationships = AsyncMock(return_value=relations)

            path_details = await self.service.find_path_details(
                tree_id=10,
                start_id=1,
                end_id=2,
            )

        self.assertEqual(
            path_details["steps"],
            [
                {
                    "from_person_id": 1,
                    "to_person_id": 2,
                    "direct_relationship_types": ["friend", "spouse"],
                    "reverse_relationship_types": ["sibling"],
                }
            ],
        )

    async def test_find_path_details_prefers_blood_path_over_equal_length_non_blood_path(self):
        relations = [
            {
                "from_person_id": 1,
                "to_person_id": 2,
                "relationship_type": "spouse",
            },
            {
                "from_person_id": 2,
                "to_person_id": 5,
                "relationship_type": "friend",
            },
            {
                "from_person_id": 1,
                "to_person_id": 3,
                "relationship_type": "parent",
            },
            {
                "from_person_id": 3,
                "to_person_id": 5,
                "relationship_type": "sibling",
            },
        ]

        with patch("app.services.graph_service.crud") as crud_mock:
            crud_mock.get_tree_relationships = AsyncMock(return_value=relations)

            path_details = await self.service.find_path_details(
                tree_id=10,
                start_id=1,
                end_id=5,
            )

        self.assertEqual(path_details["path"], [1, 3, 5])

    async def test_find_path_details_prefers_fewer_mixed_edges_when_lengths_match(self):
        relations = [
            {
                "from_person_id": 1,
                "to_person_id": 2,
                "relationship_type": "parent",
            },
            {
                "from_person_id": 2,
                "to_person_id": 6,
                "relationship_type": "sibling",
            },
            {
                "from_person_id": 1,
                "to_person_id": 3,
                "relationship_type": "parent",
            },
            {
                "from_person_id": 1,
                "to_person_id": 3,
                "relationship_type": "friend",
            },
            {
                "from_person_id": 3,
                "to_person_id": 6,
                "relationship_type": "sibling",
            },
        ]

        with patch("app.services.graph_service.crud") as crud_mock:
            crud_mock.get_tree_relationships = AsyncMock(return_value=relations)

            path_details = await self.service.find_path_details(
                tree_id=10,
                start_id=1,
                end_id=6,
            )

        self.assertEqual(path_details["path"], [1, 2, 6])

    async def test_find_path_details_still_prefers_shorter_path_over_longer_bloodier_one(self):
        relations = [
            {
                "from_person_id": 1,
                "to_person_id": 2,
                "relationship_type": "spouse",
            },
            {
                "from_person_id": 2,
                "to_person_id": 5,
                "relationship_type": "friend",
            },
            {
                "from_person_id": 1,
                "to_person_id": 3,
                "relationship_type": "parent",
            },
            {
                "from_person_id": 3,
                "to_person_id": 4,
                "relationship_type": "sibling",
            },
            {
                "from_person_id": 4,
                "to_person_id": 5,
                "relationship_type": "parent",
            },
        ]

        with patch("app.services.graph_service.crud") as crud_mock:
            crud_mock.get_tree_relationships = AsyncMock(return_value=relations)

            path_details = await self.service.find_path_details(
                tree_id=10,
                start_id=1,
                end_id=5,
            )

        self.assertEqual(path_details["path"], [1, 2, 5])

    async def test_get_ancestors_ignores_non_parent_edges(self):
        relations = [
            {
                "from_person_id": 5,
                "to_person_id": 2,
                "relationship_type": "parent",
            },
            {
                "from_person_id": 7,
                "to_person_id": 5,
                "relationship_type": "parent",
            },
            {
                "from_person_id": 9,
                "to_person_id": 2,
                "relationship_type": "spouse",
            },
            {
                "from_person_id": 10,
                "to_person_id": 2,
                "relationship_type": "friend",
            },
        ]

        with patch("app.services.graph_service.crud") as crud_mock:
            crud_mock.get_tree_relationships = AsyncMock(return_value=relations)

            ancestors = await self.service.get_ancestors(tree_id=10, person_id="2")

        self.assertEqual(ancestors, {2: 0, 5: 1, 7: 2})


if __name__ == "__main__":
    unittest.main()
