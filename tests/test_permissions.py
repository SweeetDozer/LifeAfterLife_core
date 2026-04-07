import unittest
from unittest.mock import AsyncMock, call, patch

from fastapi import HTTPException

from app.services import permissions


class PermissionsTests(unittest.IsolatedAsyncioTestCase):
    async def test_ensure_tree_edit_access_returns_403_for_view_only_user(self):
        with patch("app.services.permissions.crud") as crud_mock:
            crud_mock.get_tree = AsyncMock(return_value={"id": 10, "owner_id": 1})
            crud_mock.user_can_edit_tree = AsyncMock(return_value=False)
            crud_mock.user_can_view_tree = AsyncMock(return_value=True)

            with self.assertRaises(HTTPException) as context:
                await permissions.ensure_tree_edit_access(user_id=7, tree_id=10)

        self.assertEqual(context.exception.status_code, 403)
        self.assertEqual(context.exception.detail, "Access denied")

    async def test_ensure_tree_edit_access_returns_404_when_tree_is_hidden(self):
        with patch("app.services.permissions.crud") as crud_mock:
            crud_mock.get_tree = AsyncMock(return_value={"id": 10, "owner_id": 1})
            crud_mock.user_can_edit_tree = AsyncMock(return_value=False)
            crud_mock.user_can_view_tree = AsyncMock(return_value=False)

            with self.assertRaises(HTTPException) as context:
                await permissions.ensure_tree_edit_access(user_id=7, tree_id=10)

        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(context.exception.detail, "Tree not found")

    async def test_ensure_person_access_masks_tree_404_as_person_404(self):
        with (
            patch("app.services.permissions.crud") as crud_mock,
            patch(
                "app.services.permissions.ensure_tree_access",
                new=AsyncMock(
                    side_effect=HTTPException(status_code=404, detail="Tree not found")
                ),
            ),
        ):
            crud_mock.get_person = AsyncMock(return_value={"id": 5, "tree_id": 10})

            with self.assertRaises(HTTPException) as context:
                await permissions.ensure_person_view_access(user_id=7, person_id=5)

        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(context.exception.detail, "Person not found")

    async def test_ensure_tree_persons_access_preserves_requested_order(self):
        person_two = {"id": 2, "tree_id": 10}
        person_one = {"id": 1, "tree_id": 10}

        with (
            patch(
                "app.services.permissions.ensure_tree_access",
                new=AsyncMock(),
            ) as ensure_tree_access_mock,
            patch("app.services.permissions.crud") as crud_mock,
        ):
            crud_mock.get_tree_person = AsyncMock(side_effect=[person_two, person_one])

            persons = await permissions.ensure_tree_persons_access(
                user_id=7,
                tree_id=10,
                person_ids=[2, 1, 2],
                access="edit",
            )

        self.assertEqual(persons, [person_two, person_one, person_two])
        ensure_tree_access_mock.assert_awaited_once_with(
            7,
            10,
            access="edit",
            connection=None,
        )
        self.assertEqual(
            crud_mock.get_tree_person.await_args_list,
            [
                call(10, 2, connection=None),
                call(10, 1, connection=None),
            ],
        )

    async def test_ensure_same_tree_persons_access_rejects_cross_tree_pairs(self):
        with patch(
            "app.services.permissions.ensure_person_access",
            new=AsyncMock(
                side_effect=[
                    {"id": 1, "tree_id": 10},
                    {"id": 2, "tree_id": 11},
                ]
            ),
        ) as ensure_person_access_mock:
            with self.assertRaises(HTTPException) as context:
                await permissions.ensure_same_tree_persons_access(
                    user_id=7,
                    person_ids=[1, 2, 1],
                )

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(
            context.exception.detail,
            "Persons must belong to same tree",
        )
        self.assertEqual(
            ensure_person_access_mock.await_args_list,
            [
                call(7, 1, access="view", connection=None),
                call(7, 2, access="view", connection=None),
            ],
        )


if __name__ == "__main__":
    unittest.main()
