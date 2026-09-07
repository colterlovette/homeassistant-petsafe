from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from . import NumberEntities, PetSafeCoordinator
from .const import (
    DEFAULT_MEAL_CUPS,
    DEFAULT_SNACK_CUPS,
    DOMAIN,
    PORTION_MEAL,
    PORTION_SNACK,
)


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry, add_entities):
    coordinator: PetSafeCoordinator = hass.data[DOMAIN][config.entry_id]

    try:
        feeders = await coordinator.get_feeders()
    except Exception as ex:
        raise ConfigEntryNotReady("Failed to retrieve PetSafe devices") from ex

    entities = []
    for feeder in feeders:
        entities.append(
            NumberEntities.PetSafeFeederPortionNumber(
                hass=hass,
                name="Meal portion",
                device_type="meal_portion",
                portion_kind=PORTION_MEAL,
                default_cups=DEFAULT_MEAL_CUPS,
                device=feeder,
                coordinator=coordinator,
            )
        )
        entities.append(
            NumberEntities.PetSafeFeederPortionNumber(
                hass=hass,
                name="Snack portion",
                device_type="snack_portion",
                portion_kind=PORTION_SNACK,
                default_cups=DEFAULT_SNACK_CUPS,
                device=feeder,
                coordinator=coordinator,
            )
        )
    add_entities(entities)
