from app.db.crud import crud


class RelationshipService:

    async def create_relationship(self, from_id, to_id, rel_type):
        if from_id == to_id:
            raise ValueError("Cannot relate person to themselves")

        person1 = await crud.get_person(from_id)
        person2 = await crud.get_person(to_id)

        if not person1 or not person2:
            raise ValueError("Person not found")

        if person1["tree_id"] != person2["tree_id"]:
            raise ValueError("Persons must belong to same tree")

        tree_id = person1["tree_id"]
        created_id = await crud.create_relationship(tree_id, from_id, to_id, rel_type)

        if created_id is None:
            raise ValueError("Relationship already exists")

        if rel_type in ["spouse", "sibling", "friend"]:
            await crud.create_relationship(tree_id, to_id, from_id, rel_type)

        return created_id


service = RelationshipService()
