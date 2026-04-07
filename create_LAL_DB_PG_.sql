-- CREATE DATABASE LAL OWNER PyCore;

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

CREATE TYPE access_level_type AS ENUM ('view', 'edit');

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

-- =====================================================
-- family_trees
-- =====================================================

CREATE TABLE family_trees (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
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

    CHECK (
        date_of_birth IS NULL
        OR date_of_death IS NULL
        OR date_of_death >= date_of_birth
    ),

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

    CHECK (from_person_id <> to_person_id),

    UNIQUE (from_person_id, to_person_id, relationship_type),

    FOREIGN KEY (tree_id) REFERENCES family_trees(id) ON DELETE CASCADE,
    FOREIGN KEY (tree_id, from_person_id) REFERENCES persons(tree_id, id) ON DELETE CASCADE,
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

    UNIQUE (tree_id, user_id),

    FOREIGN KEY (tree_id) REFERENCES family_trees(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_tree_access_tree_id ON tree_access (tree_id);
CREATE INDEX idx_tree_access_user_id ON tree_access (user_id);
