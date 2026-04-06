"""Config flow for Irish Rail Commute."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .api import IrishRailAPI
from .const import (
    CONF_COMMUTE_NAME,
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
    DEFAULT_MAJOR_DELAY_THRESHOLD,
    DEFAULT_MINOR_DELAY_THRESHOLD,
    DEFAULT_NIGHT_UPDATES,
    DEFAULT_NUM_SERVICES,
    DEFAULT_SEVERE_DELAY_THRESHOLD,
    DEFAULT_TIME_WINDOW,
    DOMAIN,
    MIN_DELAY_THRESHOLD,
)

_LOGGER = logging.getLogger(__name__)


class IrishRailConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Irish Rail Commute."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._stations: list[dict[str, Any]] = []
        self._route_data: dict[str, Any] = {}

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> IrishRailOptionsFlow:
        """Get the options flow for this handler."""
        return IrishRailOptionsFlow(config_entry)

    async def _async_load_stations(self) -> None:
        """Load station list from Irish Rail API."""
        if self._stations:
            return

        try:
            api = IrishRailAPI()
            self._stations = await self.hass.async_add_executor_job(
                api.get_all_stations
            )
            _LOGGER.warning("Loaded %s Irish Rail stations", len(self._stations))
        except Exception as err:
            _LOGGER.error("Failed to load stations: %s", err)
            self._stations = []

    def _get_station_name(self, station_code: str) -> str:
        """Return a station name from a station code."""
        code = station_code.strip().upper()
        for station in self._stations:
            if station.get("code", "").strip().upper() == code:
                return station.get("name", code)
        return code

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle initial route selection step."""
        errors: dict[str, str] = {}

        await self._async_load_stations()

        if user_input is not None:
            origin = str(user_input[CONF_ORIGIN]).strip().upper()
            destination = str(user_input[CONF_DESTINATION]).strip().upper()

            if origin == destination:
                errors["base"] = "same_station"
            else:
                origin_name = self._get_station_name(origin)
                destination_name = self._get_station_name(destination)

                self._route_data = {
                    CONF_ORIGIN: origin,
                    CONF_DESTINATION: destination,
                    CONF_ORIGIN_NAME: origin_name,
                    CONF_DESTINATION_NAME: destination_name,
                }

                return await self.async_step_settings()

        options = [
            selector.SelectOptionDict(
                value=station["code"],
                label=f"{station['name']} ({station['code']})",
            )
            for station in self._stations
            if station.get("code") and station.get("name")
        ]

        if options:
            origin_field = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
            destination_field = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        else:
            _LOGGER.warning("No stations loaded, falling back to manual entry")
            origin_field = str
            destination_field = str

        data_schema = vol.Schema(
            {
                vol.Required(CONF_ORIGIN): origin_field,
                vol.Required(CONF_DESTINATION): destination_field,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle settings step."""
        errors: dict[str, str] = {}

        origin_name = self._route_data.get(CONF_ORIGIN_NAME, "Origin")
        destination_name = self._route_data.get(CONF_DESTINATION_NAME, "Destination")
        suggested_name = f"{origin_name} → {destination_name}"

        if user_input is not None:
            commute_name = str(user_input[CONF_COMMUTE_NAME]).strip() or suggested_name
            time_window = int(user_input[CONF_TIME_WINDOW])
            num_services = int(user_input[CONF_NUM_SERVICES])
            night_updates = bool(user_input[CONF_NIGHT_UPDATES])
            severe_threshold = int(user_input[CONF_SEVERE_DELAY_THRESHOLD])
            major_threshold = int(user_input[CONF_MAJOR_DELAY_THRESHOLD])
            minor_threshold = int(user_input[CONF_MINOR_DELAY_THRESHOLD])

            origin = self._route_data[CONF_ORIGIN]
            destination = self._route_data[CONF_DESTINATION]

            if time_window < 1:
                errors[CONF_TIME_WINDOW] = "invalid_time_window"
            elif num_services < 1:
                errors[CONF_NUM_SERVICES] = "invalid_num_services"
            elif not (severe_threshold >= major_threshold >= minor_threshold >= MIN_DELAY_THRESHOLD):
                errors["base"] = "invalid_delay_thresholds"
            else:
                unique_id = f"{origin}_{destination}_{slugify(commute_name)}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=commute_name,
                    data={
                        **self._route_data,
                        CONF_COMMUTE_NAME: commute_name,
                    },
                    options={
                        CONF_TIME_WINDOW: time_window,
                        CONF_NUM_SERVICES: num_services,
                        CONF_NIGHT_UPDATES: night_updates,
                        CONF_SEVERE_DELAY_THRESHOLD: severe_threshold,
                        CONF_MAJOR_DELAY_THRESHOLD: major_threshold,
                        CONF_MINOR_DELAY_THRESHOLD: minor_threshold,
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_COMMUTE_NAME,
                    default=suggested_name,
                ): str,
                vol.Required(
                    CONF_TIME_WINDOW,
                    default=DEFAULT_TIME_WINDOW,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=15,
                        max=180,
                        step=5,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_NUM_SERVICES,
                    default=DEFAULT_NUM_SERVICES,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=10,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_NIGHT_UPDATES,
                    default=DEFAULT_NIGHT_UPDATES,
                ): bool,
                vol.Required(
                    CONF_SEVERE_DELAY_THRESHOLD,
                    default=DEFAULT_SEVERE_DELAY_THRESHOLD,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_DELAY_THRESHOLD,
                        max=120,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_MAJOR_DELAY_THRESHOLD,
                    default=DEFAULT_MAJOR_DELAY_THRESHOLD,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_DELAY_THRESHOLD,
                        max=120,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_MINOR_DELAY_THRESHOLD,
                    default=DEFAULT_MINOR_DELAY_THRESHOLD,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_DELAY_THRESHOLD,
                        max=120,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="settings",
            data_schema=data_schema,
            errors=errors,
        )


class IrishRailOptionsFlow(config_entries.OptionsFlow):
    """Handle Irish Rail Commute options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        current_name = self.config_entry.data.get(CONF_COMMUTE_NAME, self.config_entry.title)
        current_time_window = self.config_entry.options.get(
            CONF_TIME_WINDOW, DEFAULT_TIME_WINDOW
        )
        current_num_services = self.config_entry.options.get(
            CONF_NUM_SERVICES, DEFAULT_NUM_SERVICES
        )
        current_night_updates = self.config_entry.options.get(
            CONF_NIGHT_UPDATES, DEFAULT_NIGHT_UPDATES
        )
        current_severe = self.config_entry.options.get(
            CONF_SEVERE_DELAY_THRESHOLD, DEFAULT_SEVERE_DELAY_THRESHOLD
        )
        current_major = self.config_entry.options.get(
            CONF_MAJOR_DELAY_THRESHOLD, DEFAULT_MAJOR_DELAY_THRESHOLD
        )
        current_minor = self.config_entry.options.get(
            CONF_MINOR_DELAY_THRESHOLD, DEFAULT_MINOR_DELAY_THRESHOLD
        )

        if user_input is not None:
            commute_name = str(user_input[CONF_COMMUTE_NAME]).strip() or self.config_entry.title
            time_window = int(user_input[CONF_TIME_WINDOW])
            num_services = int(user_input[CONF_NUM_SERVICES])
            night_updates = bool(user_input[CONF_NIGHT_UPDATES])
            severe_threshold = int(user_input[CONF_SEVERE_DELAY_THRESHOLD])
            major_threshold = int(user_input[CONF_MAJOR_DELAY_THRESHOLD])
            minor_threshold = int(user_input[CONF_MINOR_DELAY_THRESHOLD])

            if time_window < 1:
                errors[CONF_TIME_WINDOW] = "invalid_time_window"
            elif num_services < 1:
                errors[CONF_NUM_SERVICES] = "invalid_num_services"
            elif not (severe_threshold >= major_threshold >= minor_threshold >= MIN_DELAY_THRESHOLD):
                errors["base"] = "invalid_delay_thresholds"
            else:
                new_data = {
                    **self.config_entry.data,
                    CONF_COMMUTE_NAME: commute_name,
                }

                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=new_data,
                )

                return self.async_create_entry(
                    title="",
                    data={
                        CONF_TIME_WINDOW: time_window,
                        CONF_NUM_SERVICES: num_services,
                        CONF_NIGHT_UPDATES: night_updates,
                        CONF_SEVERE_DELAY_THRESHOLD: severe_threshold,
                        CONF_MAJOR_DELAY_THRESHOLD: major_threshold,
                        CONF_MINOR_DELAY_THRESHOLD: minor_threshold,
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_COMMUTE_NAME,
                    default=current_name,
                ): str,
                vol.Required(
                    CONF_TIME_WINDOW,
                    default=current_time_window,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=15,
                        max=180,
                        step=5,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_NUM_SERVICES,
                    default=current_num_services,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=10,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_NIGHT_UPDATES,
                    default=current_night_updates,
                ): bool,
                vol.Required(
                    CONF_SEVERE_DELAY_THRESHOLD,
                    default=current_severe,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_DELAY_THRESHOLD,
                        max=120,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_MAJOR_DELAY_THRESHOLD,
                    default=current_major,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_DELAY_THRESHOLD,
                        max=120,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_MINOR_DELAY_THRESHOLD,
                    default=current_minor,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_DELAY_THRESHOLD,
                        max=120,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
        )