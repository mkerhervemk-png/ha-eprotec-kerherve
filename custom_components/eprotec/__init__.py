"""Intégration e-Protec (Protection Civile) pour Home Assistant, lecture seule."""

from __future__ import annotations

from datetime import datetime
import zlib

import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.event import async_track_time_change

from .api import EProtecClient
from .const import CONF_HEURE, DEFAULT_HEURE, DOMAIN, PORTAL_HOST
from .coordinator import EProtecCoordinator
from .debug import page_slice, safe_url

SERVICE_DEBUG_FETCH = "debug_fetch"
DEBUG_SCHEMA = vol.Schema(
    {
        vol.Required("entry_id"): str,
        vol.Required("path"): str,
        vol.Optional("offset", default=0): vol.All(int, vol.Range(min=0)),
        vol.Optional("length", default=8000): vol.All(int, vol.Range(min=1, max=20000)),
        vol.Optional("links", default=False): bool,
    }
)


def _register_debug_service(hass: HomeAssistant) -> None:
    """Service de diagnostic temporaire (retiré en v0.2)."""
    if hass.services.has_service(DOMAIN, SERVICE_DEBUG_FETCH):
        return

    async def _handle(call: ServiceCall) -> ServiceResponse:
        entry = hass.config_entries.async_get_entry(call.data["entry_id"])
        if (
            entry is None
            or entry.domain != DOMAIN
            or entry.state is not ConfigEntryState.LOADED
        ):
            raise ServiceValidationError("Compte e-Protec introuvable")
        try:
            url = safe_url(call.data["path"])
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err
        status, body, final_url = await entry.runtime_data.client.fetch(url)
        if URL(final_url).host == PORTAL_HOST:
            # Jamais de reconnexion cachée : seul le bouton Actualiser se connecte.
            return {"error": "session_expiree"}
        return page_slice(
            body,
            final_url,
            status,
            call.data["offset"],
            call.data["length"],
            call.data["links"],
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_DEBUG_FETCH,
        _handle,
        schema=DEBUG_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

PLATFORMS = [Platform.BUTTON, Platform.SENSOR]

type EProtecConfigEntry = ConfigEntry[EProtecCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: EProtecConfigEntry) -> bool:
    session = async_create_clientsession(hass)
    client = EProtecClient(
        session, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
    )
    coordinator = EProtecCoordinator(hass, entry, client)
    await coordinator.async_restore()
    entry.runtime_data = coordinator
    _register_debug_service(hass)

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
