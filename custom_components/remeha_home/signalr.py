"""Push updates for Remeha Home over the Azure SignalR service.

The official app keeps a SignalR connection open and reloads its data when the
hub sends a ``newMessage`` invocation (``ApplianceUpdate_Full``). This client
does the same: it negotiates a connection, listens, and asks the coordinator
for a refresh.
The coordinator keeps polling, so a broken push connection only means slower
updates, never missing entities. Nothing in here raises into Home Assistant.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import logging
import time
from collections.abc import Awaitable, Callable

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import RemehaHomeAPI

_LOGGER = logging.getLogger(__name__)

# SignalR JSON protocol framing: every message ends with this record separator.
RECORD_SEPARATOR = "\x1e"
HANDSHAKE_REQUEST = json.dumps({"protocol": "json", "version": 1}) + RECORD_SEPARATOR
PING_MESSAGE = json.dumps({"type": 6}) + RECORD_SEPARATOR

MESSAGE_TYPE_INVOCATION = 1
MESSAGE_TYPE_CLOSE = 7

APPLIANCE_UPDATE_TARGET = "newMessage"

# Send a keep-alive ping after this many seconds without inbound traffic.
PING_INTERVAL = 15
# Drop the connection when the server has been silent this long (it pings
# about every 15 seconds).
SILENCE_TIMEOUT = 45
# Negotiate a new connection this long before the access token expires.
RENEW_BEFORE_EXPIRY = 5 * 60
# Used when the access token cannot be decoded.
FALLBACK_TOKEN_LIFETIME = 30 * 60
# A connection that lasted at least this long resets the reconnect backoff.
HEALTHY_CONNECTION_SECONDS = 60
BACKOFF_MIN = 5
BACKOFF_MAX = 300


def _token_expiry(token: str) -> float:
    """Return the expiry time (epoch seconds) of a JWT without verifying it."""
    try:
        payload = token.split(".")[1]
        claims = json.loads(
            base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        )
        return float(claims["exp"])
    except (IndexError, KeyError, TypeError, ValueError, binascii.Error):
        return time.time() + FALLBACK_TOKEN_LIFETIME


class RemehaHomeSignalR:
    """Keep a SignalR connection open and report appliance changes."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: RemehaHomeAPI,
        on_appliance_updated: Callable[[], Awaitable[None]],
    ) -> None:
        """Initialize the push client."""
        self._hass = hass
        self._api = api
        self._on_appliance_updated = on_appliance_updated
        self._failures = 0
        self.connected = False

    async def async_run(self) -> None:
        """Connect and listen until cancelled. Meant as a background task."""
        delay = BACKOFF_MIN
        while True:
            started = time.monotonic()
            try:
                await self._async_connect_and_listen()
            except asyncio.CancelledError:
                raise
            except Exception as err:
                # Push is best effort: any error here must not reach Home Assistant.
                self._failures += 1
                log = _LOGGER.warning if self._failures == 1 else _LOGGER.debug
                log("Remeha Home push connection failed: %s", err)
            finally:
                self.connected = False

            if time.monotonic() - started >= HEALTHY_CONNECTION_SECONDS:
                delay = BACKOFF_MIN
            else:
                delay = min(delay * 2, BACKOFF_MAX)
            await asyncio.sleep(delay)

    async def _async_connect_and_listen(self) -> None:
        """Negotiate, connect and listen until the connection ends.

        Returns normally when the server closes the connection or when the
        access token is about to expire; the caller then reconnects.
        """
        negotiation = await self._api.async_negotiate_signalr()
        url = negotiation["url"]
        token = negotiation["accessToken"]
        renew_at = _token_expiry(token) - RENEW_BEFORE_EXPIRY

        session = async_get_clientsession(self._hass)
        async with session.ws_connect(
            url,
            headers={"Authorization": f"Bearer {token}"},
            heartbeat=None,
            timeout=aiohttp.ClientWSTimeout(ws_close=10),
        ) as ws:
            await ws.send_str(HANDSHAKE_REQUEST)
            handshake_done = False
            last_inbound = time.monotonic()

            while time.time() < renew_at:
                try:
                    msg = await ws.receive(timeout=PING_INTERVAL)
                except TimeoutError:
                    if time.monotonic() - last_inbound > SILENCE_TIMEOUT:
                        raise ConnectionError("no traffic from the server") from None
                    await ws.send_str(PING_MESSAGE)
                    continue

                if msg.type == aiohttp.WSMsgType.TEXT:
                    last_inbound = time.monotonic()
                    for frame in msg.data.split(RECORD_SEPARATOR):
                        if not frame:
                            continue
                        if not handshake_done:
                            handshake_done = True
                            self._handle_handshake(json.loads(frame))
                            continue
                        if await self._async_handle_message(json.loads(frame)):
                            return
                elif msg.type in (
                    aiohttp.WSMsgType.CLOSE,
                    aiohttp.WSMsgType.CLOSING,
                    aiohttp.WSMsgType.CLOSED,
                ):
                    _LOGGER.debug("Remeha Home push connection closed by server")
                    return
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    raise ConnectionError(str(ws.exception()))

    def _handle_handshake(self, response: dict) -> None:
        """Check the handshake response and mark the connection as up."""
        if response.get("error"):
            raise ConnectionError(f"handshake rejected: {response['error']}")
        self.connected = True
        self._failures = 0
        _LOGGER.debug("Remeha Home push connection established")

    async def _async_handle_message(self, message: dict) -> bool:
        """Dispatch one hub message. Returns True when the server ends the connection."""
        message_type = message.get("type")
        if message_type == MESSAGE_TYPE_CLOSE:
            _LOGGER.debug("Remeha Home push server closed: %s", message.get("error"))
            return True
        if message_type == MESSAGE_TYPE_INVOCATION:
            target = message.get("target")
            if target == APPLIANCE_UPDATE_TARGET:
                # Arguments look like [{"ApplianceId": ..., "MessageType": "ApplianceUpdate_Full"}]
                _LOGGER.debug("Remeha Home push: %s, refreshing", _describe(message))
                await self._on_appliance_updated()
            else:
                _LOGGER.debug("Remeha Home push: ignoring message %s", target)
        return False


def _describe(message: dict) -> str:
    """Return the message type of a push message for logging (no ids)."""
    arguments = message.get("arguments") or [{}]
    first = arguments[0] if isinstance(arguments[0], dict) else {}
    return str(first.get("MessageType", "unknown message type"))

