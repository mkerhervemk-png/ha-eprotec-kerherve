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
    async_add_entities([MissionsCalendar(entry.runtime_data)])


class MissionsCalendar(EProtecEntity, CalendarEntity):
    _attr_name = "Missions"
    _attr_icon = "mdi:ambulance"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "calendrier")

    def _events(self) -> list[tuple[datetime, datetime, CalendarEvent]]:
        events = []
        zone = dt_util.DEFAULT_TIME_ZONE
        for mission in (self.coordinator.data or {}).get("missions") or []:
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
                        summary=mission.get("titre") or "Mission",
                        location=mission.get("lieu"),
                        description=mission.get("description"),
                        uid=mission.get("uid"),
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
