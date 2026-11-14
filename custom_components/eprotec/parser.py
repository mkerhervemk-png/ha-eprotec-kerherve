"""Lecture des pages e-Protec.

v0.1 : la structure des pages « Calendrier » et « Événements » n'est pas
encore connue. parse_missions retourne None (= non pris en charge), ce qui
laisse les capteurs de missions à l'état « inconnu » plutôt qu'à 0.

Format cible (v0.2), une mission = dict sérialisable :
    {"debut": ISO8601, "fin": ISO8601, "titre": str, "lieu": str, "role": str}
"""

from __future__ import annotations


def parse_missions(page: str) -> list[dict] | None:
    """Retourne la liste des missions à venir, ou None si non pris en charge."""
    return None
