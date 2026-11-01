"""Constants and helpers for the Entity Watchdog integration."""

from __future__ import annotations

import uuid
from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo

DOMAIN = "entity_watchdog"

CONF_NAME = "name"
CONF_ENTITY_ID = "entity_id"
CONF_TIMEOUT = "timeout"
CONF_WATCHERS = "watchers"
CONF_ID = "id"
CONF_BATTERY_ENTITY = "battery_entity"
CONF_BATTERY_TYPE = "battery_type"
CONF_BATTERY_COUNT = "battery_count"

DEFAULT_BATTERY_COUNT = 1

# Selectable battery types (also the options of the battery type sensor).
BATTERY_TYPES = [
    "CR2032",
    "CR2450",
    "CR2477",
    "CR123A",
    "CR2",
    "CR1632",
    "CR1620",
    "CR1225",
    "CR1220",
    "CR927",
    "LR44 / AG13",
    "LR41 / AG3",
    "A23",
    "AAA",
    "AA",
    "C",
    "D",
    "9V",
    "18650",
    "Akku (fest verbaut)",
    "Sonstige",
]

# Default wait time: 1 hour, expressed as a duration dict.
DEFAULT_TIMEOUT = {"hours": 1, "minutes": 0, "seconds": 0}


def timeout_seconds(watcher: dict[str, Any]) -> int:
    """Total seconds from a watcher's stored duration dict."""
    t = watcher.get(CONF_TIMEOUT) or DEFAULT_TIMEOUT
    if isinstance(t, (int, float)):
        return int(t)
    return (
        int(t.get("hours", 0)) * 3600
        + int(t.get("minutes", 0)) * 60
        + int(t.get("seconds", 0))
    )


def get_watchers(entry) -> list[dict[str, Any]]:
    """Current list of watchers (options take precedence over data)."""
    if CONF_WATCHERS in entry.options:
        return list(entry.options[CONF_WATCHERS])
    return list(entry.data.get(CONF_WATCHERS, []))


def _battery_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Battery related fields from form input, always with all keys present.

    Keys are always stored (``None`` when unset) so that a cleared battery
    entity is not auto-detected again when the watcher is edited later.
    """
    battery_type = data.get(CONF_BATTERY_TYPE) or None
    count = None
    if battery_type:
        count = int(data.get(CONF_BATTERY_COUNT) or DEFAULT_BATTERY_COUNT)
    return {
        CONF_BATTERY_ENTITY: data.get(CONF_BATTERY_ENTITY) or None,
        CONF_BATTERY_TYPE: battery_type,
        CONF_BATTERY_COUNT: count,
    }


def add_watcher(
    watchers: list[dict[str, Any]], data: dict[str, Any]
) -> list[dict[str, Any]]:
    new = {
        CONF_ID: uuid.uuid4().hex,
        CONF_NAME: data[CONF_NAME],
        CONF_ENTITY_ID: data[CONF_ENTITY_ID],
        CONF_TIMEOUT: data[CONF_TIMEOUT],
        **_battery_fields(data),
    }
    return [*watchers, new]


def update_watcher(
    watchers: list[dict[str, Any]], watcher_id: str, data: dict[str, Any]
) -> list[dict[str, Any]]:
    return [
        {
            **w,
            CONF_NAME: data[CONF_NAME],
            CONF_ENTITY_ID: data[CONF_ENTITY_ID],
            CONF_TIMEOUT: data[CONF_TIMEOUT],
            **_battery_fields(data),
        }
        if w[CONF_ID] == watcher_id
        else w
        for w in watchers
    ]


def watcher_device_info(watcher: dict[str, Any]) -> DeviceInfo:
    """Device that groups all entities belonging to one watcher."""
    return DeviceInfo(
        identifiers={(DOMAIN, watcher[CONF_ID])},
        name=watcher[CONF_NAME],
        manufacturer="Entity Watchdog",
        model="Watchdog",
    )


def remove_watchers(
    watchers: list[dict[str, Any]], ids: list[str]
) -> list[dict[str, Any]]:
    drop = set(ids)
    return [w for w in watchers if w[CONF_ID] not in drop]
