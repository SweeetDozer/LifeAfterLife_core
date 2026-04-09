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


if __name__ == "__main__":
    unittest.main()
