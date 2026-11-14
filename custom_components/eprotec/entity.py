"""Base commune des entités e-Protec."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EProtecCoordinator


class EProtecEntity(CoordinatorEntity[EProtecCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: EProtecCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Protection Civile",
            model="e-Protec",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def available(self) -> bool:
        # Les dernières données connues restent affichées même si la
        # synchronisation du jour a échoué.
        return True
