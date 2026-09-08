"""Constants and helpers for the Entity Watchdog integration."""

from __future__ import annotations

import uuid
from typing import Any

DOMAIN = "entity_watchdog"

CONF_NAME = "name"
CONF_ENTITY_ID = "entity_id"
CONF_TIMEOUT = "timeout"
CONF_WATCHERS = "watchers"
CONF_ID = "id"

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


def add_watcher(
    watchers: list[dict[str, Any]], data: dict[str, Any]
) -> list[dict[str, Any]]:
    new = {
        CONF_ID: uuid.uuid4().hex,
        CONF_NAME: data[CONF_NAME],
        CONF_ENTITY_ID: data[CONF_ENTITY_ID],
        CONF_TIMEOUT: data[CONF_TIMEOUT],
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
        }
        if w[CONF_ID] == watcher_id
        else w
        for w in watchers
    ]


def remove_watchers(
    watchers: list[dict[str, Any]], ids: list[str]
) -> list[dict[str, Any]]:
    drop = set(ids)
    return [w for w in watchers if w[CONF_ID] not in drop]
