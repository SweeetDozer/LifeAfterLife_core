BEGIN;

-- Make critical delete semantics explicit and stable for existing databases.
-- Domain contract:
--   users -> family_trees      : RESTRICT
--   family_trees -> persons    : CASCADE
--   family_trees -> relationships : CASCADE
--   family_trees -> tree_access: CASCADE
--   persons -> relationships   : CASCADE
--   users -> tree_access       : CASCADE

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_lower
    ON users (LOWER(email));

ALTER TABLE family_trees
    ALTER COLUMN user_id SET NOT NULL,
    DROP CONSTRAINT IF EXISTS family_trees_user_id_fkey,
    DROP CONSTRAINT IF EXISTS fk_family_trees_owner_user;

ALTER TABLE family_trees
    ADD CONSTRAINT fk_family_trees_owner_user
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT;

ALTER TABLE persons
    DROP CONSTRAINT IF EXISTS ck_persons_date_order,
    DROP CONSTRAINT IF EXISTS persons_tree_id_fkey,
    DROP CONSTRAINT IF EXISTS fk_persons_tree;

ALTER TABLE persons
    ADD CONSTRAINT ck_persons_date_order
    CHECK (
        date_of_birth IS NULL
        OR date_of_death IS NULL
        OR date_of_death >= date_of_birth
    ),
    ADD CONSTRAINT fk_persons_tree
    FOREIGN KEY (tree_id) REFERENCES family_trees(id) ON DELETE CASCADE;

CREATE UNIQUE INDEX IF NOT EXISTS uq_persons_tree_id_id
    ON persons (tree_id, id);

ALTER TABLE relationships
    DROP CONSTRAINT IF EXISTS relationships_check,
    DROP CONSTRAINT IF EXISTS ck_relationships_distinct_persons,
    DROP CONSTRAINT IF EXISTS relationships_from_person_id_to_person_id_relationship_type_key,
    DROP CONSTRAINT IF EXISTS uq_relationships_directed_type,
    DROP CONSTRAINT IF EXISTS relationships_tree_id_fkey,
    DROP CONSTRAINT IF EXISTS relationships_from_person_id_fkey,
    DROP CONSTRAINT IF EXISTS relationships_to_person_id_fkey,
    DROP CONSTRAINT IF EXISTS relationships_tree_id_from_person_id_fkey,
    DROP CONSTRAINT IF EXISTS relationships_tree_id_to_person_id_fkey,
    DROP CONSTRAINT IF EXISTS fk_relationships_tree,
    DROP CONSTRAINT IF EXISTS fk_relationships_from_person,
    DROP CONSTRAINT IF EXISTS fk_relationships_to_person;

ALTER TABLE relationships
    ADD CONSTRAINT ck_relationships_distinct_persons
    CHECK (from_person_id <> to_person_id),
    ADD CONSTRAINT uq_relationships_directed_type
    UNIQUE (from_person_id, to_person_id, relationship_type),
    ADD CONSTRAINT fk_relationships_tree
    FOREIGN KEY (tree_id) REFERENCES family_trees(id) ON DELETE CASCADE,
    ADD CONSTRAINT fk_relationships_from_person
    FOREIGN KEY (tree_id, from_person_id) REFERENCES persons(tree_id, id) ON DELETE CASCADE,
    ADD CONSTRAINT fk_relationships_to_person
    FOREIGN KEY (tree_id, to_person_id) REFERENCES persons(tree_id, id) ON DELETE CASCADE;

ALTER TABLE tree_access
    DROP CONSTRAINT IF EXISTS tree_access_tree_id_user_id_key,
    DROP CONSTRAINT IF EXISTS uq_tree_access_tree_user,
    DROP CONSTRAINT IF EXISTS tree_access_tree_id_fkey,
    DROP CONSTRAINT IF EXISTS tree_access_user_id_fkey,
    DROP CONSTRAINT IF EXISTS fk_tree_access_tree,
    DROP CONSTRAINT IF EXISTS fk_tree_access_user;

ALTER TABLE tree_access
    ADD CONSTRAINT uq_tree_access_tree_user UNIQUE (tree_id, user_id),
    ADD CONSTRAINT fk_tree_access_tree
    FOREIGN KEY (tree_id) REFERENCES family_trees(id) ON DELETE CASCADE,
    ADD CONSTRAINT fk_tree_access_user
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

COMMIT;
