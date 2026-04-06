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

            graph[frm].append(to)

        return graph

    async def find_path(self, tree_id, start_id, end_id):
        graph = await self.build_graph(tree_id)

        queue = deque([(start_id, [start_id])])
        visited = set()

        while queue:
            current, path = queue.popleft()

            if current == end_id:
                return path

            if current in visited:
                continue

            visited.add(current)

            for neighbor in graph.get(current, []):
                queue.append((neighbor, path + [neighbor]))

        return None


graph_service = GraphService()