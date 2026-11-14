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
from .parser import mission_bounds


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
            PostesAPourvoirSensor(coordinator),
            *(AccueilSensor(coordinator, *spec) for spec in ACCUEIL_SENSORS),
        ]
    )


def _missions(data: dict | None) -> list[dict] | None:
    """Missions à venir ou en cours, triées ; None si jamais synchronisé."""
    missions = (data or {}).get("missions")
    if missions is None:
        return None
    now = dt_util.utcnow()
    upcoming = []
    for mission in missions:
        bounds = mission_bounds(mission, dt_util.DEFAULT_TIME_ZONE)
        if bounds is not None and bounds[1] >= now:
            upcoming.append((bounds[0], mission))
    return [mission for _debut, mission in sorted(upcoming, key=lambda item: item[0])]


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
        bounds = mission_bounds(mission, dt_util.DEFAULT_TIME_ZONE) if mission else None
        return bounds[0] if bounds else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        mission = self._next() or {}
        return {
            "titre": mission.get("titre"),
            "lieu": mission.get("lieu"),
            "description": mission.get("description"),
            "fin": mission.get("fin"),
        }


class PostesAPourvoirSensor(EProtecEntity, SensorEntity):
    """Activités à venir de l'antenne où il reste des places."""

    _attr_name = "Postes à pourvoir"
    _attr_icon = "mdi:account-plus"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "postes_a_pourvoir")

    def _open(self) -> list[dict] | None:
        planning = (self.coordinator.data or {}).get("planning")
        if planning is None:
            return None
        now = dt_util.utcnow()
        result = []
        for activite in planning:
            bounds = mission_bounds(activite, dt_util.DEFAULT_TIME_ZONE)
            if bounds is None or bounds[1] < now:
                continue
            inscrits, places = activite.get("inscrits"), activite.get("places")
            if inscrits is None or places is None or inscrits >= places:
                continue
            result.append(
                {
                    "id": activite.get("id"),
                    "titre": activite.get("titre"),
                    "type": activite.get("type"),
                    "lieu": activite.get("lieu"),
                    "debut": activite.get("debut"),
                    "fin": activite.get("fin"),
                    "inscrits": inscrits,
                    "places": places,
                    "places_restantes": places - inscrits,
                }
            )
        return result

    @property
    def native_value(self) -> int | None:
        postes = self._open()
        return None if postes is None else len(postes)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        postes = self._open() or []
        return {
            "postes": postes[:25],
            "places_restantes_total": sum(p["places_restantes"] for p in postes),
        }


# --- Blocs de la page d'accueil ---------------------------------------------


def _stat(accueil: dict, groupe: str, cle: str) -> int | None:
    for name, values in (accueil.get("statistiques") or {}).items():
        if name.lower().startswith(groupe):
            for label, value in values.items():
                if label.lower().startswith(cle):
                    return value
    return None


def _len(value) -> int | None:
    return None if value is None else len(value)


def _dernier(items) -> str | None:
    if items is None:
        return None
    return items[0]["titre"][:250] if items else "Aucune"


def _heures(lines) -> float | None:
    if lines is None:
        return None
    values = [line["heures"] for line in lines if line.get("heures") is not None]
    return max(values) if values else 0


# (clé, nom, icône, unité, valeur(accueil), attributs(accueil))
ACCUEIL_SENSORS = [
    (
        "anniversaires",
        "Anniversaires du jour",
        "mdi:cake-variant",
        None,
        lambda a: _len(a.get("anniversaires")),
        lambda a: {"noms": a.get("anniversaires") or []},
    ),
    (
        "mes_participations",
        "Mes participations",
        "mdi:counter",
        None,
        lambda a: _stat(a, "mes participations", "total"),
        lambda a: {"a_venir": _stat(a, "mes participations", "à venir")},
    ),
    (
        "activite_antenne",
        "Activité de l'antenne",
        "mdi:chart-bar",
        None,
        lambda a: _stat(a, "activit", "mois"),
        lambda a: {
            "trimestre": _stat(a, "activit", "trimestre"),
            "nouveaux_mois": _stat(a, "nouveaux", "mois"),
            "nouveaux_trimestre": _stat(a, "nouveaux", "trimestre"),
            "disponibilites_ce_mois": _stat(a, "disponibilit", "ce mois"),
            "disponibilites_prochain": _stat(a, "disponibilit", "prochain"),
        },
    ),
    (
        "heures_formation",
        "Heures de formation",
        "mdi:school",
        "h",
        lambda a: _heures(a.get("formation")),
        lambda a: {"detail": a.get("formation") or []},
    ),
    (
        "consigne",
        "Consigne opérationnelle",
        "mdi:alert-decagram",
        None,
        lambda a: _dernier(a.get("consignes")),
        lambda a: {
            "nombre": _len(a.get("consignes")),
            "date": (a.get("consignes") or [{}])[0].get("date"),
            "texte": (a.get("consignes") or [{}])[0].get("texte"),
        },
    ),
    (
        "actualite",
        "Actualité",
        "mdi:newspaper-variant",
        None,
        lambda a: _dernier(a.get("actualites")),
        lambda a: {
            "nombre": _len(a.get("actualites")),
            "date": (a.get("actualites") or [{}])[0].get("date"),
            "texte": (a.get("actualites") or [{}])[0].get("texte"),
        },
    ),
    (
        "veille",
        "Veille opérationnelle",
        "mdi:phone-in-talk",
        None,
        lambda a: _len(a.get("veille")),
        lambda a: {"personnes": a.get("veille") or []},
    ),
    (
        "remplacements",
        "Remplacements",
        "mdi:account-switch",
        None,
        lambda a: a.get("remplacements"),
        lambda a: {},
    ),
    (
        "mes_activites",
        "Mes activités",
        "mdi:clipboard-list",
        None,
        lambda a: a.get("mes_activites"),
        lambda a: {},
    ),
    (
        "main_courante",
        "Main courante",
        "mdi:notebook",
        None,
        lambda a: a.get("main_courante"),
        lambda a: {},
    ),
]


class AccueilSensor(EProtecEntity, SensorEntity):
    """Un bloc de la page d'accueil e-Protec."""

    def __init__(self, coordinator, key, name, icon, unit, value_fn, attrs_fn) -> None:
        super().__init__(coordinator, key)
        self._attr_name = name
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit
        self._value_fn = value_fn
        self._attrs_fn = attrs_fn

    def _accueil(self) -> dict | None:
        return (self.coordinator.data or {}).get("accueil")

    @property
    def native_value(self):
        accueil = self._accueil()
        if accueil is None:
            return None
        try:
            return self._value_fn(accueil)
        except (KeyError, IndexError, TypeError, AttributeError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        accueil = self._accueil()
        if accueil is None:
            return {}
        try:
            return self._attrs_fn(accueil)
        except (KeyError, IndexError, TypeError, AttributeError):
            return {}
