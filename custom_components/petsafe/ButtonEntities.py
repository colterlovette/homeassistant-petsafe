from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

import petsafe

from . import PetSafeCoordinator
from .const import (
    DEFAULT_MEAL_CUPS,
    DEFAULT_SNACK_CUPS,
    DOMAIN,
    FEEDER_MODEL_GEN1,
    MANUFACTURER,
    PORTION_MEAL,
    PORTION_SNACK,
)
from .helpers import cups_to_eighths


class PetSafeButtonEntity(CoordinatorEntity, ButtonEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        api_name: str,
        name: str,
        coordinator: PetSafeCoordinator,
        device_type: str,
        icon: str = None,
        device_class: str = None,
    ):
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_has_entity_name = True
        self._coordinator = coordinator
        self._api_name = api_name
        self._attr_unique_id = api_name + "_" + device_type
        self._attr_icon = icon
        self._device_type = device_type


class PetSafeLitterboxButtonEntity(PetSafeButtonEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        coordinator: PetSafeCoordinator,
        device_type: str,
        device: petsafe.devices.DeviceScoopfree,
        icon: str = None,
        device_class: str = None,
    ):
        self._litterbox = device

        super().__init__(
            hass,
            device.api_name,
            name,
            coordinator,
            device_type,
            icon,
            device_class,
        )
        self._device = device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.api_name)},
            manufacturer=MANUFACTURER,
            name=device.friendly_name,
            model=device.product_name,
            sw_version=device.firmware,
        )

    async def async_press(self) -> None:
        if self._device_type == "reset":
            await self._device.reset(0, False)
        elif self._device_type == "clean":
            await self._device.rake(False)
        self.coordinator.invalidate_details(self._api_name)
        await self.coordinator.async_request_refresh()


class PetSafeFeederButtonEntity(PetSafeButtonEntity):
    def __init__(
        self,
        hass,
        name,
        coordinator: PetSafeCoordinator,
        device_type,
        device: petsafe.devices.DeviceSmartFeed,
        icon=None,
        device_class=None,
    ):
        self._feeder = device

        super().__init__(
            hass,
            device.api_name,
            name,
            coordinator,
            device_type,
            icon,
            device_class,
        )

        self._device = device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.api_name)},
            manufacturer=MANUFACTURER,
            name=device.friendly_name,
            sw_version=device.firmware,
            model=device.product_name or FEEDER_MODEL_GEN1,
        )

    async def async_press(self) -> None:
        if self._device_type in (PORTION_MEAL, PORTION_SNACK):
            default = (
                DEFAULT_MEAL_CUPS
                if self._device_type == PORTION_MEAL
                else DEFAULT_SNACK_CUPS
            )
            cups = self.coordinator.get_portion(
                self._api_name, self._device_type, default
            )
            await self._device.feed(cups_to_eighths(cups), None, False)

        # Drop the cached message history so last_feeding reflects this feed on
        # the next cycle rather than up to DETAILS_UPDATE_INTERVAL later.
        self.coordinator.invalidate_details(self._api_name)
        await self.coordinator.async_request_refresh()
