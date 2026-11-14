"""Lecture de l'agenda personnel e-Protec (flux iCal « Synchronisation »)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone, tzinfo
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_CID_RE = re.compile(r"evenements\.php\?cid=([0-9a-fA-F]{8,64})")
_UNESCAPE_RE = re.compile(r"\\([\;,nN])")
KEEP_PAST_DAYS = 60


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
