"""
Interface Streamlit — Text-to-SQL Intelligent
Point d'entrée principal de l'application.
"""

from __future__ import annotations

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st

from app.config import settings
from app.utils import dataframe_to_csv, detect_chart_type, sanitize_user_input
from core.explainer import SQLExplainer
from core.few_shot_selector import FewShotSelector
from core.memory import ConversationMemory
from core.schema_retriever import SchemaRetriever
from core.sql_generator import SQLGenerator
from core.sql_validator import SQLValidator
from database.connector import DatabaseConnector, DatabaseSSLConfig
from database.executor import SafeExecutor
from database.schema_extractor import SchemaExtractor
from vectorstore.indexer import VectorStoreIndexer

# ─── Configuration Streamlit ─────────────────────────────────────────────────

st.set_page_config(
    page_title="Text-to-SQL Intelligent",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS Personnalisé ────────────────────────────────────────────────────────

st.markdown(
    """
<style>
    /* Thème général */
    .stApp { background: #0f1117; }

    /* Header principal */
    .main-header {
        background: linear-gradient(135deg, #1e3a5f 0%, #0d1b2e 100%);
        padding: 2rem 2.5rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        border: 1px solid #2a4a7f;
    }
    .main-header h1 { color: #60a5fa; font-size: 2.2rem; margin: 0; }
    .main-header p { color: #94a3b8; margin: 0.3rem 0 0; font-size: 1rem; }

    /* Cartes */
    .metric-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1rem 1.5rem;
        text-align: center;
    }

    /* Badge de correction */
    .badge-success { background: #065f46; color: #34d399; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }
    .badge-warning { background: #7c2d12; color: #fb923c; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }
    .badge-danger  { background: #7f1d1d; color: #f87171; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }

    /* Bloc SQL */
    .sql-block {
        background: #0d1117;
        border: 1px solid #30363d;
        border-left: 4px solid #60a5fa;
        border-radius: 8px;
        padding: 1rem 1.5rem;
        font-family: 'JetBrains Mono', 'Fira Code', monospace;
        font-size: 0.9rem;
        color: #e2e8f0;
        white-space: pre-wrap;
        word-break: break-word;
    }

    /* Explication */
    .explanation-block {
        background: #1e3a2e;
        border: 1px solid #166534;
        border-left: 4px solid #4ade80;
        border-radius: 8px;
        padding: 1rem 1.5rem;
        color: #dcfce7;
        font-size: 0.95rem;
        line-height: 1.6;
    }

    /* Historique */
    .history-item {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.5rem;
        cursor: pointer;
    }
    .history-item:hover { border-color: #60a5fa; }
    .history-item .question { color: #e2e8f0; font-size: 0.9rem; }
    .history-item .meta { color: #64748b; font-size: 0.75rem; }

    /* Input personnalisé */
    .stTextArea textarea { background: #1e293b !important; color: #e2e8f0 !important; border-color: #334155 !important; }
    .stTextInput input { background: #1e293b !important; color: #e2e8f0 !important; border-color: #334155 !important; }
    .stSelectbox select { background: #1e293b !important; }

    /* Boutons */
    .stButton button[kind="primary"] {
        background: linear-gradient(135deg, #2563eb, #1d4ed8);
        border: none;
        border-radius: 8px;
        font-weight: 600;
        padding: 0.6rem 2rem;
    }

    /* Divider */
    hr { border-color: #334155 !important; }

    /* Sidebar */
    .css-1d391kg { background: #1e293b; }
</style>
""",
    unsafe_allow_html=True,
)

# ─── État de session ─────────────────────────────────────────────────────────


def init_session_state() -> None:
    defaults: dict = {
        "connected": False,
        "db_url": "",
        "ssl_enabled": settings.database_ssl_enabled,
        "ssl_mode": settings.database_ssl_mode,
        "ssl_ca_cert_path": settings.database_ssl_ca_cert_path or "",
        "ssl_ca_cert_content": None,
        "ssl_verify_identity": settings.database_ssl_verify_identity,
        "connector": None,
        "indexer": None,
        "generator": None,
        "validator": None,
        "explainer": None,
        "memory": ConversationMemory(),
        "schema_indexed": False,
        "schema_info": None,
        "query_history": [],
        "last_result": None,
        "last_sql": None,
        "last_explanation": None,
        "last_attempts": 1,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()


# ─── Fonctions helpers ───────────────────────────────────────────────────────


@st.cache_resource(show_spinner=False)
def get_indexer() -> VectorStoreIndexer:
    indexer = VectorStoreIndexer()
    indexer.index_few_shot("data/few_shot/examples.json")
    return indexer


def connect_database(
    db_url: str,
    ssl_config: DatabaseSSLConfig | None = None,
) -> bool:
    """Connecte la base de données et indexe le schéma."""
    try:
        connector = DatabaseConnector(db_url, ssl_config=ssl_config)
        ok, msg = connector.test_connection()
        if not ok:
            st.error(f"❌ {msg}")
            return False

        with st.spinner("📋 Extraction du schéma..."):
            extractor = SchemaExtractor(connector.connect())
            schema_info = extractor.extract()

        indexer = get_indexer()

        with st.spinner("🔍 Indexation du schéma dans ChromaDB..."):
            indexer.reset_schema()
            indexer.index_schema(schema_info.to_chunks())

        executor = SafeExecutor(connector)
        schema_retriever = SchemaRetriever(indexer)
        few_shot_selector = FewShotSelector(indexer)

        st.session_state.connector = connector
        st.session_state.indexer = indexer
        st.session_state.generator = SQLGenerator(
            schema_retriever,
            few_shot_selector,
            dialect=connector.dialect,
        )
        st.session_state.validator = SQLValidator(executor)
        st.session_state.explainer = SQLExplainer()
        st.session_state.schema_info = schema_info
        st.session_state.schema_indexed = True
        st.session_state.connected = True
        st.session_state.db_url = db_url
        st.session_state.ssl_enabled = ssl_config.enabled if ssl_config else False
        st.session_state.ssl_mode = ssl_config.mode if ssl_config else settings.database_ssl_mode
        st.session_state.ssl_ca_cert_path = ssl_config.ca_cert_path if ssl_config else ""
        st.session_state.ssl_ca_cert_content = None
        st.session_state.ssl_verify_identity = (
            ssl_config.verify_identity if ssl_config else settings.database_ssl_verify_identity
        )

        return True

    except Exception as exc:
        st.error(f"❌ Erreur de connexion : {exc}")
        return False


def run_pipeline(question: str) -> None:
    """Lance le pipeline complet Text-to-SQL."""
    generator: SQLGenerator = st.session_state.generator
    validator: SQLValidator = st.session_state.validator
    explainer: SQLExplainer = st.session_state.explainer
    memory: ConversationMemory = st.session_state.memory

    progress = st.progress(0, text="🔄 Génération SQL en cours...")

    try:
        # Étape 1 — Génération SQL
        history = memory.get_history()
        sql = generator.generate(question, chat_history=history)
        progress.progress(35, text="✅ SQL généré — Validation en cours...")

        # Étape 2 — Validation + Self-correction
        schema_text = st.session_state.schema_info.to_text()
        validation_result = validator.validate_and_correct(sql, question, schema_text)
        progress.progress(70, text="✅ Validation terminée — Explication en cours...")

        # Étape 3 — Explication pédagogique
        explanation = explainer.explain(question, validation_result.sql)
        progress.progress(100, text="✅ Pipeline complet")

        # Sauvegarde en mémoire
        row_count = 0
        if validation_result.execution_result:
            row_count = validation_result.execution_result.row_count

        memory.add_turn(
            question=question,
            sql=validation_result.sql,
            explanation=explanation,
            row_count=row_count,
            attempts=validation_result.attempts,
        )

        # Mise à jour état session
        st.session_state.last_sql = validation_result.sql
        st.session_state.last_explanation = explanation
        st.session_state.last_attempts = validation_result.attempts
        st.session_state.last_result = (
            validation_result.execution_result.data
            if validation_result.execution_result and validation_result.execution_result.success
            else None
        )
        st.session_state.last_error = (
            validation_result.errors[0] if validation_result.errors else None
        )

        # Historique de la session
        st.session_state.query_history.append({
            "question": question,
            "sql": validation_result.sql,
            "rows": row_count,
            "attempts": validation_result.attempts,
            "success": validation_result.succeeded,
        })

    except Exception as exc:
        progress.empty()
        st.error(f"❌ Erreur dans le pipeline : {exc}")
        raise
    finally:
        progress.empty()


# ─── Base démo SQLite ────────────────────────────────────────────────────────


def _create_demo_db() -> None:
    """Crée une base SQLite de démonstration avec données exemples."""
    import random
    import sqlite3
    from datetime import date, timedelta
    from pathlib import Path

    Path("data").mkdir(exist_ok=True)
    db_path = Path("data/demo.sqlite")
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            ville TEXT,
            pays TEXT DEFAULT 'France',
            date_inscription DATE DEFAULT CURRENT_DATE,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS produits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            prix_unitaire REAL NOT NULL,
            categorie TEXT,
            stock_actuel INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS commandes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER REFERENCES clients(id),
            date_commande DATE DEFAULT CURRENT_DATE,
            montant_total REAL,
            statut TEXT DEFAULT 'en_attente'
        );
        CREATE TABLE IF NOT EXISTS lignes_commande (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            commande_id INTEGER REFERENCES commandes(id),
            produit_id INTEGER REFERENCES produits(id),
            quantite INTEGER DEFAULT 1,
            prix_unitaire REAL
        );
    """)

    clients_data = [
        ("Alice Martin", "alice@example.com", "Paris", "France"),
        ("Bob Durand", "bob@example.com", "Lyon", "France"),
        ("Claire Petit", "claire@example.com", "Marseille", "France"),
        ("David Roux", "david@example.com", "Bordeaux", "France"),
        ("Emma Leroy", "emma@example.com", "Toulouse", "France"),
        ("François Bernard", "francois@example.com", "Nantes", "France"),
        ("Gabrielle Thomas", "gabrielle@example.com", "Strasbourg", "France"),
        ("Henri Moreau", "henri@example.com", "Genève", "Suisse"),
        ("Isabelle Simon", "isabelle@example.com", "Bruxelles", "Belgique"),
        ("Julien Laurent", "julien@example.com", "Paris", "France"),
    ]
    produits_data = [
        ("Laptop Pro", 1299.99, "Informatique", 15),
        ("Souris Ergonomique", 49.99, "Informatique", 80),
        ("Clavier Mécanique", 129.99, "Informatique", 45),
        ("Écran 27 pouces", 399.99, "Informatique", 20),
        ("Casque Audio", 199.99, "Audio", 60),
        ("Webcam HD", 89.99, "Périphériques", 35),
        ("Disque SSD 1TB", 149.99, "Stockage", 55),
        ("Hub USB-C", 39.99, "Accessoires", 100),
        ("Tapis de souris XXL", 24.99, "Accessoires", 200),
        ("Lampe LED", 59.99, "Bureau", 75),
    ]

    cursor.execute("SELECT COUNT(*) FROM clients")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO clients (nom, email, ville, pays) VALUES (?, ?, ?, ?)",
            clients_data,
        )
        cursor.executemany(
            "INSERT INTO produits (nom, prix_unitaire, categorie, stock_actuel) VALUES (?, ?, ?, ?)",
            produits_data,
        )
        for _ in range(30):
            client_id = random.randint(1, 10)
            days_ago = random.randint(0, 180)
            order_date = (date.today() - timedelta(days=days_ago)).isoformat()
            statut = random.choice(["livree", "livree", "livree", "en_attente", "annulee"])
            cursor.execute(
                "INSERT INTO commandes (client_id, date_commande, statut) VALUES (?, ?, ?)",
                (client_id, order_date, statut),
            )
            commande_id = cursor.lastrowid
            total = 0.0
            for _ in range(random.randint(1, 4)):
                produit_id = random.randint(1, 10)
                cursor.execute("SELECT prix_unitaire FROM produits WHERE id = ?", (produit_id,))
                row = cursor.fetchone()
                if row:
                    prix = row[0]
                    quantite = random.randint(1, 3)
                    cursor.execute(
                        "INSERT INTO lignes_commande (commande_id, produit_id, quantite, prix_unitaire) VALUES (?, ?, ?, ?)",
                        (commande_id, produit_id, quantite, prix),
                    )
                    total += prix * quantite
            cursor.execute(
                "UPDATE commandes SET montant_total = ? WHERE id = ?",
                (round(total, 2), commande_id),
            )

    conn.commit()
    conn.close()


# ─── Sidebar ─────────────────────────────────────────────────────────────────


with st.sidebar:
    st.markdown("## ⚙️ Configuration")
    st.markdown("---")

    # Connexion BDD
    st.markdown("### 🗄️ Base de données")
    db_url = st.text_input(
        "URI de connexion",
        value=st.session_state.get("db_url", ""),
        type="password",
        placeholder="postgresql://user:pass@localhost:5432/db",
        help="Format : postgresql://user:password@host:port/dbname",
    )
    ssl_enabled = st.checkbox(
        "🔒 SSL/TLS obligatoire",
        value=st.session_state.ssl_enabled,
        help="Utilise un certificat CA pour chiffrer et vérifier la connexion.",
    )
    ssl_mode = st.selectbox(
        "Mode SSL PostgreSQL",
        options=["verify-full", "verify-ca", "require"],
        index=["verify-full", "verify-ca", "require"].index(
            st.session_state.ssl_mode
            if st.session_state.ssl_mode in {"verify-full", "verify-ca", "require"}
            else "verify-full"
        ),
        disabled=not ssl_enabled,
        help="verify-full vérifie aussi que le nom d'hôte correspond au certificat.",
    )
    ssl_ca_cert_path = st.text_input(
        "Chemin du certificat CA (optionnel)",
        value=st.session_state.ssl_ca_cert_path,
        disabled=not ssl_enabled,
        placeholder="/chemin/vers/ca.pem",
        help="Chemin accessible par le processus Streamlit. Utilisez l'import ci-dessous pour envoyer un fichier.",
    )
    ssl_ca_cert_file = st.file_uploader(
        "Ou importer le certificat CA",
        type=["pem", "crt", "cer"],
        disabled=not ssl_enabled,
        help="Le fichier est conservé uniquement en mémoire de session et jamais affiché dans les logs.",
    )
    ssl_verify_identity = st.checkbox(
        "Vérifier l'identité du serveur MySQL",
        value=st.session_state.ssl_verify_identity,
        disabled=not ssl_enabled,
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔌 Connecter", type="primary", use_container_width=True):
            if db_url:
                ca_content = (
                    ssl_ca_cert_file.getvalue().decode("utf-8")
                    if ssl_ca_cert_file
                    else None
                )
                ssl_config = DatabaseSSLConfig(
                    enabled=ssl_enabled,
                    mode=ssl_mode,
                    ca_cert_path=ssl_ca_cert_path or None,
                    ca_cert_content=ca_content,
                    verify_identity=ssl_verify_identity,
                )
                with st.spinner("Connexion..."):
                    success = connect_database(db_url, ssl_config=ssl_config)
                if success:
                    st.success("✅ Connecté!")
                    st.rerun()
            else:
                st.warning("Entrez une URI valide")

    with col2:
        if st.button("Demo SQLite", use_container_width=True):
            _demo_url = "sqlite:///./data/demo.sqlite"
            _create_demo_db()
            success = connect_database(_demo_url)
            if success:
                st.success("✅ Démo chargée!")
                st.rerun()

    if st.session_state.connected:
        st.success(f"✅ Connecté")
        if st.session_state.schema_info:
            n_tables = len(st.session_state.schema_info.tables)
            st.info(f"📋 {n_tables} tables indexées")

    st.markdown("---")

    # Modèle LLM
    st.markdown("### 🦙 Modèle LLM")
    st.code(f"Ollama — {settings.ollama_model}", language=None)
    st.code(f"Embeddings : {settings.embedding_model}", language=None)

    st.markdown("---")

    # Schéma
    if st.session_state.schema_info:
        st.markdown("### 📊 Schéma détecté")
        for table in st.session_state.schema_info.tables:
            with st.expander(f"📋 {table.name} ({len(table.columns)} col.)"):
                for col in table.columns:
                    pk = " 🔑" if col.primary_key else ""
                    st.text(f"  {col.name}: {col.type}{pk}")

    st.markdown("---")

    # Historique
    if st.session_state.query_history:
        st.markdown("### 🕐 Historique de session")
        for i, item in enumerate(reversed(st.session_state.query_history[-8:])):
            icon = "✅" if item["success"] else "❌"
            with st.expander(f"{icon} {item['question'][:40]}..."):
                st.code(item["sql"], language="sql")
                st.caption(f"Lignes : {item['rows']} | Tentatives : {item['attempts']}")

    if st.button("🗑️ Vider l'historique", use_container_width=True):
        st.session_state.memory.clear()
        st.session_state.query_history = []
        st.rerun()


# ─── Corps principal ──────────────────────────────────────────────────────────


st.markdown(
    """
<div class="main-header">
    <h1>🧠 Text-to-SQL Intelligent</h1>
    <p>Interrogez votre base de données en langage naturel — propulsé par Llama 3.1 via Ollama</p>
</div>
""",
    unsafe_allow_html=True,
)

# ── Zone de question ──────────────────────────────────────────────────────────

if not st.session_state.connected:
    st.info(
        "👈 **Connectez votre base de données** dans la barre latérale pour commencer.\n\n"
        "Vous pouvez aussi utiliser la base de **démo SQLite** pour tester l'application."
    )

    # Suggestions de questions de démo
    st.markdown("### 💡 Exemples de questions")
    suggestions = [
        "Quels sont les 5 produits les plus vendus ?",
        "Quel est le chiffre d'affaires total par mois ?",
        "Combien de clients ont passé plus de 3 commandes ?",
        "Quels clients n'ont pas commandé depuis 3 mois ?",
        "Quelle est la valeur moyenne d'une commande ?",
    ]
    cols = st.columns(2)
    for i, s in enumerate(suggestions):
        with cols[i % 2]:
            st.markdown(f"- _{s}_")

else:
    # Métriques rapides
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Tables indexées", len(st.session_state.schema_info.tables))
    with col2:
        st.metric("Questions posées", len(st.session_state.query_history))
    with col3:
        success_count = sum(1 for q in st.session_state.query_history if q["success"])
        st.metric("Succès", f"{success_count}/{len(st.session_state.query_history)}")
    with col4:
        st.metric("Modèle LLM", settings.ollama_model)

    st.markdown("---")

    # Questions suggérées
    st.markdown("### 💡 Questions suggérées")
    suggestions = [
        "Combien y a-t-il d'enregistrements au total ?",
        "Quels sont les 5 premiers enregistrements ?",
        "Quelle est la distribution par catégorie ?",
    ]
    cols = st.columns(len(suggestions))
    for i, s in enumerate(suggestions):
        with cols[i]:
            if st.button(s, key=f"sugg_{i}", use_container_width=True):
                st.session_state["prefill_question"] = s

    # Zone de saisie principale
    prefill = st.session_state.pop("prefill_question", "")
    question = st.text_area(
        "Votre question en langage naturel",
        value=prefill,
        height=100,
        placeholder="Ex: Quels sont les 10 clients avec le plus grand nombre de commandes ce mois-ci ?",
        key="question_input",
    )

    col_submit, col_clear = st.columns([4, 1])
    with col_submit:
        submit = st.button(
            "⚡ Générer SQL & Exécuter",
            type="primary",
            use_container_width=True,
            disabled=not question.strip(),
        )
    with col_clear:
        if st.button("🧹 Effacer", use_container_width=True):
            st.session_state.last_sql = None
            st.session_state.last_result = None
            st.session_state.last_explanation = None
            st.rerun()

    if submit and question.strip():
        clean_question = sanitize_user_input(question)
        run_pipeline(clean_question)
        st.rerun()

    # ── Résultats ─────────────────────────────────────────────────────────────

    if st.session_state.last_sql:
        st.markdown("---")
        st.markdown("## 📊 Résultats")

        tab1, tab2, tab3 = st.tabs(["📋 Données", "💻 SQL Généré", "📖 Explication"])

        with tab1:
            # Badge de correction
            attempts = st.session_state.last_attempts
            if attempts == 1:
                badge = '<span class="badge-success">✅ Généré du premier coup</span>'
            elif attempts == 2:
                badge = '<span class="badge-warning">🔄 1 correction automatique</span>'
            else:
                badge = f'<span class="badge-danger">🔧 {attempts - 1} corrections automatiques</span>'
            st.markdown(badge, unsafe_allow_html=True)
            st.markdown("")

            if st.session_state.last_result is not None:
                df: pd.DataFrame = st.session_state.last_result
                st.success(f"✅ **{len(df)} ligne(s)** retournée(s)")

                # Tableau
                st.dataframe(df, use_container_width=True, height=300)

                # Graphique automatique
                chart_type = detect_chart_type(df)
                if chart_type:
                    st.markdown("### 📈 Visualisation automatique")
                    numeric_cols = df.select_dtypes(include="number").columns.tolist()
                    text_cols = df.select_dtypes(exclude="number").columns.tolist()

                    try:
                        if chart_type == "bar" and text_cols and numeric_cols:
                            fig = px.bar(
                                df,
                                x=text_cols[0],
                                y=numeric_cols[0],
                                color_discrete_sequence=["#60a5fa"],
                                template="plotly_dark",
                            )
                        elif chart_type == "pie" and text_cols and numeric_cols:
                            fig = px.pie(
                                df,
                                names=text_cols[0],
                                values=numeric_cols[0],
                                template="plotly_dark",
                            )
                        elif chart_type == "scatter" and len(numeric_cols) >= 2:
                            fig = px.scatter(
                                df,
                                x=numeric_cols[0],
                                y=numeric_cols[1],
                                template="plotly_dark",
                                color_discrete_sequence=["#60a5fa"],
                            )
                        else:
                            fig = px.line(
                                df,
                                y=numeric_cols[0],
                                template="plotly_dark",
                                color_discrete_sequence=["#60a5fa"],
                            )
                        fig.update_layout(
                            paper_bgcolor="#0f1117",
                            plot_bgcolor="#1e293b",
                            font_color="#e2e8f0",
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    except Exception:
                        pass

                # Export CSV
                csv_data = dataframe_to_csv(df)
                st.download_button(
                    "📥 Exporter CSV",
                    data=csv_data,
                    file_name="resultats.csv",
                    mime="text/csv",
                )
            elif st.session_state.get("last_error"):
                st.error(f"❌ Erreur après {attempts} tentative(s) : {st.session_state.last_error}")
            else:
                st.warning("Aucune donnée retournée")

        with tab2:
            st.markdown("### 💻 Requête SQL générée")
            st.markdown(
                f'<div class="sql-block">{st.session_state.last_sql}</div>',
                unsafe_allow_html=True,
            )
            st.code(st.session_state.last_sql, language="sql")
            st.button(
                "📋 Copier",
                key="copy_sql",
                help="Copiez le SQL depuis le bloc ci-dessus",
            )

        with tab3:
            st.markdown("### 📖 Explication pédagogique")
            if st.session_state.last_explanation:
                st.markdown(
                    f'<div class="explanation-block">{st.session_state.last_explanation}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.info("Aucune explication disponible")
