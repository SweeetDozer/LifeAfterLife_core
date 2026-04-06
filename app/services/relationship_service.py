from app.db.crud import crud


class RelationshipService:

    async def create_relationship(self, from_id, to_id, rel_type):
        # 1. Нельзя самому себе
        if from_id == to_id:
            raise ValueError("Cannot relate person to themselves")

        # 2. Получаем людей
        person1 = await crud.get_person(from_id)
        person2 = await crud.get_person(to_id)

        if not person1 or not person2:
            raise ValueError("Person not found")

        # 3. Проверка одного дерева
        if person1["tree_id"] != person2["tree_id"]:
            raise ValueError("Persons must belong to same tree")

        tree_id = person1["tree_id"]

        # 4. Создаём связь
        await crud.create_relationship(tree_id, from_id, to_id, rel_type)

        # 5. Если двусторонняя — создаём обратную
        if rel_type in ["spouse", "sibling", "friend"]:
            await crud.create_relationship(tree_id, to_id, from_id, rel_type)


service = RelationshipService()