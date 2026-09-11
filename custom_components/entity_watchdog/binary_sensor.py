"""Binary sensors that flag when monitored entities stop reporting."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.restore_state import RestoreEntity

try:  # HA 2025.2+
    from homeassistant.helpers.entity_platform import (
        AddConfigEntryEntitiesCallback as AddEntities,
    )
except ImportError:  # older cores
    from homeassistant.helpers.entity_platform import (
        AddEntitiesCallback as AddEntities,
    )
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ENTITY_ID,
    CONF_ID,
    CONF_NAME,
    get_watchers,
    timeout_seconds,
)

CHECK_INTERVAL = timedelta(seconds=30)
PLATFORM = "binary_sensor"


def _purge_removed(
    hass: HomeAssistant, entry: ConfigEntry, keep_unique_ids: set[str]
) -> None:
    """Drop registry entries for watchers that no longer exist."""
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.domain == PLATFORM and entity.unique_id not in keep_unique_ids:
            registry.async_remove(entity.entity_id)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntities,
) -> None:
    entities = [
        WatchdogBinarySensor(entry.entry_id, watcher)
        for watcher in get_watchers(entry)
    ]
    _purge_removed(hass, entry, {e.unique_id for e in entities})
    async_add_entities(entities)


class WatchdogBinarySensor(BinarySensorEntity, RestoreEntity):
    """On when the monitored entity has not reported within the wait time."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_should_poll = False
    _attr_has_entity_name = False

    def __init__(self, entry_id: str, watcher: dict) -> None:
        self._source: str = watcher[CONF_ENTITY_ID]
        self._timeout: int = timeout_seconds(watcher)
        self._attr_name = f"{watcher[CONF_NAME]} überfällig"
        self._attr_unique_id = f"{entry_id}_{watcher[CONF_ID]}_overdue"
        self._is_on = False
        self._last_seen: datetime | None = None
        # Raw state string of the source the last time it looked like a
        # genuine new report. Restarting HA alone must not change this.
        self._last_value: str | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._is_on = last_state.state == STATE_ON
            self._last_value = last_state.attributes.get("last_value")
            last_seen_str = last_state.attributes.get("last_seen")
            if last_seen_str:
                self._last_seen = dt_util.parse_datetime(last_seen_str)
        self._evaluate()
        self.async_on_remove(
            async_track_time_interval(self.hass, self._handle_interval, CHECK_INTERVAL)
        )
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._source], self._handle_source_change
            )
        )

    @callback
    def _handle_interval(self, now: datetime) -> None:
        self._evaluate()
        self.async_write_ha_state()

    @callback
    def _handle_source_change(self, event: Event[EventStateChangedData]) -> None:
        self._evaluate()
        self.async_write_ha_state()

    @callback
    def _evaluate(self) -> None:
        state = self.hass.states.get(self._source)
        if state is None or state.state == STATE_UNAVAILABLE:
            self._is_on = True
            return
        if state.state != self._last_value:
            # Genuine new reading from the source.
            self._last_value = state.state
            self._last_seen = state.last_reported or state.last_updated
        elif self._last_seen is None:
            # First run ever, nothing restored, nothing to compare yet.
            self._last_seen = state.last_reported or state.last_updated
        age = (dt_util.utcnow() - self._last_seen).total_seconds()
        self._is_on = age > self._timeout

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "monitored_entity": self._source,
            "last_seen": self._last_seen.isoformat() if self._last_seen else None,
            "last_value": self._last_value,
            "timeout_seconds": self._timeout,
        }
