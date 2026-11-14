"""Outil de diagnostic temporaire (v0.1.2), à retirer en v0.2.

Service eprotec.debug_fetch : lit UNE page e-Protec dans la session déjà
ouverte (aucune nouvelle connexion), en GET uniquement, sur une liste
fermée de pages de consultation. Rien n'est écrit sur disque.
"""

from __future__ import annotations

import html as html_lib
import re

from yarl import URL

from .const import BASE_URL

_SCRIPT_RE = re.compile(r"<(script|style|svg)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_HEAD_RE = re.compile(r"<head\b.*?</head>", re.IGNORECASE | re.DOTALL)
_STYLE_ATTR_RE = re.compile(r"""\sstyle\s*=\s*("[^"]*"|'[^']*')""", re.IGNORECASE)
_A_RE = re.compile(r"<a\b([^>]*)>(.*?)</a>", re.IGNORECASE | re.DOTALL)
_HREF_RE = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)

# Pages de consultation uniquement.
ALLOWED_SCRIPTS = {
    "index_d.php",
    "upd_personnel.php",
    "evenement_choice.php",
    "evenement_display.php",
    "calendar.php",
    "qualifications.php",
}
FORBIDDEN_QUERY = ("action", "delete", "del", "save", "suppr", "confirm", "valid")


def safe_url(path: str) -> str:
    """Valide un chemin relatif et retourne l'URL complète, ou lève ValueError."""
    base = URL(BASE_URL)
    target = base.join(URL(path.strip()))
    if target.scheme != "https" or target.host != base.host:
        raise ValueError("Hôte non autorisé")
    if target.name not in ALLOWED_SCRIPTS:
        raise ValueError(f"Page non autorisée : {target.name}")
    for key in target.query:
        if any(word in key.lower() for word in FORBIDDEN_QUERY):
            raise ValueError(f"Paramètre non autorisé : {key}")
    return str(target.with_fragment(None))


def _clean(page: str) -> str:
    page = _HEAD_RE.sub("", page)
    page = _SCRIPT_RE.sub("", page)
    page = _COMMENT_RE.sub("", page)
    page = _STYLE_ATTR_RE.sub("", page)
    return _WS_RE.sub(" ", page).strip()


def _links(page: str) -> list[dict]:
    links: list[dict] = []
    seen: set[str] = set()
    for attrs, inner in _A_RE.findall(page):
        href = _HREF_RE.search(attrs)
        if not href:
            continue
        target = html_lib.unescape(href.group(1))
        if target in seen or target.startswith("#"):
            continue
        seen.add(target)
        text = _WS_RE.sub(" ", html_lib.unescape(_TAG_RE.sub(" ", inner))).strip()
        links.append({"href": target, "text": text[:80]})
    return links[:300]


def page_slice(
    page: str, url: str, status: int, offset: int, length: int, links: bool
) -> dict:
    title = _TITLE_RE.search(page)
    cleaned = _clean(page)
    result = {
        "url": url,
        "status": status,
        "title": html_lib.unescape(title.group(1)).strip() if title else None,
        "clean_size": len(cleaned),
        "offset": offset,
        "html": cleaned[offset : offset + length],
    }
    if links:
        result["links"] = _links(page)
    return result
