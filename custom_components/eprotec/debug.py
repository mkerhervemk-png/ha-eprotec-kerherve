"""Mode diagnostic temporaire (v0.1.1).

Relève la structure des pages e-Protec (menu, Calendrier, Événements) pour
écrire la lecture des missions. GET uniquement, même session que
l'actualisation, données gardées en mémoire (jamais écrites sur disque).
À retirer en v0.2.
"""

from __future__ import annotations

import html as html_lib
import logging
import re

from yarl import URL

_LOGGER = logging.getLogger(__name__)

_SCRIPT_RE = re.compile(r"<(script|style|svg)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_HEAD_RE = re.compile(r"<head\b.*?</head>", re.IGNORECASE | re.DOTALL)
_A_RE = re.compile(r"<a\b([^>]*)>(.*?)</a>", re.IGNORECASE | re.DOTALL)
_HREF_RE = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_PHP_RE = re.compile(r"""[\w./-]+\.php(?:\?[^"'\s<>\\)]*)?""")

KEYWORDS = ("calend", "evenement", "événement", "event", "particip", "planning")
# Lecture seule : on ne suit jamais un lien qui pourrait agir ou télécharger.
FORBIDDEN = (
    "logout", "deconn", "déconn", "delete", "suppr", "inscri", "save",
    "del_", "action=", "export", "pdf", "xls", "ical", "javascript:", "mailto:",
)
MAX_PAGES = 6
CHUNK = 6000
MAX_CHUNKS = 40


def _clean(page: str) -> str:
    page = _HEAD_RE.sub("", page)
    page = _SCRIPT_RE.sub("", page)
    page = _COMMENT_RE.sub("", page)
    return _WS_RE.sub(" ", page).strip()


def summarize(page: str, url: str, status: int = 200) -> dict:
    title = _TITLE_RE.search(page)
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
    cleaned = _clean(page)
    chunks = [cleaned[i : i + CHUNK] for i in range(0, len(cleaned), CHUNK)]
    return {
        "url": url,
        "status": status,
        "title": html_lib.unescape(title.group(1)).strip() if title else None,
        "raw_size": len(page),
        "clean_size": len(cleaned),
        "links": links[:300],
        "php_refs": sorted({html_lib.unescape(m) for m in _PHP_RE.findall(page)})[:300],
        "chunk_count": len(chunks),
        "html_chunks": chunks[:MAX_CHUNKS],
    }


def _candidates(summary: dict) -> list[str]:
    base = URL(summary["url"])
    found: list[str] = []
    refs = [(link["href"], link["text"]) for link in summary["links"]]
    refs += [(ref, "") for ref in summary["php_refs"]]
    for href, text in refs:
        probe = f"{href} {text}".lower()
        if not any(word in probe for word in KEYWORDS):
            continue
        if any(word in probe for word in FORBIDDEN):
            continue
        try:
            target = base.join(URL(href))
        except (ValueError, TypeError):
            continue
        if target.host != base.host or target.scheme != "https":
            continue
        target_str = str(target.with_fragment(None))
        if target_str not in found:
            found.append(target_str)
    return found[:MAX_PAGES]


async def collect_debug(client, page: str, url: str) -> dict:
    """Ne lève jamais : le diagnostic ne doit pas casser l'actualisation."""
    result: dict = {"landing": None, "pages": [], "errors": []}
    try:
        landing = summarize(page, url)
        result["landing"] = landing
        for target in _candidates(landing):
            try:
                status, body, final_url = await client.fetch(target)
                result["pages"].append(summarize(body, final_url, status))
            except Exception as err:  # noqa: BLE001
                result["errors"].append(f"{target}: {err!r}")
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Diagnostic e-Protec impossible", exc_info=True)
        result["errors"].append(repr(err))
    return result
