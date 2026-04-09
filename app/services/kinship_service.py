from app.db.crud import crud
from app.services.relationship_semantics import (
    blood_relationship_types,
    supported_relationship_types,
)


class KinshipService:
    BLOOD_STEP_TYPES = blood_relationship_types() | frozenset({"child"})
    DIRECT_STEP_TYPES = supported_relationship_types() | frozenset({"child"})
    DIRECT_RELATION_WORDS = {
        "parent": ("отец", "мать"),
        "child": ("сын", "дочь"),
        "sibling": ("брат", "сестра"),
        "spouse": ("муж", "жена"),
        "friend": ("друг", "подруга"),
    }
    ANCESTOR_WORDS = {
        1: ("отец", "мать"),
        2: ("дед", "бабушка"),
        3: ("прадед", "прабабушка"),
    }
    DESCENDANT_WORDS = {
        1: ("сын", "дочь"),
        2: ("внук", "внучка"),
        3: ("правнук", "правнучка"),
    }
    COUSIN_WORDS = {
        1: ("двоюродный", "двоюродная"),
        2: ("троюродный", "троюродная"),
        3: ("четвероюродный", "четвероюродная"),
    }

    @staticmethod
    def _normalize_person_id(value):
        if isinstance(value, bool):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalize_step_type(value):
        if not isinstance(value, str):
            return "unknown"

        relation_type = value.strip().lower()
        return relation_type if relation_type else "unknown"

    @staticmethod
    def _normalize_relationship_types(relationship_types):
        normalized = set()

        for relationship_type in relationship_types or []:
            if not isinstance(relationship_type, str):
                continue

            value = relationship_type.strip().lower()
            if value:
                normalized.add(value)

        return sorted(normalized)

    @staticmethod
    def _resolve_step_type(direct_relationship_types, reverse_relationship_types):
        direct_type = (
            direct_relationship_types[0]
            if len(direct_relationship_types) == 1
            else None
        )
        reverse_type = (
            reverse_relationship_types[0]
            if len(reverse_relationship_types) == 1
            else None
        )

        if direct_type and reverse_type:
            if direct_type == reverse_type and direct_type in {
                "spouse",
                "sibling",
                "friend",
            }:
                return direct_type
            return "unknown"

        if direct_type:
            return "child" if direct_type == "parent" else direct_type

        if reverse_type:
            return "parent" if reverse_type == "parent" else reverse_type

        return "unknown"

    @classmethod
    def _normalize_path_step(cls, step):
        if not isinstance(step, dict):
            return None

        return {
            "from_person_id": cls._normalize_person_id(step.get("from_person_id")),
            "to_person_id": cls._normalize_person_id(step.get("to_person_id")),
            "direct_relationship_types": cls._normalize_relationship_types(
                step.get("direct_relationship_types")
            ),
            "reverse_relationship_types": cls._normalize_relationship_types(
                step.get("reverse_relationship_types")
            ),
        }

    @classmethod
    def _extract_path_steps(cls, path):
        raw_steps = None

        if isinstance(path, dict):
            raw_steps = path.get("steps")
        elif isinstance(path, list) and all(isinstance(step, dict) for step in path):
            raw_steps = path

        if raw_steps is None:
            return None

        normalized_steps = []
        for step in raw_steps:
            normalized_step = cls._normalize_path_step(step)
            if normalized_step is None:
                return None
            normalized_steps.append(normalized_step)

        return normalized_steps

    @classmethod
    def _relation_from_path_step(cls, step):
        return {
            "type": cls._resolve_step_type(
                step["direct_relationship_types"],
                step["reverse_relationship_types"],
            ),
            "to": step["to_person_id"],
        }

    @classmethod
    def _normalize_relation(cls, relation):
        if not isinstance(relation, dict):
            return {"type": "unknown", "to": None}

        to_person_id = cls._normalize_person_id(relation.get("to"))
        if to_person_id is None:
            to_person_id = cls._normalize_person_id(relation.get("to_person_id"))

        return {
            "type": cls._normalize_step_type(relation.get("type")),
            "to": to_person_id,
        }

    @staticmethod
    def _vertical_lineage_counts(sequence):
        split_index = 0

        while split_index < len(sequence) and sequence[split_index] == "parent":
            split_index += 1

        tail_index = split_index
        while tail_index < len(sequence) and sequence[tail_index] == "child":
            tail_index += 1

        if tail_index != len(sequence):
            return None

        return split_index, len(sequence) - split_index

    @staticmethod
    def _sibling_lineage_counts(sequence):
        if sequence.count("sibling") != 1:
            return None

        sibling_index = sequence.index("sibling")
        if any(step != "parent" for step in sequence[:sibling_index]):
            return None
        if any(step != "child" for step in sequence[sibling_index + 1 :]):
            return None

        return sibling_index + 1, len(sequence) - sibling_index

    @classmethod
    def _analyze_relations(cls, relations):
        normalized_relations = [
            cls._normalize_relation(relation) for relation in relations or []
        ]
        sequence = [relation["type"] for relation in normalized_relations]

        if not normalized_relations:
            return {
                "kind": "self",
                "relations": [],
                "sequence": [],
                "lineage": None,
                "direct_type": None,
            }

        if any(step_type == "unknown" for step_type in sequence):
            return {
                "kind": "complex",
                "relations": normalized_relations,
                "sequence": sequence,
                "lineage": None,
                "direct_type": None,
            }

        direct_type = sequence[0] if len(sequence) == 1 else None
        if direct_type in cls.DIRECT_STEP_TYPES:
            lineage = None
            if direct_type == "parent":
                lineage = (1, 0)
            elif direct_type == "child":
                lineage = (0, 1)
            elif direct_type == "sibling":
                lineage = (1, 1)

            return {
                "kind": "direct",
                "relations": normalized_relations,
                "sequence": sequence,
                "lineage": lineage,
                "direct_type": direct_type,
            }

        if any(step_type not in cls.BLOOD_STEP_TYPES for step_type in sequence):
            return {
                "kind": "complex",
                "relations": normalized_relations,
                "sequence": sequence,
                "lineage": None,
                "direct_type": None,
            }

        # Simplified model: we only interpret paths that look like
        # "go up through parents, optionally cross one sibling link,
        # then go down through children". Multiple lateral hops or
        # mixed non-blood edges are still treated as complex.
        lineage = cls._vertical_lineage_counts(sequence)
        if lineage is None:
            lineage = cls._sibling_lineage_counts(sequence)

        if lineage is None:
            return {
                "kind": "complex",
                "relations": normalized_relations,
                "sequence": sequence,
                "lineage": None,
                "direct_type": None,
            }

        return {
            "kind": "blood",
            "relations": normalized_relations,
            "sequence": sequence,
            "lineage": lineage,
            "direct_type": None,
        }

    async def _load_path_steps(self, tree_id, path, connection=None):
        path_steps = self._extract_path_steps(path)
        if path_steps is not None:
            return path_steps

        if not isinstance(path, list) or len(path) < 2:
            return []

        normalized_path = [self._normalize_person_id(person_id) for person_id in path]
        if any(person_id is None for person_id in normalized_path):
            return []

        steps = []

        for current_id, next_id in zip(normalized_path, normalized_path[1:]):
            direct_relationships = self._normalize_relationship_types(
                relation["relationship_type"]
                for relation in await crud.get_ordered_relationship_types(
                    current_id,
                    next_id,
                    tree_id=tree_id,
                    connection=connection,
                )
            )
            reverse_relationships = self._normalize_relationship_types(
                relation["relationship_type"]
                for relation in await crud.get_ordered_relationship_types(
                    next_id,
                    current_id,
                    tree_id=tree_id,
                    connection=connection,
                )
            )

            steps.append(
                {
                    "from_person_id": current_id,
                    "to_person_id": next_id,
                    "direct_relationship_types": direct_relationships,
                    "reverse_relationship_types": reverse_relationships,
                }
            )

        return steps

    async def path_to_relations(self, tree_id, path, connection=None):
        path_steps = await self._load_path_steps(
            tree_id,
            path,
            connection=connection,
        )
        return [self._relation_from_path_step(step) for step in path_steps]

    def get_degree(self, up, down):
        common_level = min(up, down)
        generation_diff = abs(up - down)
        return common_level, generation_diff

    def cousin_level(self, level, gender=None):
        base = self.COUSIN_WORDS.get(level)
        if base is None:
            return None
        return self.gender_word(base, gender)

    def gender_word(self, base, gender):
        if gender == "male":
            return base[0]
        if gender == "female":
            return base[1]
        return f"{base[0]}/{base[1]}"

    def direct_relation_word(self, relation_type, gender):
        base = self.DIRECT_RELATION_WORDS.get(relation_type)
        if base is None:
            return None
        return self.gender_word(base, gender)

    @staticmethod
    def removed_word(diff):
        if diff <= 0:
            return ""
        return f"в {diff}-м удалении"

    @staticmethod
    def generation_word(depth, subject):
        return f"{subject} в {depth}-м поколении"

    def ancestor_word(self, depth, gender):
        base = self.ANCESTOR_WORDS.get(depth)
        if base is not None:
            return self.gender_word(base, gender)
        return self.generation_word(depth, "предок")

    def descendant_word(self, depth, gender):
        base = self.DESCENDANT_WORDS.get(depth)
        if base is not None:
            return self.gender_word(base, gender)
        return self.generation_word(depth, "потомок")

    def cousin_relation_word(self, level, diff, gender):
        cousin = self.cousin_level(level, gender)
        if cousin is None:
            relation = self.gender_word(
                (
                    "родственник по боковой линии",
                    "родственница по боковой линии",
                ),
                gender,
            )
        else:
            sibling = self.direct_relation_word("sibling", gender)
            relation = f"{cousin} {sibling}"
        removed = self.removed_word(diff)
        if removed:
            return f"{relation} {removed}"
        return relation

    def collateral_ancestor_word(self, up, gender):
        if up == 2:
            return self.gender_word(("дядя", "тётя"), gender)

        branch = self.gender_word(("дяди", "тёти"), gender)
        return self.generation_word(up - 2, f"предок {branch}")

    def collateral_descendant_word(self, down, gender):
        if down == 2:
            return self.gender_word(("племянник", "племянница"), gender)

        branch = self.gender_word(("племянника", "племянницы"), gender)
        return self.generation_word(down - 2, f"потомок {branch}")

    def _describe_blood_relation(self, up, down, gender):
        if up > 0 and down == 0:
            return self.ancestor_word(up, gender)

        if down > 0 and up == 0:
            return self.descendant_word(down, gender)

        if up == 1 and down == 1:
            return self.gender_word(
                (
                    "брат",
                    "сестра",
                ),
                gender,
            )

        if up == 2 and down == 1:
            return self.collateral_ancestor_word(up, gender)

        if up == 1 and down == 2:
            return self.collateral_descendant_word(down, gender)

        common, diff = self.get_degree(up, down)

        if common == 1:
            if up > down:
                return self.collateral_ancestor_word(up, gender)
            if down > up:
                return self.collateral_descendant_word(down, gender)

        if common >= 2:
            return self.cousin_relation_word(common - 1, diff, gender)

        return "сложное родство"

    async def detect_line(self, tree_id, relations, connection=None):
        analysis = self._analyze_relations(relations)
        lineage = analysis["lineage"]

        if analysis["kind"] in {"self", "complex"} or lineage is None:
            return ""

        up, down = lineage
        if up == 0 or (up == 1 and down == 1):
            return ""

        first_relation = analysis["relations"][0]
        if first_relation["type"] != "parent" or first_relation["to"] is None:
            return ""

        person = await crud.get_tree_person(
            tree_id,
            first_relation["to"],
            connection=connection,
        )
        if not person:
            return ""
        if person["gender"] == "male":
            return "по отцовской линии"
        if person["gender"] == "female":
            return "по материнской линии"
        return ""

    async def interpret(self, tree_id, relations, target_id, connection=None):
        analysis = self._analyze_relations(relations)
        if analysis["kind"] == "self":
            return "тот же человек"

        if analysis["kind"] == "complex":
            return "сложное родство"

        person = await crud.get_tree_person(
            tree_id,
            target_id,
            connection=connection,
        )
        gender = person["gender"] if person else None

        direct_type = analysis["direct_type"]
        if direct_type is not None:
            direct_relation = self.direct_relation_word(direct_type, gender)
            if direct_relation is not None:
                return direct_relation

        up, down = analysis["lineage"]
        return self._describe_blood_relation(up, down, gender)


kinship_service = KinshipService()
