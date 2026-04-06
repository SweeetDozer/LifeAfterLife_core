from tkinter.font import names

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

    def get_degree(self, up, down):
        # общий предок на уровне min(up, down)
        common_level = min(up, down)

        # разница поколений
        generation_diff = abs(up - down)

        return common_level, generation_diff

    def cousin_level(self, level):
        names = {
        1: "двоюродный",
        2: "троюродный",
        3: "четвероюродный"
        }
        return names.get(level, f"{level}-юродный")

    def gender_word(self, base, gender):
        if gender == "male":
            return base[0]
        elif gender == "female":
            return base[1]
        return f"{base[0]}/{base[1]}"

    async def interpret(self, relations, target_id):
        up = relations.count("parent")
        down = relations.count("child")
        person = await crud.get_person(target_id)
        gender = person["gender"]   

        if up > 0 and down == 0:
            if up == 1:
                return self.gender_word(("отец", "мать"), gender)
            if up == 2:
                return "дед/бабушка"
            if up == 3:
                return "прадед/прабабушка"

        if down > 0 and up == 0:
            if down == 1:
                return "ребёнок"
            if down == 2:
                return "внук/внучка"
            if down == 3:
                return "правнук/правнучка"

        if up == 1 and down == 1:
            return "брат/сестра"

        if up == 2 and down == 1:
            return "дядя/тётя"

        if up == 1 and down == 2:
            return "племянник/племянница"

        if up == 1 and down == 1 and len(relations) == 3:
            return "двоюродный брат/сестра"
        
        common, diff = self.get_degree(up, down)

        # кузены
        if common >= 1 and diff == 0 and up > 1:
            return f"{self.cousin_level(common - 1)} брат/сестра"
        
        if common >= 1 and diff > 0:
            cousin = self.cousin_level(common - 1)
            return f"{cousin} брат/сестра, смещён на {diff} поколение"

        return "сложное родство"


kinship_service = KinshipService()