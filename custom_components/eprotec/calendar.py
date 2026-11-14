"""Calendrier des missions e-Protec, un par bénévole."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .entity import EProtecEntity
from .parser import mission_bounds


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(
        [MissionsCalendar(entry.runtime_data), AntenneCalendar(entry.runtime_data)]
    )


class _BaseCalendar(EProtecEntity, CalendarEntity):
    _source = "missions"

    def _summary(self, mission: dict) -> str:
        return mission.get("titre") or "Mission"

    def _description(self, mission: dict) -> str | None:
        return mission.get("description")

    def _events(self) -> list[tuple[datetime, datetime, CalendarEvent]]:
        events = []
        zone = dt_util.DEFAULT_TIME_ZONE
        for mission in (self.coordinator.data or {}).get(self._source) or []:
            bounds = mission_bounds(mission, zone)
            if bounds is None:
                continue
            debut, fin = bounds
            if mission.get("journee_entiere"):
                start, end = debut.date(), fin.date()
            else:
                start, end = debut, fin
            events.append(
                (
                    debut,
                    fin,
                    CalendarEvent(
                        start=start,
                        end=end,
                        summary=self._summary(mission),
                        location=mission.get("lieu"),
                        description=self._description(mission),
                        uid=mission.get("uid") or mission.get("id"),
                    ),
                )
            )
        return sorted(events, key=lambda item: item[0])

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.utcnow()
        for _debut, fin, event in self._events():
            if fin > now:
                return event
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        return [
            event
            for debut, fin, event in self._events()
            if fin > start_date and debut < end_date
        ]


class MissionsCalendar(_BaseCalendar):
    """Agenda personnel du bénévole."""

    _attr_name = "Missions"
    _attr_icon = "mdi:ambulance"
    _source = "missions"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "calendrier")


class AntenneCalendar(_BaseCalendar):
    """Toutes les activités de l'antenne, avec les places."""

    _attr_name = "Activités antenne"
    _attr_icon = "mdi:calendar-account"
    _source = "planning"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "calendrier_antenne")

    def _summary(self, mission: dict) -> str:
        titre = mission.get("titre") or "Activité"
        if mission.get("places") is not None and mission.get("inscrits") is not None:
            return f"{titre} ({mission['inscrits']}/{mission['places']})"
        return titre

    def _description(self, mission: dict) -> str | None:
        parts = [mission.get("type")]
        if mission.get("places") is not None and mission.get("inscrits") is not None:
            parts.append(f"{mission['places'] - mission['inscrits']} place(s) libre(s)")
        return " - ".join(part for part in parts if part) or None
