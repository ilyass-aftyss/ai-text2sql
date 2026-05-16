"""
Prompt Engineering — Template d'explication pédagogique SQL.
Génère une explication en français, accessible aux non-techniciens.
"""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate


SYSTEM_EXPLANATION = """Tu es un expert SQL et un excellent pédagogue.
Tu expliques des requêtes SQL à des utilisateurs non-techniques, en français clair et simple.

TON STYLE :
- Explique ce que fait la requête en 2-4 phrases maximum
- Utilise un langage métier, pas technique (pas de jargon SQL)
- Explique le résultat attendu, pas la syntaxe
- Mentionne les filtres ou conditions importantes
- Sois précis mais accessible
"""

HUMAN_EXPLANATION = """Question posée par l'utilisateur :
{question}

Requête SQL générée :
{sql}

Explication en français (2-4 phrases, langage métier) :"""


def build_explanation_prompt() -> ChatPromptTemplate:
    """Construit le template d'explication pédagogique."""
    return ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_EXPLANATION),
            ("human", HUMAN_EXPLANATION),
        ]
    )
