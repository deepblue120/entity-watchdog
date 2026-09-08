"""Config and options flow for Entity Watchdog."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    DurationSelector,
    DurationSelectorConfig,
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
)

from .const import (
    CONF_ENTITY_ID,
    CONF_ID,
    CONF_NAME,
    CONF_TIMEOUT,
    CONF_WATCHERS,
    DEFAULT_TIMEOUT,
    DOMAIN,
    add_watcher,
    get_watchers,
    remove_watchers,
    update_watcher,
)


def _watcher_schema(current: dict[str, Any] | None = None) -> vol.Schema:
    current = current or {}
    fields: dict[Any, Any] = {}
    fields[vol.Required(CONF_NAME, default=current.get(CONF_NAME, ""))] = TextSelector()
    if CONF_ENTITY_ID in current:
        fields[vol.Required(CONF_ENTITY_ID, default=current[CONF_ENTITY_ID])] = (
            EntitySelector(EntitySelectorConfig())
        )
    else:
        fields[vol.Required(CONF_ENTITY_ID)] = EntitySelector(EntitySelectorConfig())
    fields[
        vol.Required(CONF_TIMEOUT, default=current.get(CONF_TIMEOUT, DEFAULT_TIMEOUT))
    ] = DurationSelector(DurationSelectorConfig(enable_day=False))
    return vol.Schema(fields)


def _select_schema(watchers: list[dict[str, Any]], multiple: bool) -> vol.Schema:
    options = [{"value": w[CONF_ID], "label": w[CONF_NAME]} for w in watchers]
    return vol.Schema(
        {
            vol.Required(CONF_ID): SelectSelector(
                SelectSelectorConfig(options=options, multiple=multiple)
            )
        }
    )


class EntityWatchdogConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create the single Entity Watchdog hub entry."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title="Entity Watchdog", data={CONF_WATCHERS: []}
            )
        # Simple confirm form; sensors are added afterwards via Configure.
        return self.async_show_form(step_id="user")

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> "EntityWatchdogOptionsFlow":
        return EntityWatchdogOptionsFlow()


class EntityWatchdogOptionsFlow(OptionsFlow):
    """Add / edit / remove the monitored sensors."""

    _selected: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        watchers = get_watchers(self.config_entry)
        menu = ["add"]
        if watchers:
            menu += ["edit", "remove"]
        return self.async_show_menu(step_id="init", menu_options=menu)

    async def async_step_add(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            watchers = add_watcher(get_watchers(self.config_entry), user_input)
            return self._save(watchers)
        return self.async_show_form(step_id="add", data_schema=_watcher_schema())

    async def async_step_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        watchers = get_watchers(self.config_entry)
        if user_input is not None:
            self._selected = user_input[CONF_ID]
            return await self.async_step_edit_form()
        return self.async_show_form(
            step_id="edit", data_schema=_select_schema(watchers, multiple=False)
        )

    async def async_step_edit_form(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        watchers = get_watchers(self.config_entry)
        if user_input is not None:
            watchers = update_watcher(watchers, self._selected, user_input)
            return self._save(watchers)
        current = next(
            (w for w in watchers if w[CONF_ID] == self._selected), None
        )
        return self.async_show_form(
            step_id="edit_form", data_schema=_watcher_schema(current)
        )

    async def async_step_remove(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        watchers = get_watchers(self.config_entry)
        if user_input is not None:
            watchers = remove_watchers(watchers, user_input[CONF_ID])
            return self._save(watchers)
        return self.async_show_form(
            step_id="remove", data_schema=_select_schema(watchers, multiple=True)
        )

    def _save(self, watchers: list[dict[str, Any]]) -> ConfigFlowResult:
        return self.async_create_entry(title="", data={CONF_WATCHERS: watchers})
