from __future__ import annotations

import unittest
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
import asyncio
import json
from typing import Any
from urllib.parse import urlsplit
from unittest.mock import patch

from app.core.config import settings
from app.main import create_app


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class _AsyncContextManager:
    def __init__(self, value: Any):
        self.value = value

    async def __aenter__(self) -> Any:
        return self.value

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class _Record(dict):
    pass


class _InMemoryConnection:
    def __init__(self, state: "_InMemoryState"):
        self.state = state

    def transaction(self):
        return _AsyncContextManager(None)

    async def execute(self, query: str, *args):
        if "UPDATE users" in query:
            user_id, password_hash = args
            user = self.state.users.get(user_id)
            if user:
                user["password_hash"] = password_hash
            return "UPDATE 1"

        if "UPDATE family_trees" in query:
            tree_id, name, description, is_public = args
            updated = self.state.update_tree(tree_id, name, description, is_public)
            return "UPDATE 1" if updated else "UPDATE 0"

        if "DELETE FROM family_trees" in query:
            deleted = self.state.delete_tree(args[0])
            return "DELETE 1" if deleted else "DELETE 0"

        if "SELECT pg_advisory_xact_lock" in query:
            return "SELECT 1"

        if "INSERT INTO tree_access" in query:
            tree_id, user_id, access_level = args
            self.state.upsert_tree_access(tree_id, user_id, access_level)
            return "INSERT 0 1"

        if "DELETE FROM tree_access" in query:
            tree_id, user_id = args
            deleted = self.state.delete_tree_access(tree_id, user_id)
            return "DELETE 1" if deleted else "DELETE 0"

        if "UPDATE persons" in query:
            (
                person_id,
                first_name,
                middle_name,
                last_name,
                gender,
                birth_date,
                death_date,
                photo_url,
                description,
            ) = args
            updated = self.state.update_person(
                person_id=person_id,
                first_name=first_name,
                middle_name=middle_name,
                last_name=last_name,
                gender=gender,
                birth_date=birth_date,
                death_date=death_date,
                photo_url=photo_url,
                description=description,
            )
            return "UPDATE 1" if updated else "UPDATE 0"

        if "DELETE FROM persons" in query:
            deleted = self.state.delete_person(args[0])
            return "DELETE 1" if deleted else "DELETE 0"

        if "DELETE FROM relationships" in query:
            relationship_ids = args[0]
            if isinstance(relationship_ids, list):
                deleted_count = self.state.delete_relationships(relationship_ids)
                return f"DELETE {deleted_count}"

            deleted = self.state.delete_relationship(relationship_ids)
            return "DELETE 1" if deleted else "DELETE 0"

        raise AssertionError(f"Unsupported execute query: {query}")

    async def fetchrow(self, query: str, *args):
        if "FROM users" in query and "LOWER(email) = LOWER($1)" in query:
            normalized_email = args[0]
            user = self.state.find_user_by_email(normalized_email)
            if user is None:
                return None
            if "SELECT id" in query and "password_hash" not in query:
                return _Record(id=user["id"])
            return _Record(user.copy())

        if "FROM users" in query and "WHERE id = $1" in query:
            user_id = args[0]
            user = self.state.users.get(user_id)
            if user is None:
                return None
            if "password_hash" in query:
                return _Record(user.copy())
            public_user = {
                "id": user["id"],
                "email": user["email"],
                "created_at": user["created_at"],
            }
            return _Record(public_user)

        if "FROM family_trees" in query and "WHERE id = $1" in query:
            tree = self.state.trees.get(args[0])
            return _Record(tree.copy()) if tree else None

        if "FROM tree_access" in query and "JOIN users" in query:
            tree_id, user_id = args
            entry = self.state.get_tree_access_entry(tree_id, user_id)
            return _Record(entry.copy()) if entry else None

        if "FROM persons" in query and "WHERE tree_id = $1 AND id = $2" in query:
            tree_id, person_id = args
            person = self.state.persons.get(person_id)
            if person and person["tree_id"] == tree_id:
                return _Record(person.copy())
            return None

        if "FROM persons" in query and "WHERE id = $1" in query:
            person = self.state.persons.get(args[0])
            return _Record(person.copy()) if person else None

        if "FROM relationships" in query and "WHERE id = $1" in query:
            relationship = self.state.relationships.get(args[0])
            return _Record(relationship.copy()) if relationship else None

        raise AssertionError(f"Unsupported fetchrow query: {query}")

    async def fetchval(self, query: str, *args):
        if "INSERT INTO users" in query:
            email, password_hash = args
            return self.state.create_user(email, password_hash)

        if "INSERT INTO family_trees" in query:
            owner_id, name, description, is_public = args
            return self.state.create_tree(owner_id, name, description, is_public)

        if "CASE" in query and "WHEN family_trees.user_id = $1 THEN 'owner'" in query:
            user_id, tree_id = args
            return self.state.get_tree_role(user_id, tree_id)

        if "INSERT INTO persons" in query:
            (
                tree_id,
                first_name,
                middle_name,
                last_name,
                gender,
                birth_date,
                death_date,
                photo_url,
                description,
            ) = args
            return self.state.create_person(
                tree_id=tree_id,
                first_name=first_name,
                middle_name=middle_name,
                last_name=last_name,
                gender=gender,
                birth_date=birth_date,
                death_date=death_date,
                photo_url=photo_url,
                description=description,
            )

        if "INSERT INTO relationships" in query:
            tree_id, from_person_id, to_person_id, relationship_type = args
            return self.state.create_relationship(
                tree_id=tree_id,
                from_person_id=from_person_id,
                to_person_id=to_person_id,
                relationship_type=relationship_type,
            )

        if "SELECT COUNT(*)" in query and "FROM persons" in query:
            return self.state.count_tree_persons(args[0])

        if "SELECT COUNT(*)" in query and "FROM relationships" in query:
            if "WHERE tree_id = $1" in query:
                return self.state.count_tree_relationships(args[0])
            return self.state.count_person_relationships(args[0])

        if "SELECT COUNT(*)" in query and "FROM tree_access" in query:
            return self.state.count_tree_access_entries(args[0])

        raise AssertionError(f"Unsupported fetchval query: {query}")

    async def fetch(self, query: str, *args):
        if "FROM family_trees" in query and "LEFT JOIN tree_access" in query:
            return [tree.copy() for tree in self.state.get_user_trees(args[0])]

        if "FROM tree_access" in query and "JOIN users" in query:
            return [entry.copy() for entry in self.state.get_tree_access_list(args[0])]

        if "FROM persons" in query and "WHERE tree_id = $1" in query:
            return [person.copy() for person in self.state.get_tree_persons(args[0])]

        if (
            "FROM relationships" in query
            and "WHERE tree_id = $1" in query
            and "(from_person_id = $2 AND to_person_id = $3)" in query
        ):
            tree_id, first_person_id, second_person_id = args
            return [
                rel.copy()
                for rel in self.state.get_pair_relationships(
                    tree_id,
                    first_person_id,
                    second_person_id,
                )
            ]

        if (
            "FROM relationships" in query
            and "(from_person_id = $1 AND to_person_id = $2)" in query
        ):
            first_person_id, second_person_id = args
            return [
                rel.copy()
                for rel in self.state.get_pair_relationships(
                    None,
                    first_person_id,
                    second_person_id,
                )
            ]

        if "FROM relationships" in query and "WHERE tree_id = $1" in query:
            tree_id = args[0]
            if "SELECT DISTINCT relationship_type::text AS relationship_type" in query:
                from_person_id, to_person_id = args[1:]
                return [
                    {"relationship_type": rel["relationship_type"]}
                    for rel in self.state.get_ordered_relationship_types(
                        tree_id,
                        from_person_id,
                        to_person_id,
                    )
                ]
            return [rel.copy() for rel in self.state.get_tree_relationships(tree_id)]

        if "FROM relationships" in query and "WHERE from_person_id = $1 OR to_person_id = $1" in query:
            person_id = args[0]
            return [
                rel.copy()
                for rel in self.state.get_person_relationships(person_id)
            ]

        raise AssertionError(f"Unsupported fetch query: {query}")


class _InMemoryPool:
    def __init__(self, state: "_InMemoryState"):
        self.state = state
        self.connection = _InMemoryConnection(state)

    def acquire(self):
        return _AsyncContextManager(self.connection)

    async def execute(self, query: str, *args):
        return await self.connection.execute(query, *args)

    async def fetchrow(self, query: str, *args):
        return await self.connection.fetchrow(query, *args)

    async def fetchval(self, query: str, *args):
        return await self.connection.fetchval(query, *args)

    async def fetch(self, query: str, *args):
        return await self.connection.fetch(query, *args)


class _InMemoryState:
    def __init__(self):
        self.users: dict[int, dict[str, Any]] = {}
        self.trees: dict[int, dict[str, Any]] = {}
        self.persons: dict[int, dict[str, Any]] = {}
        self.relationships: dict[int, dict[str, Any]] = {}
        self.tree_access: dict[tuple[int, int], dict[str, Any]] = {}
        self.next_user_id = 1
        self.next_tree_id = 1
        self.next_person_id = 1
        self.next_relationship_id = 1

    def find_user_by_email(self, email: str) -> dict[str, Any] | None:
        normalized_email = email.strip().lower()
        for user in self.users.values():
            if user["email"] == normalized_email:
                return user
        return None

    def create_user(self, email: str, password_hash: str) -> int | None:
        normalized_email = email.strip().lower()
        if self.find_user_by_email(normalized_email):
            return None

        user_id = self.next_user_id
        self.next_user_id += 1
        self.users[user_id] = {
            "id": user_id,
            "email": normalized_email,
            "password_hash": password_hash,
            "created_at": _utcnow(),
        }
        return user_id

    def create_tree(
        self,
        owner_id: int,
        name: str,
        description: str | None,
        is_public: bool,
    ) -> int:
        tree_id = self.next_tree_id
        self.next_tree_id += 1
        self.trees[tree_id] = {
            "id": tree_id,
            "owner_id": owner_id,
            "name": name,
            "description": description,
            "is_public": is_public,
            "created_at": _utcnow(),
            "access_level": "owner",
        }
        return tree_id

    def update_tree(
        self,
        tree_id: int,
        name: str,
        description: str | None,
        is_public: bool,
    ) -> bool:
        tree = self.trees.get(tree_id)
        if not tree:
            return False
        tree["name"] = name
        tree["description"] = description
        tree["is_public"] = is_public
        return True

    def delete_tree(self, tree_id: int) -> bool:
        tree = self.trees.pop(tree_id, None)
        if tree is None:
            return False

        person_ids = [
            person_id
            for person_id, person in self.persons.items()
            if person["tree_id"] == tree_id
        ]
        for person_id in person_ids:
            self.delete_person(person_id)

        relationship_ids = [
            relationship_id
            for relationship_id, relationship in self.relationships.items()
            if relationship["tree_id"] == tree_id
        ]
        for relationship_id in relationship_ids:
            self.relationships.pop(relationship_id, None)

        access_keys = [
            key for key in self.tree_access if key[0] == tree_id
        ]
        for key in access_keys:
            self.tree_access.pop(key, None)

        return True

    def get_user_trees(self, user_id: int) -> list[dict[str, Any]]:
        result = []
        for tree in sorted(
            self.trees.values(),
            key=lambda tree: tree["created_at"],
            reverse=True,
        ):
            if tree["owner_id"] == user_id:
                result.append(tree.copy())
                continue

            access_entry = self.tree_access.get((tree["id"], user_id))
            if access_entry:
                shared_tree = tree.copy()
                shared_tree["access_level"] = access_entry["access_level"]
                result.append(shared_tree)

        return result

    def get_tree_role(self, user_id: int, tree_id: int) -> str | None:
        tree = self.trees.get(tree_id)
        if not tree:
            return None

        if tree["owner_id"] == user_id:
            return "owner"

        access_entry = self.tree_access.get((tree_id, user_id))
        if access_entry is not None:
            return {
                "view": "viewer",
                "edit": "editor",
            }.get(access_entry["access_level"], access_entry["access_level"])

        if tree["is_public"]:
            return "viewer"

        return None

    def upsert_tree_access(self, tree_id: int, user_id: int, access_level: str):
        self.tree_access[(tree_id, user_id)] = {
            "tree_id": tree_id,
            "user_id": user_id,
            "access_level": access_level,
        }

    def delete_tree_access(self, tree_id: int, user_id: int) -> bool:
        return self.tree_access.pop((tree_id, user_id), None) is not None

    def get_tree_access_list(self, tree_id: int) -> list[dict[str, Any]]:
        entries = []
        tree = self.trees.get(tree_id)
        owner_id = tree["owner_id"] if tree else None
        for (entry_tree_id, user_id), entry in self.tree_access.items():
            if entry_tree_id != tree_id:
                continue
            if owner_id == user_id:
                continue
            user = self.users.get(user_id)
            if not user:
                continue
            entries.append(
                {
                    "user_id": user_id,
                    "email": user["email"],
                    "access_level": entry["access_level"],
                }
            )
        entries.sort(key=lambda item: item["email"])
        return entries

    def get_tree_access_entry(self, tree_id: int, user_id: int) -> dict[str, Any] | None:
        tree = self.trees.get(tree_id)
        if tree and tree["owner_id"] == user_id:
            return None
        entry = self.tree_access.get((tree_id, user_id))
        if not entry:
            return None
        user = self.users.get(user_id)
        if not user:
            return None
        return {
            "user_id": user_id,
            "email": user["email"],
            "access_level": {
                "view": "viewer",
                "edit": "editor",
            }.get(entry["access_level"], entry["access_level"]),
        }

    def create_person(
        self,
        *,
        tree_id: int,
        first_name: str,
        middle_name: str | None,
        last_name: str | None,
        gender: str | None,
        birth_date,
        death_date,
        photo_url: str | None,
        description: str | None,
    ) -> int:
        person_id = self.next_person_id
        self.next_person_id += 1
        self.persons[person_id] = {
            "id": person_id,
            "tree_id": tree_id,
            "first_name": first_name,
            "middle_name": middle_name,
            "last_name": last_name,
            "birth_date": birth_date,
            "death_date": death_date,
            "gender": gender,
            "photo_url": photo_url,
            "description": description,
        }
        return person_id

    def update_person(
        self,
        *,
        person_id: int,
        first_name: str,
        middle_name: str | None,
        last_name: str | None,
        gender: str | None,
        birth_date,
        death_date,
        photo_url: str | None,
        description: str | None,
    ) -> bool:
        person = self.persons.get(person_id)
        if person is None:
            return False
        person.update(
            {
                "first_name": first_name,
                "middle_name": middle_name,
                "last_name": last_name,
                "gender": gender,
                "birth_date": birth_date,
                "death_date": death_date,
                "photo_url": photo_url,
                "description": description,
            }
        )
        return True

    def delete_person(self, person_id: int) -> bool:
        person = self.persons.pop(person_id, None)
        if person is None:
            return False

        relationship_ids = [
            relationship_id
            for relationship_id, relationship in self.relationships.items()
            if relationship["from_person_id"] == person_id
            or relationship["to_person_id"] == person_id
        ]
        for relationship_id in relationship_ids:
            self.relationships.pop(relationship_id, None)
        return True

    def get_tree_persons(self, tree_id: int) -> list[dict[str, Any]]:
        persons = [
            person.copy()
            for person in self.persons.values()
            if person["tree_id"] == tree_id
        ]
        persons.sort(
            key=lambda person: (
                person["first_name"],
                person["last_name"] or "",
                person["id"],
            )
        )
        return persons

    def count_tree_persons(self, tree_id: int) -> int:
        return len(
            [
                person
                for person in self.persons.values()
                if person["tree_id"] == tree_id
            ]
        )

    def create_relationship(
        self,
        *,
        tree_id: int,
        from_person_id: int,
        to_person_id: int,
        relationship_type: str,
    ) -> int | None:
        for relationship in self.relationships.values():
            if (
                relationship["from_person_id"] == from_person_id
                and relationship["to_person_id"] == to_person_id
                and relationship["relationship_type"] == relationship_type
            ):
                return None

        relationship_id = self.next_relationship_id
        self.next_relationship_id += 1
        self.relationships[relationship_id] = {
            "id": relationship_id,
            "tree_id": tree_id,
            "from_person_id": from_person_id,
            "to_person_id": to_person_id,
            "relationship_type": relationship_type,
        }
        return relationship_id

    def get_tree_relationships(self, tree_id: int) -> list[dict[str, Any]]:
        relationships = [
            relationship.copy()
            for relationship in self.relationships.values()
            if relationship["tree_id"] == tree_id
        ]
        relationships.sort(key=lambda relationship: relationship["id"])
        return relationships

    def count_tree_relationships(self, tree_id: int) -> int:
        return len(
            [
                relationship
                for relationship in self.relationships.values()
                if relationship["tree_id"] == tree_id
            ]
        )

    def get_person_relationships(self, person_id: int) -> list[dict[str, Any]]:
        relationships = [
            relationship.copy()
            for relationship in self.relationships.values()
            if relationship["from_person_id"] == person_id
            or relationship["to_person_id"] == person_id
        ]
        relationships.sort(key=lambda relationship: relationship["id"])
        return relationships

    def count_person_relationships(self, person_id: int) -> int:
        return len(self.get_person_relationships(person_id))

    def count_tree_access_entries(self, tree_id: int) -> int:
        tree = self.trees.get(tree_id)
        owner_id = tree["owner_id"] if tree else None
        return sum(
            1
            for (entry_tree_id, user_id) in self.tree_access
            if entry_tree_id == tree_id and user_id != owner_id
        )

    def delete_relationship(self, relationship_id: int) -> bool:
        return self.relationships.pop(relationship_id, None) is not None

    def delete_relationships(self, relationship_ids: list[int]) -> int:
        deleted_count = 0
        for relationship_id in relationship_ids:
            if self.delete_relationship(relationship_id):
                deleted_count += 1
        return deleted_count

    def get_pair_relationships(
        self,
        tree_id: int | None,
        first_person_id: int,
        second_person_id: int,
    ) -> list[dict[str, Any]]:
        relationships = [
            relationship.copy()
            for relationship in self.relationships.values()
            if (tree_id is None or relationship["tree_id"] == tree_id)
            and (
                (
                    relationship["from_person_id"] == first_person_id
                    and relationship["to_person_id"] == second_person_id
                )
                or (
                    relationship["from_person_id"] == second_person_id
                    and relationship["to_person_id"] == first_person_id
                )
            )
        ]
        relationships.sort(key=lambda relationship: relationship["id"])
        return relationships

    def get_ordered_relationship_types(
        self,
        tree_id: int,
        from_person_id: int,
        to_person_id: int,
    ) -> list[dict[str, str]]:
        relationship_types = sorted(
            {
                relationship["relationship_type"]
                for relationship in self.relationships.values()
                if relationship["tree_id"] == tree_id
                and relationship["from_person_id"] == from_person_id
                and relationship["to_person_id"] == to_person_id
            }
        )
        return [
            {"relationship_type": relationship_type}
            for relationship_type in relationship_types
        ]


class _TestResponse:
    def __init__(self, status_code: int, headers: list[tuple[bytes, bytes]], body: bytes):
        self.status_code = status_code
        self._body = body
        self.headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in headers
        }

    def json(self):
        if not self._body:
            return None
        return json.loads(self._body.decode("utf-8"))


class _AsgiTestClient:
    def __init__(self, app):
        self.app = app

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, path: str, json: dict[str, Any] | None = None, headers=None):
        body = b""
        request_headers = list((headers or {}).items())
        if json is not None:
            body = self._encode_json(json)
            request_headers.append(("content-type", "application/json"))
        return self.request("POST", path, headers=request_headers, body=body)

    def get(self, path: str, headers=None):
        return self.request("GET", path, headers=list((headers or {}).items()))

    def options(self, path: str, headers=None):
        return self.request("OPTIONS", path, headers=list((headers or {}).items()))

    @staticmethod
    def _encode_json(payload: dict[str, Any]) -> bytes:
        return json.dumps(payload, separators=(",", ":")).encode("utf-8")

    def request(
        self,
        method: str,
        path: str,
        headers: list[tuple[str, str]] | None = None,
        body: bytes = b"",
    ):
        return asyncio.run(
            self._request_async(
                method=method,
                path=path,
                headers=headers or [],
                body=body,
            )
        )

    async def _request_async(
        self,
        *,
        method: str,
        path: str,
        headers: list[tuple[str, str]],
        body: bytes,
    ):
        url = urlsplit(path)
        raw_headers = [
            (key.lower().encode("latin-1"), value.encode("latin-1"))
            for key, value in headers
        ]
        if not any(key == b"host" for key, _ in raw_headers):
            raw_headers.append((b"host", b"testserver"))

        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": method.upper(),
            "scheme": "http",
            "path": url.path,
            "raw_path": url.path.encode("ascii"),
            "query_string": url.query.encode("ascii"),
            "root_path": "",
            "headers": raw_headers,
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        }

        response_start: dict[str, Any] = {}
        response_body_chunks: list[bytes] = []
        body_sent = False

        async def receive():
            nonlocal body_sent
            if body_sent:
                return {"type": "http.disconnect"}
            body_sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message):
            if message["type"] == "http.response.start":
                response_start["status"] = message["status"]
                response_start["headers"] = message.get("headers", [])
            elif message["type"] == "http.response.body":
                response_body_chunks.append(message.get("body", b""))

        await self.app(scope, receive, send)
        return _TestResponse(
            status_code=response_start["status"],
            headers=response_start.get("headers", []),
            body=b"".join(response_body_chunks),
        )


class ApiIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.state = _InMemoryState()
        self.pool = _InMemoryPool(self.state)
        self.patch_stack = ExitStack()

        self.patch_stack.enter_context(
            patch.object(settings, "DB_HOST", "test-db")
        )
        self.patch_stack.enter_context(
            patch.object(settings, "DB_NAME", "test_lal")
        )
        self.patch_stack.enter_context(
            patch.object(settings, "DB_USER", "test_user")
        )
        self.patch_stack.enter_context(
            patch.object(settings, "DB_PASSWORD", "test_password")
        )
        self.patch_stack.enter_context(
            patch.object(settings, "DB_PORT", 5432)
        )
        self.patch_stack.enter_context(
            patch.object(settings, "SECRET_KEY", "test-secret-key-with-at-least-32-chars")
        )
        self.patch_stack.enter_context(
            patch.object(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 60)
        )
        self.patch_stack.enter_context(
            patch.object(settings, "ALLOW_LEGACY_TOKEN_HEADER", False)
        )
        self.patch_stack.enter_context(
            patch.object(
                settings,
                "CORS_ALLOW_ORIGINS",
                ["http://localhost:5173", "http://127.0.0.1:5173"],
            )
        )

        from app.db.database import db

        db.pool = self.pool

        self.client = _AsgiTestClient(create_app())
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        from app.db.database import db

        db.pool = None
        self.patch_stack.close()

    def _register_user(
        self,
        email: str = "user@example.com",
        password: str = "password123",
    ):
        return self.client.post(
            "/auth/register",
            json={"email": email, "password": password},
        )

    def _login_user(
        self,
        email: str = "user@example.com",
        password: str = "password123",
    ):
        return self.client.post(
            "/auth/login",
            json={"email": email, "password": password},
        )

    def _auth_headers(
        self,
        email: str = "user@example.com",
        password: str = "password123",
    ) -> dict[str, str]:
        self._register_user(email=email, password=password)
        login_response = self._login_user(email=email, password=password)
        token = login_response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def _create_tree(
        self,
        headers: dict[str, str],
        *,
        name: str = "Private tree",
        description: str | None = None,
        is_public: bool = False,
    ) -> int:
        response = self.client.post(
            "/trees/",
            json={
                "name": name,
                "description": description,
                "is_public": is_public,
            },
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["tree_id"]

    def _create_person(
        self,
        headers: dict[str, str],
        *,
        tree_id: int,
        first_name: str = "Anna",
    ) -> int:
        response = self.client.post(
            "/persons/",
            json={"tree_id": tree_id, "first_name": first_name},
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["person_id"]

    def _grant_tree_access(
        self,
        owner_headers: dict[str, str],
        *,
        tree_id: int,
        email: str,
        access_level: str,
    ):
        response = self.client.post(
            f"/trees/{tree_id}/access",
            json={"email": email, "access_level": access_level},
            headers=owner_headers,
        )
        self.assertEqual(response.status_code, 200)
        return response

    def _create_relationship(
        self,
        headers: dict[str, str],
        *,
        from_person_id: int,
        to_person_id: int,
        relationship_type: str,
    ) -> int:
        response = self.client.post(
            "/relationships/",
            json={
                "from_person_id": from_person_id,
                "to_person_id": to_person_id,
                "relationship_type": relationship_type,
            },
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["relationship_id"]

    def test_register_and_login_happy_path(self):
        register_response = self._register_user()
        self.assertEqual(register_response.status_code, 200)
        self.assertEqual(
            register_response.json(),
            {"detail": "If the account can be created, you can sign in."},
        )

        login_response = self._login_user()
        self.assertEqual(login_response.status_code, 200)
        login_payload = login_response.json()
        self.assertEqual(login_payload["token_type"], "bearer")
        self.assertTrue(login_payload["access_token"])

    def test_auth_rejects_invalid_payload_and_invalid_credentials(self):
        invalid_register_response = self.client.post(
            "/auth/register",
            json={"email": "not-an-email", "password": "123"},
        )
        self.assertEqual(invalid_register_response.status_code, 422)

        self._register_user()
        invalid_login_response = self._login_user(password="wrong-password")
        self.assertEqual(invalid_login_response.status_code, 401)
        self.assertEqual(
            invalid_login_response.json(),
            {"detail": "Invalid credentials"},
        )

    def test_protected_routes_require_token_and_allow_happy_path_with_token(self):
        unauthorized_response = self.client.post(
            "/trees/",
            json={"name": "Family tree", "description": "Main", "is_public": False},
        )
        self.assertEqual(unauthorized_response.status_code, 401)
        self.assertEqual(unauthorized_response.json(), {"detail": "Not authenticated"})

        headers = self._auth_headers()
        create_tree_response = self.client.post(
            "/trees/",
            json={"name": "Family tree", "description": "Main", "is_public": False},
            headers=headers,
        )
        self.assertEqual(create_tree_response.status_code, 200)
        tree_id = create_tree_response.json()["tree_id"]

        list_trees_response = self.client.get("/trees/", headers=headers)
        self.assertEqual(list_trees_response.status_code, 200)
        self.assertEqual(len(list_trees_response.json()), 1)
        self.assertEqual(list_trees_response.json()[0]["id"], tree_id)

    def test_persons_relationships_and_kinship_happy_path(self):
        headers = self._auth_headers()
        tree_response = self.client.post(
            "/trees/",
            json={"name": "Family tree", "description": None, "is_public": False},
            headers=headers,
        )
        tree_id = tree_response.json()["tree_id"]

        father_response = self.client.post(
            "/persons/",
            json={
                "tree_id": tree_id,
                "first_name": "Ivan",
                "gender": "male",
            },
            headers=headers,
        )
        self.assertEqual(father_response.status_code, 200)
        father_id = father_response.json()["person_id"]

        child_response = self.client.post(
            "/persons/",
            json={
                "tree_id": tree_id,
                "first_name": "Petr",
                "gender": "male",
            },
            headers=headers,
        )
        self.assertEqual(child_response.status_code, 200)
        child_id = child_response.json()["person_id"]

        list_persons_response = self.client.get(
            f"/persons/tree/{tree_id}",
            headers=headers,
        )
        self.assertEqual(list_persons_response.status_code, 200)
        self.assertEqual(len(list_persons_response.json()), 2)

        get_person_response = self.client.get(f"/persons/{father_id}", headers=headers)
        self.assertEqual(get_person_response.status_code, 200)
        self.assertEqual(get_person_response.json()["first_name"], "Ivan")

        relationship_response = self.client.post(
            "/relationships/",
            json={
                "from_person_id": father_id,
                "to_person_id": child_id,
                "relationship_type": "parent",
            },
            headers=headers,
        )
        self.assertEqual(relationship_response.status_code, 200)
        self.assertGreater(relationship_response.json()["relationship_id"], 0)

        kinship_response = self.client.get(
            f"/kinship/?tree_id={tree_id}&from_person_id={child_id}&to_person_id={father_id}",
            headers=headers,
        )
        self.assertEqual(kinship_response.status_code, 200)
        kinship_payload = kinship_response.json()
        self.assertEqual(kinship_payload["path"], [child_id, father_id])
        self.assertEqual(
            kinship_payload["relations"],
            [{"type": "parent", "to": father_id}],
        )
        self.assertEqual(kinship_payload["result"], "отец")
        self.assertEqual(kinship_payload["line"], "по отцовской линии")
        self.assertEqual(kinship_payload["lca"], father_id)

    def test_invalid_person_and_relationship_payloads_return_422(self):
        headers = self._auth_headers()
        tree_response = self.client.post(
            "/trees/",
            json={"name": "Family tree", "description": None, "is_public": False},
            headers=headers,
        )
        tree_id = tree_response.json()["tree_id"]

        invalid_person_response = self.client.post(
            "/persons/",
            json={"tree_id": tree_id, "first_name": ""},
            headers=headers,
        )
        self.assertEqual(invalid_person_response.status_code, 422)

        person_response = self.client.post(
            "/persons/",
            json={"tree_id": tree_id, "first_name": "Anna"},
            headers=headers,
        )
        person_id = person_response.json()["person_id"]
        invalid_relationship_response = self.client.post(
            "/relationships/",
            json={
                "from_person_id": person_id,
                "to_person_id": person_id,
                "relationship_type": "parent",
            },
            headers=headers,
        )
        self.assertEqual(invalid_relationship_response.status_code, 422)

    def test_cors_preflight_for_frontend_route_does_not_return_405(self):
        response = self.client.options(
            "/persons/",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )

        self.assertNotEqual(response.status_code, 405)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            "http://localhost:5173",
        )

    def test_role_based_access_owner_editor_viewer_and_outsider(self):
        owner_headers = self._auth_headers(email="owner@example.com")
        editor_headers = self._auth_headers(email="editor@example.com")
        viewer_headers = self._auth_headers(email="viewer@example.com")
        outsider_headers = self._auth_headers(email="outsider@example.com")

        tree_id = self._create_tree(
            owner_headers,
            name="Shared private tree",
            description="Initial",
        )
        person_id = self._create_person(
            owner_headers,
            tree_id=tree_id,
            first_name="Root",
        )
        self._grant_tree_access(
            owner_headers,
            tree_id=tree_id,
            email="editor@example.com",
            access_level="editor",
        )
        self._grant_tree_access(
            owner_headers,
            tree_id=tree_id,
            email="viewer@example.com",
            access_level="viewer",
        )

        owner_view_response = self.client.get(
            f"/persons/tree/{tree_id}",
            headers=owner_headers,
        )
        self.assertEqual(owner_view_response.status_code, 200)
        self.assertEqual(owner_view_response.json()[0]["id"], person_id)

        owner_edit_response = self.client.request(
            "PATCH",
            f"/trees/{tree_id}",
            headers=[*owner_headers.items(), ("content-type", "application/json")],
            body=json.dumps({"description": "Owner updated"}).encode("utf-8"),
        )
        self.assertEqual(owner_edit_response.status_code, 200)
        self.assertEqual(owner_edit_response.json()["access_level"], "owner")

        owner_access_response = self.client.get(
            f"/trees/{tree_id}/access",
            headers=owner_headers,
        )
        self.assertEqual(owner_access_response.status_code, 200)
        self.assertEqual(len(owner_access_response.json()), 3)

        editor_view_response = self.client.get(
            f"/persons/tree/{tree_id}",
            headers=editor_headers,
        )
        self.assertEqual(editor_view_response.status_code, 200)

        editor_edit_response = self.client.request(
            "PATCH",
            f"/trees/{tree_id}",
            headers=[*editor_headers.items(), ("content-type", "application/json")],
            body=json.dumps({"description": "Editor updated"}).encode("utf-8"),
        )
        self.assertEqual(editor_edit_response.status_code, 200)
        self.assertEqual(editor_edit_response.json()["access_level"], "editor")

        editor_access_list_response = self.client.get(
            f"/trees/{tree_id}/access",
            headers=editor_headers,
        )
        self.assertEqual(editor_access_list_response.status_code, 403)

        editor_self_promote_response = self.client.request(
            "PATCH",
            f"/trees/{tree_id}/access/2",
            headers=[*editor_headers.items(), ("content-type", "application/json")],
            body=json.dumps({"access_level": "viewer"}).encode("utf-8"),
        )
        self.assertEqual(editor_self_promote_response.status_code, 403)

        viewer_view_response = self.client.get(
            f"/persons/tree/{tree_id}",
            headers=viewer_headers,
        )
        self.assertEqual(viewer_view_response.status_code, 200)

        viewer_edit_response = self.client.request(
            "PATCH",
            f"/trees/{tree_id}",
            headers=[*viewer_headers.items(), ("content-type", "application/json")],
            body=json.dumps({"description": "Viewer updated"}).encode("utf-8"),
        )
        self.assertEqual(viewer_edit_response.status_code, 403)
        self.assertEqual(viewer_edit_response.json(), {"detail": "Access denied"})

        viewer_create_person_response = self.client.post(
            "/persons/",
            json={"tree_id": tree_id, "first_name": "Viewer child"},
            headers=viewer_headers,
        )
        self.assertEqual(viewer_create_person_response.status_code, 403)
        self.assertEqual(
            viewer_create_person_response.json(),
            {"detail": "Access denied"},
        )

        viewer_self_promote_response = self.client.request(
            "PATCH",
            f"/trees/{tree_id}/access/3",
            headers=[*viewer_headers.items(), ("content-type", "application/json")],
            body=json.dumps({"access_level": "editor"}).encode("utf-8"),
        )
        self.assertEqual(viewer_self_promote_response.status_code, 403)

        outsider_view_response = self.client.get(
            f"/persons/tree/{tree_id}",
            headers=outsider_headers,
        )
        self.assertEqual(outsider_view_response.status_code, 404)
        self.assertEqual(outsider_view_response.json(), {"detail": "Tree not found"})

        outsider_edit_response = self.client.request(
            "PATCH",
            f"/trees/{tree_id}",
            headers=[*outsider_headers.items(), ("content-type", "application/json")],
            body=json.dumps({"description": "Outsider updated"}).encode("utf-8"),
        )
        self.assertEqual(outsider_edit_response.status_code, 404)
        self.assertEqual(outsider_edit_response.json(), {"detail": "Tree not found"})

        outsider_access_response = self.client.get(
            f"/trees/{tree_id}/access",
            headers=outsider_headers,
        )
        self.assertEqual(outsider_access_response.status_code, 404)
        self.assertEqual(outsider_access_response.json(), {"detail": "Tree not found"})

        outsider_list_trees_response = self.client.get("/trees/", headers=outsider_headers)
        self.assertEqual(outsider_list_trees_response.status_code, 200)
        self.assertEqual(outsider_list_trees_response.json(), [])

    def test_owner_access_invariants_and_invalid_role_validation(self):
        owner_headers = self._auth_headers(email="owner@example.com")
        viewer_headers = self._auth_headers(email="viewer@example.com")

        tree_id = self._create_tree(owner_headers, name="Invariant tree")
        self._grant_tree_access(
            owner_headers,
            tree_id=tree_id,
            email="viewer@example.com",
            access_level="viewer",
        )

        revoke_owner_response = self.client.request(
            "DELETE",
            f"/trees/{tree_id}/access/1",
            headers=list(owner_headers.items()),
        )
        self.assertEqual(revoke_owner_response.status_code, 400)
        self.assertEqual(
            revoke_owner_response.json(),
            {"detail": "Cannot revoke owner access"},
        )

        demote_owner_response = self.client.request(
            "PATCH",
            f"/trees/{tree_id}/access/1",
            headers=[*owner_headers.items(), ("content-type", "application/json")],
            body=json.dumps({"access_level": "viewer"}).encode("utf-8"),
        )
        self.assertEqual(demote_owner_response.status_code, 400)
        self.assertEqual(
            demote_owner_response.json(),
            {"detail": "Cannot change owner access"},
        )

        viewer_grant_response = self.client.post(
            f"/trees/{tree_id}/access",
            json={"email": "viewer@example.com", "access_level": "editor"},
            headers=viewer_headers,
        )
        self.assertEqual(viewer_grant_response.status_code, 403)
        self.assertEqual(viewer_grant_response.json(), {"detail": "Access denied"})

        invalid_grant_role_response = self.client.post(
            f"/trees/{tree_id}/access",
            json={"email": "viewer@example.com", "access_level": "admin"},
            headers=owner_headers,
        )
        self.assertEqual(invalid_grant_role_response.status_code, 422)

        invalid_patch_role_response = self.client.request(
            "PATCH",
            f"/trees/{tree_id}/access/2",
            headers=[*owner_headers.items(), ("content-type", "application/json")],
            body=json.dumps({"access_level": ""}).encode("utf-8"),
        )
        self.assertEqual(invalid_patch_role_response.status_code, 422)

    def test_tree_access_owner_can_grant_list_and_revoke(self):
        owner_headers = self._auth_headers(email="owner@example.com")
        self._register_user(email="viewer@example.com")

        tree_response = self.client.post(
            "/trees/",
            json={"name": "Shared tree", "description": None, "is_public": False},
            headers=owner_headers,
        )
        tree_id = tree_response.json()["tree_id"]

        grant_response = self.client.post(
            f"/trees/{tree_id}/access",
            json={"email": "viewer@example.com", "access_level": "viewer"},
            headers=owner_headers,
        )
        self.assertEqual(grant_response.status_code, 200)
        self.assertEqual(
            grant_response.json(),
            {"user_id": 2, "access_level": "viewer"},
        )

        list_response = self.client.get(f"/trees/{tree_id}/access", headers=owner_headers)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(
            list_response.json(),
            [
                {
                    "user_id": 1,
                    "email": "owner@example.com",
                    "access_level": "owner",
                },
                {
                    "user_id": 2,
                    "email": "viewer@example.com",
                    "access_level": "viewer",
                },
            ],
        )

        revoke_response = self.client.request(
            "DELETE",
            f"/trees/{tree_id}/access/2",
            headers=list(owner_headers.items()),
        )
        self.assertEqual(revoke_response.status_code, 200)
        self.assertEqual(revoke_response.json(), {"detail": "Access revoked"})

        list_after_revoke_response = self.client.get(
            f"/trees/{tree_id}/access",
            headers=owner_headers,
        )
        self.assertEqual(
            list_after_revoke_response.json(),
            [
                {
                    "user_id": 1,
                    "email": "owner@example.com",
                    "access_level": "owner",
                }
            ],
        )

    def test_tree_access_owner_can_update_existing_role(self):
        owner_headers = self._auth_headers(email="owner@example.com")
        self._register_user(email="viewer@example.com")

        tree_id = self.client.post(
            "/trees/",
            json={"name": "Shared tree", "description": None, "is_public": False},
            headers=owner_headers,
        ).json()["tree_id"]

        self.client.post(
            f"/trees/{tree_id}/access",
            json={"email": "viewer@example.com", "access_level": "viewer"},
            headers=owner_headers,
        )

        update_response = self.client.request(
            "PATCH",
            f"/trees/{tree_id}/access/2",
            headers=[*owner_headers.items(), ("content-type", "application/json")],
            body=json.dumps({"access_level": "editor"}).encode("utf-8"),
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(
            update_response.json(),
            {"user_id": 2, "access_level": "editor"},
        )

        list_response = self.client.get(f"/trees/{tree_id}/access", headers=owner_headers)
        self.assertEqual(
            list_response.json(),
            [
                {
                    "user_id": 1,
                    "email": "owner@example.com",
                    "access_level": "owner",
                },
                {
                    "user_id": 2,
                    "email": "viewer@example.com",
                    "access_level": "editor",
                },
            ],
        )

    def test_tree_access_non_owner_cannot_manage_access(self):
        owner_headers = self._auth_headers(email="owner@example.com")
        viewer_headers = self._auth_headers(email="viewer@example.com")

        tree_response = self.client.post(
            "/trees/",
            json={"name": "Private tree", "description": None, "is_public": False},
            headers=owner_headers,
        )
        tree_id = tree_response.json()["tree_id"]

        owner_grant_response = self.client.post(
            f"/trees/{tree_id}/access",
            json={"email": "viewer@example.com", "access_level": "viewer"},
            headers=owner_headers,
        )
        self.assertEqual(owner_grant_response.status_code, 200)

        forbidden_grant_response = self.client.post(
            f"/trees/{tree_id}/access",
            json={"email": "owner@example.com", "access_level": "viewer"},
            headers=viewer_headers,
        )
        self.assertEqual(forbidden_grant_response.status_code, 403)
        self.assertEqual(forbidden_grant_response.json(), {"detail": "Access denied"})

        forbidden_list_response = self.client.get(
            f"/trees/{tree_id}/access",
            headers=viewer_headers,
        )
        self.assertEqual(forbidden_list_response.status_code, 403)
        self.assertEqual(forbidden_list_response.json(), {"detail": "Access denied"})

        forbidden_update_response = self.client.request(
            "PATCH",
            f"/trees/{tree_id}/access/2",
            headers=[*viewer_headers.items(), ("content-type", "application/json")],
            body=json.dumps({"access_level": "editor"}).encode("utf-8"),
        )
        self.assertEqual(forbidden_update_response.status_code, 403)
        self.assertEqual(forbidden_update_response.json(), {"detail": "Access denied"})

        forbidden_revoke_response = self.client.request(
            "DELETE",
            f"/trees/{tree_id}/access/2",
            headers=list(viewer_headers.items()),
        )
        self.assertEqual(forbidden_revoke_response.status_code, 403)
        self.assertEqual(forbidden_revoke_response.json(), {"detail": "Access denied"})

    def test_tree_access_accepts_legacy_access_level_aliases(self):
        owner_headers = self._auth_headers(email="owner@example.com")
        self._register_user(email="viewer@example.com")

        tree_id = self.client.post(
            "/trees/",
            json={"name": "Shared tree", "description": None, "is_public": False},
            headers=owner_headers,
        ).json()["tree_id"]

        grant_response = self.client.post(
            f"/trees/{tree_id}/access",
            json={"email": "viewer@example.com", "access_level": "view"},
            headers=owner_headers,
        )
        self.assertEqual(grant_response.status_code, 200)
        self.assertEqual(
            grant_response.json(),
            {"user_id": 2, "access_level": "viewer"},
        )

    def test_tree_access_rejects_owner_grant_duplicate_grant_and_invalid_updates(self):
        owner_headers = self._auth_headers(email="owner@example.com")
        self._register_user(email="viewer@example.com")

        tree_response = self.client.post(
            "/trees/",
            json={"name": "Private tree", "description": None, "is_public": False},
            headers=owner_headers,
        )
        tree_id = tree_response.json()["tree_id"]

        owner_grant_response = self.client.post(
            f"/trees/{tree_id}/access",
            json={"email": "owner@example.com", "access_level": "editor"},
            headers=owner_headers,
        )
        self.assertEqual(owner_grant_response.status_code, 400)
        self.assertEqual(
            owner_grant_response.json(),
            {"detail": "Owner already has full access"},
        )

        grant_response = self.client.post(
            f"/trees/{tree_id}/access",
            json={"email": "viewer@example.com", "access_level": "viewer"},
            headers=owner_headers,
        )
        self.assertEqual(grant_response.status_code, 200)

        duplicate_grant_response = self.client.post(
            f"/trees/{tree_id}/access",
            json={"email": "viewer@example.com", "access_level": "editor"},
            headers=owner_headers,
        )
        self.assertEqual(duplicate_grant_response.status_code, 409)
        self.assertEqual(
            duplicate_grant_response.json(),
            {"detail": "Access entry already exists"},
        )

        update_owner_response = self.client.request(
            "PATCH",
            f"/trees/{tree_id}/access/1",
            headers=[*owner_headers.items(), ("content-type", "application/json")],
            body=json.dumps({"access_level": "viewer"}).encode("utf-8"),
        )
        self.assertEqual(update_owner_response.status_code, 400)
        self.assertEqual(
            update_owner_response.json(),
            {"detail": "Cannot change owner access"},
        )

        update_missing_response = self.client.request(
            "PATCH",
            f"/trees/{tree_id}/access/999",
            headers=[*owner_headers.items(), ("content-type", "application/json")],
            body=json.dumps({"access_level": "viewer"}).encode("utf-8"),
        )
        self.assertEqual(update_missing_response.status_code, 404)
        self.assertEqual(
            update_missing_response.json(),
            {"detail": "Access entry not found"},
        )

        revoke_missing_response = self.client.request(
            "DELETE",
            f"/trees/{tree_id}/access/999",
            headers=list(owner_headers.items()),
        )
        self.assertEqual(revoke_missing_response.status_code, 404)
        self.assertEqual(
            revoke_missing_response.json(),
            {"detail": "Access entry not found"},
        )

        revoke_owner_response = self.client.request(
            "DELETE",
            f"/trees/{tree_id}/access/1",
            headers=list(owner_headers.items()),
        )
        self.assertEqual(revoke_owner_response.status_code, 400)
        self.assertEqual(
            revoke_owner_response.json(),
            {"detail": "Cannot revoke owner access"},
        )

    def test_tree_access_owner_source_of_truth_is_family_tree_owner_id(self):
        owner_headers = self._auth_headers(email="owner@example.com")

        tree_id = self.client.post(
            "/trees/",
            json={"name": "Owner tree", "description": None, "is_public": False},
            headers=owner_headers,
        ).json()["tree_id"]

        self.state.upsert_tree_access(tree_id, 1, "view")

        list_response = self.client.get(f"/trees/{tree_id}/access", headers=owner_headers)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(
            list_response.json(),
            [
                {
                    "user_id": 1,
                    "email": "owner@example.com",
                    "access_level": "owner",
                }
            ],
        )
        self.assertNotIn((tree_id, 1), self.state.tree_access)

    def test_person_patch_updates_only_provided_fields_and_delete_reports_cascade(self):
        headers = self._auth_headers()
        tree_response = self.client.post(
            "/trees/",
            json={"name": "Family tree", "description": "Main", "is_public": False},
            headers=headers,
        )
        tree_id = tree_response.json()["tree_id"]

        first_person_response = self.client.post(
            "/persons/",
            json={
                "tree_id": tree_id,
                "first_name": "Ivan",
                "middle_name": "Ivanovich",
                "description": "Original",
                "gender": "male",
            },
            headers=headers,
        )
        first_person_id = first_person_response.json()["person_id"]

        second_person_response = self.client.post(
            "/persons/",
            json={"tree_id": tree_id, "first_name": "Petr", "gender": "male"},
            headers=headers,
        )
        second_person_id = second_person_response.json()["person_id"]

        self.client.post(
            "/relationships/",
            json={
                "from_person_id": first_person_id,
                "to_person_id": second_person_id,
                "relationship_type": "parent",
            },
            headers=headers,
        )

        update_response = self.client.request(
            "PATCH",
            f"/persons/{first_person_id}",
            headers=[*headers.items(), ("content-type", "application/json")],
            body=json.dumps(
                {"middle_name": "", "description": None, "last_name": "Sidorov"}
            ).encode("utf-8"),
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["first_name"], "Ivan")
        self.assertIsNone(update_response.json()["middle_name"])
        self.assertIsNone(update_response.json()["description"])
        self.assertEqual(update_response.json()["last_name"], "Sidorov")

        delete_response = self.client.request(
            "DELETE",
            f"/persons/{first_person_id}",
            headers=list(headers.items()),
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(
            delete_response.json(),
            {
                "detail": "Person deleted; related relationships removed by database cascade",
                "deleted_relationships": 1,
            },
        )

    def test_tree_patch_and_owner_only_delete(self):
        owner_headers = self._auth_headers(email="owner@example.com")
        editor_headers = self._auth_headers(email="editor@example.com")

        tree_response = self.client.post(
            "/trees/",
            json={"name": "Original tree", "description": "Main", "is_public": False},
            headers=owner_headers,
        )
        tree_id = tree_response.json()["tree_id"]

        self.client.post(
            f"/trees/{tree_id}/access",
            json={"email": "editor@example.com", "access_level": "editor"},
            headers=owner_headers,
        )

        patch_response = self.client.request(
            "PATCH",
            f"/trees/{tree_id}",
            headers=[*editor_headers.items(), ("content-type", "application/json")],
            body=json.dumps({"description": "", "is_public": True}).encode("utf-8"),
        )
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.json()["name"], "Original tree")
        self.assertIsNone(patch_response.json()["description"])
        self.assertTrue(patch_response.json()["is_public"])

        forbidden_delete_response = self.client.request(
            "DELETE",
            f"/trees/{tree_id}",
            headers=list(editor_headers.items()),
        )
        self.assertEqual(forbidden_delete_response.status_code, 403)

        owner_delete_response = self.client.request(
            "DELETE",
            f"/trees/{tree_id}",
            headers=list(owner_headers.items()),
        )
        self.assertEqual(owner_delete_response.status_code, 200)
        self.assertEqual(
            owner_delete_response.json(),
            {
                "detail": "Tree deleted",
                "deleted_persons": 0,
                "deleted_relationships": 0,
                "deleted_access_entries": 1,
            },
        )

    def test_relationship_delete_removes_peer_pair(self):
        headers = self._auth_headers()
        tree_response = self.client.post(
            "/trees/",
            json={"name": "Family tree", "description": None, "is_public": False},
            headers=headers,
        )
        tree_id = tree_response.json()["tree_id"]

        first_person_id = self.client.post(
            "/persons/",
            json={"tree_id": tree_id, "first_name": "Anna"},
            headers=headers,
        ).json()["person_id"]
        second_person_id = self.client.post(
            "/persons/",
            json={"tree_id": tree_id, "first_name": "Maria"},
            headers=headers,
        ).json()["person_id"]

        relationship_id = self.client.post(
            "/relationships/",
            json={
                "from_person_id": first_person_id,
                "to_person_id": second_person_id,
                "relationship_type": "sibling",
            },
            headers=headers,
        ).json()["relationship_id"]

        delete_response = self.client.request(
            "DELETE",
            f"/relationships/{relationship_id}",
            headers=list(headers.items()),
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(
            delete_response.json(),
            {"detail": "Relationship deleted", "deleted_relationships": 2},
        )

    def test_delete_person_cascades_relationships_and_blocks_graph_and_kinship_on_deleted_vertex(self):
        headers = self._auth_headers()
        tree_id = self._create_tree(headers, name="Cascade person tree")
        parent_id = self._create_person(headers, tree_id=tree_id, first_name="Parent")
        child_id = self._create_person(headers, tree_id=tree_id, first_name="Child")
        relationship_id = self._create_relationship(
            headers,
            from_person_id=parent_id,
            to_person_id=child_id,
            relationship_type="parent",
        )

        delete_response = self.client.request(
            "DELETE",
            f"/persons/{child_id}",
            headers=list(headers.items()),
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(
            delete_response.json(),
            {
                "detail": "Person deleted; related relationships removed by database cascade",
                "deleted_relationships": 1,
            },
        )

        self.assertEqual(
            self.client.get(f"/persons/{child_id}", headers=headers).status_code,
            404,
        )
        self.assertEqual(
            self.client.request(
                "DELETE",
                f"/relationships/{relationship_id}",
                headers=list(headers.items()),
            ).json(),
            {"detail": "Relationship not found"},
        )
        self.assertEqual(
            self.client.get(
                f"/graph/path?tree_id={tree_id}&from_person_id={parent_id}&to_person_id={child_id}",
                headers=headers,
            ).json(),
            {"detail": "Person not found"},
        )
        self.assertEqual(
            self.client.get(
                f"/kinship/?tree_id={tree_id}&from_person_id={parent_id}&to_person_id={child_id}",
                headers=headers,
            ).json(),
            {"detail": "Person not found"},
        )
        self.assertNotIn(child_id, self.state.persons)
        self.assertEqual(self.state.get_person_relationships(child_id), [])

    def test_delete_tree_cascades_persons_relationships_and_access_entries(self):
        owner_headers = self._auth_headers(email="owner@example.com")
        viewer_headers = self._auth_headers(email="viewer@example.com")
        tree_id = self._create_tree(owner_headers, name="Cascade tree")
        first_person_id = self._create_person(owner_headers, tree_id=tree_id, first_name="Anna")
        second_person_id = self._create_person(owner_headers, tree_id=tree_id, first_name="Maria")
        relationship_id = self._create_relationship(
            owner_headers,
            from_person_id=first_person_id,
            to_person_id=second_person_id,
            relationship_type="spouse",
        )
        self._grant_tree_access(
            owner_headers,
            tree_id=tree_id,
            email="viewer@example.com",
            access_level="viewer",
        )

        delete_response = self.client.request(
            "DELETE",
            f"/trees/{tree_id}",
            headers=list(owner_headers.items()),
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(
            delete_response.json(),
            {
                "detail": "Tree deleted",
                "deleted_persons": 2,
                "deleted_relationships": 2,
                "deleted_access_entries": 1,
            },
        )

        self.assertEqual(self.client.get("/trees/", headers=owner_headers).json(), [])
        self.assertEqual(self.client.get("/trees/", headers=viewer_headers).json(), [])
        self.assertEqual(
            self.client.get(f"/persons/tree/{tree_id}", headers=owner_headers).json(),
            {"detail": "Tree not found"},
        )
        self.assertEqual(
            self.client.get(f"/persons/{first_person_id}", headers=owner_headers).json(),
            {"detail": "Person not found"},
        )
        self.assertEqual(
            self.client.request(
                "DELETE",
                f"/relationships/{relationship_id}",
                headers=list(owner_headers.items()),
            ).json(),
            {"detail": "Relationship not found"},
        )
        self.assertEqual(
            self.client.get(f"/trees/{tree_id}/access", headers=owner_headers).json(),
            {"detail": "Tree not found"},
        )
        self.assertEqual(
            self.client.get(
                f"/graph/path?tree_id={tree_id}&from_person_id={first_person_id}&to_person_id={second_person_id}",
                headers=owner_headers,
            ).json(),
            {"detail": "Tree not found"},
        )
        self.assertFalse(any(person["tree_id"] == tree_id for person in self.state.persons.values()))
        self.assertFalse(
            any(relationship["tree_id"] == tree_id for relationship in self.state.relationships.values())
        )
        self.assertFalse(any(key[0] == tree_id for key in self.state.tree_access))

    def test_delete_parent_relationship_removes_only_one_directed_edge(self):
        headers = self._auth_headers()
        tree_id = self._create_tree(headers, name="Parent delete tree")
        first_parent_id = self._create_person(headers, tree_id=tree_id, first_name="First")
        second_parent_id = self._create_person(headers, tree_id=tree_id, first_name="Second")
        child_id = self._create_person(headers, tree_id=tree_id, first_name="Child")
        first_relationship_id = self._create_relationship(
            headers,
            from_person_id=first_parent_id,
            to_person_id=child_id,
            relationship_type="parent",
        )
        self._create_relationship(
            headers,
            from_person_id=second_parent_id,
            to_person_id=child_id,
            relationship_type="parent",
        )

        delete_response = self.client.request(
            "DELETE",
            f"/relationships/{first_relationship_id}",
            headers=list(headers.items()),
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(
            delete_response.json(),
            {"detail": "Relationship deleted", "deleted_relationships": 1},
        )

        no_path_response = self.client.get(
            f"/graph/path?tree_id={tree_id}&from_person_id={child_id}&to_person_id={first_parent_id}",
            headers=headers,
        )
        self.assertEqual(no_path_response.status_code, 404)
        self.assertEqual(no_path_response.json(), {"detail": "No path found"})

        surviving_path_response = self.client.get(
            f"/graph/path?tree_id={tree_id}&from_person_id={child_id}&to_person_id={second_parent_id}",
            headers=headers,
        )
        self.assertEqual(surviving_path_response.status_code, 200)
        self.assertEqual(
            surviving_path_response.json(),
            {"path": [child_id, second_parent_id]},
        )
        surviving_kinship_response = self.client.get(
            f"/kinship/?tree_id={tree_id}&from_person_id={child_id}&to_person_id={second_parent_id}",
            headers=headers,
        )
        self.assertEqual(surviving_kinship_response.status_code, 200)
        self.assertEqual(
            surviving_kinship_response.json()["path"],
            [child_id, second_parent_id],
        )
        self.assertEqual(
            self.state.get_pair_relationships(tree_id, child_id, first_parent_id),
            [],
        )

    def test_delete_peer_relationship_removes_symmetric_pair_for_all_peer_types(self):
        headers = self._auth_headers()

        for relationship_type in ("spouse", "sibling", "friend"):
            with self.subTest(relationship_type=relationship_type):
                tree_id = self._create_tree(headers, name=f"{relationship_type} tree")
                first_person_id = self._create_person(
                    headers,
                    tree_id=tree_id,
                    first_name=f"{relationship_type}-a",
                )
                second_person_id = self._create_person(
                    headers,
                    tree_id=tree_id,
                    first_name=f"{relationship_type}-b",
                )
                relationship_id = self._create_relationship(
                    headers,
                    from_person_id=first_person_id,
                    to_person_id=second_person_id,
                    relationship_type=relationship_type,
                )

                pair_before_delete = self.state.get_pair_relationships(
                    tree_id,
                    first_person_id,
                    second_person_id,
                )
                self.assertEqual(len(pair_before_delete), 2)

                delete_response = self.client.request(
                    "DELETE",
                    f"/relationships/{relationship_id}",
                    headers=list(headers.items()),
                )
                self.assertEqual(delete_response.status_code, 200)
                self.assertEqual(
                    delete_response.json(),
                    {"detail": "Relationship deleted", "deleted_relationships": 2},
                )
                self.assertEqual(
                    self.state.get_pair_relationships(
                        tree_id,
                        first_person_id,
                        second_person_id,
                    ),
                    [],
                )

                no_path_response = self.client.get(
                    f"/graph/path?tree_id={tree_id}&from_person_id={first_person_id}&to_person_id={second_person_id}",
                    headers=headers,
                )
                self.assertEqual(no_path_response.status_code, 404)
                self.assertEqual(no_path_response.json(), {"detail": "No path found"})
                no_kinship_response = self.client.get(
                    f"/kinship/?tree_id={tree_id}&from_person_id={first_person_id}&to_person_id={second_person_id}",
                    headers=headers,
                )
                self.assertEqual(no_kinship_response.status_code, 404)
                self.assertEqual(no_kinship_response.json(), {"detail": "No path"})

    def test_repeat_delete_returns_not_found_for_tree_person_and_relationship(self):
        headers = self._auth_headers()

        tree_id = self._create_tree(headers, name="Repeat delete tree")
        tree_delete_response = self.client.request(
            "DELETE",
            f"/trees/{tree_id}",
            headers=list(headers.items()),
        )
        self.assertEqual(tree_delete_response.status_code, 200)
        repeated_tree_delete_response = self.client.request(
            "DELETE",
            f"/trees/{tree_id}",
            headers=list(headers.items()),
        )
        self.assertEqual(repeated_tree_delete_response.status_code, 404)
        self.assertEqual(
            repeated_tree_delete_response.json(),
            {"detail": "Tree not found"},
        )

        tree_id = self._create_tree(headers, name="Repeat delete person tree")
        person_id = self._create_person(headers, tree_id=tree_id, first_name="Ghost")
        person_delete_response = self.client.request(
            "DELETE",
            f"/persons/{person_id}",
            headers=list(headers.items()),
        )
        self.assertEqual(person_delete_response.status_code, 200)
        repeated_person_delete_response = self.client.request(
            "DELETE",
            f"/persons/{person_id}",
            headers=list(headers.items()),
        )
        self.assertEqual(repeated_person_delete_response.status_code, 404)
        self.assertEqual(
            repeated_person_delete_response.json(),
            {"detail": "Person not found"},
        )

        tree_id = self._create_tree(headers, name="Repeat delete relationship tree")
        first_person_id = self._create_person(headers, tree_id=tree_id, first_name="Left")
        second_person_id = self._create_person(headers, tree_id=tree_id, first_name="Right")
        relationship_id = self._create_relationship(
            headers,
            from_person_id=first_person_id,
            to_person_id=second_person_id,
            relationship_type="friend",
        )
        relationship_delete_response = self.client.request(
            "DELETE",
            f"/relationships/{relationship_id}",
            headers=list(headers.items()),
        )
        self.assertEqual(relationship_delete_response.status_code, 200)
        repeated_relationship_delete_response = self.client.request(
            "DELETE",
            f"/relationships/{relationship_id}",
            headers=list(headers.items()),
        )
        self.assertEqual(repeated_relationship_delete_response.status_code, 404)
        self.assertEqual(
            repeated_relationship_delete_response.json(),
            {"detail": "Relationship not found"},
        )

    def test_delete_routes_reject_missing_entities_and_users_without_required_rights(self):
        owner_headers = self._auth_headers(email="owner@example.com")
        editor_headers = self._auth_headers(email="editor@example.com")
        outsider_headers = self._auth_headers(email="outsider@example.com")
        tree_id = self._create_tree(owner_headers, name="Protected tree")
        person_id = self._create_person(owner_headers, tree_id=tree_id, first_name="Protected")
        other_person_id = self._create_person(owner_headers, tree_id=tree_id, first_name="Other")
        relationship_id = self._create_relationship(
            owner_headers,
            from_person_id=person_id,
            to_person_id=other_person_id,
            relationship_type="parent",
        )
        self._grant_tree_access(
            owner_headers,
            tree_id=tree_id,
            email="editor@example.com",
            access_level="editor",
        )

        missing_person_delete = self.client.request(
            "DELETE",
            "/persons/999",
            headers=list(owner_headers.items()),
        )
        self.assertEqual(missing_person_delete.status_code, 404)
        self.assertEqual(missing_person_delete.json(), {"detail": "Person not found"})

        missing_relationship_delete = self.client.request(
            "DELETE",
            "/relationships/999",
            headers=list(owner_headers.items()),
        )
        self.assertEqual(missing_relationship_delete.status_code, 404)
        self.assertEqual(
            missing_relationship_delete.json(),
            {"detail": "Relationship not found"},
        )

        missing_tree_delete = self.client.request(
            "DELETE",
            "/trees/999",
            headers=list(owner_headers.items()),
        )
        self.assertEqual(missing_tree_delete.status_code, 404)
        self.assertEqual(missing_tree_delete.json(), {"detail": "Tree not found"})

        forbidden_tree_delete = self.client.request(
            "DELETE",
            f"/trees/{tree_id}",
            headers=list(editor_headers.items()),
        )
        self.assertEqual(forbidden_tree_delete.status_code, 403)
        self.assertEqual(forbidden_tree_delete.json(), {"detail": "Access denied"})

        hidden_person_delete = self.client.request(
            "DELETE",
            f"/persons/{person_id}",
            headers=list(outsider_headers.items()),
        )
        self.assertEqual(hidden_person_delete.status_code, 404)
        self.assertEqual(hidden_person_delete.json(), {"detail": "Person not found"})

        hidden_relationship_delete = self.client.request(
            "DELETE",
            f"/relationships/{relationship_id}",
            headers=list(outsider_headers.items()),
        )
        self.assertEqual(hidden_relationship_delete.status_code, 404)
        self.assertEqual(hidden_relationship_delete.json(), {"detail": "Tree not found"})


if __name__ == "__main__":
    unittest.main()
