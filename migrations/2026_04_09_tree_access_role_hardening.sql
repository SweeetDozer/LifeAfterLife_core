BEGIN;

-- 1. Normalize legacy delegated access values before tightening the enum.
UPDATE tree_access
SET access_level = 'viewer'
WHERE access_level::text = 'view';

UPDATE tree_access
SET access_level = 'editor'
WHERE access_level::text = 'edit';

-- 2. Remove invalid owner duplicates from delegated access storage.
DELETE FROM tree_access
USING family_trees
WHERE family_trees.id = tree_access.tree_id
  AND family_trees.user_id = tree_access.user_id;

-- 3. Recreate enum so tree_access stores only delegated roles.
ALTER TYPE access_level_type RENAME TO access_level_type_old;
CREATE TYPE access_level_type AS ENUM ('viewer', 'editor');

ALTER TABLE tree_access
    ALTER COLUMN access_level TYPE access_level_type
    USING access_level::text::access_level_type;

DROP TYPE access_level_type_old;

-- 4. Enforce that every tree has an explicit owner.
ALTER TABLE family_trees
    ALTER COLUMN user_id SET NOT NULL;

ALTER TABLE family_trees
    DROP CONSTRAINT IF EXISTS family_trees_user_id_fkey;

ALTER TABLE family_trees
    ADD CONSTRAINT family_trees_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT;

-- 5. Prevent storing owner rows inside tree_access.
CREATE OR REPLACE FUNCTION prevent_tree_owner_in_tree_access()
RETURNS TRIGGER AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM family_trees
        WHERE id = NEW.tree_id
          AND user_id = NEW.user_id
    ) THEN
        RAISE EXCEPTION 'Owner must not be stored in tree_access';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevent_tree_owner_in_tree_access ON tree_access;

CREATE TRIGGER trg_prevent_tree_owner_in_tree_access
BEFORE INSERT OR UPDATE ON tree_access
FOR EACH ROW
EXECUTE FUNCTION prevent_tree_owner_in_tree_access();

COMMIT;
