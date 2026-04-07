from collections import deque

from app.db.crud import crud


class GraphService:

    async def build_graph(self, tree_id):
        relations = await crud.get_tree_relationships(tree_id)
        graph = {}

        for rel in relations:
            frm = rel["from_person_id"]
            to = rel["to_person_id"]

            if frm not in graph:
                graph[frm] = []
            if to not in graph:
                graph[to] = []

            graph[frm].append(to)
            graph[to].append(frm)

        return graph

    async def find_path(self, tree_id, start_id, end_id):
        graph = await self.build_graph(tree_id)
        queue = deque([(start_id, [start_id])])
        visited = {start_id}

        while queue:
            current, path = queue.popleft()

            if current == end_id:
                return path

            for neighbor in graph.get(current, []):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))

        return None

    async def get_ancestors(self, tree_id, person_id):
        relations = await crud.get_tree_relationships(tree_id)
        parents_map = {}

        for rel in relations:
            if rel["relationship_type"] == "parent":
                child = rel["to_person_id"]
                parent = rel["from_person_id"]
                parents_map.setdefault(child, []).append(parent)

        ancestors = {person_id: 0}
        queue = deque([(person_id, 0)])

        while queue:
            current, depth = queue.popleft()

            for parent in parents_map.get(current, []):
                if parent in ancestors:
                    continue
                ancestors[parent] = depth + 1
                queue.append((parent, depth + 1))

        return ancestors

    async def find_lca(self, tree_id, p1, p2):
        a1 = await self.get_ancestors(tree_id, p1)
        a2 = await self.get_ancestors(tree_id, p2)

        common = set(a1.keys()) & set(a2.keys())
        if not common:
            return None

        return min(common, key=lambda person_id: a1[person_id] + a2[person_id])


graph_service = GraphService()
