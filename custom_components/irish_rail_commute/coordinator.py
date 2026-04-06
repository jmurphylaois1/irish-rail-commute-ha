"""Data update coordinator for Irish Rail Commute integration."""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import IrishRailAPI
from .const import (
    CONF_DEPARTED_TRAIN_GRACE_PERIOD,
    CONF_DESTINATION,
    CONF_MAJOR_DELAY_THRESHOLD,
    CONF_MINOR_DELAY_THRESHOLD,
    CONF_NIGHT_UPDATES,
    CONF_NUM_SERVICES,
    CONF_ORIGIN,
    CONF_SEVERE_DELAY_THRESHOLD,
    CONF_TIME_WINDOW,
    DEFAULT_DEPARTED_TRAIN_GRACE_PERIOD,
    DEFAULT_MAJOR_DELAY_THRESHOLD,
    DEFAULT_MINOR_DELAY_THRESHOLD,
    DEFAULT_SEVERE_DELAY_THRESHOLD,
    DOMAIN,
    EVENT_STATUS_CHANGED,
    MIN_DELAY_THRESHOLD,
    NIGHT_HOURS,
    PEAK_HOURS,
    STATUS_CRITICAL,
    STATUS_MAJOR_DELAYS,
    STATUS_MINOR_DELAYS,
    STATUS_NORMAL,
    STATUS_SEVERE_DISRUPTION,
    UPDATE_INTERVAL_NIGHT,
    UPDATE_INTERVAL_OFF_PEAK,
    UPDATE_INTERVAL_PEAK,
)
from .reliability import ReliabilityTracker

_LOGGER = logging.getLogger(__name__)
_TIME_FORMAT_RE = re.compile(r"^\d{2}:\d{2}$")
_INTERNAL_STOP_NAME_RE = re.compile(r"^[A-Z]{1,4}\d+[A-Z0-9]*$")


class IrishRailDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Irish Rail data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: IrishRailAPI,
        config: dict[str, Any],
        entry_id: str = "",
    ) -> None:
        """Initialize the coordinator."""
        self.api = api
        self.config = config
        self.entry_id = entry_id
        self._failed_updates = 0
        self._max_failed_updates = 3
        self._update_interval_lock = asyncio.Lock()
        self._previous_status: str | None = None
        self.reliability_tracker = ReliabilityTracker(hass, entry_id) if entry_id else None

        self.origin = config[CONF_ORIGIN]
        self.destination = config[CONF_DESTINATION]
        self.origin_name = config.get("origin_name")
        self.destination_name = config.get("destination_name")
        self.time_window = int(config[CONF_TIME_WINDOW])
        self.num_services = int(config[CONF_NUM_SERVICES])
        self.night_updates_enabled = config.get(CONF_NIGHT_UPDATES, False)
        self.departed_train_grace_period = int(
            config.get(
                CONF_DEPARTED_TRAIN_GRACE_PERIOD,
                DEFAULT_DEPARTED_TRAIN_GRACE_PERIOD,
            )
        )

        self.severe_delay_threshold = int(
            config.get(CONF_SEVERE_DELAY_THRESHOLD, DEFAULT_SEVERE_DELAY_THRESHOLD)
        )
        self.major_delay_threshold = int(
            config.get(CONF_MAJOR_DELAY_THRESHOLD, DEFAULT_MAJOR_DELAY_THRESHOLD)
        )
        self.minor_delay_threshold = int(
            config.get(CONF_MINOR_DELAY_THRESHOLD, DEFAULT_MINOR_DELAY_THRESHOLD)
        )

        if not (
            self.severe_delay_threshold
            >= self.major_delay_threshold
            >= self.minor_delay_threshold
            >= MIN_DELAY_THRESHOLD
        ):
            _LOGGER.warning(
                "Invalid delay threshold hierarchy detected; resetting to defaults"
            )
            self.severe_delay_threshold = DEFAULT_SEVERE_DELAY_THRESHOLD
            self.major_delay_threshold = DEFAULT_MAJOR_DELAY_THRESHOLD
            self.minor_delay_threshold = DEFAULT_MINOR_DELAY_THRESHOLD

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=self._get_update_interval(),
        )

    def _clean_time(self, value: Any) -> str | None:
        """Return HH:MM string or None."""
        if value in (None, "", "None"):
            return None

        value_str = str(value).strip()
        if not value_str:
            return None

        if _TIME_FORMAT_RE.match(value_str[:5]):
            return value_str[:5]

        for fmt in (
            "%H:%M",
            "%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                return datetime.strptime(value_str, fmt).strftime("%H:%M")
            except (ValueError, TypeError):
                continue

        return value_str[:5] if len(value_str) >= 5 and ":" in value_str else None

    def _minutes_between_times(
        self, start_time: str | None, end_time: str | None
    ) -> int | None:
        """Return positive/negative minutes between two HH:MM times, handling midnight."""
        if (
            not start_time
            or not end_time
            or not _TIME_FORMAT_RE.match(start_time)
            or not _TIME_FORMAT_RE.match(end_time)
        ):
            return None

        try:
            start_dt = datetime.strptime(f"2000-01-01 {start_time}", "%Y-%m-%d %H:%M")
            end_dt = datetime.strptime(f"2000-01-01 {end_time}", "%Y-%m-%d %H:%M")

            diff_seconds = (end_dt - start_dt).total_seconds()

            if diff_seconds < -12 * 3600:
                end_dt += timedelta(days=1)
            elif diff_seconds > 12 * 3600:
                end_dt -= timedelta(days=1)

            diff_seconds = (end_dt - start_dt).total_seconds()
            return int(round(diff_seconds / 60))
        except (ValueError, TypeError):
            return None

    def _normalize_service_status(
        self,
        raw_status: Any,
        is_cancelled: bool = False,
        delay_minutes: int = 0,
    ) -> str:
        """Normalize service status wording for UI."""
        if is_cancelled:
            return "Cancelled"

        status = str(raw_status or "").strip().lower()

        if status in {"cancelled", "canceled"}:
            return "Cancelled"
        if delay_minutes > 0:
            return "Delayed"
        if status in {"on time", "on_time", "ontime", "normal"}:
            return "On Time"
        if "delay" in status:
            return "Delayed"

        return "On Time"

    def _is_active_journey(self, service: dict[str, Any]) -> bool:
        """Return True when a matched service is already in motion but not complete."""
        if service.get("is_cancelled", False):
            return False

        route_stops = service.get("route_stops") or []
        if len(route_stops) < 2:
            return False

        stops_completed = int(service.get("stops_completed", 0) or 0)
        segment_stop_count = int(service.get("segment_stop_count", 0) or 0)

        if stops_completed <= 0:
            return False

        if segment_stop_count > 0 and stops_completed >= segment_stop_count:
            return False

        return True

    def _service_sort_key(self, service: dict[str, Any]) -> datetime:
        """Return a sortable datetime for a service departure, handling midnight crossing."""
        departure_time = (
            service.get("departure_time")
            or service.get("expected_departure")
            or service.get("scheduled_departure")
        )
        now = dt_util.now()

        if not departure_time or not _TIME_FORMAT_RE.match(str(departure_time)):
            return now + timedelta(days=2)

        try:
            departure_dt = datetime.strptime(
                f"{now.strftime('%Y-%m-%d')} {departure_time}",
                "%Y-%m-%d %H:%M",
            )

            time_diff_seconds = (
                departure_dt.replace(second=0, microsecond=0)
                - departure_dt.replace(
                    hour=now.hour,
                    minute=now.minute,
                    second=0,
                    microsecond=0,
                )
            ).total_seconds()
            if time_diff_seconds < -12 * 3600:
                departure_dt += timedelta(days=1)
            elif time_diff_seconds > 12 * 3600:
                departure_dt -= timedelta(days=1)

            return departure_dt
        except (ValueError, TypeError):
            return now + timedelta(days=2)

    def _sort_services(self, services: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Sort services by departure time."""
        return sorted(services, key=self._service_sort_key)

    def _minutes_until(self, time_str: str | None) -> int | None:
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

    def _get_update_interval(self) -> timedelta:
        """Get update interval based on current time."""
        now = dt_util.now()
        current_hour = now.hour

        night_start, night_end = NIGHT_HOURS
        if night_start <= current_hour or current_hour < night_end:
            if not self.night_updates_enabled:
                return timedelta(hours=1)
            return UPDATE_INTERVAL_NIGHT

        for peak_start, peak_end in PEAK_HOURS:
            if peak_start <= current_hour < peak_end:
                return UPDATE_INTERVAL_PEAK

        return UPDATE_INTERVAL_OFF_PEAK

    def _is_display_stop(
        self,
        stop: dict[str, Any],
        *,
        idx: int,
        total: int,
    ) -> bool:
        """Return True if a stop should be shown in the passenger-facing route UI."""
        if idx == 0 or idx == total - 1:
            return True

        name = str(stop.get("location_name") or "").strip()
        code = str(stop.get("location_code") or "").strip().upper()
        stop_type = str(stop.get("stop_type") or "").strip().lower()
        location_type = str(stop.get("location_type") or "").strip().upper()

        # Irish Rail LocationType='T' means timing/pass-through point — not a passenger stop
        if location_type == "T":
            return False
        if name and _INTERNAL_STOP_NAME_RE.match(name.upper()):
            return False
        if not name and code and _INTERNAL_STOP_NAME_RE.match(code):
            return False
        if stop_type in {"n", "nonstop", "through", "passing"}:
            return False

        return True

    def _stop_is_passed(self, stop: dict[str, Any]) -> bool:
        """Check whether a stop has been passed using real movement only."""
        return any(
            str(stop.get(key) or "").strip()
            for key in ("actual_arrival", "actual_departure")
        )

    def _build_route_progress(
        self, segment_stops: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Build progress info for route segment."""
        if not segment_stops:
            return {
                "route_stops": [],
                "segment_stop_count": 0,
                "stops_completed": 0,
                "progress_percent": 0,
                "current_stop": None,
                "next_stop": None,
            }

        display_source: list[dict[str, Any]] = []
        total = len(segment_stops)

        for idx, stop in enumerate(segment_stops):
            if not self._is_display_stop(stop, idx=idx, total=total):
                continue

            display_source.append(
                {
                    "name": stop.get("location_name") or stop.get("location_code"),
                    "code": stop.get("location_code"),
                    "order": stop.get("location_order"),
                    "scheduled_arrival": self._clean_time(stop.get("scheduled_arrival")),
                    "expected_arrival": self._clean_time(stop.get("expected_arrival")),
                    "scheduled_departure": self._clean_time(stop.get("scheduled_departure")),
                    "expected_departure": self._clean_time(stop.get("expected_departure")),
                    "passed": self._stop_is_passed(stop),
                    "stop_type": stop.get("stop_type"),
                }
            )

        display_source.sort(key=lambda s: s.get("order") or 0)

        route_stops: list[dict[str, Any]] = []
        for stop in display_source:
            if route_stops and (
                route_stops[-1].get("name") == stop.get("name")
                or (
                    route_stops[-1].get("code")
                    and route_stops[-1].get("code") == stop.get("code")
                )
            ):
                route_stops[-1]["passed"] = route_stops[-1]["passed"] or stop.get("passed", False)
                continue
            route_stops.append(stop)

        # Back-fill pass-through stops: if any stop with a higher location_order
        # has been confirmed passed, stops with lower order must also be passed
        # (pass-through stations have no actual_arrival/actual_departure recorded).
        max_passed_order = max(
            (s.get("order") or 0 for s in route_stops if s.get("passed")),
            default=0,
        )
        if max_passed_order > 0:
            for stop in route_stops:
                if (stop.get("order") or 0) <= max_passed_order:
                    stop["passed"] = True

        current_stop = None
        next_stop = None
        passed_indices = [idx for idx, stop in enumerate(route_stops) if stop.get("passed")]
        stops_completed = len(passed_indices)

        if passed_indices:
            current_stop = route_stops[passed_indices[-1]]["name"]

        # Start from the last confirmed-passed stop so we never return a stop
        # that is behind the train's current position.
        search_from = (passed_indices[-1] + 1) if passed_indices else 1
        for idx in range(search_from, len(route_stops)):
            stop = route_stops[idx]
            if not stop["passed"]:
                next_stop = stop["name"]
                break

        if len(route_stops) <= 1:
            progress_percent = 0
        else:
            segments_total = len(route_stops) - 1
            if stops_completed <= 0:
                progress_percent = 0
            elif stops_completed >= len(route_stops):
                progress_percent = 100
            else:
                segments_done = max(stops_completed - 1, 0)
                base_progress = segments_done / segments_total
                progress_percent = int((base_progress * 100) + 5)
                if progress_percent == 0:
                    progress_percent = max(5, int(100 / max(segments_total, 1) / 2))
            progress_percent = max(0, min(progress_percent, 100))

        return {
            "route_stops": route_stops,
            "segment_stop_count": len(route_stops),
            "stops_completed": stops_completed,
            "progress_percent": progress_percent,
            "current_stop": current_stop,
            "next_stop": next_stop,
        }

    def _movement_matches_departure(
        self,
        raw_service: dict[str, Any],
        segment: dict[str, Any],
    ) -> bool:
        """Return True when movement data plausibly matches the departure-board row."""
        origin_stop = segment.get("origin_stop") or {}
        board_departure = (
            self._clean_time(raw_service.get("expected_departure"))
            or self._clean_time(raw_service.get("scheduled_departure"))
        )
        movement_departure = (
            self._clean_time(origin_stop.get("expected_departure"))
            or self._clean_time(origin_stop.get("scheduled_departure"))
        )

        if not board_departure or not movement_departure:
            return True

        diff = self._minutes_between_times(board_departure, movement_departure)
        if diff is None:
            return True

        if abs(diff) > 5:
            return False

        minutes_until_board = self._minutes_until(board_departure)
        if minutes_until_board is not None and minutes_until_board > 2:
            if any(
                str(origin_stop.get(key) or "").strip()
                for key in ("actual_arrival", "actual_departure", "auto_arrival", "auto_depart")
            ):
                return False

        return True

    def _normalize_route_name(self, value: Any) -> str:
        """Normalize route/station strings for loose matching."""
        if value is None:
            return ""
        return "".join(ch for ch in str(value).lower() if ch.isalnum())

    def _service_matches_selected_route(
        self,
        raw_service: dict[str, Any],
        movement_data: dict[str, Any],
    ) -> bool:
        """Return True when a service plausibly belongs to the configured route."""
        if movement_data.get("segment_stop_count", 0) > 1:
            return True

        configured_dest = self._normalize_route_name(self.destination_name or self.destination)
        raw_dest = self._normalize_route_name(raw_service.get("destination"))

        if not configured_dest or not raw_dest:
            return False

        return configured_dest in raw_dest or raw_dest in configured_dest

    def _normalize_future_route_state(
        self,
        service: dict[str, Any],
    ) -> dict[str, Any]:
        """Hide in-journey progress for trains that have not departed origin yet."""
        departure_time = (
            service.get("departure_time")
            or service.get("expected_departure")
            or service.get("scheduled_departure")
        )
        minutes_until = self._minutes_until(departure_time)

        if service.get("stops_completed", 0) > 0 or service.get("current_stop"):
            return service

        if minutes_until is None or minutes_until <= 2:
            return service

        route_stops = list(service.get("route_stops") or [])
        normalized_stops = []
        for stop in route_stops:
            cloned = dict(stop)
            cloned["passed"] = False
            normalized_stops.append(cloned)

        next_stop = None
        for idx, stop in enumerate(normalized_stops):
            if idx == 0:
                continue
            next_stop = stop.get("name")
            if next_stop:
                break

        service["route_stops"] = normalized_stops
        service["stops_completed"] = 0
        service["progress_percent"] = 0
        service["current_stop"] = None
        service["next_stop"] = next_stop
        service["segment_stop_count"] = len(normalized_stops)
        return service

    def _enrich_with_movements(
        self, raw_service: dict[str, Any]
    ) -> dict[str, Any]:
        """Enrich a departure with destination-specific route/movement data."""
        train_code = raw_service.get("train_code")
        train_date = raw_service.get("train_date")

        if not train_code:
            return {}

        train_date = train_date or raw_service.get("train_date")

        if not train_date:
            try:
                train_date = self.api.resolve_train_date(train_code)
            except Exception as err:
                _LOGGER.debug("Could not resolve train date for %s: %s", train_code, err)
                train_date = None

        if not train_date:
            return {}

        try:
            segment = self.api.get_route_segment(
                train_code=train_code,
                train_date=train_date,
                origin_code=self.origin,
                destination_code=self.destination,
            )
        except Exception as err:
            _LOGGER.debug(
                "Could not fetch movement data for %s (%s): %s",
                train_code,
                train_date,
                err,
            )
            return {}

        if not segment:
            return {}

        if not self._movement_matches_departure(raw_service, segment):
            _LOGGER.debug(
                "Discarding movement data for %s because origin timing did not match departure row",
                train_code,
            )
            return {}

        segment_stops = segment.get("segment_stops", [])
        progress = self._build_route_progress(segment_stops)

        board_departure = (
            self._clean_time(raw_service.get("expected_departure"))
            or self._clean_time(raw_service.get("scheduled_departure"))
        )
        minutes_until_board = self._minutes_until(board_departure)
        if (
            minutes_until_board is not None
            and minutes_until_board > 2
            and (progress.get("stops_completed", 0) > 1 or progress.get("current_stop"))
        ):
            _LOGGER.debug(
                "Discarding movement data for %s because the board departure is still in the future",
                train_code,
            )
            return {}

        scheduled_arrival = self._clean_time(segment.get("scheduled_arrival"))
        expected_arrival = self._clean_time(segment.get("expected_arrival"))
        arrival_time = (
            self._clean_time(segment.get("arrival_time"))
            or expected_arrival
            or scheduled_arrival
        )

        return {
            "train_date": train_date,
            "scheduled_arrival": scheduled_arrival,
            "expected_arrival": expected_arrival,
            "arrival_time": arrival_time,
            **progress,
        }

    def _build_active_service_from_current_train(
        self, current_train: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Build an active route service from current-train movement data."""
        train_code = current_train.get("train_code")
        train_date = current_train.get("train_date")

        if not train_code or not train_date:
            return None

        try:
            segment = self.api.get_route_segment(
                train_code=train_code,
                train_date=train_date,
                origin_code=self.origin,
                destination_code=self.destination,
            )
        except Exception as err:
            _LOGGER.debug(
                "Could not fetch active movement data for %s (%s): %s",
                train_code,
                train_date,
                err,
            )
            return None

        if not segment:
            return None

        segment_stops = segment.get("segment_stops", [])
        progress = self._build_route_progress(segment_stops)

        if progress.get("stops_completed", 0) <= 0:
            return None
        if (
            progress.get("segment_stop_count", 0) > 0
            and progress.get("stops_completed", 0) >= progress.get("segment_stop_count", 0)
        ):
            return None

        scheduled_arrival = self._clean_time(segment.get("scheduled_arrival"))
        expected_arrival = self._clean_time(segment.get("expected_arrival"))
        arrival_time = (
            self._clean_time(segment.get("arrival_time"))
            or expected_arrival
            or scheduled_arrival
        )

        origin_stop = segment.get("origin_stop") or {}
        destination_stop = segment.get("destination_stop") or {}

        scheduled_departure = self._clean_time(origin_stop.get("scheduled_departure"))
        expected_departure = self._clean_time(origin_stop.get("expected_departure"))
        departure_time = expected_departure or scheduled_departure

        departure_delay_minutes = (
            self._minutes_between_times(scheduled_departure, expected_departure) or 0
        )
        arrival_delay_minutes = (
            self._minutes_between_times(scheduled_arrival, expected_arrival) or 0
        )
        delay_minutes = max(departure_delay_minutes, arrival_delay_minutes)

        status = self._normalize_service_status(
            current_train.get("status"),
            is_cancelled=False,
            delay_minutes=delay_minutes,
        )

        service = {
            "train_code": train_code,
            "train_date": train_date,
            "departure": departure_time,
            "departure_time": departure_time,
            "scheduled_departure": scheduled_departure,
            "expected_departure": expected_departure,
            "arrival": arrival_time,
            "arrival_time": arrival_time,
            "scheduled_arrival": scheduled_arrival,
            "expected_arrival": expected_arrival,
            "estimated_arrival": expected_arrival,
            "destination": destination_stop.get("train_destination")
            or self.destination_name
            or self.destination,
            "origin": origin_stop.get("train_origin") or self.origin_name or self.origin,
            "delay_minutes": delay_minutes,
            "departure_delay_minutes": departure_delay_minutes,
            "arrival_delay_minutes": arrival_delay_minutes,
            "arrival_slipping": arrival_delay_minutes > 0,
            "status": status,
            "is_cancelled": False,
            "delay_reason": None,
            "cancellation_reason": None,
            "service_id": train_code,
            "operator": None,
            "platform": None,
            "calling_points": [],
            "route_stops": progress.get("route_stops", []),
            "segment_stop_count": progress.get("segment_stop_count", 0),
            "stops_completed": progress.get("stops_completed", 0),
            "progress_percent": progress.get("progress_percent", 0),
            "current_stop": progress.get("current_stop"),
            "next_stop": progress.get("next_stop"),
            "source": "current_trains",
        }

        return service

    def _dedupe_services_by_key(
        self, services: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """De-duplicate services using train/date/departure identity."""
        deduped: list[dict[str, Any]] = []
        seen: set[tuple[str | None, str | None, str | None]] = set()

        for service in services:
            key = (
                service.get("train_code") or service.get("service_id"),
                service.get("train_date"),
                service.get("scheduled_departure") or service.get("departure_time"),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(service)

        return deduped

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Irish Rail API."""
        _LOGGER.debug(
            "Fetching Irish Rail data for %s -> %s", self.origin, self.destination
        )

        async with self._update_interval_lock:
            new_interval = self._get_update_interval()
            if new_interval != self.update_interval:
                self.update_interval = new_interval

        try:
            raw_trains = await self.hass.async_add_executor_job(
                self.api.get_station_departures,
                self.origin,
                self.time_window,
            )
            current_trains = await self.hass.async_add_executor_job(
                self.api.get_current_trains,
            )

            _LOGGER.debug(
                "Fetched %s raw departures from origin %s and %s current trains",
                len(raw_trains),
                self.origin,
                len(current_trains),
            )

            services: list[dict[str, Any]] = []

            for t in raw_trains:
                is_cancelled = str(t.get("status") or "").strip().lower() in {
                    "cancelled",
                    "canceled",
                }

                scheduled_departure = self._clean_time(t.get("scheduled_departure"))
                expected_departure = self._clean_time(t.get("expected_departure"))
                departure_time = expected_departure or scheduled_departure

                movement_data = await self.hass.async_add_executor_job(
                    self._enrich_with_movements,
                    t,
                )

                if not self._service_matches_selected_route(t, movement_data):
                    _LOGGER.debug(
                        "Skipping service %s because it does not match route %s -> %s",
                        t.get("train_code"),
                        self.origin,
                        self.destination,
                    )
                    continue

                # Only use arrival times from movement data (destination arrival).
                # The departure board's Scharrival/Exparrival fields represent arrival
                # at the *origin* station, not the destination — using them as a fallback
                # falsely inflates arrival_delay_minutes and shows wrong arrival times.
                scheduled_arrival = movement_data.get("scheduled_arrival")
                expected_arrival = movement_data.get("expected_arrival")
                arrival_time = movement_data.get("arrival_time") or expected_arrival or scheduled_arrival

                departure_delay_minutes = (
                    self._minutes_between_times(
                        scheduled_departure,
                        expected_departure,
                    )
                    or 0
                )
                # Only compute arrival delay when movement data provides destination times
                arrival_delay_minutes = (
                    self._minutes_between_times(scheduled_arrival, expected_arrival) or 0
                ) if movement_data else 0

                try:
                    raw_delay_int = int(t.get("late") or 0)
                except (TypeError, ValueError):
                    raw_delay_int = 0

                delay_minutes = max(
                    raw_delay_int,
                    departure_delay_minutes,
                    arrival_delay_minutes,
                )

                status = self._normalize_service_status(
                    t.get("status"),
                    is_cancelled=is_cancelled,
                    delay_minutes=delay_minutes,
                )

                service = {
                    "train_code": t.get("train_code"),
                    "train_date": movement_data.get("train_date") or t.get("train_date"),
                    "departure": departure_time,
                    "departure_time": departure_time,
                    "scheduled_departure": scheduled_departure,
                    "expected_departure": expected_departure,
                    "arrival": arrival_time,
                    "arrival_time": arrival_time,
                    "scheduled_arrival": scheduled_arrival,
                    "expected_arrival": expected_arrival,
                    "estimated_arrival": expected_arrival,
                    "destination": t.get("destination"),
                    "origin": t.get("origin"),
                    "delay_minutes": delay_minutes,
                    "departure_delay_minutes": departure_delay_minutes,
                    "arrival_delay_minutes": arrival_delay_minutes,
                    "arrival_slipping": arrival_delay_minutes > 0,
                    "status": status,
                    "is_cancelled": is_cancelled,
                    "delay_reason": None,
                    "cancellation_reason": None,
                    "service_id": t.get("train_code"),
                    "operator": t.get("operator"),
                    "platform": t.get("platform"),
                    "calling_points": [],
                    "route_stops": movement_data.get("route_stops", []),
                    "segment_stop_count": movement_data.get("segment_stop_count", 0),
                    "stops_completed": movement_data.get("stops_completed", 0),
                    "progress_percent": movement_data.get("progress_percent", 0),
                    "current_stop": movement_data.get("current_stop"),
                    "next_stop": movement_data.get("next_stop"),
                    "source": "station_board",
                }
                service = self._normalize_future_route_state(service)
                services.append(service)

            for current_train in current_trains:
                active_service = await self.hass.async_add_executor_job(
                    self._build_active_service_from_current_train,
                    current_train,
                )
                if not active_service:
                    continue
                services.append(active_service)

            services = self._dedupe_services_by_key(services)

            data = {
                "services": services,
                "location_name": self.origin,
                "destination_name": self.destination,
                "nrcc_messages": [],
            }

            parsed_data = self._parse_data(data)
            self._failed_updates = 0

            # Record reliability observations (must be awaited — lives here, not in _parse_data)
            if self.reliability_tracker is not None:
                await self.reliability_tracker.async_record(
                    parsed_data.get("services", [])
                )

            return parsed_data

        except Exception as err:
            self._failed_updates += 1
            _LOGGER.error(
                "Error fetching Irish Rail data: %s (attempt %s/%s)",
                err,
                self._failed_updates,
                self._max_failed_updates,
            )

            if self._failed_updates >= self._max_failed_updates:
                raise UpdateFailed(f"Failed to fetch Irish Rail data: {err}") from err

            if self.data:
                _LOGGER.warning("Using last known data after failed update")
                return self.data

            raise UpdateFailed(f"Failed to fetch Irish Rail data: {err}") from err

    def _filter_departed_trains(
        self, services: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Filter out trains that have already departed origin when they are not active journeys."""
        if not services:
            return services

        now = dt_util.now()
        current_time_str = now.strftime("%H:%M")
        filtered_services = []

        for service in services:
            if service.get("is_cancelled", False) or self._is_active_journey(service):
                filtered_services.append(service)
                continue

            departure_time = (
                service.get("departure_time")
                or service.get("expected_departure")
                or service.get("scheduled_departure")
            )

            if not departure_time or not _TIME_FORMAT_RE.match(str(departure_time)):
                filtered_services.append(service)
                continue

            try:
                current_dt = datetime.strptime(
                    f"2000-01-01 {current_time_str}",
                    "%Y-%m-%d %H:%M",
                )
                departure_dt = datetime.strptime(
                    f"2000-01-01 {departure_time}",
                    "%Y-%m-%d %H:%M",
                )

                time_diff_seconds = (departure_dt - current_dt).total_seconds()

                if time_diff_seconds < -12 * 3600:
                    departure_dt += timedelta(days=1)
                    time_diff_seconds = (departure_dt - current_dt).total_seconds()
                elif time_diff_seconds > 12 * 3600:
                    departure_dt -= timedelta(days=1)
                    time_diff_seconds = (departure_dt - current_dt).total_seconds()

                grace_period_seconds = self.departed_train_grace_period * 60
                if time_diff_seconds >= -grace_period_seconds:
                    filtered_services.append(service)
                else:
                    _LOGGER.debug(
                        "Filtering out departed train: scheduled=%s expected=%s current=%s",
                        service.get("scheduled_departure"),
                        service.get("expected_departure"),
                        current_time_str,
                    )

            except (ValueError, TypeError) as err:
                _LOGGER.debug("Could not parse departure time for filtering: %s", err)
                filtered_services.append(service)

        return filtered_services

    def _parse_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Parse and enrich API data."""
        services = data.get("services", [])
        services = self._sort_services(services)

        active_trains: list[dict[str, Any]] = []
        upcoming_candidates: list[dict[str, Any]] = []

        for service in services:
            departure_time = (
                service.get("departure_time")
                or service.get("expected_departure")
                or service.get("scheduled_departure")
            )
            if not departure_time:
                continue

            arrival_time = (
                service.get("arrival_time")
                or service.get("expected_arrival")
                or service.get("scheduled_arrival")
            )

            service_status = self._normalize_service_status(
                service.get("status"),
                is_cancelled=service.get("is_cancelled", False),
                delay_minutes=int(service.get("delay_minutes", 0) or 0),
            )

            row = {
                "departure": departure_time,
                "departure_time": departure_time,
                "scheduled_departure": service.get("scheduled_departure"),
                "expected_departure": service.get("expected_departure"),
                "arrival": arrival_time,
                "arrival_time": arrival_time,
                "scheduled_arrival": service.get("scheduled_arrival"),
                "expected_arrival": service.get("expected_arrival"),
                "estimated_arrival": service.get("estimated_arrival"),
                "status": service_status,
                "delay_minutes": service.get("delay_minutes", 0),
                "departure_delay_minutes": service.get("departure_delay_minutes", 0),
                "arrival_delay_minutes": service.get("arrival_delay_minutes", 0),
                "arrival_slipping": service.get("arrival_slipping", False),
                "is_cancelled": service.get("is_cancelled", False),
                "destination": service.get("destination"),
                "origin": service.get("origin"),
                "service_id": service.get("service_id"),
                "operator": service.get("operator"),
                "platform": service.get("platform"),
                "route_stops": service.get("route_stops", []),
                "segment_stop_count": service.get("segment_stop_count", 0),
                "stops_completed": service.get("stops_completed", 0),
                "progress_percent": service.get("progress_percent", 0),
                "current_stop": service.get("current_stop"),
                "next_stop": service.get("next_stop"),
                "train_date": service.get("train_date"),
                "train_code": service.get("train_code"),
                "source": service.get("source", "station_board"),
            }

            if self._is_active_journey(service):
                active_trains.append(row)
            else:
                upcoming_candidates.append(row)

        active_trains = self._sort_services(
            self._dedupe_services_by_key(active_trains)
        )[: self.num_services]
        upcoming_trains = self._filter_departed_trains(upcoming_candidates)
        upcoming_trains = self._sort_services(
            self._dedupe_services_by_key(upcoming_trains)
        )[: self.num_services]

        # Recalculate counts and status on the filtered set (active + upcoming only).
        # Using the raw services list inflates status with old departed trains.
        _status_trains = active_trains + upcoming_trains
        cancelled_count = sum(1 for s in _status_trains if s.get("is_cancelled", False))
        delayed_count = sum(
            1
            for s in _status_trains
            if not s.get("is_cancelled", False) and s.get("delay_minutes", 0) > 0
        )
        on_time_count = sum(
            1
            for s in _status_trains
            if not s.get("is_cancelled", False) and s.get("delay_minutes", 0) <= 0
        )
        overall_status = self._calculate_overall_status(_status_trains)
        delay_info = self._collect_delay_info(_status_trains)
        summary = self._build_summary(on_time_count, delayed_count, cancelled_count, overall_status)

        # Fire event when overall status changes
        if self._previous_status is not None and overall_status != self._previous_status:
            self.hass.bus.async_fire(
                EVENT_STATUS_CHANGED,
                {
                    "entry_id": self.entry_id,
                    "commute_name": self.config.get("commute_name", ""),
                    "origin": self.origin,
                    "destination": self.destination,
                    "origin_name": self.origin_name or self.origin,
                    "destination_name": self.destination_name or self.destination,
                    "previous_status": self._previous_status,
                    "new_status": overall_status,
                },
            )
        self._previous_status = overall_status

        next_train = None
        for service in upcoming_trains:
            if not service.get("is_cancelled", False):
                next_train = service
                break

        countdown = "No trains"
        next_train_time = "No trains"

        if next_train:
            departure_time = (
                next_train.get("departure_time")
                or next_train.get("expected_departure")
                or next_train.get("scheduled_departure")
            )
            if departure_time:
                next_train_time = departure_time
                minutes_until = self._minutes_until(departure_time)

                if minutes_until is None:
                    countdown = "Unknown"
                else:
                    grace = int(getattr(self, "departed_train_grace_period", 2))
                    if minutes_until < -grace:
                        countdown = "Departed"
                    elif minutes_until <= 0:
                        countdown = "Due"
                    elif minutes_until == 1:
                        countdown = "1 min"
                    else:
                        countdown = f"{minutes_until} min"

        return {
            "origin": self.origin,
            "origin_name": self.origin_name or self.origin,
            "destination": self.destination,
            "destination_name": self.destination_name or self.destination,
            "route_name": (
                f"{self.origin_name or self.origin} → "
                f"{self.destination_name or self.destination}"
            ),
            "time_window": self.time_window,
            "services_tracked": len(services),
            "total_services_found": len(data.get("services", [])),
            "services": services,
            "upcoming_trains": upcoming_trains,
            "active_trains": active_trains,
            "live_trains": active_trains,
            "all_trains": active_trains + upcoming_trains,
            "on_time_count": on_time_count,
            "delayed_count": delayed_count,
            "cancelled_count": cancelled_count,
            "next_train": next_train,
            "next_train_time": next_train_time,
            "countdown": countdown,
            "overall_status": overall_status,
            "status": overall_status,
            "max_delay_minutes": delay_info["max_delay_minutes"],
            "disruption_reasons": delay_info["disruption_reasons"],
            "summary": summary,
            "last_updated": dt_util.now().isoformat(),
            "next_update": (dt_util.now() + self.update_interval).isoformat(),
            "nrcc_messages": data.get("nrcc_messages", []),
        }

    def _collect_delay_info(self, services: list[dict[str, Any]]) -> dict[str, Any]:
        """Collect delay information for display attributes."""
        max_delay = 0
        disruption_reasons = []

        for service in services:
            is_cancelled = service.get("is_cancelled", False)
            delay_minutes = int(service.get("delay_minutes", 0) or 0)

            if is_cancelled:
                reason = service.get("cancellation_reason")
                if reason and reason not in disruption_reasons:
                    disruption_reasons.append(reason)
            elif delay_minutes > 0:
                max_delay = max(max_delay, delay_minutes)
                reason = service.get("delay_reason")
                if reason and reason not in disruption_reasons:
                    disruption_reasons.append(reason)

        return {
            "max_delay_minutes": max_delay,
            "disruption_reasons": disruption_reasons,
        }

    def _calculate_overall_status(self, services: list[dict[str, Any]]) -> str:
        """Calculate overall commute status."""
        if not services:
            return STATUS_NORMAL

        if any(s.get("is_cancelled", False) for s in services):
            return STATUS_CRITICAL

        max_delay = max(
            (
                int(s.get("delay_minutes", 0) or 0)
                for s in services
                if not s.get("is_cancelled", False)
            ),
            default=0,
        )

        if max_delay >= self.severe_delay_threshold:
            return STATUS_SEVERE_DISRUPTION
        if max_delay >= self.major_delay_threshold:
            return STATUS_MAJOR_DELAYS
        if max_delay >= self.minor_delay_threshold:
            return STATUS_MINOR_DELAYS

        return STATUS_NORMAL

    def _build_summary(
        self,
        on_time_count: int,
        delayed_count: int,
        cancelled_count: int,
        overall_status: str,
    ) -> str:
        """Build a summary string for the commute status."""
        total = on_time_count + delayed_count + cancelled_count

        if total == 0:
            return "No trains found"

        if cancelled_count > 0:
            if cancelled_count == total:
                return "All trains cancelled"
            running = on_time_count + delayed_count
            return (
                f"{running} train{'s' if running != 1 else ''} running, "
                f"{cancelled_count} cancelled"
            )

        if overall_status == STATUS_NORMAL:
            if delayed_count > 0:
                return f"{on_time_count} on time, {delayed_count} delayed"
            return f"{on_time_count} on time"

        if overall_status == STATUS_MINOR_DELAYS:
            if delayed_count == total:
                return "Minor delays"
            return (
                f"{total} train{'s' if total != 1 else ''} running, "
                f"{delayed_count} minor delay{'s' if delayed_count != 1 else ''}"
            )

        if overall_status == STATUS_MAJOR_DELAYS:
            if delayed_count == total:
                return "Major delays"
            return (
                f"{total} train{'s' if total != 1 else ''} running, "
                f"{delayed_count} major delay{'s' if delayed_count != 1 else ''}"
            )

        if overall_status == STATUS_SEVERE_DISRUPTION:
            if delayed_count == total:
                return "Severe disruption"
            return (
                f"{total} train{'s' if total != 1 else ''} running, "
                f"{delayed_count} severely delayed"
            )

        if delayed_count > 0:
            return (
                f"{total} train{'s' if total != 1 else ''} running, "
                f"{delayed_count} delayed"
            )

        return f"{on_time_count} on time"
