"""Capteurs e-Protec."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .entity import EProtecEntity


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            ConnexionSensor(coordinator),
            DerniereSynchroSensor(coordinator),
            MissionsAVenirSensor(coordinator),
            ProchaineMissionSensor(coordinator),
        ]
    )


def _missions(data: dict | None) -> list[dict] | None:
    """Missions à venir triées, ou None si la lecture n'est pas disponible."""
    missions = (data or {}).get("missions")
    if missions is None:
        return None
    now = dt_util.utcnow()
    upcoming = []
    for mission in missions:
        fin = dt_util.parse_datetime(mission.get("fin") or mission.get("debut") or "")
        if fin is not None and dt_util.as_utc(fin) >= now:
            upcoming.append(mission)
    return sorted(upcoming, key=lambda m: m.get("debut") or "")


class ConnexionSensor(EProtecEntity, SensorEntity):
    _attr_name = "Connexion"
    _attr_icon = "mdi:shield-check"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["ok", "erreur", "en_attente"]
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "connexion")

    @property
    def native_value(self) -> str:
        if self.coordinator.last_error:
            return "erreur"
        if not self.coordinator.data:
            return "en_attente"
        return "ok"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"detail": self.coordinator.last_error}


class DerniereSynchroSensor(EProtecEntity, SensorEntity):
    _attr_name = "Dernière synchronisation"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "derniere_synchro")

    @property
    def native_value(self) -> datetime | None:
        return dt_util.parse_datetime(
            (self.coordinator.data or {}).get("last_sync") or ""
        )


class MissionsAVenirSensor(EProtecEntity, SensorEntity):
    _attr_name = "Missions à venir"
    _attr_icon = "mdi:calendar-multiple"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "missions_a_venir")

    @property
    def native_value(self) -> int | None:
        missions = _missions(self.coordinator.data)
        return None if missions is None else len(missions)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"missions": _missions(self.coordinator.data) or []}


class ProchaineMissionSensor(EProtecEntity, SensorEntity):
    _attr_name = "Prochaine mission"
    _attr_icon = "mdi:ambulance"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "prochaine_mission")

    def _next(self) -> dict | None:
        missions = _missions(self.coordinator.data)
        return missions[0] if missions else None

    @property
    def native_value(self) -> datetime | None:
        mission = self._next()
        return dt_util.parse_datetime(mission.get("debut") or "") if mission else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        mission = self._next() or {}
        return {
            "titre": mission.get("titre"),
            "lieu": mission.get("lieu"),
            "role": mission.get("role"),
            "fin": mission.get("fin"),
        }
