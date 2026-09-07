"""The PetSafe Integration integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from time import monotonic

import httpx
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    CONF_ACCESS_TOKEN,
    CONF_EMAIL,
    CONF_TOKEN,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

import petsafe

from .const import (
    ATTR_AMOUNT,
    ATTR_SLOW_FEED,
    ATTR_TIME,
    CONF_REFRESH_TOKEN,
    DETAILS_UPDATE_INTERVAL,
    DOMAIN,
    MESSAGE_LOOKBACK_DAYS,
    SERVICE_ADD_SCHEDULE,
    SERVICE_DELETE_ALL_SCHEDULES,
    SERVICE_DELETE_SCHEDULE,
    SERVICE_FEED,
    SERVICE_MODIFY_SCHEDULE,
    SERVICE_PRIME,
)
from .helpers import get_feeders_for_service

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.NUMBER,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PetSafe Integration from a config entry."""
    client = petsafe.PetSafeClient(
        entry.data.get(CONF_EMAIL),
        entry.data.get(CONF_TOKEN),
        entry.data.get(CONF_REFRESH_TOKEN),
        entry.data.get(CONF_ACCESS_TOKEN),
        client = get_async_client(hass)
    )

    hass.data.setdefault(DOMAIN, {})

    coordinator = PetSafeCoordinator(hass, client, entry)

    hass.data[DOMAIN][entry.entry_id] = coordinator

    async def handle_add_schedule(call: ServiceCall) -> None:
        device_ids = call.data.get(ATTR_DEVICE_ID)
        area_ids = call.data.get(ATTR_AREA_ID)
        entity_ids = call.data.get(ATTR_ENTITY_ID)
        time = call.data.get(ATTR_TIME)
        amount = call.data.get(ATTR_AMOUNT)
        matched_devices = get_feeders_for_service(
            hass, area_ids, device_ids, entity_ids
        )
        for device_id in matched_devices:
            device = next(
                d for d in await coordinator.get_feeders() if d.api_name == device_id
            )
            if device is not None:
                await device.schedule_feed(time, amount, False)
                coordinator.invalidate_details(device_id)

    hass.services.async_register(DOMAIN, SERVICE_ADD_SCHEDULE, handle_add_schedule)

    async def handle_delete_schedule(call: ServiceCall) -> None:
        device_ids = call.data.get(ATTR_DEVICE_ID)
        area_ids = call.data.get(ATTR_AREA_ID)
        entity_ids = call.data.get(ATTR_ENTITY_ID)
        time = call.data.get(ATTR_TIME)
        matched_devices = get_feeders_for_service(
            hass, area_ids, device_ids, entity_ids
        )

        for device_id in matched_devices:
            device = next(
                d for d in await coordinator.get_feeders() if d.api_name == device_id
            )
            if device is not None:
                schedules = await device.get_schedules()
                for schedule in schedules:
                    if schedule["time"] + ":00" == time:
                        await device.delete_schedule(str(schedule["id"]), False)
                        coordinator.invalidate_details(device_id)
                        break

    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_SCHEDULE, handle_delete_schedule
    )

    async def handle_delete_all_schedules(call: ServiceCall) -> None:
        device_ids = call.data.get(ATTR_DEVICE_ID)
        area_ids = call.data.get(ATTR_AREA_ID)
        entity_ids = call.data.get(ATTR_ENTITY_ID)
        matched_devices = get_feeders_for_service(
            hass, area_ids, device_ids, entity_ids
        )

        for device_id in matched_devices:
            device = next(
                d for d in await coordinator.get_feeders() if d.api_name == device_id
            )
            if device is not None:
                await device.delete_all_schedules(False)
                coordinator.invalidate_details(device_id)

    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_ALL_SCHEDULES, handle_delete_all_schedules
    )

    async def handle_modify_schedule(call: ServiceCall) -> None:
        device_ids = call.data.get(ATTR_DEVICE_ID)
        area_ids = call.data.get(ATTR_AREA_ID)
        entity_ids = call.data.get(ATTR_ENTITY_ID)
        time = call.data.get(ATTR_TIME)
        amount = call.data.get(ATTR_AMOUNT)
        matched_devices = get_feeders_for_service(
            hass, area_ids, device_ids, entity_ids
        )

        for device_id in matched_devices:
            device = next(
                d for d in await coordinator.get_feeders() if d.api_name == device_id
            )
            if device is not None:
                schedules = await device.get_schedules()
                for schedule in schedules:
                    if schedule["time"] + ":00" == time:
                        await device.modify_schedule(
                            schedule["time"], amount, str(schedule["id"]), False
                        )
                        coordinator.invalidate_details(device_id)
                        break

    hass.services.async_register(
        DOMAIN, SERVICE_MODIFY_SCHEDULE, handle_modify_schedule
    )

    async def handle_feed(call: ServiceCall) -> None:
        device_ids = call.data.get(ATTR_DEVICE_ID)
        area_ids = call.data.get(ATTR_AREA_ID)
        entity_ids = call.data.get(ATTR_ENTITY_ID)
        amount = call.data.get(ATTR_AMOUNT)
        slow_feed = call.data.get(ATTR_SLOW_FEED)
        matched_devices = get_feeders_for_service(
            hass, area_ids, device_ids, entity_ids
        )

        for device_id in matched_devices:
            device = next(
                d for d in await coordinator.get_feeders() if d.api_name == device_id
            )
            if device is not None:
                await device.feed(amount, slow_feed, False)
                coordinator.invalidate_details(device_id)
                await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, SERVICE_FEED, handle_feed)

    async def handle_prime(call: ServiceCall) -> None:
        device_ids = call.data.get(ATTR_DEVICE_ID)
        area_ids = call.data.get(ATTR_AREA_ID)
        entity_ids = call.data.get(ATTR_ENTITY_ID)
        matched_devices = get_feeders_for_service(
            hass, area_ids, device_ids, entity_ids
        )

        for device_id in matched_devices:
            device = next(
                d for d in await coordinator.get_feeders() if d.api_name == device_id
            )
            if device is not None:
                # NB: DeviceSmartFeed.prime() synchronously updates state after priming.
                # Directly send a 5/8 cup meal here so that we can defer the update.
                await device.feed(5, False, False)
                coordinator.invalidate_details(device_id)
                await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, SERVICE_PRIME, handle_prime)

    # Refresh before forwarding to the platforms, so entities are created
    # with data already available and a failed first fetch raises
    # ConfigEntryNotReady instead of producing entities with no data.
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class PetSafeData:
    """Snapshot of everything the entities need for one coordinator cycle.

    feeders/litterboxes come from the main poll. The three dicts hold the
    "extra" per-device data that each needs its own API call, refreshed on the
    slower DETAILS_UPDATE_INTERVAL cadence and keyed by api_name.
    """

    def __init__(
        self,
        feeders: list[petsafe.devices.DeviceSmartFeed],
        litterboxes: list[petsafe.devices.DeviceScoopfree],
        feeder_messages: dict[str, list] | None = None,
        feeder_schedules: dict[str, list] | None = None,
        litterbox_activity: dict[str, dict] | None = None,
    ):
        self.feeders = feeders
        self.litterboxes = litterboxes
        self.feeder_messages = feeder_messages or {}
        self.feeder_schedules = feeder_schedules or {}
        self.litterbox_activity = litterbox_activity or {}


class PetSafeCoordinator(DataUpdateCoordinator):
    """Data Update Coordinator for petsafe devices."""

    def __init__(
        self, hass: HomeAssistant, api: petsafe.PetSafeClient, entry: ConfigEntry
    ):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="PetSafe",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=30),
        )
        self.api: petsafe.PetSafeClient = api
        self.hass: HomeAssistant = hass
        self._feeders: list[petsafe.devices.DeviceSmartFeed] = None
        self._litterboxes: list[petsafe.devices.DeviceScoopfree] = None
        self._device_lock = asyncio.Lock()
        self.entry = entry
        self._authErrorCount = 0

        # Cached "extra" per-device data, plus the monotonic timestamp of the
        # last successful fetch for each device.
        self._feeder_messages: dict[str, list] = {}
        self._feeder_schedules: dict[str, list] = {}
        self._litterbox_activity: dict[str, dict] = {}
        self._details_fetched_at: dict[str, float] = {}

        # Portion sizes in cups, per feeder, for the Meal/Snack buttons:
        # {api_name: {"meal": 1.0, "snack": 0.125}}. The number entities own
        # these values and push them here; the buttons read them. Going through
        # the coordinator rather than looking up a number entity's state keeps
        # the buttons working if those entities are ever renamed.
        self._portions: dict[str, dict[str, float]] = {}

    async def get_feeders(self) -> list[petsafe.devices.DeviceSmartFeed]:
        """Return the list of feeders."""
        async with self._device_lock:
            try:
                if self._feeders is None:
                    self._feeders = await self.api.get_feeders()
            except httpx.HTTPStatusError as ex:
                if ex.response.status_code in (401, 403):
                    await self.entry.async_start_reauth(self.hass)
                else:
                    raise
            return self._feeders

    async def get_litterboxes(self) -> list[petsafe.devices.DeviceScoopfree]:
        """Return the list of litterboxes."""
        async with self._device_lock:
            try:
                if self._litterboxes is None:
                    self._litterboxes = await self.api.get_litterboxes()
            except httpx.HTTPStatusError as ex:
                if ex.response.status_code in (401, 403):
                    await self.entry.async_start_reauth(self.hass)
                else:
                    raise
            return self._litterboxes

    def get_portion(self, api_name: str, kind: str, default: float) -> float:
        """Return a feeder's configured portion in cups."""
        return self._portions.get(api_name, {}).get(kind, default)

    def set_portion(self, api_name: str, kind: str, cups: float) -> None:
        """Record a feeder's portion in cups. Called by the number entities."""
        self._portions.setdefault(api_name, {})[kind] = cups

    def invalidate_details(self, api_name: str | None = None) -> None:
        """Force the next cycle to re-fetch cached detail data.

        Called after an action that changes it (feeding, editing a schedule) so
        the sensors reflect the change on the next tick instead of up to
        DETAILS_UPDATE_INTERVAL later.
        """
        if api_name is None:
            self._details_fetched_at.clear()
        else:
            self._details_fetched_at.pop(api_name, None)

    def _sync_token_expiry(self) -> None:
        """Work around a typo in petsafe's token expiry bookkeeping.

        PetSafeClient.__refresh_tokens() stores the new expiry on
        ``token_expires_time`` while __get_headers() reads ``_token_expires_time``,
        which therefore stays 0 forever -- so every single request performs a
        full Cognito re-auth first, doubling request volume and hammering an
        endpoint that rate limits aggressively.

        Copying the value across suppresses the redundant refreshes. This is
        safe because petsafe >= 2.0.7 retries with a token refresh on a 403, so
        an expiry we misjudge is recovered automatically. Every access is
        guarded, so a future library that fixes the typo simply no-ops here.
        """
        try:
            computed = getattr(self.api, "token_expires_time", 0) or 0
            current = getattr(self.api, "_token_expires_time", 0) or 0
            if computed > current:
                self.api._token_expires_time = computed
        except Exception:  # noqa: BLE001 - never let bookkeeping break an update
            _LOGGER.debug("Could not sync PetSafe token expiry", exc_info=True)

    async def _async_refresh_details(self) -> None:
        """Refresh cached per-device detail data whose TTL has expired.

        Each device is fetched independently and failures are swallowed with a
        debug log: stale detail data is much better than failing the whole
        update and marking every entity unavailable.
        """
        now = monotonic()

        for feeder in self._feeders or []:
            api_name = feeder.api_name
            last = self._details_fetched_at.get(api_name)
            if last is not None and now - last < DETAILS_UPDATE_INTERVAL:
                continue
            try:
                self._feeder_messages[api_name] = await feeder.get_messages_since(
                    MESSAGE_LOOKBACK_DAYS
                )
                self._feeder_schedules[api_name] = await feeder.get_schedules()
            except Exception:  # noqa: BLE001
                _LOGGER.debug(
                    "Could not refresh details for feeder %s", api_name, exc_info=True
                )
            else:
                self._details_fetched_at[api_name] = now

        for litterbox in self._litterboxes or []:
            api_name = litterbox.api_name
            last = self._details_fetched_at.get(api_name)
            if last is not None and now - last < DETAILS_UPDATE_INTERVAL:
                continue
            try:
                self._litterbox_activity[api_name] = await litterbox.get_activity()
            except Exception:  # noqa: BLE001
                _LOGGER.debug(
                    "Could not refresh activity for litterbox %s",
                    api_name,
                    exc_info=True,
                )
            else:
                self._details_fetched_at[api_name] = now

    async def _async_update_data(self) -> PetSafeData:
        """Fetch data from API endpoint."""
        try:
            async with self._device_lock:
                self._feeders = await self.api.get_feeders()
                self._litterboxes = await self.api.get_litterboxes()
                self._authErrorCount = 0
                self._sync_token_expiry()
                await self._async_refresh_details()
                return PetSafeData(
                    self._feeders,
                    self._litterboxes,
                    self._feeder_messages,
                    self._feeder_schedules,
                    self._litterbox_activity,
                )
        except httpx.HTTPStatusError as ex:
            if ex.response.status_code in (401, 403):
                self._authErrorCount += 1
                if self._authErrorCount >= 5:
                    self._authErrorCount = 0
                    raise ConfigEntryAuthFailed() from ex
                # Below the reauth threshold this used to fall through and
                # return None, which set coordinator.data to None and made
                # every entity raise on the next update. Fail the update
                # instead so the last good data is retained.
                raise UpdateFailed() from ex
            raise UpdateFailed() from ex
        except Exception as ex:
            raise UpdateFailed() from ex
