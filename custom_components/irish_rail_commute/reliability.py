"""Rolling 7-day reliability tracker for Irish Rail Commute."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

_STORAGE_VERSION = 1
_STORAGE_KEY_PREFIX = "irish_rail_commute_reliability_"
_WINDOW_DAYS = 7


class ReliabilityTracker:
    """Persist and query rolling 7-day on-time statistics per commute route."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._hass = hass
        self._entry_id = entry_id
        self._store: Store = Store(
            hass,
            _STORAGE_VERSION,
            f"{_STORAGE_KEY_PREFIX}{entry_id}",
        )
        self._observations: list[dict[str, Any]] = []
        self._loaded = False

    async def async_load(self) -> None:
        """Load persisted observations from storage."""
        data = await self._store.async_load()
        if data and isinstance(data.get("observations"), list):
            self._observations = data["observations"]
        self._loaded = True
        self._prune()

    async def async_record(self, services: list[dict[str, Any]]) -> None:
        """Record on-time/late status for each completed or upcoming service.

        Each (date, service_id) pair is stored at most once so repeated
        coordinator polls do not inflate the count.
        """
        if not self._loaded:
            await self.async_load()

        today = dt_util.now().strftime("%Y-%m-%d")

        seen_keys: set[tuple[str, str]] = {
            (obs["date"], obs["service_id"])
            for obs in self._observations
        }

        changed = False
        for service in services:
            service_id = service.get("service_id")
            if not service_id:
                continue

            key = (today, str(service_id))
            if key in seen_keys:
                continue

            is_cancelled = bool(service.get("is_cancelled", False))
            delay = int(service.get("delay_minutes", 0) or 0)
            on_time = not is_cancelled and delay < 3  # up to 2 min considered on time

            self._observations.append(
                {
                    "date": today,
                    "service_id": str(service_id),
                    "on_time": on_time,
                }
            )
            seen_keys.add(key)
            changed = True

        self._prune()

        if changed:
            await self._store.async_save({"observations": self._observations})

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _prune(self) -> None:
        """Remove observations older than the rolling window."""
        cutoff = (dt_util.now() - timedelta(days=_WINDOW_DAYS)).strftime("%Y-%m-%d")
        self._observations = [
            obs for obs in self._observations if obs.get("date", "") >= cutoff
        ]

    # ------------------------------------------------------------------
    # Properties used by the sensor
    # ------------------------------------------------------------------

    @property
    def reliability_percent(self) -> float | None:
        """Return the percentage of on-time trains in the last 7 days."""
        if not self._loaded or not self._observations:
            return None
        total = len(self._observations)
        on_time = sum(1 for obs in self._observations if obs.get("on_time"))
        return round((on_time / total) * 100, 1)

    @property
    def total_observations(self) -> int:
        """Total number of train observations in the rolling window."""
        return len(self._observations)

    @property
    def on_time_count(self) -> int:
        """Number of on-time trains in the rolling window."""
        return sum(1 for obs in self._observations if obs.get("on_time"))
