"""Data update coordinator for the MobileAlerts integration."""
from __future__ import annotations

import logging
import asyncio #Home Assistant's built-in scheduler

from homeassistant.const import Platform
from homeassistant.components.network import async_get_source_ip
from mobilealerts import Gateway, Sensor, SensorHandler

from .base import MobileAlertesBaseCoordinator
from .binary_sensor import create_binary_sensor_entities
from .sensor import create_sensor_entities

_LOGGER = logging.getLogger(__name__)


class MobileAlertesDataCoordinator(MobileAlertesBaseCoordinator, SensorHandler):
    """Class to manage MobileAlerts data."""

    @property
    def gateway(self) -> Gateway:
        return self._gateway
    
    async def sensor_added(self, sensor: Sensor) -> None:
        _LOGGER.debug("sensor_added %r", sensor)

        binary_entity_component = self.hass.data[Platform.BINARY_SENSOR]
        binary_entity_platform = binary_entity_component._platforms.get(
            self._entry.entry_id, None
        )
        if binary_entity_platform is not None:
            self.hass.async_add_job(
                binary_entity_platform.async_add_entities(
                    create_binary_sensor_entities(self, sensor), True
                )
            )

        sensor_entity_component = self.hass.data[Platform.SENSOR]
        sensor_entity_platform = sensor_entity_component._platforms.get(
            self._entry.entry_id, None
        )
        if sensor_entity_platform is not None:
            self.hass.async_add_job(
                sensor_entity_platform.async_add_entities(
                    create_sensor_entities(self, sensor), True
                )
            )

        self.hass.config_entries.async_update_entry(self._entry)

    async def sensor_updated(self, sensor: Sensor) -> None:
        _LOGGER.debug("sensor_updated %r", sensor)
        self.async_set_updated_data({})
    
    async def update_proxy_ip(self) -> None:
        """Update the proxy IP on the MobileAlert gateway."""
        # Add your logic to update the proxy IP
        proxy_ip = await async_get_source_ip(self.hass, self._gateway.ip_address)
        _LOGGER.debug("Updating proxy IP to %s", proxy_ip)
        self._proxy.set_ip(proxy_ip)

    async def periodic_update_proxy_ip(self) -> None:
        """Periodically update the proxy IP."""
        while True:
            await self.update_proxy_ip()
            # Set the interval for updating the proxy IP (e.g., every Once a Week)
            await asyncio.sleep(86400)
