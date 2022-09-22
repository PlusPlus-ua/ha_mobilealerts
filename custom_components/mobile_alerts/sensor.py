"""Support for MobileAlerts binary sensors."""
#from __future__ import annotations

import copy
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    LENGTH_MILLIMETERS,
    PERCENTAGE,
    CONCENTRATION_PARTS_PER_MILLION,
    PRESSURE_HPA,
    TEMP_CELSIUS,
    TIME_SECONDS,
    SPEED_METERS_PER_SECOND,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback


from .base import MobileAlertesBaseCoordinator, MobileAlertesEntity
from .const import BINARY_MAEASUREMENT_TYPES, DOMAIN, MobileAlertsDeviceClass
from .mobilealerts import MeasurementError, MeasurementType, Measurement, Sensor

import logging

_LOGGER = logging.getLogger(__name__)

descriptions: dict[MeasurementType: SensorEntityDescription] = {
    MeasurementType.TEMPERATURE: SensorEntityDescription(
        key=None,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    MeasurementType.HUMIDITY: SensorEntityDescription(
        key=None,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
    ),
    MeasurementType.AIR_QUALITY: SensorEntityDescription(
        key=None,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
    ),
    MeasurementType.AIR_PRESSURE: SensorEntityDescription(
        key=None,
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=PRESSURE_HPA,
    ),
    MeasurementType.RAIN: SensorEntityDescription(
        key=None,
        icon="mdi:weather-rainy",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=LENGTH_MILLIMETERS
    ),
    MeasurementType.TIME_SPAN: SensorEntityDescription(
        key=None,
        icon="mdi:timer",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=TIME_SECONDS
    ),
    MeasurementType.WIND_SPEED: SensorEntityDescription(
        key=None,
        icon="mdi:weather-windy",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SPEED_METERS_PER_SECOND
    ),
    MeasurementType.GUST: SensorEntityDescription(
        key=None,
        icon="mdi:weather-windy",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SPEED_METERS_PER_SECOND
    ),
    MeasurementType.WIND_DIRECTION: SensorEntityDescription(
        key=None,
        icon="mdi:windsock",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=DEGREE
    ),
    MeasurementType.KEY_PRESSED: SensorEntityDescription(
        key=None,
        icon="mdi:button-pointer",
        device_class=MobileAlertsDeviceClass.KEY_PRESSED,
    ),
    MeasurementType.KEY_PRESS_TYPE: SensorEntityDescription(
        key=None,
        icon="mdi:button-pointer",
        device_class=MobileAlertsDeviceClass.KEY_PRESS_TYPE,
    ),
}


class MobileAlertesSensor(MobileAlertesEntity, SensorEntity):
    """Representation of a MobileAlertes binary sensor."""

    def __init__(self,
                 coordinator: Any,
                 sensor: Sensor,
                 measurement: Measurement | None
                 ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, sensor, measurement)

        description: SensorEntityDescription = None
        description = copy.deepcopy(descriptions[self._measurement.type])
        description.name = self._measurement.name
        description.key = self._measurement.name.lower().replace(' ', '_').replace('/', '_')
        if description.device_class == SensorDeviceClass.TEMPERATURE:
            if self._measurement.prefix:
                if self._measurement.prefix == "Pool":
                    description.icon = "mdi:pool-thermometer"
                else:
                    description.icon = "mdi:home-thermometer"

        self.entity_description = description

        self._attr_name = f"{description.name}"
        self._attr_unique_id = f"{self._sensor.sensor_id}-{description.key}"

    def update_data_from_sensor(self) -> None:
        if type(self._measurement.value) is MeasurementError:
            self._attr_native_value = None
        elif self._measurement.type in [MeasurementType.KEY_PRESSED, MeasurementType.KEY_PRESS_TYPE]:
            self._attr_native_value = self._measurement.value_str
        else:
            self._attr_native_value = self._measurement.value
        _LOGGER.debug("update_data_from_sensor %s", self._attr_native_value)

    def update_data_from_last_state(self) -> None:
        """Update data from stored last state."""
        self._attr_native_value = self._last_state.state
        _LOGGER.debug("update_data_from_last_state %s", self._attr_native_value)


def create_sensor_entities(
    coordinator: MobileAlertesBaseCoordinator,
    sensor: Sensor,
) -> list[MobileAlertesSensor]:
    return [
        MobileAlertesSensor(coordinator, sensor, measurement)
        for measurement in sensor.measurements
        if measurement.type not in BINARY_MAEASUREMENT_TYPES
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    _LOGGER.debug("async_setup_entry %s", entry)

    coordinator: MobileAlertesBaseCoordinator = hass.data[DOMAIN][entry.entry_id]
    sensors: list[Sensor] = coordinator.gateway.sensors

    for sensor in sensors:
        async_add_entities(create_sensor_entities(coordinator, sensor))
