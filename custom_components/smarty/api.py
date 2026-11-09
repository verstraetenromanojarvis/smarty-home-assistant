"""Minimal client for the read-only SMARTY Home Assistant API."""
from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .const import REQUEST_TIMEOUT_S, STATE_PATH


class SmartyError(Exception):
    """Base error."""


class SmartyAuthError(SmartyError):
    """Token invalid, revoked, or the account lost access."""


class SmartyRateLimited(SmartyError):
    """Too many requests for this token."""


def normalize_host(host: str) -> str:
    host = str(host or "").strip().rstrip("/")
    if not host.startswith(("https://", "http://")):
        host = "https://" + host
    return host


class SmartyClient:
    def __init__(self, session: aiohttp.ClientSession, host: str, token: str) -> None:
        self._session = session
        self._host = normalize_host(host)
        self._token = token.strip()

    async def async_get_state(self) -> dict[str, Any]:
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT_S):
                response = await self._session.get(
                    self._host + STATE_PATH,
                    headers={"Authorization": f"Bearer {self._token}", "Accept": "application/json"},
                )
                if response.status == 401:
                    raise SmartyAuthError("Token rejected")
                if response.status == 429:
                    raise SmartyRateLimited("Rate limited")
                if response.status != 200:
                    raise SmartyError(f"HTTP {response.status}")
                data = await response.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise SmartyError(str(err) or type(err).__name__) from err
        if not isinstance(data, dict) or "site" not in data:
            raise SmartyError("Unexpected response")
        return data
