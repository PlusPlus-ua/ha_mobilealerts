"""Data update coordinator for the MobileAlerts integration."""
from __future__ import annotations

import logging

from homeassistant.const import Platform
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
