"""Config flow for MobileAlerts."""
from __future__ import annotations

from typing import Any

import logging
import socket

import voluptuous as vol
from homeassistant.components import dhcp, onboarding
from homeassistant.components.network import async_get_source_ip
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from mobilealerts import Gateway

from .const import CONF_GATEWAY, CONF_SEND_DATA_TO_CLOUD, DOMAIN
from .util import gateway_full_name, gateway_short_name

_LOGGER = logging.getLogger(__name__)


class MobileAlertsOptionsFlowHandler(OptionsFlow):
    """Handle a MobileAlerts options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        return await self.async_step_proxy(user_input)

    async def async_step_proxy(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="proxy",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SEND_DATA_TO_CLOUD,
                        default=self.config_entry.options.get(
                            CONF_SEND_DATA_TO_CLOUD, True
                        ),
                    ): bool,
                }
            ),
        )


class MobileAlertsConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a MobileAlerts config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._gateway: Gateway | None = None
        self._gateways: dict[str, Gateway] = {}

    async def async_step_single_gateway(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure the gateway."""
        gateway = self._gateway
        assert gateway is not None
        _LOGGER.debug("async_step_single_gateway gateway %s", gateway)

        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            await self.async_set_unique_id(gateway.gateway_id, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=gateway_short_name(gateway),
                data=user_input,
            )

        return self.async_show_form(
            step_id="single_gateway",
            description_placeholders={"name": gateway_full_name(gateway)},
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SEND_DATA_TO_CLOUD,
                        default=True,
                    ): bool,
                }
            ),
        )

    async def async_step_multiple_gateways(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select a gateway."""

        if user_input is not None:
            assert self._gateways is not None
            gateway_id = user_input[CONF_GATEWAY]
            await self.async_set_unique_id(gateway_id, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            gateway = self._gateways[gateway_id]
            return self.async_create_entry(
                title=gateway_short_name(gateway),
                data={},
            )

        configured_gateways = self._async_current_ids()

        gateways = []
        ip_address = await async_get_source_ip(self.hass)
        try:
            gateways = await Gateway.discover(ip_address)
        except socket.error as err:
            _LOGGER.error("Gateways discovery error %r", err)

        if len(gateways) == 0:
            return self.async_abort(reason="no_devices_found")

        self._gateways = {gateway.gateway_id: gateway for gateway in gateways}

        unconfigured_gateways = [
            gateway
            for gateway in gateways
            if gateway.gateway_id not in configured_gateways
        ]

        if not unconfigured_gateways:
            return self.async_abort(reason="no_gateways")

        if len(unconfigured_gateways) == 1:
            self._gateway = unconfigured_gateways[0]
            return await self.async_step_single_gateway()

        return self.async_show_form(
            step_id="multiple_gateways",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_GATEWAY): vol.In(
                        {
                            gateway.gateway_id: gateway_short_name(gateway)
                            for gateway in unconfigured_gateways
                        }
                    ),
                }
            ),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        return await self.async_step_multiple_gateways(user_input)

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Handle a flow initialized by DHCP discovery."""
        _LOGGER.debug("async_step_dhcp %s", discovery_info)

        gateway_id = discovery_info.macaddress.upper().replace(":", "")
        await self.async_set_unique_id(gateway_id)
        self._abort_if_unique_id_configured()

        gateway = Gateway(gateway_id)
        try:
            if not await gateway.init():
                return self.async_abort(reason="unknown")
        except socket.error as err:
            _LOGGER.error("Gateways initialization error %r", err)
            return self.async_abort(reason="unknown")

        self._gateway = gateway
        self.context["title_placeholders"] = {"name": gateway_full_name(gateway)}
        return await self.async_step_single_gateway()
    
    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> MobileAlertsOptionsFlowHandler:
        """Get the options flow for this handler."""
        return MobileAlertsOptionsFlowHandler(config_entry)
