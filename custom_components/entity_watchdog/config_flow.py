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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.loader import async_get_integration
from homeassistant.helpers.selector import (
    DeviceSelector,
    DeviceSelectorConfig,
    DurationSelector,
    DurationSelectorConfig,
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
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

CONF_DEVICE_ID = "device_id"
CONF_DEVICE_IDS = "device_ids"
CONF_INTEGRATION = "integration"

# Device classes tried in order when an entity has to be picked automatically.
# The watchdog only counts a report when the value changes, so the signal
# strength (changes on almost every report) comes first.
AUTO_DEVICE_CLASSES = ("signal_strength", "temperature", "humidity")


def _device_schema() -> vol.Schema:
    return vol.Schema(
        {vol.Required(CONF_DEVICE_ID): DeviceSelector(DeviceSelectorConfig())}
    )


def _watcher_schema(
    current: dict[str, Any] | None = None,
    entity_ids: list[str] | None = None,
) -> vol.Schema:
    current = current or {}
    fields: dict[Any, Any] = {}
    fields[vol.Required(CONF_NAME, default=current.get(CONF_NAME, ""))] = TextSelector()

    entity_selector_config = (
        EntitySelectorConfig(include_entities=entity_ids)
        if entity_ids
        else EntitySelectorConfig()
    )

    if CONF_ENTITY_ID in current:
        fields[vol.Required(CONF_ENTITY_ID, default=current[CONF_ENTITY_ID])] = (
            EntitySelector(entity_selector_config)
        )
    else:
        fields[vol.Required(CONF_ENTITY_ID)] = EntitySelector(entity_selector_config)

    fields[
        vol.Required(CONF_TIMEOUT, default=current.get(CONF_TIMEOUT, DEFAULT_TIMEOUT))
    ] = DurationSelector(DurationSelectorConfig(enable_day=False))
    return vol.Schema(fields)


def _device_name(device: dr.DeviceEntry) -> str:
    return device.name_by_user or device.name or device.id


def _pick_entity(entries: list[er.RegistryEntry], domain: str) -> str | None:
    """Pick the entity of a device that best shows that it is still reporting."""
    candidates = [
        e for e in entries if e.platform == domain and e.domain == "sensor"
    ]
    for device_class in AUTO_DEVICE_CLASSES:
        for entry in candidates:
            if (entry.device_class or entry.original_device_class) == device_class:
                return entry.entity_id
    return None


async def _integration_options(hass: HomeAssistant) -> list[dict[str, str]]:
    """Integrations that own at least one device, sorted by name."""
    device_reg = dr.async_get(hass)
    entry_ids = {
        entry_id
        for device in device_reg.devices.values()
        if device.disabled_by is None
        for entry_id in device.config_entries
    }
    domains = {
        entry.domain
        for entry in hass.config_entries.async_entries()
        if entry.entry_id in entry_ids and entry.domain != DOMAIN
    }
    options = []
    for domain in domains:
        try:
            label = (await async_get_integration(hass, domain)).name
        except Exception:  # noqa: BLE001 - fall back to the raw domain
            label = domain
        options.append({"value": domain, "label": label})
    return sorted(options, key=lambda o: o["label"].lower())


def _bulk_candidates(
    hass: HomeAssistant, domain: str, watched: set[str]
) -> tuple[dict[str, tuple[str, str]], int]:
    """Devices of an integration that can be added in bulk.

    Returns ({device_id: (name, entity_id)}, number of devices skipped
    because no suitable entity was found). Devices that already have a
    watched entity are left out entirely.
    """
    device_reg = dr.async_get(hass)
    entity_reg = er.async_get(hass)
    entry_ids = {e.entry_id for e in hass.config_entries.async_entries(domain)}
    candidates: dict[str, tuple[str, str]] = {}
    skipped = 0
    for device in device_reg.devices.values():
        if device.disabled_by is not None or not entry_ids & device.config_entries:
            continue
        entries = er.async_entries_for_device(
            entity_reg, device.id, include_disabled_entities=False
        )
        if any(e.entity_id in watched for e in entries):
            continue
        entity_id = _pick_entity(entries, domain)
        if entity_id is None:
            skipped += 1
            continue
        candidates[device.id] = (_device_name(device), entity_id)
    return candidates, skipped


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
    _selected_device: str | None = None
    _bulk_domain: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        watchers = get_watchers(self.config_entry)
        menu = ["add", "add_bulk"]
        if watchers:
            menu += ["edit", "remove"]
        return self.async_show_menu(step_id="init", menu_options=menu)

    async def async_step_add(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: pick the device."""
        if user_input is not None:
            self._selected_device = user_input[CONF_DEVICE_ID]
            return await self.async_step_add_entity()
        return self.async_show_form(step_id="add", data_schema=_device_schema())

    async def async_step_add_entity(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2: pick one of the device's entities."""
        if user_input is not None:
            watchers = add_watcher(get_watchers(self.config_entry), user_input)
            return self._save(watchers)

        entity_reg = er.async_get(self.hass)
        entries = er.async_entries_for_device(
            entity_reg, self._selected_device, include_disabled_entities=False
        )
        entity_ids = [entry.entity_id for entry in entries]

        return self.async_show_form(
            step_id="add_entity",
            data_schema=_watcher_schema(entity_ids=entity_ids),
        )

    async def async_step_add_bulk(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Bulk step 1: pick the integration."""
        if user_input is not None:
            self._bulk_domain = user_input[CONF_INTEGRATION]
            return await self.async_step_add_bulk_devices()
        options = await _integration_options(self.hass)
        if not options:
            return self.async_abort(reason="no_devices")
        return self.async_show_form(
            step_id="add_bulk",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_INTEGRATION): SelectSelector(
                        SelectSelectorConfig(options=options)
                    )
                }
            ),
        )

    async def async_step_add_bulk_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Bulk step 2: tick the devices, set one wait time for all of them."""
        watchers = get_watchers(self.config_entry)
        watched = {w[CONF_ENTITY_ID] for w in watchers}
        candidates, skipped = _bulk_candidates(self.hass, self._bulk_domain, watched)
        if not candidates:
            return self.async_abort(reason="no_devices")

        errors: dict[str, str] = {}
        if user_input is not None:
            selected = [d for d in user_input[CONF_DEVICE_IDS] if d in candidates]
            if not selected:
                errors["base"] = "no_selection"
            else:
                for device_id in selected:
                    name, entity_id = candidates[device_id]
                    watchers = add_watcher(
                        watchers,
                        {
                            CONF_NAME: name,
                            CONF_ENTITY_ID: entity_id,
                            CONF_TIMEOUT: user_input[CONF_TIMEOUT],
                        },
                    )
                return self._save(watchers)

        options = [
            {"value": device_id, "label": f"{name} ({entity_id})"}
            for device_id, (name, entity_id) in sorted(
                candidates.items(), key=lambda c: c[1][0].lower()
            )
        ]
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_DEVICE_IDS, default=[o["value"] for o in options]
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Required(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): DurationSelector(
                    DurationSelectorConfig(enable_day=False)
                ),
            }
        )
        return self.async_show_form(
            step_id="add_bulk_devices",
            data_schema=schema,
            errors=errors,
            description_placeholders={"skipped": str(skipped)},
        )

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
        current = next((w for w in watchers if w[CONF_ID] == self._selected), None)
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
