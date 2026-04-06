"""The Irish Rail Commute integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api import IrishRailAPI
from .const import (
    CONF_DEPARTED_TRAIN_GRACE_PERIOD,
    CONF_DESTINATION,
    CONF_DESTINATION_NAME,
    CONF_MAJOR_DELAY_THRESHOLD,
    CONF_MINOR_DELAY_THRESHOLD,
    CONF_NIGHT_UPDATES,
    CONF_NUM_SERVICES,
    CONF_ORIGIN,
    CONF_ORIGIN_NAME,
    CONF_SEVERE_DELAY_THRESHOLD,
    CONF_TIME_WINDOW,
    DEFAULT_DEPARTED_TRAIN_GRACE_PERIOD,
    DEFAULT_MAJOR_DELAY_THRESHOLD,
    DEFAULT_MINOR_DELAY_THRESHOLD,
    DEFAULT_NIGHT_UPDATES,
    DEFAULT_NUM_SERVICES,
    DEFAULT_SEVERE_DELAY_THRESHOLD,
    DEFAULT_TIME_WINDOW,
    DOMAIN,
)
from .coordinator import IrishRailDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def _async_backfill_station_names(
    hass: HomeAssistant,
    entry: ConfigEntry,
    api: IrishRailAPI,
) -> ConfigEntry:
    """Backfill station names for older config entries."""
    origin = entry.data.get(CONF_ORIGIN)
    destination = entry.data.get(CONF_DESTINATION)
    origin_name = entry.data.get(CONF_ORIGIN_NAME)
    destination_name = entry.data.get(CONF_DESTINATION_NAME)

    if origin_name and destination_name:
        return entry

    try:
        stations = await hass.async_add_executor_job(api.get_all_stations)
    except Exception:
        return entry

    station_map = {
        str(station.get("code", "")).strip().upper(): station.get("name")
        for station in stations
        if station.get("code") and station.get("name")
    }

    new_origin_name = origin_name or station_map.get(str(origin).strip().upper(), origin)
    new_destination_name = destination_name or station_map.get(
        str(destination).strip().upper(), destination
    )

    new_data = {
        **entry.data,
        CONF_ORIGIN_NAME: new_origin_name,
        CONF_DESTINATION_NAME: new_destination_name,
    }

    new_title = f"{new_origin_name} → {new_destination_name}"

    hass.config_entries.async_update_entry(
        entry,
        data=new_data,
        title=new_title,
    )

    return entry


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Irish Rail Commute from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    api = IrishRailAPI()

    entry = await _async_backfill_station_names(hass, entry, api)

    config = {
        CONF_TIME_WINDOW: DEFAULT_TIME_WINDOW,
        CONF_NUM_SERVICES: DEFAULT_NUM_SERVICES,
        CONF_NIGHT_UPDATES: DEFAULT_NIGHT_UPDATES,
        CONF_DEPARTED_TRAIN_GRACE_PERIOD: DEFAULT_DEPARTED_TRAIN_GRACE_PERIOD,
        CONF_SEVERE_DELAY_THRESHOLD: DEFAULT_SEVERE_DELAY_THRESHOLD,
        CONF_MAJOR_DELAY_THRESHOLD: DEFAULT_MAJOR_DELAY_THRESHOLD,
        CONF_MINOR_DELAY_THRESHOLD: DEFAULT_MINOR_DELAY_THRESHOLD,
        **entry.data,
        **entry.options,
    }

    coordinator = IrishRailDataUpdateCoordinator(hass, api, config, entry_id=entry.entry_id)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "config": config,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Irish Rail Commute config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok