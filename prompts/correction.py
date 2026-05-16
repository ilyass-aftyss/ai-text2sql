"""
Prompt Engineering — Template de self-correction SQL.
Utilisé par la boucle LangGraph en cas d'erreur d'exécution.
"""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate


SYSTEM_CORRECTION = """Tu es un expert SQL. Une requête SQL a échoué lors de son exécution.

TON RÔLE :
1. Analyser l'erreur retournée par la base de données
2. Identifier la cause précise du problème
3. Retourner UNIQUEMENT le SQL corrigé, sans aucun commentaire ni explication
4. Le SQL corrigé doit toujours être une requête SELECT

RÈGLES :
- Ne génère AUCUNE requête DML ou DDL
- Utilise uniquement les tables et colonnes présentes dans le schéma
- Termine par un point-virgule
"""

HUMAN_CORRECTION = """=== SCHÉMA DISPONIBLE ===
{schema}

=== QUESTION ORIGINALE DE L'UTILISATEUR ===
{question}

=== REQUÊTE SQL INCORRECTE ===
{sql_invalide}

=== ERREUR RETOURNÉE PAR LA BASE DE DONNÉES ===
{message_erreur}

=== TENTATIVE N°{attempt} / {max_attempts} ===

SQL corrigé :"""


def build_correction_prompt() -> ChatPromptTemplate:
    """Construit le template de self-correction."""
    return ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_CORRECTION),
            ("human", HUMAN_CORRECTION),
        ]
    )
