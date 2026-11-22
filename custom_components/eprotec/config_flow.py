"""Ajout d'un compte e-Protec depuis l'interface Home Assistant."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import EProtecAuthError, EProtecClient, EProtecError, EProtecMfaRequired
from .const import CONF_HEURE, CONF_PRENOM, DEFAULT_HEURE, DOMAIN

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PRENOM): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_HEURE, default=DEFAULT_HEURE): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=23)
        ),
    }
)
REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


class EProtecConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _validate(self, username: str, password: str) -> str | None:
        # Session jetable (cookies propres à ce test), fermée juste après.
        session = async_create_clientsession(self.hass, auto_cleanup=False)
        client = EProtecClient(session, username, password)
        try:
            await client.login()
        except EProtecAuthError:
            return "invalid_auth"
        except EProtecMfaRequired:
            return "mfa_required"
        except EProtecError:
            return "cannot_connect"
        finally:
            await session.close()
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()
            error = await self._validate(username, user_input[CONF_PASSWORD])
            if error is None:
                return self.async_create_entry(
                    title=f"e-Protec {user_input[CONF_PRENOM].strip()}",
                    data={**user_input, CONF_USERNAME: username},
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            error = await self._validate(
                entry.data[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            if error is None:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=REAUTH_SCHEMA, errors=errors
        )
