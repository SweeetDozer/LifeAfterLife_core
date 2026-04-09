import unittest
from unittest.mock import AsyncMock, patch

from app.db.crud import crud


class TreeAccessValidationTests(unittest.IsolatedAsyncioTestCase):
    async def test_upsert_tree_access_rejects_unsupported_role(self):
        with patch("app.db.crud.db") as db_mock:
            db_mock.pool.execute = AsyncMock()

            with self.assertRaises(ValueError) as context:
                await crud.upsert_tree_access(1, 2, "owner")

        self.assertEqual(
            str(context.exception),
            "Unsupported tree access role: owner",
        )
        db_mock.pool.execute.assert_not_awaited()

    async def test_get_tree_role_query_uses_canonical_tree_access_labels(self):
        with patch("app.db.crud.db") as db_mock:
            db_mock.pool.fetchval = AsyncMock(return_value="editor")

            role = await crud.get_tree_role(7, 10)

        self.assertEqual(role, "editor")
        query = db_mock.pool.fetchval.await_args.args[0]
        self.assertIn("tree_access.access_level::text", query)
        self.assertNotIn("tree_access.access_level = 'view'", query)
        self.assertNotIn("tree_access.access_level = 'edit'", query)


if __name__ == "__main__":
    unittest.main()
