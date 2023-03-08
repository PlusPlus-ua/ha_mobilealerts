"""Support for MobileAlerts binary sensors."""
from __future__ import annotations

import copy
from typing import Any, Callable

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
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from mobilealerts import Gateway, MeasurementError, MeasurementType, Measurement, Sensor

from .base import MobileAlertesBaseCoordinator, MobileAlertesEntity
from .const import (
    BINARY_MEASUREMENT_TYPES, 
    ENUM_MEASUREMENT_TYPES, DOMAIN, 
    MobileAlertsDeviceClass,
)

import logging

_LOGGER = logging.getLogger(__name__)


gateway_descriptions: list[tuple[SensorEntityDescription, Callable[[Gateway], str]]] = (
    (
        SensorEntityDescription(
            key="proxy",
            name="Proxy",
            icon="mdi:server-network",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        lambda gateway: ("http://%s:%s") % (
            gateway.orig_proxy,
            gateway.orig_proxy_port,
        ),
    ),
)

descriptions: dict[MeasurementType:SensorEntityDescription] = {
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
    MeasurementType.CO2: SensorEntityDescription(
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
        native_unit_of_measurement=LENGTH_MILLIMETERS,
    ),
    MeasurementType.TIME_SPAN: SensorEntityDescription(
        key=None,
        icon="mdi:timer",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=TIME_SECONDS,
    ),
    MeasurementType.WIND_SPEED: SensorEntityDescription(
        key=None,
        icon="mdi:weather-windy",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=SPEED_METERS_PER_SECOND,
    ),
    MeasurementType.GUST: SensorEntityDescription(
        key=None,
        icon="mdi:weather-windy",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=SPEED_METERS_PER_SECOND,
    ),
    MeasurementType.WIND_DIRECTION: SensorEntityDescription(
        key=None,
        icon="mdi:windsock",
        native_unit_of_measurement=DEGREE,
    ),
    MeasurementType.KEY_PRESSED: SensorEntityDescription(
        key=None,
        icon="mdi:button-pointer",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=MobileAlertsDeviceClass.KEY_PRESSED,
    ),
    MeasurementType.KEY_PRESS_TYPE: SensorEntityDescription(
        key=None,
        icon="mdi:button-pointer",
        device_class=MobileAlertsDeviceClass.KEY_PRESS_TYPE,
    ),
}


class MobileAlertesGatewaySensor(SensorEntity):

    def __init__(
        self,
        gateway: Gateway,
        description: SensorEntityDescription,
        value: str,
    ) -> None:
        """Initialize the sensor."""
        _LOGGER.debug(
            "MobileAlertesGatewaySensor(%r, %r, %s)", gateway, description, value
        )
        super().__init__()
        self._gateway = gateway
        self.entity_description = description
        self._attr_device_class = None
        self._attr_native_value = value
        self._attr_unique_id = f"{self._gateway.gateway_id}-{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        _LOGGER.debug("device_info")
        return  DeviceInfo(
            identifiers={(DOMAIN, self._gateway.gateway_id)},
        )

class MobileAlertesSensor(MobileAlertesEntity, SensorEntity):
    """Representation of a MobileAlertes binary sensor."""

    def __init__(
        self, coordinator: Any, sensor: Sensor, measurement: Measurement
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, sensor, measurement)

        description: SensorEntityDescription = None
        description = copy.deepcopy(descriptions[self._measurement.type])
        description.name = self._measurement.name
        description.key = (
            self._measurement.name.lower().replace(" ", "_").replace("/", "_")
        )
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
        if isinstance(self._measurement.value, MeasurementError):
            self._attr_native_value = None
        elif self._measurement.type in ENUM_MEASUREMENT_TYPES:
            self._attr_native_value = self._measurement.value_str
        else:
            self._attr_native_value = self._measurement.value
        _LOGGER.debug("update_data_from_sensor %s", self._attr_native_value)

    def update_data_from_last_state(self) -> None:
        """Update data from stored last state."""
        if self._measurement.type in ENUM_MEASUREMENT_TYPES:
            self._attr_native_value = self._measurement.unit[0]
        else:
            self._attr_native_value = self._last_state.state
        _LOGGER.debug("update_data_from_last_state %s", self._attr_native_value)


def create_gateway_sensor_entities(
    gateway: Gateway,
) -> list[MobileAlertesGatewaySensor]:
    return [
        MobileAlertesGatewaySensor(
            gateway,
            description,
            get_value(gateway)
        )
        for description, get_value in gateway_descriptions
    ]

def create_sensor_entities(
    coordinator: MobileAlertesBaseCoordinator,
    sensor: Sensor,
) -> list[MobileAlertesSensor]:
    """Create list of sensor entities"""
    return [
        MobileAlertesSensor(coordinator, sensor, measurement)
        for measurement in sensor.measurements
        if measurement.type not in BINARY_MEASUREMENT_TYPES
    ]

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MobileAlerts sensors."""
    _LOGGER.debug("async_setup_entry %s", entry)

    coordinator: MobileAlertesBaseCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(create_gateway_sensor_entities(coordinator.gateway))

    sensors: list[Sensor] = coordinator.gateway.sensors
    for sensor in sensors:
        async_add_entities(create_sensor_entities(coordinator, sensor))
