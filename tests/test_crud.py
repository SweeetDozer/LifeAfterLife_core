import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.db import crud as crud_module


class _AsyncContextManager:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeConnection:
    def __init__(self):
        self.execute = AsyncMock()
        self.fetchrow = AsyncMock()
        self.fetchval = AsyncMock()
        self.fetch = AsyncMock()

    def transaction(self):
        return _AsyncContextManager(None)


class CrudTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_user_normalizes_email_and_inserts_when_unique(self):
        connection = _FakeConnection()
        connection.fetchrow.return_value = None
        connection.fetchval.return_value = 11

        pool = MagicMock()
        pool.acquire.return_value = _AsyncContextManager(connection)

        with patch.object(crud_module.db, "pool", pool):
            user_id = await crud_module.crud.create_user(
                "  User@Example.COM  ",
                "hash-1",
            )

        self.assertEqual(user_id, 11)
        self.assertEqual(connection.execute.await_args.args[1], "user@example.com")
        self.assertEqual(connection.fetchrow.await_args.args[1], "user@example.com")
        self.assertEqual(
            connection.fetchval.await_args.args[1:],
            ("user@example.com", "hash-1"),
        )

    async def test_create_user_skips_insert_for_duplicate_email(self):
        connection = _FakeConnection()
        connection.fetchrow.return_value = {"id": 5}

        pool = MagicMock()
        pool.acquire.return_value = _AsyncContextManager(connection)

        with patch.object(crud_module.db, "pool", pool):
            user_id = await crud_module.crud.create_user(
                "User@Example.COM",
                "hash-1",
            )

        self.assertIsNone(user_id)
        connection.fetchval.assert_not_awaited()

    async def test_get_user_by_email_normalizes_lookup_key(self):
        pool = MagicMock()
        pool.fetchrow = AsyncMock(
            return_value={
                "id": 3,
                "email": "user@example.com",
                "password_hash": "hash",
                "created_at": "2026-01-01",
            }
        )

        with patch.object(crud_module.db, "pool", pool):
            user = await crud_module.crud.get_user_by_email(" User@Example.COM ")

        self.assertEqual(user["email"], "user@example.com")
        self.assertEqual(pool.fetchrow.await_args.args[1], "user@example.com")

    async def test_get_ordered_relationship_types_uses_connection_and_tree_scope(self):
        connection = _FakeConnection()
        connection.fetch.return_value = [{"relationship_type": "parent"}]

        pool = MagicMock()
        pool.fetch = AsyncMock(side_effect=AssertionError("pool should not be used"))

        with patch.object(crud_module.db, "pool", pool):
            relationships = await crud_module.crud.get_ordered_relationship_types(
                1,
                2,
                tree_id=10,
                connection=connection,
            )

        self.assertEqual(relationships, [{"relationship_type": "parent"}])
        self.assertIn("WHERE tree_id = $1", connection.fetch.await_args.args[0])
        self.assertEqual(connection.fetch.await_args.args[1:], (10, 1, 2))

    async def test_get_pair_relationships_without_tree_id_queries_both_directions(self):
        pool = MagicMock()
        pool.fetch = AsyncMock(
            return_value=[
                {
                    "id": 9,
                    "tree_id": 10,
                    "from_person_id": 1,
                    "to_person_id": 2,
                    "relationship_type": "friend",
                }
            ]
        )

        with patch.object(crud_module.db, "pool", pool):
            relationships = await crud_module.crud.get_pair_relationships(1, 2)

        self.assertEqual(relationships[0]["relationship_type"], "friend")
        self.assertIn(
            "OR (from_person_id = $2 AND to_person_id = $1)",
            pool.fetch.await_args.args[0],
        )
        self.assertEqual(pool.fetch.await_args.args[1:], (1, 2))


if __name__ == "__main__":
    unittest.main()
