"""SMARTY Energy — read-only Home Assistant integration.

Reads the site snapshot SMARTY already has, so Home Assistant never needs its
own Modbus connection to the inverter or battery.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SmartyAuthError, SmartyClient, SmartyError
from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]

type SmartyConfigEntry = ConfigEntry[DataUpdateCoordinator[dict]]


async def async_setup_entry(hass: HomeAssistant, entry: SmartyConfigEntry) -> bool:
    client = SmartyClient(async_get_clientsession(hass), entry.data[CONF_HOST], entry.data[CONF_TOKEN])

    async def _update() -> dict:
        try:
            return await client.async_get_state()
        except SmartyAuthError as err:
            raise ConfigEntryAuthFailed("SMARTY token is invalid or revoked") from err
        except SmartyError as err:
            raise UpdateFailed(str(err)) from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        config_entry=entry,
        name=DOMAIN,
        update_method=_update,
        update_interval=SCAN_INTERVAL,
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SmartyConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
