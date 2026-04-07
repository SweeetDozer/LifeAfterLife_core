from app.db.crud import crud


class KinshipService:

    async def path_to_relations(self, path):
        relations = []

        for current_id, next_id in zip(path, path[1:]):
            rel = await crud.get_relationship(current_id, next_id)

            if rel:
                relation_type = rel["relationship_type"]
                step_type = "child" if relation_type == "parent" else relation_type
            else:
                rel = await crud.get_relationship(next_id, current_id)
                if rel:
                    relation_type = rel["relationship_type"]
                    step_type = "parent" if relation_type == "parent" else relation_type
                else:
                    step_type = "unknown"

            relations.append({"type": step_type, "to": next_id})

        return relations

    def get_degree(self, up, down):
        common_level = min(up, down)
        generation_diff = abs(up - down)
        return common_level, generation_diff

    def cousin_level(self, level):
        names = {
            1: "двоюродный",
            2: "троюродный",
            3: "четвероюродный",
        }
        return names.get(level, f"{level}-юродный")

    def gender_word(self, base, gender):
        if gender == "male":
            return base[0]
        if gender == "female":
            return base[1]
        return f"{base[0]}/{base[1]}"

    def ancestor_word(self, depth, gender):
        if depth == 1:
            return self.gender_word(("отец", "мать"), gender)
        if depth == 2:
            return self.gender_word(("дед", "бабушка"), gender)
        if depth == 3:
            return self.gender_word(("прадед", "прабабушка"), gender)
        return f"предок в {depth}-м поколении"

    def descendant_word(self, depth, gender):
        if depth == 1:
            return self.gender_word(("сын", "дочь"), gender)
        if depth == 2:
            return self.gender_word(("внук", "внучка"), gender)
        if depth == 3:
            return self.gender_word(("правнук", "правнучка"), gender)
        return f"потомок в {depth}-м поколении"

    async def detect_line(self, relations):
        for rel in relations:
            if rel["type"] == "parent":
                person = await crud.get_person(rel["to"])
                if person and person["gender"] == "male":
                    return "по отцовской линии"
                if person and person["gender"] == "female":
                    return "по материнской линии"
        return ""

    async def interpret(self, relations, target_id):
        if not relations:
            return "тот же человек"

        if any(rel["type"] == "unknown" for rel in relations):
            return "сложное родство"

        person = await crud.get_person(target_id)
        gender = person["gender"] if person else None

        if len(relations) == 1:
            relation_type = relations[0]["type"]

            if relation_type == "parent":
                return self.gender_word(("отец", "мать"), gender)
            if relation_type == "child":
                return self.gender_word(("сын", "дочь"), gender)
            if relation_type == "sibling":
                return self.gender_word(("брат", "сестра"), gender)
            if relation_type == "spouse":
                return self.gender_word(("муж", "жена"), gender)
            if relation_type == "friend":
                return self.gender_word(("друг", "подруга"), gender)

        up = sum(1 for rel in relations if rel["type"] == "parent")
        down = sum(1 for rel in relations if rel["type"] == "child")
        lateral = [rel["type"] for rel in relations if rel["type"] not in {"parent", "child"}]

        if lateral:
            return "сложное родство"

        if up > 0 and down == 0:
            return self.ancestor_word(up, gender)

        if down > 0 and up == 0:
            return self.descendant_word(down, gender)

        if up == 1 and down == 1:
            return self.gender_word(("брат", "сестра"), gender)

        if up == 2 and down == 1:
            return self.gender_word(("дядя", "тётя"), gender)

        if up == 1 and down == 2:
            return self.gender_word(("племянник", "племянница"), gender)

        common, diff = self.get_degree(up, down)

        if common >= 2 and diff == 0:
            cousin = self.cousin_level(common - 1)
            sibling = self.gender_word(("брат", "сестра"), gender)
            return f"{cousin} {sibling}"

        if common >= 2 and diff > 0:
            cousin = self.cousin_level(common - 1)
            sibling = self.gender_word(("брат", "сестра"), gender)
            return f"{cousin} {sibling}, смещен(а) на {diff} поколение"

        return "сложное родство"


kinship_service = KinshipService()
