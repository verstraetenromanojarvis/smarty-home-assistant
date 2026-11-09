"""Config flow: paste the server URL and the read-only token from the SMARTY app."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SmartyAuthError, SmartyClient, SmartyError, SmartyRateLimited, normalize_host
from .const import DEFAULT_HOST, DOMAIN


class SmartyConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _validate(self, host: str, token: str) -> tuple[dict | None, str | None]:
        client = SmartyClient(async_get_clientsession(self.hass), host, token)
        try:
            return await client.async_get_state(), None
        except SmartyAuthError:
            return None, "invalid_auth"
        except SmartyRateLimited:
            return None, "rate_limited"
        except SmartyError:
            return None, "cannot_connect"

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = normalize_host(user_input[CONF_HOST])
            token = user_input[CONF_TOKEN].strip()
            state, error = await self._validate(host, token)
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(str(state["site"]["id"]))
                self._abort_if_unique_id_configured(updates={CONF_HOST: host, CONF_TOKEN: token})
                return self.async_create_entry(
                    title=state["site"].get("name") or "SMARTY",
                    data={CONF_HOST: host, CONF_TOKEN: token},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                    vol.Required(CONF_TOKEN): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            token = user_input[CONF_TOKEN].strip()
            state, error = await self._validate(entry.data[CONF_HOST], token)
            if error:
                errors["base"] = error
            elif str(state["site"]["id"]) != entry.unique_id:
                errors["base"] = "wrong_site"
            else:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_TOKEN: token})
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
            errors=errors,
        )
