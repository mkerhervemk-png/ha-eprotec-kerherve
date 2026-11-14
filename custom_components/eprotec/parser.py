"""Lecture de l'agenda personnel e-Protec (flux iCal « Synchronisation »)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone, tzinfo
import html as html_lib
import json
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_CID_RE = re.compile(r"evenements\.php\?cid=([0-9a-fA-F]{8,64})")
_UNESCAPE_RE = re.compile(r"\\([\;,nN])")
_PID_RE = re.compile(r"pompier=(\d+)")
_ICAL_RE = re.compile(r"evenement_ical\.php\?pid=(\d+)&(?:amp;)?section=(\d+)")
KEEP_PAST_DAYS = 60


def find_person_id(page: str) -> str | None:
    """Numéro de fiche du bénévole connecté (le plus fréquent dans l'accueil)."""
    ids = _PID_RE.findall(page)
    return max(set(ids), key=ids.count) if ids else None


def find_section_id(page: str) -> str | None:
    """Numéro de l'antenne du bénévole (lu dans le lien d'export)."""
    match = _ICAL_RE.search(page)
    return match.group(2) if match else None


def find_ical_export(page: str) -> str | None:
    """Lien d'export iCal de l'onglet « Liste » des participations."""
    match = _ICAL_RE.search(page)
    if not match:
        return None
    return f"evenement_ical.php?pid={match.group(1)}&section={match.group(2)}"


def find_agenda_cid(page: str) -> str | None:
    """Identifiant du flux d'agenda personnel dans la page Synchronisation."""
    match = _CID_RE.search(page)
    return match.group(1) if match else None


def _unfold(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        elif raw:
            lines.append(raw)
    return lines


def _text(value: str) -> str:
    def repl(match: re.Match) -> str:
        char = match.group(1)
        return "\n" if char in "nN" else char

    return _UNESCAPE_RE.sub(repl, value).strip()


def _split(line: str) -> tuple[str, dict[str, str], str]:
    head, _, value = line.partition(":")
    name, *params = head.split(";")
    parsed = {}
    for param in params:
        key, _, val = param.partition("=")
        parsed[key.upper()] = val.strip('"')
    return name.upper(), parsed, value


def _when(params: dict[str, str], value: str, default_tz: tzinfo):
    """Retourne (date | datetime aware, journee_entiere) ou None."""
    value = value.strip()
    try:
        if params.get("VALUE", "").upper() == "DATE" or len(value) == 8:
            return datetime.strptime(value[:8], "%Y%m%d").date(), True
        utc = value.endswith("Z")
        parsed = datetime.strptime(value.rstrip("Z")[:15], "%Y%m%dT%H%M%S")
    except ValueError:
        return None
    if utc:
        return parsed.replace(tzinfo=timezone.utc), False
    zone: tzinfo = default_tz
    if tzid := params.get("TZID"):
        try:
            zone = ZoneInfo(tzid)
        except (ZoneInfoNotFoundError, ValueError):
            zone = default_tz
    return parsed.replace(tzinfo=zone), False


def parse_ical(text: str, default_tz: tzinfo, now: datetime) -> tuple[list[dict], dict]:
    """Retourne (missions, infos techniques sans donnée personnelle)."""
    missions: list[dict] = []
    properties: set[str] = set()
    current: dict | None = None
    total = 0
    limit = now - timedelta(days=KEEP_PAST_DAYS)

    for line in _unfold(text):
        name, params, value = _split(line)
        if name == "BEGIN" and value.upper() == "VEVENT":
            current = {}
            continue
        if current is None:
            continue
        if name == "END" and value.upper() == "VEVENT":
            total += 1
            start = current.get("DTSTART")
            if start:
                debut, all_day = start
                fin = (current.get("DTEND") or (None, all_day))[0]
                if all_day:
                    if not isinstance(fin, date) or isinstance(fin, datetime) or fin <= debut:
                        fin = debut + timedelta(days=1)
                    fin_dt = datetime.combine(fin, datetime.min.time(), default_tz)
                else:
                    if not isinstance(fin, datetime) or fin <= debut:
                        fin = debut + timedelta(hours=1)
                    fin_dt = fin
                if fin_dt >= limit:
                    missions.append(
                        {
                            "uid": current.get("UID"),
                            "debut": debut.isoformat(),
                            "fin": fin.isoformat(),
                            "journee_entiere": all_day,
                            "titre": current.get("SUMMARY") or "Mission",
                            "lieu": current.get("LOCATION") or None,
                            "description": current.get("DESCRIPTION") or None,
                            "role": None,
                        }
                    )
            current = None
            continue
        properties.add(name)
        if name in ("DTSTART", "DTEND"):
            current[name] = _when(params, value, default_tz)
        elif name in ("SUMMARY", "LOCATION", "DESCRIPTION", "UID"):
            current[name] = _text(value)

    missions.sort(key=lambda m: m["debut"])
    info = {
        "est_un_calendrier": "BEGIN:VCALENDAR" in text[:200].upper(),
        "taille": len(text),
        "evenements_total": total,
        "evenements_gardes": len(missions),
        "proprietes": sorted(properties),
    }
    return missions, info


def mission_bounds(mission: dict, default_tz: tzinfo) -> tuple[datetime, datetime] | None:
    """Début et fin sous forme de datetimes avec fuseau."""
    try:
        if mission.get("journee_entiere"):
            debut = datetime.combine(
                date.fromisoformat(mission["debut"]), datetime.min.time(), default_tz
            )
            fin = datetime.combine(
                date.fromisoformat(mission["fin"]), datetime.min.time(), default_tz
            )
        else:
            debut = datetime.fromisoformat(mission["debut"])
            fin = datetime.fromisoformat(mission["fin"])
    except (KeyError, TypeError, ValueError):
        return None
    return debut, fin


# --- Planning de l'antenne (activités et places restantes) -----------------

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_ISO_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_HOURS_RE = re.compile(r"(\d{1,2})[:h](\d{2})\s*-\s*(\d{1,2})[:h](\d{2})")
_COUNT_RE = re.compile(r"(\d+)\s*/\s*(\d+)")
_TITLE_ATTR_RE = re.compile(r"""title\s*=\s*(["'])(.*?)\1""", re.DOTALL)
_BOLD_RE = re.compile(r"<b\b[^>]*>(.*?)</b>", re.IGNORECASE | re.DOTALL)
_BADGE_RE = re.compile(
    r"<(font|span)\b[^>]*badge[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL
)
_ID_RE = re.compile(r"\d{3,}")


def _plain(value) -> str:
    text = _TAG_RE.sub(" ", str(value or ""))
    return _WS_RE.sub(" ", html_lib.unescape(text)).strip()


def parse_planning(text: str, default_tz: tzinfo) -> tuple[list[dict] | None, dict]:
    """Retourne (activités de l'antenne | None si illisible, infos techniques)."""
    info: dict = {"json": False, "lignes": 0, "cles": [], "lues": 0}
    try:
        payload = json.loads(text)
    except ValueError:
        return None, info
    rows = payload.get("rows") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return None, info
    info["json"] = True
    info["lignes"] = len(rows)
    if rows and isinstance(rows[0], dict):
        info["cles"] = sorted(rows[0])

    activites: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        dates = _ISO_RE.findall(str(row.get("date") or ""))
        if not dates:
            continue
        try:
            first = date.fromisoformat(dates[0])
            last = date.fromisoformat(dates[-1])
        except ValueError:
            continue
        hours = _HOURS_RE.search(_plain(row.get("horaire")))
        if hours:
            h1, m1, h2, m2 = (int(part) for part in hours.groups())
            try:
                debut = datetime.combine(first, time(h1, m1), default_tz)
                fin = datetime.combine(last, time(h2, m2), default_tz)
            except ValueError:
                continue
            if fin <= debut:
                fin += timedelta(days=1)
            debut_s, fin_s, all_day = debut.isoformat(), fin.isoformat(), False
        else:
            debut_s = first.isoformat()
            fin_s = (max(first, last) + timedelta(days=1)).isoformat()
            all_day = True

        activite = str(row.get("activite") or "")
        bold = _BOLD_RE.search(activite)
        titre = _plain(_BADGE_RE.sub(" ", bold.group(1) if bold else activite))
        type_match = _TITLE_ATTR_RE.search(str(row.get("logo") or ""))
        count = _COUNT_RE.search(_plain(row.get("inscrits")))
        ident = _ID_RE.search(_plain(row.get("code")))
        activites.append(
            {
                "id": ident.group(0) if ident else None,
                "debut": debut_s,
                "fin": fin_s,
                "journee_entiere": all_day,
                "titre": titre or "Activité",
                "type": html_lib.unescape(type_match.group(2)).strip()
                if type_match
                else None,
                "lieu": _plain(row.get("lieu")) or None,
                "inscrits": int(count.group(1)) if count else None,
                "places": int(count.group(2)) if count else None,
                "renfort": "renfort" in _plain(activite).lower(),
                "inscription_ouverte": "openModalInscription"
                in str(row.get("icone") or ""),
            }
        )
    activites.sort(key=lambda a: a["debut"])
    info["lues"] = len(activites)
    return activites, info
