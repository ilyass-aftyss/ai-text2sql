# 🧠 Text-to-SQL Intelligent

> Interrogez n'importe quelle base de données SQL en **langage naturel** (français ou anglais),  
> propulsé par **Llama 3.1 via Ollama** — 100% local, zéro coût d'API, zéro cloud.

---

## ✨ Ce que fait ce système

| Couche | Technologie | Rôle |
|--------|-------------|------|
| 1 – Schema RAG | ChromaDB + Sentence Transformers | Récupère les tables/colonnes pertinentes |
| 2 – Few-Shot | ChromaDB + ST | Injecte les 3 exemples NL→SQL les plus proches |
| 3 – Génération SQL | Llama 3.1 (Ollama) + LangChain | Génère la requête SQL |
| 4 – Self-Correction | LangGraph + Llama 3.1 | Corrige automatiquement jusqu'à 3× |
| 5 – Explication | Llama 3.1 + LangChain | Explique le SQL en français pédagogique |

**Interface** : Streamlit avec visualisations Plotly  
**API REST** : FastAPI avec docs interactives  
**Base de données** : PostgreSQL, MySQL ou SQLite

---

## 🖥️ Prérequis — Installation sur votre PC

### 1. Python 3.11+

Vérifiez votre version :
```bash
python --version
# Doit afficher : Python 3.11.x ou 3.12.x
```

Si nécessaire, téléchargez Python 3.11 sur https://www.python.org/downloads/

---

### 2. Ollama — LLM Local Llama 3.1

**Ollama** fait tourner Llama 3.1 entièrement sur votre machine, sans API key.

#### Installation Ollama :

**macOS / Linux :**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

**Windows :**
Téléchargez l'installateur sur https://ollama.com/download

#### Téléchargement de Llama 3.1 (après installation Ollama) :

```bash
# Modèle 8B (recommandé, ~5 Go, rapide)
ollama pull llama3.1

# Modèle 70B (plus précis, ~40 Go, GPU puissant requis)
ollama pull llama3.1:70b

# Modèle d'embeddings (requis pour ChromaDB)
ollama pull nomic-embed-text
```

#### Vérification Ollama :
```bash
ollama serve          # Démarre le serveur Ollama (laissez ce terminal ouvert)
ollama list           # Doit afficher llama3.1 et nomic-embed-text
```

---

### 3. PostgreSQL (recommandé) ou SQLite (démo)

**Option A — PostgreSQL (production):**

```bash
# macOS (Homebrew)
brew install postgresql@16
brew services start postgresql@16

# Ubuntu / Debian
sudo apt install postgresql-16
sudo systemctl start postgresql

# Windows : https://www.postgresql.org/download/windows/
```

Créez la base de données :
```bash
psql -U postgres
CREATE USER text2sql WITH PASSWORD 'votre_mot_de_passe';
CREATE DATABASE text2sql_db OWNER text2sql;
GRANT ALL PRIVILEGES ON DATABASE text2sql_db TO text2sql;
\q
```

**Option B — SQLite (démo, aucune installation requise):**  
La base de démo SQLite est créée automatiquement par Streamlit. Cliquez "Demo SQLite" dans la sidebar.

---

## 🚀 Installation du projet

### Étape 1 — Clonez / copiez le projet

```bash
# Si vous avez téléchargé le dossier text2sql, naviguez dedans :
cd text2sql
```

### Étape 2 — Créez l'environnement virtuel Python

```bash
# macOS / Linux
python -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.venv\Scripts\activate
```

### Étape 3 — Installez les dépendances

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> ⚠️ L'installation peut prendre 5-10 minutes (Sentence Transformers, PyTorch, etc.)

### Étape 4 — Configurez l'environnement

```bash
# Copiez le fichier de configuration exemple
cp .env.example .env

# Éditez .env avec votre éditeur
nano .env        # Linux/macOS
notepad .env     # Windows
```

**Paramètres essentiels dans `.env` :**

```env
# Base de données PostgreSQL
DATABASE_URL=postgresql://text2sql:votre_mot_de_passe@localhost:5432/text2sql_db

# OU SQLite (démo, aucune config requise)
# DATABASE_URL=sqlite:///./data/demo.sqlite

# SSL/TLS avec certificat CA (PostgreSQL ou MySQL)
# DATABASE_SSL_ENABLED=true
# DATABASE_SSL_MODE=verify-full
# DATABASE_SSL_CA_CERT_PATH=/chemin/vers/ca.pem
# Pour un certificat fourni par un secret, utilisez plutôt :
# DATABASE_SSL_CA_CERT_CONTENT=-----BEGIN CERTIFICATE-----...

# Ollama (laisser les valeurs par défaut si Ollama tourne en local)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1
```

Depuis l'interface Streamlit, activez **SSL/TLS obligatoire**, puis indiquez
le chemin du fichier CA ou importez directement un fichier `.pem`, `.crt` ou
`.cer`. Le fichier importé reste en mémoire de session et est converti en
fichier temporaire privé uniquement pendant la connexion.

L'API accepte les mêmes options sur `POST /connect` :

```json
{
  "database_url": "postgresql+psycopg2://user:password@db.example.com:5432/app",
  "ssl_enabled": true,
  "ssl_mode": "verify-full",
  "ssl_ca_cert_path": "/run/secrets/database-ca.pem"
}
```

Pour MySQL avec `mysql+pymysql://`, le certificat CA est transmis au pilote
PyMySQL et la vérification du nom d'hôte est activée par défaut.

---

## ▶️ Lancement de l'application

### Terminal 1 — Démarrez Ollama

```bash
ollama serve
```

Laissez ce terminal ouvert. Vous devez voir : `Listening on http://127.0.0.1:11434`

### Terminal 2 — Lancez l'interface Streamlit

```bash
# Activez l'environnement virtuel si pas déjà fait
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Lancez l'application
PYTHONPATH=. streamlit run app/main.py

# OU utilisez le script fourni (macOS/Linux)
chmod +x run_streamlit.sh
./run_streamlit.sh
```

Ouvrez votre navigateur sur : **http://localhost:8501**

### Terminal 3 (optionnel) — Lancez l'API FastAPI

```bash
source .venv/bin/activate
PYTHONPATH=. uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload

# OU
./run_api.sh
```

Documentation API interactive : **http://localhost:8000/docs**

---

## 📱 Guide d'utilisation — Streamlit

### 1. Connexion à la base de données

Dans la **barre latérale** à gauche :
- Entrez votre URI de connexion PostgreSQL
- Cliquez **"🔌 Connecter"**
- Le schéma est extrait et indexé automatiquement (~10-30 secondes)

**Pour tester sans PostgreSQL :**
- Cliquez **"Demo SQLite"** — une base avec clients/produits/commandes est créée automatiquement

### 2. Posez vos questions

Dans la zone de texte principale :
```
Exemples de questions :
- "Quels sont les 5 produits les plus vendus ?"
- "Quel est le chiffre d'affaires par mois ?"
- "Combien de clients sont inactifs depuis 6 mois ?"
- "Quelle est la valeur moyenne d'une commande ?"
- "Show me the top 10 customers by total spending"
```

Cliquez **"⚡ Générer SQL & Exécuter"**

### 3. Résultats

L'interface affiche :
- **Onglet Données** : tableau paginable + graphique Plotly automatique + export CSV
- **Onglet SQL** : requête générée avec coloration syntaxique
- **Onglet Explication** : explication pédagogique en français

### 4. Badge de correction

| Badge | Signification |
|-------|--------------|
| ✅ Vert | Généré du premier coup |
| 🟠 Orange | 1 correction automatique |
| 🔴 Rouge | 2-3 corrections automatiques |

### 5. Questions de suivi (multi-tours)

Posez des questions de suivi en référence aux résultats :
```
Premier : "Quels sont les 10 meilleurs clients ?"
Suivi   : "Et parmi eux, lesquels ont commandé ce mois-ci ?"
```

---

## 🌐 Utilisation de l'API FastAPI

### Connexion via API

```bash
curl -X POST "http://localhost:8000/connect" \
  -H "Content-Type: application/json" \
  -d '{"database_url": "postgresql://text2sql:password@localhost:5432/text2sql_db"}'
```

### Requête en langage naturel

```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"question": "Quels sont les 5 produits les plus vendus ?"}'
```

### Réponse JSON

```json
{
  "question": "Quels sont les 5 produits les plus vendus ?",
  "sql": "SELECT p.nom, SUM(l.quantite) AS total FROM produits p ...",
  "explanation": "Cette requête récupère les 5 produits avec le plus grand nombre d'unités vendues...",
  "success": true,
  "row_count": 5,
  "attempts": 1,
  "data": [...],
  "execution_time_ms": 23.4
}
```

---

## 🧪 Lancer les tests

```bash
# Tous les tests unitaires (sans Ollama requis)
cd text2sql
PYTHONPATH=. SKIP_E2E=1 pytest tests/ -v

# Tests avec couverture de code
PYTHONPATH=. SKIP_E2E=1 pytest tests/ --cov=. --cov-report=html

# Tests complets (avec Ollama en cours d'exécution)
PYTHONPATH=. pytest tests/ -v
```

---

## 🐳 Option Docker Compose (tout-en-un)

Si vous avez Docker installé, cette commande lance tout :

```bash
# Construire et démarrer tous les services
docker compose up --build

# Avec GPU NVIDIA (pour Llama 3.1 plus rapide)
docker compose up --build

# En arrière-plan
docker compose up -d --build
```

Téléchargez ensuite Llama 3.1 dans le conteneur Ollama :
```bash
docker exec -it text2sql_ollama ollama pull llama3.1
docker exec -it text2sql_ollama ollama pull nomic-embed-text
```

Services disponibles :
- Streamlit : http://localhost:8501
- FastAPI : http://localhost:8000
- PostgreSQL : localhost:5432

---

## 🏗️ Architecture du projet

```
text2sql/
├── app/
│   ├── main.py            # Interface Streamlit
│   ├── api.py             # API FastAPI
│   ├── config.py          # Configuration (.env)
│   └── utils.py           # Utilitaires communs
│
├── core/                  # ← 5 couches IA
│   ├── schema_retriever.py    # Couche 1 : RAG schéma SQL
│   ├── few_shot_selector.py   # Couche 2 : Few-shot dynamique
│   ├── sql_generator.py       # Couche 3 : Génération SQL (Llama 3.1)
│   ├── sql_validator.py       # Couche 4 : LangGraph self-correction
│   ├── explainer.py           # Couche 5 : Explication pédagogique
│   ├── security.py            # Blocage DML/DDL (regex + AST)
│   └── memory.py              # Mémoire conversationnelle multi-tours
│
├── database/
│   ├── connector.py       # Connexion SQLAlchemy (PG/MySQL/SQLite)
│   ├── schema_extractor.py # Extraction métadonnées
│   └── executor.py        # Exécution sécurisée
│
├── vectorstore/
│   └── indexer.py         # ChromaDB + Sentence Transformers
│
├── prompts/
│   ├── generation.py      # Template 6 blocs (génération SQL)
│   ├── correction.py      # Template self-correction
│   └── explanation.py     # Template explication pédagogique
│
├── evaluation/
│   └── metrics.py         # Exact Match, Execution Match
│
├── data/
│   ├── few_shot/
│   │   └── examples.json  # 25 exemples NL→SQL validés
│   └── init.sql           # Base de démo PostgreSQL
│
├── tests/
│   ├── test_security.py   # Tests couche sécurité
│   ├── test_validator.py  # Tests validation + métriques
│   ├── test_generator.py  # Tests utilitaires
│   └── test_e2e.py        # Tests intégration E2E
│
├── requirements.txt
├── docker-compose.yml
├── Dockerfile
├── .env.example
└── README.md
```

---

## ⚠️ Résolution des problèmes fréquents

### Ollama ne répond pas

```bash
# Vérifiez qu'Ollama tourne
curl http://localhost:11434/api/tags

# Si non, redémarrez
ollama serve
```

### Le modèle llama3.1 n'est pas trouvé

```bash
ollama pull llama3.1
ollama list  # Vérifiez qu'il apparaît
```

### Erreur de connexion PostgreSQL

```bash
# Testez la connexion manuellement
psql -U text2sql -d text2sql_db -h localhost

# Vérifiez que PostgreSQL tourne
pg_isready -h localhost -p 5432
```

### Sentence Transformers lent au premier démarrage

Normal — le modèle `all-MiniLM-L6-v2` (~90 Mo) est téléchargé la première fois.  
Les démarrages suivants sont instantanés (cache local).

### Mémoire insuffisante pour Llama 3.1 8B

Llama 3.1 8B requiert environ **8 Go de RAM** (ou VRAM si GPU).  
Si vous avez moins de 8 Go, utilisez un modèle plus léger :
```bash
ollama pull phi3        # ~3.8 Go
# Puis dans .env : OLLAMA_MODEL=phi3
```

### ChromaDB — erreur de collection

```bash
# Supprimez et réindexez
rm -rf data/chroma_db
# Redémarrez l'application
```

---

## 📊 Performances attendues

| Métrique | Cible | Notes |
|---------|-------|-------|
| Temps de réponse (simple) | < 10s | Avec Llama 3.1 8B CPU |
| Temps de réponse (avec correction) | < 30s | CPU, 3 tentatives max |
| Temps de réponse (GPU) | < 3s | NVIDIA RTX 3080+ |
| Précision (base simple) | ≥ 70% | Spider benchmark |
| Requêtes bloquées DML/DDL | 100% | Sécurité garantie |

---

## 🔒 Sécurité

- **Blocage systématique** de DROP, DELETE, INSERT, UPDATE, TRUNCATE, ALTER, CREATE
- **Double validation** : regex rapide + analyse AST sqlparse
- **Mode READ ONLY** PostgreSQL activé automatiquement si `SQL_READ_ONLY=true`
- **Aucun secret** stocké en dur — tout via `.env`
- **Sanitisation** des entrées utilisateur avant injection dans les prompts

---

## 📄 Licence

MIT — Projet portfolio senior. Utilisation libre.

---

*Document généré le Mai 2026 — Version 1.0*
