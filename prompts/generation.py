"""
Prompt Engineering — Template de génération SQL.
Structuré en 6 blocs injectés dynamiquement.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


SYSTEM_GENERATION = """Tu es un expert SQL spécialisé en génération de requêtes précises et optimisées.

RÈGLES ABSOLUES — À respecter sans exception :
1. Génère UNIQUEMENT des requêtes SELECT (jamais INSERT, UPDATE, DELETE, DROP, etc.)
2. Retourne UNIQUEMENT le SQL brut, sans bloc markdown, sans commentaire, sans explication
3. Utilise EXCLUSIVEMENT les tables et colonnes listées dans le schéma fourni
4. En cas de doute sur une colonne, préfère NULL plutôt qu'inventer un nom
5. Termine toujours par un point-virgule
6. Pour les agrégations, utilise toujours GROUP BY correctement
7. Utilise des alias de colonnes explicites pour les expressions calculées

DIALECTE : {dialect}
"""

HUMAN_GENERATION = """=== SCHÉMA PERTINENT ===
{schema_retrieved}

=== EXEMPLES FEW-SHOT (question → SQL validé) ===
{few_shot_examples}

=== HISTORIQUE DE CONVERSATION ===
{chat_history}

=== QUESTION DE L'UTILISATEUR ===
{question}

SQL :"""


def build_generation_prompt() -> ChatPromptTemplate:
    """Construit le template de génération SQL."""
    return ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_GENERATION),
            MessagesPlaceholder(variable_name="messages", optional=True),
            ("human", HUMAN_GENERATION),
        ]
    )


def format_few_shot_examples(examples: list[dict[str, str]]) -> str:
    """Formate les exemples few-shot pour injection dans le prompt."""
    if not examples:
        return "Aucun exemple disponible."
    lines: list[str] = []
    for i, ex in enumerate(examples, 1):
        lines.append(f"Exemple {i}:")
        lines.append(f"  Question : {ex['question']}")
        lines.append(f"  SQL      : {ex['sql']}")
        lines.append("")
    return "\n".join(lines)


def format_chat_history(history: list[dict[str, str]]) -> str:
    """Formate l'historique conversationnel."""
    if not history:
        return "Aucun historique."
    lines: list[str] = []
    for entry in history[-6:]:  # max 6 derniers échanges
        lines.append(f"Utilisateur : {entry['question']}")
        if entry.get("sql"):
            lines.append(f"SQL généré  : {entry['sql']}")
        lines.append("")
    return "\n".join(lines)
