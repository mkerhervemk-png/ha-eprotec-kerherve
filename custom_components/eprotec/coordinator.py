"""Coordinateur : 1 actualisation par 24 h, données conservées entre redémarrages."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import EProtecAuthError, EProtecClient, EProtecError
from .const import DOMAIN, MIN_INTERVAL_HOURS
from .parser import parse_missions

_LOGGER = logging.getLogger(__name__)


class EProtecCoordinator(DataUpdateCoordinator[dict]):
    """Pas d'intervalle automatique : déclenché à heure fixe ou par le bouton."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: EProtecClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=None,
            config_entry=entry,
        )
        self.client = client
        self.last_error: str | None = None
        self._store: Store[dict] = Store(hass, 1, f"{DOMAIN}_{entry.entry_id}")

    async def async_restore(self) -> None:
        """Recharge les dernières données sans se connecter au portail."""
        saved = await self._store.async_load()
        if saved:
            self.async_set_updated_data(saved)

    def is_stale(self) -> bool:
        """Vrai si la dernière synchronisation a plus de 24 h (ou n'existe pas)."""
        last = dt_util.parse_datetime((self.data or {}).get("last_sync") or "")
        if last is None:
            return True
        return dt_util.utcnow() - last >= timedelta(hours=MIN_INTERVAL_HOURS)

    async def _async_update_data(self) -> dict:
        try:
            page, _url = await self.client.login()
        except EProtecAuthError as err:
            self.last_error = str(err)
            raise ConfigEntryAuthFailed(str(err)) from err
        except EProtecError as err:
            self.last_error = str(err)
            raise UpdateFailed(str(err)) from err

        self.last_error = None
        data = {
            "last_sync": dt_util.utcnow().isoformat(),
            "missions": parse_missions(page),
        }
        await self._store.async_save(data)
        return data

    async def async_remove_store(self) -> None:
        await self._store.async_remove()
