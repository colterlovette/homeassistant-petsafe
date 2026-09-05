"""Sensor entities for the PetSafe integration."""

from __future__ import annotations

import datetime
import logging
import time

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

import petsafe

from . import PetSafeCoordinator, PetSafeData
from .const import (
    CAT_IN_BOX,
    DOMAIN,
    ERROR_SENSOR_BLOCKED,
    FEED_DONE,
    FEEDER_MODEL_GEN1,
    FEEDER_MODEL_GEN2,
    MANUFACTURER,
    RAKE_BUTTON_DETECTED,
    RAKE_FINISHED,
    RAKE_NOW,
    SCHEDULE_TIME_FORMAT,
)

_LOGGER = logging.getLogger(__name__)


class PetSafeSensorEntity(CoordinatorEntity, SensorEntity):
    """Base class for PetSafe sensors.

    These entities are driven entirely by the coordinator. They never poll and
    never call the API themselves -- see the note in _handle_coordinator_update.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        api_name: str,
        name: str,
        coordinator: PetSafeCoordinator,
        device_type: str,
        icon: str = None,
        device_class: str = None,
        entity_category: str = None,
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
        self._attr_entity_category = entity_category

        if device_class == "signal_strength":
            self._attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
        elif device_class == "battery":
            self._attr_native_unit_of_measurement = PERCENTAGE

    async def async_added_to_hass(self) -> None:
        """Populate the initial value before the first coordinator tick.

        CoordinatorEntity.async_added_to_hass only registers the update
        listener; it does not seed the entity's state. Without this the sensor
        would sit at "unknown" until the coordinator next fires.
        """
        await super().async_added_to_hass()
        self._update_from_coordinator()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Recompute this sensor's value from the coordinator's data.

        This must stay free of I/O. The previous implementation called
        schedule_update_ha_state(True) here, which ran async_update(), which
        ended in CoordinatorEntity.async_update() -- and that calls
        coordinator.async_request_refresh(). Each coordinator tick therefore
        requested another one, so the integration span-polled the PetSafe API
        at the request-refresh debouncer's 10 second cooldown forever, ignoring
        both the 30s update_interval and the 60s SCAN_INTERVAL.
        """
        self._update_from_coordinator()
        super()._handle_coordinator_update()

    @callback
    def _update_from_coordinator(self) -> None:
        """Set _attr_native_value from coordinator data. Overridden below."""
        raise NotImplementedError


class PetSafeLitterboxSensorEntity(PetSafeSensorEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        coordinator: PetSafeCoordinator,
        device_type: str,
        device: petsafe.devices.DeviceScoopfree,
        icon: str = None,
        device_class: str = None,
        entity_category: str = None,
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
            entity_category,
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.api_name)},
            manufacturer=MANUFACTURER,
            name=device.friendly_name,
            model=device.product_name,
            sw_version=device.firmware,
        )

    @callback
    def _update_from_coordinator(self) -> None:
        data: PetSafeData = self.coordinator.data
        if data is None:
            return

        litterbox: petsafe.devices.DeviceScoopfree | None = next(
            (x for x in data.litterboxes if x.api_name == self._api_name), None
        )
        if litterbox is None:
            # The device is no longer in the account payload. Keep the previous
            # value rather than raising StopIteration inside a callback.
            return

        shadow = litterbox.data.get("shadow") or {}
        reported = (shadow.get("state") or {}).get("reported") or {}

        if self._device_type == "rake_counter":
            self._attr_native_value = reported.get("rakeCount")
        elif self._device_type == "signal_strength":
            self._attr_native_value = reported.get("rssi")
        elif self._device_type == "last_cleaning":
            self._attr_native_value = self._last_cleaning(
                data.litterbox_activity.get(self._api_name)
            )
        elif self._device_type == "rake_status":
            self._attr_native_value = self._rake_status(
                data.litterbox_activity.get(self._api_name),
                reported.get("rakeDelayTime"),
            )

    @staticmethod
    def _events(activity) -> list:
        """Return the event list from an activity response, oldest first."""
        if not activity:
            return []
        events = activity.get("data") if isinstance(activity, dict) else activity
        return events or []

    def _last_cleaning(self, activity) -> datetime.datetime | None:
        """Most recent completed rake.

        Selected with max() rather than by trusting the response ordering.
        """
        timestamps = []
        for item in self._events(activity):
            payload = item.get("payload") or {}
            if payload.get("code") != RAKE_FINISHED:
                continue
            try:
                timestamps.append(int(payload["timestamp"]) / 1000)
            except (KeyError, TypeError, ValueError):
                continue
        if not timestamps:
            return None
        return dt_util.utc_from_timestamp(max(timestamps))

    def _rake_status(self, activity, rake_delay_time) -> str | None:
        """Derive rake status from the newest interesting activity event."""
        events = self._events(activity)
        if not events:
            return None

        for item in reversed(events):
            payload = item.get("payload") or {}
            code = payload.get("code")
            if code == RAKE_FINISHED:
                return "idle"
            if code == CAT_IN_BOX:
                try:
                    timestamp = int(payload["timestamp"]) / 1000
                    delay_seconds = int(rake_delay_time) * 60
                except (KeyError, TypeError, ValueError):
                    return "timing"
                if timestamp + delay_seconds <= time.time():
                    return "raking"
                return "timing"
            if code in (RAKE_BUTTON_DETECTED, RAKE_NOW):
                return "raking"
            if code == ERROR_SENSOR_BLOCKED:
                return "jammed"
        return None


class PetSafeFeederSensorEntity(PetSafeSensorEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        coordinator: PetSafeCoordinator,
        device_type: str,
        device: petsafe.devices.DeviceSmartFeed,
        icon: str = None,
        device_class: str = None,
        entity_category: str = None,
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
            entity_category,
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.api_name)},
            manufacturer=MANUFACTURER,
            name=device.friendly_name,
            sw_version=device.firmware,
            # NB: Gen1 smart feeders do not report a product_name
            model=device.product_name or FEEDER_MODEL_GEN1,
        )

    @callback
    def _update_from_coordinator(self) -> None:
        data: PetSafeData = self.coordinator.data
        if data is None:
            return

        feeder: petsafe.devices.DeviceSmartFeed | None = next(
            (x for x in data.feeders if x.api_name == self._api_name), None
        )
        if feeder is None:
            return

        if self._device_type == "battery":
            self._attr_native_value = self._battery_level(feeder)
        elif self._device_type == "food_level":
            if feeder.food_low_status == 0:
                self._attr_native_value = "full"
            elif feeder.food_low_status == 1:
                self._attr_native_value = "low"
            else:
                self._attr_native_value = "empty"
        elif self._device_type == "signal_strength":
            self._attr_native_value = feeder.data.get("network_rssi")
        elif self._device_type == "last_feeding":
            self._attr_native_value = self._last_feeding(
                data.feeder_messages.get(self._api_name)
            )
        elif self._device_type == "next_feeding":
            self._attr_native_value = self._next_feeding(
                feeder, data.feeder_schedules.get(self._api_name)
            )

    @staticmethod
    def _battery_level(feeder: petsafe.devices.DeviceSmartFeed) -> int | None:
        """Battery percentage, or None when no backup cells are fitted.

        These feeders run on mains with optional D-cell backup. The library's
        battery_level returns 0 when is_batteries_installed is false, which is
        indistinguishable from a flat battery and trips low-battery automations
        forever. Report unknown instead -- absent is not the same as empty.
        """
        if not feeder.data.get("is_batteries_installed"):
            return None
        return feeder.battery_level

    @staticmethod
    def _last_feeding(messages) -> datetime.datetime | None:
        """Most recent completed feeding.

        Deliberately does not use petsafe's DeviceSmartFeed.get_last_feeding().
        That returns the *first* FEED_DONE in the message list, and the API
        returns messages oldest first over a rolling 7 day window -- so it
        reports a feeding from exactly 7 days ago and steps forward by a day
        each time the window slides, rather than reporting the latest feeding.

        Selecting with max() makes this correct regardless of response order.
        """
        if not messages:
            return None

        timestamps = []
        for message in messages:
            if message.get("message_type") != FEED_DONE:
                continue
            payload = message.get("payload") or {}
            raw = payload.get("time")
            if raw is None:
                continue
            try:
                timestamps.append(float(raw))
            except (TypeError, ValueError):
                continue

        if not timestamps:
            return None
        return dt_util.utc_from_timestamp(max(timestamps))

    @staticmethod
    def _next_feeding(
        feeder: petsafe.devices.DeviceSmartFeed, schedules
    ) -> datetime.datetime | None:
        """Next scheduled feeding, or None when there is nothing scheduled.

        An empty schedule list is a valid, supported state -- a feeder that is
        only ever fed on demand has no schedule and never will. So is a paused
        feeder: its schedule exists but will not fire, and showing the time it
        would have fired is worse than showing nothing.
        """
        if not schedules:
            return None

        try:
            if feeder.is_paused:
                return None
        except (KeyError, TypeError):
            pass

        times_of_day = []
        for schedule in schedules:
            raw = schedule.get("time") if isinstance(schedule, dict) else None
            if not raw:
                continue
            try:
                times_of_day.append(
                    datetime.datetime.strptime(raw, SCHEDULE_TIME_FORMAT).time()
                )
            except (TypeError, ValueError):
                _LOGGER.debug("Ignoring unparseable feeding schedule time %r", raw)

        if not times_of_day:
            return None
        times_of_day.sort()

        now = dt_util.now()
        today = now.date()

        # Combine the time-of-day with each date separately rather than adding
        # a day to an aware datetime, so this stays correct across DST changes.
        for day in (today, today + datetime.timedelta(days=1)):
            for time_of_day in times_of_day:
                candidate = dt_util.as_local(
                    datetime.datetime.combine(day, time_of_day)
                )
                if candidate > now:
                    return candidate
        return None
