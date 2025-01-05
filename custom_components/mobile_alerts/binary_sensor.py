"""Support for MobileAlerts binary sensors."""
from __future__ import annotations

from typing import Callable

import copy
import datetime
import logging
import time
import dataclasses

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from mobilealerts import Gateway, Measurement, MeasurementType, Sensor

from .base import MobileAlertesBaseCoordinator, MobileAlertesEntity
from .const import BINARY_MEASUREMENT_TYPES, DOMAIN, LAST_RAIN_PERIOD
from .sensor import MobileAlertesSensor

_LOGGER = logging.getLogger(__name__)

gateway_descriptions: list[tuple[
    BinarySensorEntityDescription, Callable[[Gateway], bool]]] = [
    (
        BinarySensorEntityDescription(
            key="use_proxy",
            icon="mdi:server-network-off",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        lambda gateway: bool(gateway.orig_use_proxy),
    ),
]

low_battery_description = BinarySensorEntityDescription(
    key="battery",
    device_class=BinarySensorDeviceClass.BATTERY,
    entity_category=EntityCategory.DIAGNOSTIC,
)

is_raining_description = BinarySensorEntityDescription(
    key="is_raining",
    device_class=BinarySensorDeviceClass.MOISTURE,
)

descriptions: dict[MeasurementType, BinarySensorEntityDescription] = {
    MeasurementType.WETNESS: BinarySensorEntityDescription(
        key=None,
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    MeasurementType.ALARM: BinarySensorEntityDescription(
        key=None,
        device_class=BinarySensorDeviceClass.SMOKE,
    ),
    MeasurementType.DOOR_WINDOW: BinarySensorEntityDescription(
        key=None,
        device_class=BinarySensorDeviceClass.DOOR,
    ),
}


class MobileAlertesGatewayBinarySensor(BinarySensorEntity):
    """Representation of a MobileAlertes is gateway uses proxy binary sensor."""

    def __init__(
        self,
        gateway: Gateway,
        description: BinarySensorEntityDescription,
        value: bool,
    ) -> None:
        """Initialize the sensor."""
        super().__init__()
        self._gateway = gateway
        description = dataclasses.replace(
            description,
            translation_key = description.key
        )
        self.entity_description = description
        self._attr_has_entity_name = True
        self._attr_device_class = None
        self._attr_is_on = value
        if value and description.icon is not None:
            self._attr_icon = description.icon.removesuffix("-off")
        self._attr_unique_id = f"{self._gateway.gateway_id}-{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return  DeviceInfo(
            identifiers={(DOMAIN, self._gateway.gateway_id)},
        )
    
    
class MobileAlertesBinarySensor(MobileAlertesEntity, BinarySensorEntity):
    """Representation of a MobileAlertes binary sensor."""

    def __init__(
        self,
        coordinator: MobileAlertesBaseCoordinator,
        sensor: Sensor,
        measurement: Measurement | None,
        description: BinarySensorEntityDescription | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, sensor, measurement)
        if description is None and measurement is not None:
            description = copy.deepcopy(descriptions[measurement.type])
            description = dataclasses.replace(
                description,
                name = measurement.name,
                key = (
                    measurement.name.lower().replace(" ", "_").replace("/", "_")
                )
            )

        if description is not None and description.translation_key is None:
            description = dataclasses.replace(
                description,
                translation_key = description.key
            )

        _LOGGER.debug("translation_key %s", description.translation_key)

        self.entity_description = description

        if description is not None:
            self._attr_unique_id = f"{self._sensor.sensor_id}-{description.key}"

    def update_data_from_sensor(self) -> None:
        """Update data from the sensor."""
        if self._measurement is not None:
            self._attr_is_on = self._measurement.value
        else:
            self._attr_is_on = self._sensor.low_battery
        _LOGGER.debug("update_data_from_sensor %s", self._attr_is_on)

    def update_data_from_last_state(self) -> None:
        """Update data from stored last state."""
        if self._last_state is not None:
            self._attr_is_on = self._last_state.state == "on"
            self._last_state = None
        else:
            self._attr_is_on = None
        _LOGGER.debug("update_data_from_last_state %s", self._attr_is_on)


class MobileAlertesIsRainingBinarySensor(MobileAlertesBinarySensor):
    """Representation of a MobileAlertes is raining binary sensor."""

    def __init__(
        self,
        coordinator: MobileAlertesBaseCoordinator,
        sensor: Sensor,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, sensor, None, description)
        self._value_is_calculated = True
        self._attr_should_poll = True
        self._attr_is_on = False

    def update_data_from_sensor(self) -> None:
        """Update data from the sensor."""
        value: bool = False
        time_span_sensor = self._coordinator.get_entity(self._sensor.measurements[2])
        if time_span_sensor is not None:
            time_span_sensor.add_dependent(self)
            if time_span_sensor._attr_native_value is not None:
                _LOGGER.debug(
                    "is_raining time_span_sensor is not None %s %s",
                    time_span_sensor._attr_native_value,
                    time.ctime(time_span_sensor.last_update),
                )
                value = (
                    (int(float(time_span_sensor._attr_native_value)) == 0) and
                    (
                        time_span_sensor.last_update >= 
                        time.time() - LAST_RAIN_PERIOD
                    )
                )
        self._attr_is_on = value
        _LOGGER.debug("is_raining update_data_from_sensor %s", self._attr_is_on)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        time_span_sensor = self._coordinator.get_entity(self._sensor.measurements[2])
        return time_span_sensor is not None and time_span_sensor.available

    

def create_gateway_binary_sensor_entities(
    gateway: Gateway,
) -> list[MobileAlertesGatewayBinarySensor]:
    return [
        MobileAlertesGatewayBinarySensor(
            gateway,
            description,
            get_value(gateway)
        )
        for description, get_value in gateway_descriptions
    ]

def create_binary_sensor_entities(
    coordinator: MobileAlertesBaseCoordinator,
    sensor: Sensor,
) -> list[MobileAlertesBinarySensor]:
    """Create list of binary sensor entities"""
    entities = [
        MobileAlertesBinarySensor(coordinator, sensor, measurement)
        for measurement in sensor.measurements
        if measurement.type in BINARY_MEASUREMENT_TYPES
    ]
    entities.append(MobileAlertesBinarySensor(
        coordinator, 
        sensor,
        None,
        low_battery_description,
    ))
    for measurement in sensor.measurements:
        if measurement.type == MeasurementType.RAIN:
            entities.append(MobileAlertesIsRainingBinarySensor(
                coordinator,
                sensor,
                is_raining_description,
            ))
            break
    return entities

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MobileAlerts binary sensors."""
    _LOGGER.debug("async_setup_entry %s", entry)

    coordinator: MobileAlertesBaseCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(create_gateway_binary_sensor_entities(coordinator.gateway))

    sensors: list[Sensor] = coordinator.gateway.sensors
    for sensor in sensors:
        entities = create_binary_sensor_entities(coordinator, sensor)
        async_add_entities(entities)
        coordinator.add_entities(entities)
