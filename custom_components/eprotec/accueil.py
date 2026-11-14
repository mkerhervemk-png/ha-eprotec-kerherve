"""Lecture de la page d'accueil e-Protec (blocs du tableau de bord)."""

from __future__ import annotations

from html.parser import HTMLParser
import re
import unicodedata

_PHONE_RE = re.compile(r"(?:\+33|0)\s?\d(?:[\s.]?\d{2}){4}")
_INT_RE = re.compile(r"^\d+$")
_HOURS_RE = re.compile(r"(\d+)\s*[:h]\s*(\d{2})")
_WS_RE = re.compile(r"\s+")
VIDE = "aucun resultat"

# classe CSS -> repère inséré dans le flux de texte
_MARKS = {
    "stats-container": "stats",
    "infos-date": "date",
    "infos-content": "content",
    "widget-title": "wt",
    "widget-text": "wx",
    "fa-birthday-cake": "cake",
}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).lower().strip()


class _Flattener(HTMLParser):
    """Transforme la page en suite de (type, valeur) : header, mark, text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tokens: list[tuple[str, str]] = []
        self._skip = 0
        self._header_depth = 0
        self._header_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
            return
        classes = (dict(attrs).get("class") or "").split()
        if self._header_depth:
            if tag == "div":
                self._header_depth += 1
            return
        if tag == "div" and "card-header" in classes:
            self._header_depth = 1
            self._header_text = []
            return
        if tag == "tr":
            self.tokens.append(("mark", "tr"))
        for cls in classes:
            if cls in _MARKS:
                self.tokens.append(("mark", _MARKS[cls]))

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
            return
        if self._header_depth and tag == "div":
            self._header_depth -= 1
            if self._header_depth == 0:
                self.tokens.append(("header", " ".join(self._header_text)))

    def handle_data(self, data):
        if self._skip:
            return
        text = _WS_RE.sub(" ", data).strip()
        if not text:
            return
        if self._header_depth:
            self._header_text.append(text)
        else:
            self.tokens.append(("text", text))


def _until(tokens, start, stop_marks=(), stop_header=True):
    """Textes à partir de start jusqu'au prochain repère d'arrêt."""
    texts = []
    for kind, value in tokens[start:]:
        if kind == "header" and stop_header:
            break
        if kind == "mark" and value in stop_marks:
            break
        if kind == "text":
            texts.append(value)
    return texts


def _sections(tokens) -> dict[str, list[tuple[str, str]]]:
    sections: dict[str, list[tuple[str, str]]] = {}
    current: list[tuple[str, str]] | None = None
    for kind, value in tokens:
        if kind == "header":
            current = sections.setdefault(_norm(value), [])
        elif current is not None:
            current.append((kind, value))
    return sections


def _find(sections, prefix):
    for name, content in sections.items():
        if name.startswith(prefix):
            return content
    return None


def _texts(content) -> list[str]:
    return [value for kind, value in content if kind == "text"]


def _count(content) -> int | None:
    """Nombre d'éléments d'un bloc simple (0 si « Aucun résultat »)."""
    if content is None:
        return None
    texts = _texts(content)
    if not texts or _norm(texts[0]).startswith(VIDE):
        return 0
    rows = sum(1 for kind, value in content if kind == "mark" and value == "tr")
    return rows or 1


def _infos(content) -> list[dict] | None:
    """Messages datés (consignes, actualités)."""
    if content is None:
        return None
    items: list[dict] = []
    for index, (kind, value) in enumerate(content):
        if kind == "mark" and value == "date":
            date_texts = _until(content, index + 1, ("content", "tr", "date"))
            body: list[str] = []
            for offset in range(index + 1, len(content)):
                k, v = content[offset]
                if k == "mark" and v == "content":
                    body = _until(content, offset + 1, ("tr", "date"))
                    break
                if k == "mark" and v in ("tr", "date"):
                    break
            if not body:
                continue
            items.append(
                {
                    "date": date_texts[0] if date_texts else None,
                    "titre": body[0][:200],
                    "texte": " ".join(body[1:])[:600] or None,
                }
            )
    return items


def _stats(tokens) -> dict[str, dict[str, int]]:
    groups: dict[str, dict[str, int]] = {}
    for index, (kind, value) in enumerate(tokens):
        if kind == "mark" and value == "stats":
            texts = _until(tokens, index + 1, ("stats",))
            if not texts:
                continue
            values: dict[str, int] = {}
            label = None
            for text in texts[1:]:
                if _INT_RE.match(text) and label:
                    values[label] = int(text)
                    label = None
                else:
                    label = text
            groups[texts[0]] = values
    return groups


def _birthdays(tokens) -> list[str] | None:
    for index, (kind, value) in enumerate(tokens):
        if kind == "mark" and value == "cake":
            texts = _until(tokens, index + 1, ("tr", "cake"))
            if not texts or _norm(texts[0]).startswith(VIDE):
                return []
            return [text[:80] for text in texts if len(text) > 1][:30]
    return None


def _veille(content) -> list[dict] | None:
    if content is None:
        return None
    people: list[dict] = []
    row: list[str] = []

    def flush():
        # Les numéros de téléphone ne sont volontairement pas conservés.
        kept = [t for t in (_PHONE_RE.sub("", x).strip() for x in row) if t]
        if kept and not _norm(kept[0]).startswith(VIDE):
            people.append({"nom": kept[0][:80], "role": " ".join(kept[1:])[:160] or None})

    for kind, value in content:
        if kind == "mark" and value == "tr":
            flush()
            row = []
        elif kind == "text":
            row.append(value)
    flush()
    return people


def _formation(content) -> list[dict] | None:
    if content is None:
        return None
    lines: list[dict] = []
    for index, (kind, value) in enumerate(content):
        if kind == "mark" and value == "wt":
            label = _until(content, index + 1, ("wx", "wt", "tr"))
            detail: list[str] = []
            for offset in range(index + 1, len(content)):
                k, v = content[offset]
                if k == "mark" and v == "wx":
                    detail = _until(content, offset + 1, ("wt", "tr"))
                    break
                if k == "mark" and v in ("wt", "tr"):
                    break
            joined = " ".join(detail)
            match = _HOURS_RE.search(joined)
            lines.append(
                {
                    "libelle": " ".join(label)[:80] or None,
                    "heures": round(int(match.group(1)) + int(match.group(2)) / 60, 2)
                    if match
                    else None,
                    "detail": joined[:80] or None,
                }
            )
    return lines


def parse_accueil(page: str) -> tuple[dict, dict]:
    """Retourne (données de l'accueil, infos techniques sans donnée personnelle)."""
    flat = _Flattener()
    flat.feed(page)
    tokens = flat.tokens
    sections = _sections(tokens)
    data = {
        "statistiques": _stats(tokens),
        "anniversaires": _birthdays(tokens),
        "veille": _veille(_find(sections, "astreinte")),
        "consignes": _infos(_find(sections, "consigne")),
        "actualites": _infos(_find(sections, "actualite")),
        "remplacements": _count(_find(sections, "remplacement")),
        "mes_activites": _count(_find(sections, "mes activites")),
        "main_courante": _count(_find(sections, "main courante")),
        "formation": _formation(_find(sections, "heure de formation")),
    }
    info = {
        "blocs": len(sections),
        "trouves": sorted(key for key, value in data.items() if value not in (None, {})),
        "manquants": sorted(key for key, value in data.items() if value in (None, {})),
    }
    return data, info
