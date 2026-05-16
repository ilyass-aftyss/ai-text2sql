-- ============================================================
--  Base de données de démonstration PostgreSQL
--  Text-to-SQL Intelligent
-- ============================================================

-- Clients
CREATE TABLE IF NOT EXISTS clients (
    id          SERIAL PRIMARY KEY,
    nom         VARCHAR(100) NOT NULL,
    email       VARCHAR(150) UNIQUE NOT NULL,
    ville       VARCHAR(100),
    pays        VARCHAR(50) DEFAULT 'France',
    date_inscription DATE DEFAULT CURRENT_DATE,
    is_active   BOOLEAN DEFAULT true
);

-- Catégories produits
CREATE TABLE IF NOT EXISTS categories (
    id   SERIAL PRIMARY KEY,
    nom  VARCHAR(100) NOT NULL UNIQUE
);

-- Produits
CREATE TABLE IF NOT EXISTS produits (
    id              SERIAL PRIMARY KEY,
    nom             VARCHAR(200) NOT NULL,
    prix_unitaire   DECIMAL(10,2) NOT NULL,
    categorie_id    INTEGER REFERENCES categories(id),
    stock_actuel    INTEGER DEFAULT 0,
    description     TEXT
);

-- Commandes
CREATE TABLE IF NOT EXISTS commandes (
    id              SERIAL PRIMARY KEY,
    client_id       INTEGER REFERENCES clients(id),
    date_commande   DATE DEFAULT CURRENT_DATE,
    montant_total   DECIMAL(10,2),
    statut          VARCHAR(50) DEFAULT 'en_attente'
);

-- Lignes de commande
CREATE TABLE IF NOT EXISTS lignes_commande (
    id          SERIAL PRIMARY KEY,
    commande_id INTEGER REFERENCES commandes(id),
    produit_id  INTEGER REFERENCES produits(id),
    quantite    INTEGER DEFAULT 1,
    prix_unitaire DECIMAL(10,2)
);

-- ── Données de démonstration ─────────────────────────────────────────────────

INSERT INTO categories (nom) VALUES
    ('Informatique'), ('Audio'), ('Bureau'), ('Accessoires')
ON CONFLICT DO NOTHING;

INSERT INTO clients (nom, email, ville, pays) VALUES
    ('Alice Martin',     'alice@example.com',    'Paris',     'France'),
    ('Bob Durand',       'bob@example.com',      'Lyon',      'France'),
    ('Claire Petit',     'claire@example.com',   'Marseille', 'France'),
    ('David Roux',       'david@example.com',    'Bordeaux',  'France'),
    ('Emma Leroy',       'emma@example.com',     'Toulouse',  'France'),
    ('François Bernard', 'francois@example.com', 'Nantes',    'France'),
    ('Henri Moreau',     'henri@example.com',    'Genève',    'Suisse'),
    ('Isabelle Simon',   'isabelle@example.com', 'Bruxelles', 'Belgique')
ON CONFLICT DO NOTHING;

INSERT INTO produits (nom, prix_unitaire, categorie_id, stock_actuel) VALUES
    ('Laptop Pro',          1299.99, 1, 15),
    ('Souris Ergonomique',    49.99, 1, 80),
    ('Clavier Mécanique',   129.99, 1, 45),
    ('Casque Audio',         199.99, 2, 60),
    ('Lampe LED Bureau',      59.99, 3, 75),
    ('Hub USB-C',             39.99, 4, 100),
    ('Tapis de souris XXL',   24.99, 4, 200),
    ('Webcam HD',             89.99, 1, 35)
ON CONFLICT DO NOTHING;

INSERT INTO commandes (client_id, date_commande, statut, montant_total) VALUES
    (1, CURRENT_DATE - 10, 'livree',      1299.99),
    (2, CURRENT_DATE - 5,  'en_attente',   249.98),
    (3, CURRENT_DATE - 15, 'livree',       199.99),
    (1, CURRENT_DATE - 2,  'en_attente',    89.99),
    (4, CURRENT_DATE - 20, 'livree',       129.99),
    (5, CURRENT_DATE - 8,  'livree',        49.99),
    (6, CURRENT_DATE - 1,  'en_attente',   199.99)
ON CONFLICT DO NOTHING;

INSERT INTO lignes_commande (commande_id, produit_id, quantite, prix_unitaire) VALUES
    (1, 1, 1, 1299.99),
    (2, 2, 3,   49.99),
    (2, 6, 1,   39.99),
    (3, 4, 1,  199.99),
    (4, 8, 1,   89.99),
    (5, 3, 1,  129.99),
    (6, 2, 1,   49.99),
    (7, 4, 1,  199.99)
ON CONFLICT DO NOTHING;
