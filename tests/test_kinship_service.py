import unittest
from unittest.mock import AsyncMock, patch

from app.services.kinship_service import KinshipService


class KinshipServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = KinshipService()

    async def test_path_to_relations_uses_step_metadata_without_db_reads(self):
        steps = [
            {
                "from_person_id": 2,
                "to_person_id": 1,
                "direct_relationship_types": [],
                "reverse_relationship_types": ["parent"],
            },
            {
                "from_person_id": 1,
                "to_person_id": 3,
                "direct_relationship_types": ["sibling"],
                "reverse_relationship_types": ["sibling"],
            },
        ]

        with patch("app.services.kinship_service.crud") as crud_mock:
            crud_mock.get_ordered_relationship_types = AsyncMock()

            relations = await self.service.path_to_relations(tree_id=10, path=steps)

        self.assertEqual(
            relations,
            [
                {"type": "parent", "to": 1},
                {"type": "sibling", "to": 3},
            ],
        )
        crud_mock.get_ordered_relationship_types.assert_not_awaited()

    async def test_path_to_relations_accepts_path_wrapper_with_steps(self):
        path = {
            "steps": [
                {
                    "from_person_id": 1,
                    "to_person_id": 2,
                    "direct_relationship_types": ["parent"],
                    "reverse_relationship_types": [],
                }
            ]
        }

        relations = await self.service.path_to_relations(tree_id=10, path=path)

        self.assertEqual(relations, [{"type": "child", "to": 2}])

    async def test_path_to_relations_builds_consistent_steps_from_person_id_path(self):
        async def get_ordered_relationship_types(from_id, to_id, **kwargs):
            mapping = {
                (2, 1): [],
                (1, 2): [{"relationship_type": "parent"}],
                (1, 3): [{"relationship_type": "sibling"}],
                (3, 1): [{"relationship_type": "sibling"}],
            }
            return mapping[(from_id, to_id)]

        with patch("app.services.kinship_service.crud") as crud_mock:
            crud_mock.get_ordered_relationship_types = AsyncMock(
                side_effect=get_ordered_relationship_types
            )

            relations = await self.service.path_to_relations(tree_id=10, path=[2, 1, 3])

        self.assertEqual(
            relations,
            [
                {"type": "parent", "to": 1},
                {"type": "sibling", "to": 3},
            ],
        )

    async def test_path_to_relations_marks_ambiguous_step_as_unknown(self):
        steps = [
            {
                "from_person_id": 1,
                "to_person_id": 2,
                "direct_relationship_types": ["parent", "friend"],
                "reverse_relationship_types": [],
            }
        ]

        relations = await self.service.path_to_relations(tree_id=10, path=steps)

        self.assertEqual(relations, [{"type": "unknown", "to": 2}])

    async def test_path_to_relations_returns_empty_list_for_missing_path(self):
        relations = await self.service.path_to_relations(tree_id=10, path=None)

        self.assertEqual(relations, [])

    async def test_interpret_direct_parent(self):
        relations = [{"type": "parent", "to": 10}]

        with patch("app.services.kinship_service.crud") as crud_mock:
            crud_mock.get_tree_person = AsyncMock(return_value={"gender": "male"})

            result = await self.service.interpret(
                tree_id=10,
                relations=relations,
                target_id=10,
            )

        self.assertEqual(result, "отец")

    async def test_interpret_direct_child(self):
        relations = [{"type": "child", "to": 20}]

        with patch("app.services.kinship_service.crud") as crud_mock:
            crud_mock.get_tree_person = AsyncMock(return_value={"gender": "female"})

            result = await self.service.interpret(
                tree_id=10,
                relations=relations,
                target_id=20,
            )

        self.assertEqual(result, "дочь")

    async def test_interpret_direct_sibling(self):
        relations = [{"type": "sibling", "to": 20}]

        with patch("app.services.kinship_service.crud") as crud_mock:
            crud_mock.get_tree_person = AsyncMock(return_value={"gender": "female"})

            result = await self.service.interpret(
                tree_id=10,
                relations=relations,
                target_id=20,
            )

        self.assertEqual(result, "сестра")

    async def test_interpret_parent_child_path_as_sibling(self):
        relations = [
            {"type": "parent", "to": 10},
            {"type": "child", "to": 20},
        ]

        with patch("app.services.kinship_service.crud") as crud_mock:
            crud_mock.get_tree_person = AsyncMock(return_value={"gender": "female"})

            result = await self.service.interpret(
                tree_id=10,
                relations=relations,
                target_id=20,
            )

        self.assertEqual(result, "сестра")

    async def test_interpret_parent_then_sibling_as_aunt(self):
        relations = [
            {"type": "parent", "to": 10},
            {"type": "sibling", "to": 20},
        ]

        with patch("app.services.kinship_service.crud") as crud_mock:
            crud_mock.get_tree_person = AsyncMock(return_value={"gender": "female"})

            result = await self.service.interpret(
                tree_id=10,
                relations=relations,
                target_id=20,
            )

        self.assertEqual(result, "тётя")

    async def test_interpret_sibling_then_child_as_nephew(self):
        relations = [
            {"type": "sibling", "to": 10},
            {"type": "child", "to": 20},
        ]

        with patch("app.services.kinship_service.crud") as crud_mock:
            crud_mock.get_tree_person = AsyncMock(return_value={"gender": "male"})

            result = await self.service.interpret(
                tree_id=10,
                relations=relations,
                target_id=20,
            )

        self.assertEqual(result, "племянник")

    async def test_interpret_parent_sibling_child_as_cousin(self):
        relations = [
            {"type": "parent", "to": 10},
            {"type": "sibling", "to": 11},
            {"type": "child", "to": 20},
        ]

        with patch("app.services.kinship_service.crud") as crud_mock:
            crud_mock.get_tree_person = AsyncMock(return_value={"gender": "male"})

            result = await self.service.interpret(
                tree_id=10,
                relations=relations,
                target_id=20,
            )

        self.assertEqual(result, "двоюродный брат")

    async def test_interpret_second_cousin(self):
        relations = [
            {"type": "parent", "to": 10},
            {"type": "parent", "to": 11},
            {"type": "sibling", "to": 12},
            {"type": "child", "to": 13},
            {"type": "child", "to": 20},
        ]

        with patch("app.services.kinship_service.crud") as crud_mock:
            crud_mock.get_tree_person = AsyncMock(return_value={"gender": "female"})

            result = await self.service.interpret(
                tree_id=10,
                relations=relations,
                target_id=20,
            )

        self.assertEqual(result, "троюродная сестра")

    async def test_interpret_third_cousin(self):
        relations = [
            {"type": "parent", "to": 10},
            {"type": "parent", "to": 11},
            {"type": "parent", "to": 12},
            {"type": "sibling", "to": 13},
            {"type": "child", "to": 14},
            {"type": "child", "to": 15},
            {"type": "child", "to": 20},
        ]

        with patch("app.services.kinship_service.crud") as crud_mock:
            crud_mock.get_tree_person = AsyncMock(return_value={"gender": "male"})

            result = await self.service.interpret(
                tree_id=10,
                relations=relations,
                target_id=20,
            )

        self.assertEqual(result, "четвероюродный брат")

    async def test_interpret_distant_cousin_uses_consistent_collateral_label(self):
        relations = [
            {"type": "parent", "to": 10},
            {"type": "parent", "to": 11},
            {"type": "parent", "to": 12},
            {"type": "parent", "to": 13},
            {"type": "sibling", "to": 14},
            {"type": "child", "to": 15},
            {"type": "child", "to": 16},
            {"type": "child", "to": 17},
            {"type": "child", "to": 20},
        ]

        with patch("app.services.kinship_service.crud") as crud_mock:
            crud_mock.get_tree_person = AsyncMock(return_value={"gender": "female"})

            result = await self.service.interpret(
                tree_id=10,
                relations=relations,
                target_id=20,
            )

        self.assertEqual(result, "родственница по боковой линии")

    async def test_interpret_first_cousin_once_removed(self):
        relations = [
            {"type": "parent", "to": 10},
            {"type": "parent", "to": 11},
            {"type": "sibling", "to": 12},
            {"type": "child", "to": 20},
        ]

        with patch("app.services.kinship_service.crud") as crud_mock:
            crud_mock.get_tree_person = AsyncMock(return_value={"gender": "female"})

            result = await self.service.interpret(
                tree_id=10,
                relations=relations,
                target_id=20,
            )

        self.assertEqual(result, "двоюродная сестра в 1-м удалении")

    async def test_interpret_first_cousin_twice_removed(self):
        relations = [
            {"type": "parent", "to": 10},
            {"type": "parent", "to": 11},
            {"type": "parent", "to": 12},
            {"type": "sibling", "to": 13},
            {"type": "child", "to": 20},
        ]

        with patch("app.services.kinship_service.crud") as crud_mock:
            crud_mock.get_tree_person = AsyncMock(return_value={"gender": "male"})

            result = await self.service.interpret(
                tree_id=10,
                relations=relations,
                target_id=20,
            )

        self.assertEqual(result, "двоюродный брат в 2-м удалении")

    async def test_interpret_second_cousin_once_removed(self):
        relations = [
            {"type": "parent", "to": 10},
            {"type": "parent", "to": 11},
            {"type": "parent", "to": 12},
            {"type": "sibling", "to": 13},
            {"type": "child", "to": 14},
            {"type": "child", "to": 20},
        ]

        with patch("app.services.kinship_service.crud") as crud_mock:
            crud_mock.get_tree_person = AsyncMock(return_value={"gender": "female"})

            result = await self.service.interpret(
                tree_id=10,
                relations=relations,
                target_id=20,
            )

        self.assertEqual(result, "троюродная сестра в 1-м удалении")

    async def test_interpret_descendant_of_nephew_line(self):
        relations = [
            {"type": "sibling", "to": 10},
            {"type": "child", "to": 11},
            {"type": "child", "to": 20},
        ]

        with patch("app.services.kinship_service.crud") as crud_mock:
            crud_mock.get_tree_person = AsyncMock(return_value={"gender": "male"})

            result = await self.service.interpret(
                tree_id=10,
                relations=relations,
                target_id=20,
            )

        self.assertEqual(result, "потомок племянника в 1-м поколении")

    async def test_interpret_ancestor_of_aunt_line(self):
        relations = [
            {"type": "parent", "to": 10},
            {"type": "parent", "to": 11},
            {"type": "sibling", "to": 20},
        ]

        with patch("app.services.kinship_service.crud") as crud_mock:
            crud_mock.get_tree_person = AsyncMock(return_value={"gender": "female"})

            result = await self.service.interpret(
                tree_id=10,
                relations=relations,
                target_id=20,
            )

        self.assertEqual(result, "предок тёти в 1-м поколении")

    async def test_interpret_distant_ancestor(self):
        relations = [
            {"type": "parent", "to": 10},
            {"type": "parent", "to": 11},
            {"type": "parent", "to": 12},
            {"type": "parent", "to": 20},
        ]

        with patch("app.services.kinship_service.crud") as crud_mock:
            crud_mock.get_tree_person = AsyncMock(return_value={"gender": "female"})

            result = await self.service.interpret(
                tree_id=10,
                relations=relations,
                target_id=20,
            )

        self.assertEqual(result, "предок в 4-м поколении")

    async def test_interpret_distant_descendant(self):
        relations = [
            {"type": "child", "to": 10},
            {"type": "child", "to": 11},
            {"type": "child", "to": 12},
            {"type": "child", "to": 20},
        ]

        with patch("app.services.kinship_service.crud") as crud_mock:
            crud_mock.get_tree_person = AsyncMock(return_value={"gender": "male"})

            result = await self.service.interpret(
                tree_id=10,
                relations=relations,
                target_id=20,
            )

        self.assertEqual(result, "потомок в 4-м поколении")

    async def test_interpret_marks_mixed_non_blood_path_as_complex(self):
        relations = [
            {"type": "spouse", "to": 10},
            {"type": "parent", "to": 20},
        ]

        with patch("app.services.kinship_service.crud") as crud_mock:
            crud_mock.get_tree_person = AsyncMock(return_value={"gender": "female"})

            result = await self.service.interpret(
                tree_id=10,
                relations=relations,
                target_id=20,
            )

        self.assertEqual(result, "сложное родство")

    async def test_interpret_marks_non_monotonic_blood_path_as_complex(self):
        relations = [
            {"type": "parent", "to": 10},
            {"type": "child", "to": 20},
            {"type": "parent", "to": 30},
        ]

        with patch("app.services.kinship_service.crud") as crud_mock:
            crud_mock.get_tree_person = AsyncMock(return_value={"gender": "female"})

            result = await self.service.interpret(
                tree_id=10,
                relations=relations,
                target_id=30,
            )

        self.assertEqual(result, "сложное родство")

    async def test_detect_line_uses_first_parent_for_collateral_blood_relation(self):
        relations = [
            {"type": "parent", "to": 10},
            {"type": "sibling", "to": 11},
            {"type": "child", "to": 20},
        ]

        with patch("app.services.kinship_service.crud") as crud_mock:
            crud_mock.get_tree_person = AsyncMock(return_value={"gender": "female"})

            line = await self.service.detect_line(tree_id=10, relations=relations)

        self.assertEqual(line, "по материнской линии")
        crud_mock.get_tree_person.assert_awaited_once_with(
            10,
            10,
            connection=None,
        )

    async def test_detect_line_does_not_label_sibling_path_via_parent(self):
        relations = [
            {"type": "parent", "to": 10},
            {"type": "child", "to": 20},
        ]

        with patch("app.services.kinship_service.crud") as crud_mock:
            crud_mock.get_tree_person = AsyncMock()

            line = await self.service.detect_line(tree_id=10, relations=relations)

        self.assertEqual(line, "")
        crud_mock.get_tree_person.assert_not_awaited()

    async def test_path_to_relations_normalizes_db_relationship_types(self):
        async def get_ordered_relationship_types(from_id, to_id, **kwargs):
            mapping = {
                (1, 2): [
                    {"relationship_type": " Parent "},
                    {"relationship_type": "parent"},
                ],
                (2, 1): [],
            }
            return mapping[(from_id, to_id)]

        with patch("app.services.kinship_service.crud") as crud_mock:
            crud_mock.get_ordered_relationship_types = AsyncMock(
                side_effect=get_ordered_relationship_types
            )

            relations = await self.service.path_to_relations(tree_id=10, path=[1, 2])

        self.assertEqual(relations, [{"type": "child", "to": 2}])

    async def test_interpret_self_short_circuits_without_db_lookup(self):
        with patch("app.services.kinship_service.crud") as crud_mock:
            crud_mock.get_tree_person = AsyncMock()

            result = await self.service.interpret(
                tree_id=10,
                relations=[],
                target_id=20,
            )

        self.assertEqual(result, "\u0442\u043e\u0442 \u0436\u0435 \u0447\u0435\u043b\u043e\u0432\u0435\u043a")
        crud_mock.get_tree_person.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
