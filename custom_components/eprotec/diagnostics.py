"""Diagnostic de l'intégration : infos techniques, sans identifiant ni mission."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry) -> dict[str, Any]:
    coordinator = entry.runtime_data
    return {
        "last_sync": (coordinator.data or {}).get("last_sync"),
        "last_error": coordinator.last_error,
        "agenda": coordinator.agenda_info,
    }
