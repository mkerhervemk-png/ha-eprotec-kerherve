"""Intégration e-Protec (Protection Civile) pour Home Assistant, lecture seule."""

from __future__ import annotations

from datetime import datetime
import zlib

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.event import async_track_time_change

from .api import EProtecClient
from .const import CONF_HEURE, DEFAULT_HEURE, DOMAIN
from .coordinator import EProtecCoordinator

PLATFORMS = [Platform.BUTTON, Platform.CALENDAR, Platform.SENSOR]

type EProtecConfigEntry = ConfigEntry[EProtecCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: EProtecConfigEntry) -> bool:
    # Session propre au compte (cookies séparés), fermée au déchargement pour
    # ne pas en accumuler à chaque rechargement de l'intégration.
    session = async_create_clientsession(hass)
    entry.async_on_unload(session.close)
    client = EProtecClient(
        session, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
    )
    coordinator = EProtecCoordinator(hass, entry, client)
    await coordinator.async_restore()
    entry.runtime_data = coordinator

    # Heure fixe + minute propre à chaque compte (les comptes ne se
    # connectent jamais à la même minute).
    minute = zlib.crc32(entry.data[CONF_USERNAME].lower().encode()) % 30

    @callback
    def _daily(_now: datetime) -> None:
        entry.async_create_background_task(
            hass, coordinator.async_refresh(), "eprotec_daily_refresh"
        )

    entry.async_on_unload(
        async_track_time_change(
            hass,
            _daily,
            hour=int(entry.data.get(CONF_HEURE, DEFAULT_HEURE)),
            minute=minute,
            second=0,
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Au démarrage : connexion seulement si les données ont plus de 24 h.
    # Volontairement pas de « first refresh » bloquant, pour qu'un échec ne
    # provoque pas de tentatives de connexion en boucle.
    if coordinator.is_stale():
        entry.async_create_background_task(
            hass, coordinator.async_refresh(), "eprotec_initial_refresh"
        )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EProtecConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: EProtecConfigEntry) -> None:
    # Efface les données conservées quand le compte est supprimé.
    from homeassistant.helpers.storage import Store

    await Store(hass, 1, f"{DOMAIN}_{entry.entry_id}").async_remove()
