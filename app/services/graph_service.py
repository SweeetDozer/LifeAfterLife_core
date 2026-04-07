from collections import defaultdict, deque
from dataclasses import dataclass

from app.db.crud import crud


@dataclass(frozen=True)
class _GraphState:
    adjacency: dict[int, tuple[int, ...]]
    relationship_types: dict[tuple[int, int], tuple[str, ...]]
    parents_map: dict[int, tuple[int, ...]]


class GraphService:

    @staticmethod
    def _normalize_person_id(value):
        if isinstance(value, bool):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalize_relationship_type(value):
        if not isinstance(value, str):
            return None
        relationship_type = value.strip().lower()
        return relationship_type or None

    @classmethod
    def _build_graph_state(cls, relations):
        adjacency = defaultdict(set)
        relationship_types = defaultdict(set)
        parents_map = defaultdict(set)

        for relation in relations or []:
            if not isinstance(relation, dict):
                continue

            from_person_id = cls._normalize_person_id(relation.get("from_person_id"))
            to_person_id = cls._normalize_person_id(relation.get("to_person_id"))
            relationship_type = cls._normalize_relationship_type(
                relation.get("relationship_type")
            )

            if (
                from_person_id is None
                or to_person_id is None
                or relationship_type is None
                or from_person_id == to_person_id
            ):
                continue

            adjacency[from_person_id].add(to_person_id)
            adjacency[to_person_id].add(from_person_id)
            relationship_types[(from_person_id, to_person_id)].add(relationship_type)

            if relationship_type == "parent":
                parents_map[to_person_id].add(from_person_id)

        return _GraphState(
            adjacency={
                person_id: tuple(sorted(neighbors))
                for person_id, neighbors in adjacency.items()
            },
            relationship_types={
                pair: tuple(sorted(types))
                for pair, types in relationship_types.items()
            },
            parents_map={
                child_id: tuple(sorted(parent_ids))
                for child_id, parent_ids in parents_map.items()
            },
        )

    async def _load_graph_state(self, tree_id, connection=None):
        relations = await crud.get_tree_relationships(tree_id, connection=connection)
        return self._build_graph_state(relations)

    @staticmethod
    def _find_path_node_ids(adjacency, start_id, end_id):
        if start_id == end_id:
            return [start_id]

        queue = deque([start_id])
        previous = {start_id: None}

        while queue:
            current = queue.popleft()

            for neighbor in adjacency.get(current, ()):
                if neighbor in previous:
                    continue

                previous[neighbor] = current
                if neighbor == end_id:
                    return GraphService._reconstruct_path(previous, end_id)

                queue.append(neighbor)

        return None

    @staticmethod
    def _reconstruct_path(previous, end_id):
        if end_id not in previous:
            return None

        path = []
        current = end_id

        while current is not None:
            path.append(current)
            current = previous[current]

        path.reverse()
        return path

    @staticmethod
    def _build_path_steps(path, relationship_types):
        steps = []

        for current_id, next_id in zip(path, path[1:]):
            steps.append(
                {
                    "from_person_id": current_id,
                    "to_person_id": next_id,
                    "direct_relationship_types": list(
                        relationship_types.get((current_id, next_id), ())
                    ),
                    "reverse_relationship_types": list(
                        relationship_types.get((next_id, current_id), ())
                    ),
                }
            )

        return steps

    @staticmethod
    def _get_ancestors_from_parents_map(parents_map, person_id):
        ancestors = {person_id: 0}
        queue = deque([(person_id, 0)])

        while queue:
            current, depth = queue.popleft()

            for parent_id in parents_map.get(current, ()):
                if parent_id in ancestors:
                    continue

                ancestors[parent_id] = depth + 1
                queue.append((parent_id, depth + 1))

        return ancestors

    async def build_graph(self, tree_id, connection=None):
        state = await self._load_graph_state(tree_id, connection=connection)
        return {
            person_id: list(neighbors) for person_id, neighbors in state.adjacency.items()
        }

    async def find_path_details(self, tree_id, start_id, end_id, connection=None):
        start_person_id = self._normalize_person_id(start_id)
        end_person_id = self._normalize_person_id(end_id)
        if start_person_id is None or end_person_id is None:
            return None

        state = await self._load_graph_state(tree_id, connection=connection)

        # Simplified model: every stored relationship counts as one hop.
        # We keep the current "shortest path in the graph" idea, but this does
        # not try to rank equally short paths by genealogical meaning.
        path = self._find_path_node_ids(
            state.adjacency,
            start_person_id,
            end_person_id,
        )
        if path is None:
            return None

        return {
            "path": path,
            "steps": self._build_path_steps(path, state.relationship_types),
        }

    async def find_path(self, tree_id, start_id, end_id, connection=None):
        path_details = await self.find_path_details(
            tree_id,
            start_id,
            end_id,
            connection=connection,
        )
        if path_details is None:
            return None
        return path_details["path"]

    async def get_ancestors(self, tree_id, person_id, connection=None):
        normalized_person_id = self._normalize_person_id(person_id)
        if normalized_person_id is None:
            return {}

        state = await self._load_graph_state(tree_id, connection=connection)
        return self._get_ancestors_from_parents_map(
            state.parents_map,
            normalized_person_id,
        )

    async def find_lca(self, tree_id, p1, p2, connection=None):
        first_person_id = self._normalize_person_id(p1)
        second_person_id = self._normalize_person_id(p2)
        if first_person_id is None or second_person_id is None:
            return None

        state = await self._load_graph_state(tree_id, connection=connection)
        first_ancestors = self._get_ancestors_from_parents_map(
            state.parents_map,
            first_person_id,
        )
        second_ancestors = self._get_ancestors_from_parents_map(
            state.parents_map,
            second_person_id,
        )

        common_ancestors = set(first_ancestors) & set(second_ancestors)
        if not common_ancestors:
            return None

        # Simplified family graphs can have multiple equally near common
        # ancestors, for example both parents of siblings. Return one of them
        # deterministically so callers do not depend on hash/set ordering.
        return min(
            common_ancestors,
            key=lambda person_id: (
                first_ancestors[person_id] + second_ancestors[person_id],
                max(first_ancestors[person_id], second_ancestors[person_id]),
                person_id,
            ),
        )


graph_service = GraphService()
