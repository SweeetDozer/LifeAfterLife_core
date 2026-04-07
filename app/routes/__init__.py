from . import auth, graph, kinship, persons, relationships, trees

ROUTERS = (
    auth.router,
    trees.router,
    persons.router,
    relationships.router,
    graph.router,
    kinship.router,
)

__all__ = ["ROUTERS"]
