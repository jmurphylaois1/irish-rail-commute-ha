"""Sensor platform for Irish Rail Commute integration."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_COMMUTE_NAME,
    CONF_DESTINATION,
    CONF_DESTINATION_NAME,
    CONF_NUM_SERVICES,
    CONF_ORIGIN,
    CONF_ORIGIN_NAME,
    DOMAIN,
)
from .coordinator import IrishRailDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

_TIME_FORMAT_RE = re.compile(r"^\d{2}:\d{2}$")


def _minutes_until(time_str: str | None) -> int | None:
    """Return minutes until the given HH:MM time, handling midnight crossing."""
    if not time_str or not _TIME_FORMAT_RE.match(time_str):
        return None

    now = dt_util.now()
    current_time_str = now.strftime("%H:%M")

    try:
        current_dt = datetime.strptime(
            f"2000-01-01 {current_time_str}",
            "%Y-%m-%d %H:%M",
        )
        target_dt = datetime.strptime(
            f"2000-01-01 {time_str}",
            "%Y-%m-%d %H:%M",
        )

        diff_seconds = (target_dt - current_dt).total_seconds()

        if diff_seconds < -12 * 3600:
            target_dt += timedelta(days=1)
        elif diff_seconds > 12 * 3600:
            target_dt -= timedelta(days=1)

        diff_seconds = (target_dt - current_dt).total_seconds()
        return int(round(diff_seconds / 60))
    except (ValueError, TypeError):
        return None


def _parse_iso_datetime(value: str | None) -> datetime | None:
    """Parse ISO datetime string into local datetime."""
    if not value:
        return None

    try:
        dt_value = dt_util.parse_datetime(value)
        if dt_value is None:
            return None

        if dt_util.as_local(dt_value):
            return dt_util.as_local(dt_value)
    except Exception:
        pass

    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def _data_age_info(last_updated: str | None) -> dict[str, Any]:
    """Return data age information from last_updated ISO string."""
    last_dt = _parse_iso_datetime(last_updated)
    if last_dt is None:
        return {
            "data_age_minutes": None,
            "is_stale": False,
            "stale_reason": None,
        }

    now = dt_util.now()
    try:
        age_seconds = max((now - last_dt).total_seconds(), 0)
    except TypeError:
        last_dt = dt_util.as_local(last_dt)
        age_seconds = max((now - last_dt).total_seconds(), 0)

    age_minutes = int(age_seconds // 60)

    # Simple practical thresholds for UI.
    is_stale = age_minutes >= 10
    stale_reason = f"Last successful update was {age_minutes} min ago" if is_stale else None

    return {
        "data_age_minutes": age_minutes,
        "is_stale": is_stale,
        "stale_reason": stale_reason,
    }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Irish Rail sensor platform."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: IrishRailDataUpdateCoordinator = entry_data["coordinator"]

    config = {**entry.data, **entry.options}
    num_trains = int(config.get(CONF_NUM_SERVICES, 3))

    entities: list[SensorEntity] = [
        CommuteSummarySensor(coordinator, entry),
        CommuteStatusSensor(coordinator, entry),
        NextTrainSensor(coordinator, entry),
        CountdownSensor(coordinator, entry),
    ]

    for i in range(1, num_trains + 1):
        entities.append(TrainSensor(coordinator, entry, i))

    async_add_entities(entities)


class BaseEntity(CoordinatorEntity, SensorEntity):
    """Base Irish Rail entity."""

    def __init__(
        self,
        coordinator: IrishRailDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_has_entity_name = True

        commute_name = entry.data.get(CONF_COMMUTE_NAME)

        if not commute_name:
            data = coordinator.data or {}
            origin_name = (
                entry.data.get(CONF_ORIGIN_NAME)
                or data.get("origin_name")
                or entry.data.get(CONF_ORIGIN)
                or "Origin"
            )
            destination_name = (
                entry.data.get(CONF_DESTINATION_NAME)
                or data.get("destination_name")
                or entry.data.get(CONF_DESTINATION)
                or "Destination"
            )
            commute_name = f"{origin_name} → {destination_name}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=commute_name,
            manufacturer="Irish Rail",
            model="Realtime API",
            entry_type="service",
        )

    def _base_data_age_attributes(self, data: dict[str, Any]) -> dict[str, Any]:
        """Common stale-data attributes."""
        last_updated = data.get("last_updated")
        return {
            "last_updated": last_updated,
            **_data_age_info(last_updated),
        }


class CommuteSummarySensor(BaseEntity):
    """Summary sensor."""

    def __init__(
        self,
        coordinator: IrishRailDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = "Summary"
        self._attr_unique_id = f"{entry.entry_id}_summary"
        self._attr_icon = "mdi:train"

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.data
        if not data:
            return None
        return data.get("summary") or data.get("overall_status")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        if not data:
            return {}

        services = data.get("services", [])
        upcoming_trains = data.get("upcoming_trains", [])
        trains = []

        for idx, train in enumerate(services, start=1):
            dep = (
                train.get("departure_time")
                or train.get("expected_departure")
                or train.get("scheduled_departure")
            )
            arr = (
                train.get("arrival_time")
                or train.get("expected_arrival")
                or train.get("scheduled_arrival")
            )

            trains.append(
                {
                    "train_number": idx,
                    "origin": train.get("origin"),
                    "destination": train.get("destination"),
                    "scheduled_departure": train.get("scheduled_departure"),
                    "expected_departure": train.get("expected_departure"),
                    "departure_time": dep,
                    "scheduled_arrival": train.get("scheduled_arrival"),
                    "expected_arrival": train.get("expected_arrival"),
                    "arrival_time": arr,
                    "delay_minutes": train.get("delay_minutes", 0),
                    "departure_delay_minutes": train.get("departure_delay_minutes", 0),
                    "arrival_delay_minutes": train.get("arrival_delay_minutes", 0),
                    "arrival_slipping": train.get("arrival_slipping", False),
                    "status": train.get("status"),
                    "is_cancelled": train.get("is_cancelled", False),
                    "platform": train.get("platform"),
                    "service_id": train.get("service_id"),
                    "operator": train.get("operator"),
                }
            )

        return {
            "origin": data.get("origin"),
            "origin_name": data.get("origin_name"),
            "destination": data.get("destination"),
            "destination_name": data.get("destination_name"),
            "route_name": data.get("route_name"),
            "status": data.get("status") or data.get("overall_status"),
            "overall_status": data.get("overall_status"),
            "summary": data.get("summary"),
            "countdown": data.get("countdown"),
            "next_train_time": data.get("next_train_time"),
            "services_requested": self.coordinator.num_services,
            "services_tracked": len(services),
            "on_time_count": data.get("on_time_count"),
            "delayed_count": data.get("delayed_count"),
            "cancelled_count": data.get("cancelled_count"),
            "upcoming_trains": upcoming_trains,
            "active_trains": data.get("active_trains", []),
            "all_trains": trains,
            **self._base_data_age_attributes(data),
        }


class CommuteStatusSensor(BaseEntity):
    """Overall commute status sensor."""

    def __init__(
        self,
        coordinator: IrishRailDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = "Status"
        self._attr_unique_id = f"{entry.entry_id}_status"

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.data
        if not data:
            return None
        return data.get("overall_status")

    @property
    def icon(self) -> str:
        status = self.native_value

        if status == "Critical":
            return "mdi:alert-octagon"
        if status == "Severe Disruption":
            return "mdi:alert-circle"
        if status == "Major Delays":
            return "mdi:clock-alert"
        if status == "Minor Delays":
            return "mdi:train-variant"

        return "mdi:train"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        if not data:
            return {}

        services = data.get("services", [])
        max_delay = max((s.get("delay_minutes", 0) for s in services), default=0)
        max_arrival_delay = max(
            (s.get("arrival_delay_minutes", 0) for s in services),
            default=0,
        )

        return {
            "origin": data.get("origin_name"),
            "origin_name": data.get("origin_name"),
            "destination": data.get("destination_name"),
            "destination_name": data.get("destination_name"),
            "route_name": data.get("route_name"),
            "total_trains": len(services),
            "on_time_count": data.get("on_time_count"),
            "delayed_count": data.get("delayed_count"),
            "cancelled_count": data.get("cancelled_count"),
            "max_delay_minutes": max_delay,
            "max_arrival_delay_minutes": max_arrival_delay,
            **self._base_data_age_attributes(data),
        }


class NextTrainSensor(BaseEntity):
    """Next train sensor."""

    def __init__(
        self,
        coordinator: IrishRailDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = "Next Train"
        self._attr_unique_id = f"{entry.entry_id}_next_train"
        self._attr_icon = "mdi:train-car"

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.data
        if not data:
            return None

        if data.get("next_train_time") == "No trains":
            return "No trains"

        train = data.get("next_train")
        if not train:
            return "No trains"

        dep = (
            train.get("departure_time")
            or train.get("expected_departure")
            or train.get("scheduled_departure")
        )
        delay = train.get("delay_minutes", 0)

        if train.get("is_cancelled"):
            return "Cancelled"
        if delay > 0:
            return f"{dep} (+{delay} min)"
        return dep

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        if not data:
            return {}

        train = data.get("next_train")
        if not train:
            return self._base_data_age_attributes(data)

        dep = (
            train.get("departure_time")
            or train.get("expected_departure")
            or train.get("scheduled_departure")
        )
        arr = (
            train.get("arrival_time")
            or train.get("expected_arrival")
            or train.get("scheduled_arrival")
        )
        mins = _minutes_until(dep)

        return {
            "origin": train.get("origin"),
            "destination": train.get("destination"),
            "scheduled_departure": train.get("scheduled_departure"),
            "expected_departure": train.get("expected_departure"),
            "departure_time": dep,
            "scheduled_arrival": train.get("scheduled_arrival"),
            "expected_arrival": train.get("expected_arrival"),
            "arrival_time": arr,
            "delay_minutes": train.get("delay_minutes", 0),
            "departure_delay_minutes": train.get("departure_delay_minutes", 0),
            "arrival_delay_minutes": train.get("arrival_delay_minutes", 0),
            "arrival_slipping": train.get("arrival_slipping", False),
            "minutes_until": mins,
            "status": train.get("status"),
            "is_cancelled": train.get("is_cancelled", False),
            "platform": train.get("platform"),
            "service_id": train.get("service_id"),
            "operator": train.get("operator"),
            **self._base_data_age_attributes(data),
        }


class CountdownSensor(BaseEntity):
    """Countdown to next train."""

    _attr_icon = "mdi:timer-outline"

    def __init__(
        self,
        coordinator: IrishRailDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = "Countdown"
        self._attr_unique_id = f"{entry.entry_id}_countdown"

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.data
        if not data:
            return None

        countdown = data.get("countdown")
        if countdown:
            return countdown

        train = data.get("next_train")
        if not train:
            return "No trains"

        if train.get("is_cancelled"):
            return "Cancelled"

        dep = (
            train.get("departure_time")
            or train.get("expected_departure")
            or train.get("scheduled_departure")
        )
        mins = _minutes_until(dep)

        if mins is None:
            return "Unknown"

        grace = int(getattr(self.coordinator, "departed_train_grace_period", 2))

        if mins < -grace:
            return "Departed"
        if mins <= 0:
            return "Due"
        if mins == 1:
            return "1 min"
        return f"{mins} min"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        if not data:
            return {}

        train = data.get("next_train")
        if not train:
            return self._base_data_age_attributes(data)

        dep = (
            train.get("departure_time")
            or train.get("expected_departure")
            or train.get("scheduled_departure")
        )
        arr = (
            train.get("arrival_time")
            or train.get("expected_arrival")
            or train.get("scheduled_arrival")
        )
        mins = _minutes_until(dep)

        return {
            "origin": train.get("origin"),
            "destination": train.get("destination"),
            "scheduled_departure": train.get("scheduled_departure"),
            "expected_departure": train.get("expected_departure"),
            "departure_time": dep,
            "scheduled_arrival": train.get("scheduled_arrival"),
            "expected_arrival": train.get("expected_arrival"),
            "arrival_time": arr,
            "delay_minutes": train.get("delay_minutes", 0),
            "departure_delay_minutes": train.get("departure_delay_minutes", 0),
            "arrival_delay_minutes": train.get("arrival_delay_minutes", 0),
            "arrival_slipping": train.get("arrival_slipping", False),
            "minutes_until": mins,
            "status": train.get("status"),
            "is_cancelled": train.get("is_cancelled", False),
            "platform": train.get("platform"),
            "service_id": train.get("service_id"),
            "operator": train.get("operator"),
            **self._base_data_age_attributes(data),
        }


class TrainSensor(BaseEntity):
    """Individual train sensor."""

    def __init__(
        self,
        coordinator: IrishRailDataUpdateCoordinator,
        entry: ConfigEntry,
        train_number: int,
    ) -> None:
        super().__init__(coordinator, entry)
        self._train_number = train_number
        self._attr_name = f"Train {train_number}"
        self._attr_unique_id = f"{entry.entry_id}_train_{train_number}"

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.data
        if not data:
            return None

        upcoming = data.get("upcoming_trains", [])
        if len(upcoming) < self._train_number:
            return "No upcoming train"

        train = upcoming[self._train_number - 1]

        if train.get("is_cancelled"):
            return "Cancelled"

        dep = (
            train.get("departure_time")
            or train.get("expected_departure")
            or train.get("scheduled_departure")
        )
        delay = train.get("delay_minutes", 0)

        if delay > 0:
            return f"{dep} (+{delay} min)"
        return dep

    @property
    def icon(self) -> str:
        data = self.coordinator.data
        if not data:
            return "mdi:train"

        upcoming = data.get("upcoming_trains", [])
        if len(upcoming) < self._train_number:
            return "mdi:train"

        train = upcoming[self._train_number - 1]

        if train.get("is_cancelled"):
            return "mdi:alert-circle"
        if train.get("delay_minutes", 0) > 10:
            return "mdi:clock-alert"
        if train.get("delay_minutes", 0) > 0:
            return "mdi:train-variant"
        return "mdi:train"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        if not data:
            return {}

        upcoming = data.get("upcoming_trains", [])
        if len(upcoming) < self._train_number:
            return {
                "train_number": self._train_number,
                "status": "no_service",
                **self._base_data_age_attributes(data),
            }

        train = upcoming[self._train_number - 1]
        dep = (
            train.get("departure_time")
            or train.get("expected_departure")
            or train.get("scheduled_departure")
        )
        arr = (
            train.get("arrival_time")
            or train.get("expected_arrival")
            or train.get("scheduled_arrival")
        )
        mins = _minutes_until(dep)

        return {
            "train_number": self._train_number,
            "origin": train.get("origin"),
            "destination": train.get("destination"),
            "scheduled_departure": train.get("scheduled_departure"),
            "expected_departure": train.get("expected_departure"),
            "departure_time": dep,
            "scheduled_arrival": train.get("scheduled_arrival"),
            "expected_arrival": train.get("expected_arrival"),
            "arrival_time": arr,
            "delay_minutes": train.get("delay_minutes", 0),
            "departure_delay_minutes": train.get("departure_delay_minutes", 0),
            "arrival_delay_minutes": train.get("arrival_delay_minutes", 0),
            "arrival_slipping": train.get("arrival_slipping", False),
            "minutes_until": mins,
            "status": train.get("status"),
            "is_cancelled": train.get("is_cancelled", False),
            "platform": train.get("platform"),
            "service_id": train.get("service_id"),
            "operator": train.get("operator"),
            **self._base_data_age_attributes(data),
        }