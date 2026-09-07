"""Number entities for the PetSafe integration."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

import petsafe

from . import PetSafeCoordinator
from .const import (
    CUP_STEP,
    DOMAIN,
    FEEDER_MODEL_GEN1,
    MANUFACTURER,
    MAX_FEED_EIGHTHS,
)

_LOGGER = logging.getLogger(__name__)


class PetSafeFeederPortionNumber(CoordinatorEntity, RestoreNumber):
    """How much the matching Meal or Snack button dispenses, in cups.

    Sits in the device's Configuration section rather than Controls: it is a
    setting you adjust once per pet, not something to press. The value lives on
    the coordinator so the buttons can read it without depending on this
    entity's id, and is restored across restarts so a portion set once stays
    set.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_unit_of_measurement = "cup"
    _attr_native_min_value = CUP_STEP
    _attr_native_max_value = MAX_FEED_EIGHTHS * CUP_STEP
    _attr_native_step = CUP_STEP
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:cup"

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        coordinator: PetSafeCoordinator,
        device_type: str,
        device: petsafe.devices.DeviceSmartFeed,
        portion_kind: str,
        default_cups: float,
    ):
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_has_entity_name = True
        self._coordinator = coordinator
        self._api_name = device.api_name
        self._attr_unique_id = device.api_name + "_" + device_type
        self._device_type = device_type
        self._portion_kind = portion_kind
        self._default_cups = default_cups
        self._attr_native_value = default_cups

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.api_name)},
            manufacturer=MANUFACTURER,
            name=device.friendly_name,
            sw_version=device.firmware,
            model=device.product_name or FEEDER_MODEL_GEN1,
        )

    async def async_added_to_hass(self) -> None:
        """Restore the previously set portion, then publish it to the coordinator."""
        await super().async_added_to_hass()

        restored = await self.async_get_last_number_data()
        if restored is not None and restored.native_value is not None:
            self._attr_native_value = restored.native_value

        self._coordinator.set_portion(
            self._api_name, self._portion_kind, self._attr_native_value
        )

    async def async_set_native_value(self, value: float) -> None:
        """Store a new portion size."""
        self._attr_native_value = value
        self._coordinator.set_portion(self._api_name, self._portion_kind, value)
        self.async_write_ha_state()
