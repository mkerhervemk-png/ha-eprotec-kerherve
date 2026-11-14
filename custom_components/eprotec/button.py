"""Bouton d'actualisation manuelle."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import EProtecEntity


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([ActualiserButton(entry.runtime_data)])


class ActualiserButton(EProtecEntity, ButtonEntity):
    _attr_name = "Actualiser"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "actualiser")

    async def async_press(self) -> None:
        await self.coordinator.async_refresh()
