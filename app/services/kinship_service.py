from app.db.crud import crud


class KinshipService:

    async def path_to_relations(self, path):
        relations = []

        for i in range(len(path) - 1):
            rel = await crud.get_relationship(path[i], path[i+1])

            if rel:
                relations.append(rel["relationship_type"])
            else:
                # обратное направление (для parent)
                rel = await crud.get_relationship(path[i+1], path[i])
                if rel and rel["relationship_type"] == "parent":
                    relations.append("child")
                else:
                    relations.append("unknown")

        return relations


    def interpret(self, relations):
        # MVP логика

        if relations == ["parent"]:
            return "родитель"

        if relations == ["child"]:
            return "ребёнок"

        if relations == ["parent", "parent"]:
            return "дед/бабушка"

        if relations == ["child", "child"]:
            return "внук/внучка"

        if relations == ["parent", "child"]:
            return "брат/сестра"

        if relations == ["parent", "parent", "child"]:
            return "дядя/тётя"

        if relations == ["child", "parent", "child"]:
            return "двоюродный брат/сестра"
        
        if relations == ["child", "spouse"]:
            return "отчим/мачеха"
        
        if relations == ["spouse"]:
            return "супруг/супруга"

        if relations == ["child", "parent"]:
            return "брат/сестра"

        if relations == ["parent", "spouse"]:
            return "родитель через брак"

        # fallback
        return "сложное родство"


kinship_service = KinshipService()