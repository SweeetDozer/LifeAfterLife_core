-- CREATE DATABASE LAL OWNER PyCore;
-- Canonical schema for a new database created from scratch.
-- Legacy migrations in migrations/*.sql are for existing databases only.

-- =====================================================
-- ENUM типы
-- =====================================================

CREATE TYPE gender_type AS ENUM ('male', 'female', 'other');

CREATE TYPE relationship_type AS ENUM (
    'parent',
    'spouse',
    'sibling',
    'friend'
);

CREATE TYPE access_level_type AS ENUM ('viewer', 'editor');

-- =====================================================
-- users
-- =====================================================

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX uq_users_email_lower ON users (LOWER(email));

CREATE TABLE user_refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    family_id VARCHAR(128) NOT NULL,
    token_id VARCHAR(128) NOT NULL,
    token_hash CHAR(64) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    revoked_at TIMESTAMP,
    replaced_by_token_id VARCHAR(128),

    CONSTRAINT uq_user_refresh_tokens_token_id UNIQUE (token_id),
    CONSTRAINT fk_user_refresh_tokens_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_user_refresh_tokens_user_id ON user_refresh_tokens (user_id);
CREATE INDEX idx_user_refresh_tokens_family_id ON user_refresh_tokens (family_id);
CREATE INDEX idx_user_refresh_tokens_expires_at ON user_refresh_tokens (expires_at);

CREATE TABLE auth_throttle_entries (
    id SERIAL PRIMARY KEY,
    throttle_key_type VARCHAR(64) NOT NULL,
    throttle_key_value VARCHAR(320) NOT NULL,
    attempt_count INTEGER NOT NULL,
    window_started_at TIMESTAMP NOT NULL,
    last_attempt_at TIMESTAMP NOT NULL,
    locked_until TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_auth_throttle_entries_key UNIQUE (throttle_key_type, throttle_key_value),
    CONSTRAINT ck_auth_throttle_entries_attempt_count CHECK (attempt_count > 0)
);

CREATE INDEX idx_auth_throttle_entries_locked_until ON auth_throttle_entries (locked_until);

-- =====================================================
-- family_trees
-- =====================================================

CREATE TABLE family_trees (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_family_trees_owner_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX idx_family_trees_user_id ON family_trees (user_id);

-- =====================================================
-- persons
-- =====================================================

CREATE TABLE persons (
    id SERIAL PRIMARY KEY,
    tree_id INTEGER NOT NULL,

    first_name VARCHAR(100) NOT NULL,
    midle_name VARCHAR(100),
    last_name VARCHAR(100),

    date_of_birth DATE,
    date_of_death DATE,

    gender gender_type,
    photo_url VARCHAR(500),
    info_about_person TEXT,

    CONSTRAINT ck_persons_date_order CHECK (
        date_of_birth IS NULL
        OR date_of_death IS NULL
        OR date_of_death >= date_of_birth
    ),

    CONSTRAINT fk_persons_tree
        FOREIGN KEY (tree_id) REFERENCES family_trees(id) ON DELETE CASCADE
);

CREATE INDEX idx_persons_tree_id ON persons (tree_id);
CREATE UNIQUE INDEX uq_persons_tree_id_id ON persons (tree_id, id);

-- =====================================================
-- relationships (ключевая таблица)
-- =====================================================

CREATE TABLE relationships (
    id SERIAL PRIMARY KEY,
    tree_id INTEGER NOT NULL,

    from_person_id INTEGER NOT NULL,
    to_person_id INTEGER NOT NULL,

    relationship_type relationship_type NOT NULL,

    CONSTRAINT ck_relationships_distinct_persons
        CHECK (from_person_id <> to_person_id),

    CONSTRAINT uq_relationships_directed_type
        UNIQUE (from_person_id, to_person_id, relationship_type),

    CONSTRAINT fk_relationships_tree
        FOREIGN KEY (tree_id) REFERENCES family_trees(id) ON DELETE CASCADE,
    CONSTRAINT fk_relationships_from_person
        FOREIGN KEY (tree_id, from_person_id) REFERENCES persons(tree_id, id) ON DELETE CASCADE,
    CONSTRAINT fk_relationships_to_person
        FOREIGN KEY (tree_id, to_person_id) REFERENCES persons(tree_id, id) ON DELETE CASCADE
);

CREATE INDEX idx_relationships_tree_id ON relationships (tree_id);
CREATE INDEX idx_relationships_from_person ON relationships (from_person_id);
CREATE INDEX idx_relationships_to_person ON relationships (to_person_id);

-- =====================================================
-- tree_access
-- =====================================================

CREATE TABLE tree_access (
    id SERIAL PRIMARY KEY,
    tree_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    access_level access_level_type NOT NULL,

    CONSTRAINT uq_tree_access_tree_user UNIQUE (tree_id, user_id),

    CONSTRAINT fk_tree_access_tree
        FOREIGN KEY (tree_id) REFERENCES family_trees(id) ON DELETE CASCADE,
    CONSTRAINT fk_tree_access_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_tree_access_tree_id ON tree_access (tree_id);
CREATE INDEX idx_tree_access_user_id ON tree_access (user_id);

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

CREATE TRIGGER trg_prevent_tree_owner_in_tree_access
BEFORE INSERT OR UPDATE ON tree_access
FOR EACH ROW
EXECUTE FUNCTION prevent_tree_owner_in_tree_access();
