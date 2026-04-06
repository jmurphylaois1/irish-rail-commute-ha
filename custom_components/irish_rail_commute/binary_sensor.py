"""Binary sensor platform for Irish Rail Commute integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_COMMUTE_NAME, DOMAIN
from .coordinator import IrishRailDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Irish Rail binary sensors."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: IrishRailDataUpdateCoordinator = entry_data["coordinator"]
    async_add_entities([IrishRailDisruptionBinarySensor(coordinator, entry)])


class IrishRailBinarySensorBase(
    CoordinatorEntity[IrishRailDataUpdateCoordinator], BinarySensorEntity
):
    """Base binary sensor for Irish Rail Commute."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IrishRailDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._entry = entry

        commute_name = entry.data.get(CONF_COMMUTE_NAME)
        if not commute_name:
            data = coordinator.data or {}
            origin_name = (
                entry.data.get("origin_name")
                or data.get("origin_name")
                or entry.data.get("origin")
                or "Origin"
            )
            destination_name = (
                entry.data.get("destination_name")
                or data.get("destination_name")
                or entry.data.get("destination")
                or "Destination"
            )
            commute_name = f"{origin_name} → {destination_name}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=commute_name,
            manufacturer="Irish Rail",
            model="Realtime API",
        )


class IrishRailDisruptionBinarySensor(IrishRailBinarySensorBase):
    """Binary sensor indicating whether the commute has disruption."""

    _attr_name = "Has disruption"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        coordinator: IrishRailDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_has_disruption"

    @property
    def is_on(self) -> bool:
        """Return true if overall status is not Normal."""
        data = self.coordinator.data or {}
        status = data.get("overall_status", "Unknown")
        return status not in ("Normal", "Unknown", None)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        data = self.coordinator.data or {}
        next_train = data.get("next_train")

        if isinstance(next_train, dict):
            next_train_value = (
                next_train.get("expected_departure")
                or next_train.get("scheduled_departure")
                or "Unknown"
            )
        else:
            next_train_value = None

        return {
            "status": data.get("overall_status"),
            "summary": data.get("summary"),
            "next_train": next_train_value,
            "delayed_count": data.get("delayed_count", 0),
            "cancelled_count": data.get("cancelled_count", 0),
        }