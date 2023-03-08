"""Support for MobileAlerts binary sensors."""
from __future__ import annotations

import copy
from typing import Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from mobilealerts import Gateway, MeasurementType, Measurement, Sensor

from .base import MobileAlertesBaseCoordinator, MobileAlertesEntity
from .const import BINARY_MEASUREMENT_TYPES, DOMAIN

import logging

_LOGGER = logging.getLogger(__name__)

gateway_descriptions: list[tuple[
    BinarySensorEntityDescription, Callable[[Gateway], bool]]] = (
    (
        BinarySensorEntityDescription(
            key="use_proxy",
            name="Proxy is used",
            icon="mdi:server-network-off",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        lambda gateway: gateway.orig_use_proxy,
    ),
)

low_battery_entity_description = BinarySensorEntityDescription(
    key="battery",
    name="Battery",
    device_class=BinarySensorDeviceClass.BATTERY,
    entity_category=EntityCategory.DIAGNOSTIC,
)

descriptions: dict[MeasurementType:BinarySensorEntityDescription] = {
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

    def __init__(
        self,
        gateway: Gateway,
        description: BinarySensorEntityDescription,
        value: bool,
    ) -> None:
        """Initialize the sensor."""
        super().__init__()
        self._gateway = gateway
        self.entity_description = description
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
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, sensor, measurement)
        description: BinarySensorEntityDescription = None
        if self._measurement is None:
            description = low_battery_entity_description
        else:
            description = copy.deepcopy(descriptions[self._measurement.type])
            description.name = self._measurement.name

        description.key = description.device_class

        self.entity_description = description

        self._attr_name = f"{description.name}"
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
        self._attr_is_on = self._last_state.state == "on"
        _LOGGER.debug("update_data_from_last_state %s", self._attr_is_on)

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
    entities.append(MobileAlertesBinarySensor(coordinator, sensor, None))
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
        async_add_entities(create_binary_sensor_entities(coordinator, sensor))
