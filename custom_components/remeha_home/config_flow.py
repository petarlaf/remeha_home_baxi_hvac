"""Config flow for Remeha Home."""

import logging
from typing import Any, Mapping

import voluptuous as vol

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .const import DOMAIN
from .api import RemehaHomeAuthFailed

_LOGGER = logging.getLogger(__name__)


class RemehaHomeLoginFlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle RemehaHome authentication."""

    DOMAIN = DOMAIN

    def __init__(self):
        """Create a Remeha Home login flow."""
        super().__init__()

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return _LOGGER

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> dict[str, Any]:
        """Perform reauth upon an API authentication error."""
        _LOGGER.debug("reauth triggered")
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
                last_step=False,
            )
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        await self.async_set_unique_id(DOMAIN)
        # The OAuth2 implementation is registered once in __init__.py's async_setup.
        # We do not re-register it here to avoid duplicate registrations on reauth.
        return await super().async_step_user(user_input)

    async def async_step_auth(self, user_input=None) -> dict[str, Any]:
        """Create an entry for auth."""
        errors = {}

        if user_input and CONF_EMAIL in user_input and CONF_PASSWORD in user_input:
            self.external_data = {
                "email": user_input[CONF_EMAIL],
                "password": user_input[CONF_PASSWORD],
            }
            try:
                return await self.async_step_creation()
            except RemehaHomeAuthFailed:
                errors["base"] = "failed_to_authenticate"

        if user_input is None or errors:
            return self.async_show_form(
                step_id="auth",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_EMAIL, default=""): str,
                        vol.Required(CONF_PASSWORD, default=""): str,
                    }
                ),
                last_step=False,
                errors=errors,
            )

        return self.async_abort(reason="failed_to_authenticate")

    async def async_oauth_create_entry(self, data: dict) -> dict:
        """Create an oauth config entry or update existing entry for reauth."""
        existing_entry = await self.async_set_unique_id(DOMAIN)
        if existing_entry:
            self.hass.config_entries.async_update_entry(existing_entry, data=data)
            await self.hass.config_entries.async_reload(existing_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        return self.async_create_entry(title=self.external_data["email"], data=data)
