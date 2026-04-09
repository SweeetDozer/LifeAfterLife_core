import unittest

from app.services.relationship_semantics import (
    blood_relationship_types,
    get_relationship_definition,
    peer_relationship_types,
    relationship_priority,
    supported_relationship_types,
)


class RelationshipSemanticsTests(unittest.TestCase):
    def test_supported_relationship_types_remain_current_api_surface(self):
        self.assertEqual(
            supported_relationship_types(),
            frozenset({"parent", "spouse", "sibling", "friend"}),
        )

    def test_blood_and_peer_semantics_are_explicit(self):
        self.assertEqual(blood_relationship_types(), frozenset({"parent", "sibling"}))
        self.assertEqual(peer_relationship_types(), frozenset({"spouse", "sibling", "friend"}))

    def test_parent_definition_keeps_type_and_nature_separate(self):
        definition = get_relationship_definition("parent")

        self.assertIsNotNone(definition)
        self.assertEqual(definition.type_key, "parent")
        self.assertEqual(definition.axis, "vertical")
        self.assertEqual(definition.nature, "biological")
        self.assertEqual(definition.reciprocity, "directed")

    def test_relationship_priority_prefers_blood_over_social_edges(self):
        self.assertLess(relationship_priority("parent"), relationship_priority("spouse"))
        self.assertLess(relationship_priority("sibling"), relationship_priority("friend"))


if __name__ == "__main__":
    unittest.main()
