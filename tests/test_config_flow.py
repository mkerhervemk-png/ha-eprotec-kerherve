"""Lot 5 : mot de passe masqué, clé CONF_PASSWORD inchangée."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.selector import TextSelector, TextSelectorType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.eprotec.config_flow import REAUTH_SCHEMA, USER_SCHEMA
from custom_components.eprotec.const import CONF_HEURE, CONF_PRENOM, DOMAIN

LOGIN = "custom_components.eprotec.config_flow.EProtecClient.login"


def _selecteur(schema, cle):
    for marqueur, valeur in schema.schema.items():
        if marqueur == cle:
            return valeur
    raise AssertionError(cle)


def test_mot_de_passe_masque_dans_les_deux_formulaires():
    for schema in (USER_SCHEMA, REAUTH_SCHEMA):
        sel = _selecteur(schema, CONF_PASSWORD)
        assert isinstance(sel, TextSelector)
        assert sel.config["type"] == TextSelectorType.PASSWORD


def test_autres_champs_inchanges():
    assert _selecteur(USER_SCHEMA, CONF_USERNAME) is str
    assert _selecteur(USER_SCHEMA, CONF_PRENOM) is str
    assert [str(k) for k in USER_SCHEMA.schema] == [CONF_PRENOM, CONF_USERNAME, CONF_PASSWORD, CONF_HEURE]


async def test_creation_de_compte_stocke_le_mot_de_passe(hass):
    with patch(LOGIN, AsyncMock()), patch(
        "custom_components.eprotec.async_setup_entry", AsyncMock(return_value=True)
    ):
        r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert r["type"] is FlowResultType.FORM
        r = await hass.config_entries.flow.async_configure(
            r["flow_id"],
            {CONF_PRENOM: "Ryan", CONF_USERNAME: " ryan@exemple.fr ", CONF_PASSWORD: "s3cret", CONF_HEURE: 7},
        )
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert r["data"][CONF_PASSWORD] == "s3cret"
    assert r["data"][CONF_USERNAME] == "ryan@exemple.fr"


async def test_reauthentification_met_a_jour_le_mot_de_passe(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ryan@exemple.fr",
        data={CONF_PRENOM: "Ryan", CONF_USERNAME: "ryan@exemple.fr", CONF_PASSWORD: "ancien", CONF_HEURE: 7},
    )
    entry.add_to_hass(hass)
    with patch(LOGIN, AsyncMock()), patch(
        "custom_components.eprotec.async_setup_entry", AsyncMock(return_value=True)
    ):
        r = await entry.start_reauth_flow(hass)
        assert r["step_id"] == "reauth_confirm"
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {CONF_PASSWORD: "nouveau"})
    assert r["type"] is FlowResultType.ABORT
    assert r["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "nouveau"
