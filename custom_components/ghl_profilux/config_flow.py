"""Einrichtung über die Oberfläche: IP-Adresse des ProfiLux eingeben."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .api import (
    GhlAccessError,
    GhlClient,
    GhlConnectionError,
    GhlOutdated,
    read_identity,
)
from .const import DEFAULT_PORT, DOMAIN


class GhlConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            client = GhlClient(user_input[CONF_HOST], user_input[CONF_PORT])
            try:
                async with client.connection() as conn:
                    _, serial = await read_identity(conn)
            except GhlAccessError:
                errors["base"] = "no_access"
            except GhlOutdated:
                errors["base"] = "outdated"
            except GhlConnectionError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"ProfiLux ({user_input[CONF_HOST]})", data=user_input
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
