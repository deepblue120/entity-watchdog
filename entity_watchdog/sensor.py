"""Timestamp sensors exposing when monitored entities last reported."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

try:  # HA 2025.2+
    from homeassistant.helpers.entity_platform import (
        AddConfigEntryEntitiesCallback as AddEntities,
    )
except ImportError:  # older cores
    from homeassistant.helpers.entity_platform import (
        AddEntitiesCallback as AddEntities,
    )
from homeassistant.helpers.event import async_track_state_change_event

from .const import CONF_ENTITY_ID, CONF_ID, CONF_NAME, get_watchers

PLATFORM = "sensor"


def _purge_removed(
    hass: HomeAssistant, entry: ConfigEntry, keep_unique_ids: set[str]
) -> None:
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
        WatchdogLastSeenSensor(entry.entry_id, watcher)
        for watcher in get_watchers(entry)
    ]
    _purge_removed(hass, entry, {e.unique_id for e in entities})
    async_add_entities(entities)


class WatchdogLastSeenSensor(SensorEntity):
    """Reports the timestamp of the monitored entity's last update."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_should_poll = False
    _attr_has_entity_name = False

    def __init__(self, entry_id: str, watcher: dict) -> None:
        self._source: str = watcher[CONF_ENTITY_ID]
        self._attr_name = f"{watcher[CONF_NAME]} zuletzt gesehen"
        self._attr_unique_id = f"{entry_id}_{watcher[CONF_ID]}_last_seen"
        self._value: datetime | None = None

    async def async_added_to_hass(self) -> None:
        self._evaluate()
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._source], self._handle_source_change
            )
        )

    @callback
    def _handle_source_change(self, event: Event[EventStateChangedData]) -> None:
        self._evaluate()
        self.async_write_ha_state()

    @callback
    def _evaluate(self) -> None:
        state = self.hass.states.get(self._source)
        if state is None or state.state == STATE_UNAVAILABLE:
            return
        self._value = state.last_reported or state.last_updated

    @property
    def native_value(self) -> datetime | None:
        return self._value
