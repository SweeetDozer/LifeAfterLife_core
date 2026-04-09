BEGIN;

-- Make critical delete semantics explicit and stable for existing databases.
-- Domain contract:
--   users -> family_trees      : RESTRICT
--   family_trees -> persons    : CASCADE
--   family_trees -> relationships : CASCADE
--   family_trees -> tree_access: CASCADE
--   persons -> relationships   : CASCADE
--   users -> tree_access       : CASCADE

ALTER TABLE family_trees
    DROP CONSTRAINT IF EXISTS family_trees_user_id_fkey,
    DROP CONSTRAINT IF EXISTS fk_family_trees_owner_user;

ALTER TABLE family_trees
    ADD CONSTRAINT fk_family_trees_owner_user
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT;

ALTER TABLE persons
    DROP CONSTRAINT IF EXISTS persons_tree_id_fkey,
    DROP CONSTRAINT IF EXISTS fk_persons_tree;

ALTER TABLE persons
    ADD CONSTRAINT fk_persons_tree
    FOREIGN KEY (tree_id) REFERENCES family_trees(id) ON DELETE CASCADE;

ALTER TABLE relationships
    DROP CONSTRAINT IF EXISTS relationships_tree_id_fkey,
    DROP CONSTRAINT IF EXISTS relationships_tree_id_from_person_id_fkey,
    DROP CONSTRAINT IF EXISTS relationships_tree_id_to_person_id_fkey,
    DROP CONSTRAINT IF EXISTS fk_relationships_tree,
    DROP CONSTRAINT IF EXISTS fk_relationships_from_person,
    DROP CONSTRAINT IF EXISTS fk_relationships_to_person;

ALTER TABLE relationships
    ADD CONSTRAINT fk_relationships_tree
    FOREIGN KEY (tree_id) REFERENCES family_trees(id) ON DELETE CASCADE,
    ADD CONSTRAINT fk_relationships_from_person
    FOREIGN KEY (tree_id, from_person_id) REFERENCES persons(tree_id, id) ON DELETE CASCADE,
    ADD CONSTRAINT fk_relationships_to_person
    FOREIGN KEY (tree_id, to_person_id) REFERENCES persons(tree_id, id) ON DELETE CASCADE;

ALTER TABLE tree_access
    DROP CONSTRAINT IF EXISTS tree_access_tree_id_fkey,
    DROP CONSTRAINT IF EXISTS tree_access_user_id_fkey,
    DROP CONSTRAINT IF EXISTS fk_tree_access_tree,
    DROP CONSTRAINT IF EXISTS fk_tree_access_user;

ALTER TABLE tree_access
    ADD CONSTRAINT fk_tree_access_tree
    FOREIGN KEY (tree_id) REFERENCES family_trees(id) ON DELETE CASCADE,
    ADD CONSTRAINT fk_tree_access_user
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

COMMIT;
