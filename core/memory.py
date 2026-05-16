"""
Mémoire conversationnelle multi-tours.
Stocke l'historique des échanges pour le contexte des questions de suivi.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ConversationTurn:
    """Un échange question/SQL dans la conversation."""
    question: str
    sql: str
    explanation: str
    timestamp: datetime = field(default_factory=datetime.now)
    row_count: int = 0
    attempts: int = 1


class ConversationMemory:
    """
    Mémoire conversationnelle avec fenêtre glissante.
    Conserve les N derniers échanges pour le contexte multi-tours.
    """

    def __init__(self, max_turns: int = 10) -> None:
        self._history: deque[ConversationTurn] = deque(maxlen=max_turns)

    def add_turn(
        self,
        question: str,
        sql: str,
        explanation: str = "",
        row_count: int = 0,
        attempts: int = 1,
    ) -> None:
        """Ajoute un nouvel échange à la mémoire."""
        self._history.append(
            ConversationTurn(
                question=question,
                sql=sql,
                explanation=explanation,
                row_count=row_count,
                attempts=attempts,
            )
        )

    def get_history(self) -> list[dict[str, str]]:
        """Retourne l'historique formaté pour injection dans le prompt."""
        return [
            {"question": turn.question, "sql": turn.sql}
            for turn in self._history
        ]

    def get_turns(self) -> list[ConversationTurn]:
        """Retourne tous les échanges (objets complets)."""
        return list(self._history)

    def clear(self) -> None:
        """Réinitialise la mémoire conversationnelle."""
        self._history.clear()

    def __len__(self) -> int:
        return len(self._history)
