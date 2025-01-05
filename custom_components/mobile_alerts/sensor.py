"""Support for MobileAlerts binary sensors."""
from __future__ import annotations
from datetime import datetime
import time

from typing import Any, Callable

import copy
import logging
import dataclasses

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    PERCENTAGE,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from mobilealerts import Gateway, Measurement, MeasurementError, MeasurementType, Sensor

from .base import MobileAlertesBaseCoordinator, MobileAlertesEntity
from .const import (
    BINARY_MEASUREMENT_TYPES,
    DOMAIN,
    ENUM_MEASUREMENT_TYPES,
    LAST_RAIN_PERIOD,
    STATE_ATTR_LAST_UPDATED,
    STATE_ATTR_MEASUREMTS,
)

_LOGGER = logging.getLogger(__name__)


gateway_descriptions: list[tuple[SensorEntityDescription, Callable[[Gateway], str]]] = [
    (
        SensorEntityDescription(
            key="proxy",
            icon="mdi:server-network",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        lambda gateway: ("http://%s:%s") % (
            gateway.orig_proxy,
            gateway.orig_proxy_port,
        ),
    ),
]

last_rain_description = SensorEntityDescription(
    key="last_rain",
    icon="mdi:water",
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfLength.MILLIMETERS,
)

last_hour_rain_description = SensorEntityDescription(
    key="last_hour_rain",
    icon="mdi:water",
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfLength.MILLIMETERS,
)

last_day_rain_description = SensorEntityDescription(
    key="last_day_rain",
    icon="mdi:water",
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfLength.MILLIMETERS,
)

descriptions: dict[MeasurementType, SensorEntityDescription] = {
    MeasurementType.TEMPERATURE: SensorEntityDescription(
        key=None,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    MeasurementType.HUMIDITY: SensorEntityDescription(
        key=None,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    MeasurementType.CO2: SensorEntityDescription(
        key=None,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
    ),
    MeasurementType.AIR_PRESSURE: SensorEntityDescription(
        key=None,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.HPA,
    ),
    MeasurementType.RAIN: SensorEntityDescription(
        key=None,
        icon="mdi:water",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
    ),
    MeasurementType.TIME_SPAN: SensorEntityDescription(
        key=None,
        icon="mdi:timer",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
    ),
    MeasurementType.WIND_SPEED: SensorEntityDescription(
        key=None,
        icon="mdi:weather-windy",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
    ),
    MeasurementType.GUST: SensorEntityDescription(
        key=None,
        icon="mdi:weather-windy",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
    ),
    MeasurementType.WIND_DIRECTION: SensorEntityDescription(
        key=None,
        icon="mdi:windsock",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=DEGREE,
    ),
    MeasurementType.KEY_PRESSED: SensorEntityDescription(
        key=None,
        icon="mdi:button-pointer",
        device_class=SensorDeviceClass.ENUM,
        state_class=SensorStateClass.MEASUREMENT,
        options=["none", "green", "orange", "red", "yellow"],
    ),
    MeasurementType.KEY_PRESS_TYPE: SensorEntityDescription(
        key=None,
        icon="mdi:button-pointer",
        device_class=SensorDeviceClass.ENUM,
        options=["none", "short", "double", "long"],
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
        description = dataclasses.replace(
            description,
            translation_key = description.key
        )
        self.entity_description = description
        self._attr_has_entity_name = True
        self._attr_device_class = None
        self._attr_native_value = value
        self._attr_unique_id = f"{self._gateway.gateway_id}-{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        _LOGGER.debug("device_info")
        return DeviceInfo(
            identifiers={(DOMAIN, self._gateway.gateway_id)},
        )


class MobileAlertesSensor(MobileAlertesEntity, SensorEntity):
    """Representation of a MobileAlertes sensor."""

    def __init__(
        self,
        coordinator: Any,
        sensor: Sensor,
        measurement: Measurement | None,
        description: SensorEntityDescription | None = None,
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
            
            if description.device_class == SensorDeviceClass.TEMPERATURE:
                if measurement.prefix:
                    if measurement.prefix == "Pool":
                        description = dataclasses.replace(
                            description,
                            icon = "mdi:pool-thermometer"
                        )
                    else:
                        description = dataclasses.replace(
                            description,
                            icon = "mdi:home-thermometer"
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
        if self._measurement is not None:
            if (self._measurement.type == MeasurementType.RAIN and
                    self._measurement.prior_value is None):
                self._measurement.prior_value = self._attr_native_value
            if isinstance(self._measurement.value, MeasurementError):
                self._attr_native_value = None
            elif self._measurement.type in ENUM_MEASUREMENT_TYPES:
                self._attr_native_value = self._measurement.value_str
            else:
                self._attr_native_value = self._measurement.value
        else:
            self._attr_native_value = None
        _LOGGER.debug("update_data_from_sensor %s", self._attr_native_value)

    def update_data_from_last_state(self) -> None:
        """Update data from stored last state."""
        if self._last_state is not None:
            self._attr_native_value = self._last_state.state
            self._last_state = None
        else:
            self._attr_native_value = None
        _LOGGER.debug("update_data_from_last_state %s",
                      self._attr_native_value)

'''
class MobileAlertesRainSensor(MobileAlertesSensor):
    """Representation of a MobileAlertes general rain sensor."""

    def __init__(
        self,
        coordinator: MobileAlertesBaseCoordinator,
        sensor: Sensor,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, sensor, None, description)
        self._value_is_calculated = True
        self._attr_should_poll = True
        self._last_update: float = 0.0
        self._rain_sensor: MobileAlertesSensor | None = None

    def _get_rain_sensor(self) -> MobileAlertesSensor | None:
        if self._rain_sensor is None:
            rain_entity = self._coordinator.get_entity(
                self._sensor.measurements[1])
            if type(rain_entity) == MobileAlertesSensor:
                self._rain_sensor = rain_entity
                self._rain_sensor.add_dependent(self)

        return self._rain_sensor

    def _get_last_rain_value(self) -> float | None:
        rain_sensor = self._get_rain_sensor()
        if rain_sensor is not None:
            curr_value = float(rain_sensor._attr_native_value)
            prior_value = rain_sensor.prior_value
            rain_sensor.last_update
            _LOGGER.debug(
                "last_rain curr_value %s prior_value %s self._last_update %s rain_sensor.last_update %s",
                curr_value,
                prior_value,
                datetime.fromtimestamp(self._last_update).isoformat(),
                datetime.fromtimestamp(rain_sensor.last_update).isoformat(),
            )
            if prior_value >= 0 and rain_sensor.last_update > self._last_update:
                return curr_value - prior_value
            else:
                return None
        else:
            return None

    def update_data_from_last_state(self) -> None:
        """Update data from stored last state."""
        super().update_data_from_last_state()
        _LOGGER.debug("rain update_data_from_last_state")
        if self._last_extra_data is not None:
            _LOGGER.debug(
                "rain update_data_from_last_state self._last_extra_data is not None")
            extra_state_attributes = self._last_extra_data.as_dict()
            if extra_state_attributes is not None:
                last_update_iso = extra_state_attributes.get(
                    STATE_ATTR_LAST_UPDATED, None)
                if last_update_iso is not None:
                    _LOGGER.debug(
                        "rain update_data_from_last_state last_update_iso %s", last_update_iso)
                    self._last_update = datetime.fromisoformat(
                        last_update_iso).timestamp()
                    self._last_extra_data = None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        rain_sensor = self._get_rain_sensor()
        return rain_sensor is not None and rain_sensor.available


class MobileAlertesLastRainSensor(MobileAlertesRainSensor):
    """Representation of a MobileAlertes last rain sensor."""

    def update_data_from_sensor(self) -> None:
        """Update data from the sensor."""
        self._attr_native_value = self._get_last_rain_value()
        if self._attr_native_value is None:
            self._attr_native_value = 0.0
        _LOGGER.debug("rain update_data_from_sensor %s",
                      self._attr_native_value)
        attr: dict[str, Any] = {
            STATE_ATTR_LAST_UPDATED:
            datetime.fromtimestamp(self._last_update).isoformat()
        }
        self._attr_extra_state_attributes = attr
'''

class MobileAlertesPeriodRainSensor(MobileAlertesSensor):
    """Representation of a MobileAlertes rain by period sensor."""

    def __init__(
        self,
        coordinator: MobileAlertesBaseCoordinator,
        sensor: Sensor,
        description: SensorEntityDescription,
        period: float,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, sensor, None, description)
        self._value_is_calculated = True
        self._attr_should_poll = True
        self._period = period
        self._last_update: float = 0.0
        self._measurements: dict[float, float] = {}
        self._rain_sensor: MobileAlertesSensor | None = None

    def _get_rain_sensor(self) -> MobileAlertesSensor | None:
        if self._rain_sensor is None:
            rain_entity = self._coordinator.get_entity(
                self._sensor.measurements[1])
            if type(rain_entity) == MobileAlertesSensor:
                self._rain_sensor = rain_entity
                self._rain_sensor.add_dependent(self)

        _LOGGER.debug("_get_rain_sensor %s", self._rain_sensor)
        return self._rain_sensor

    def _get_last_rain_value(self) -> float | None:
        result: float | None = None
        rain_sensor = self._get_rain_sensor()
        if rain_sensor is not None:
            curr_value = float(rain_sensor._attr_native_value)
            prior_value = rain_sensor.prior_value
            if (
                prior_value >= 0 and 
                rain_sensor.last_update > self._last_update
            ):
                result = curr_value - prior_value

        _LOGGER.debug("_get_last_rain_value %s", result)
        return result

    def update_data_from_sensor(self) -> None:
        """Update data from the sensor."""
        now = time.time()
        total: float = 0.0
        rain_sensor = self._get_rain_sensor()
        if rain_sensor:
            last_rain = self._get_last_rain_value()
            if last_rain:
                last_rain_time = rain_sensor.last_update
                self._measurements[last_rain_time] = last_rain
                _LOGGER.debug(
                    "period_rain update_data_from_sensor added (%s: %s)",
                    datetime.fromtimestamp(last_rain_time).isoformat(),
                    last_rain
                )
                self._last_update = last_rain_time

        for measurement_time in list(self._measurements.keys()):
            if measurement_time < (now - self._period):
                _LOGGER.debug(
                    "period_rain update_data_from_sensor removed (%s: %s)",
                    datetime.fromtimestamp(measurement_time).isoformat(),
                    self._measurements[measurement_time]
                )
                self._measurements.pop(measurement_time)
            else:
                total += self._measurements[measurement_time]
        self._attr_native_value = total
        _LOGGER.debug(
            "period_rain update_data_from_sensor result %s",
            self._attr_native_value
        )

        attr: dict[str, Any] = {}
        attr[STATE_ATTR_LAST_UPDATED] = datetime.fromtimestamp(
            self._last_update
        ).isoformat()
        attr[STATE_ATTR_MEASUREMTS] = [
            (
                datetime.fromtimestamp(measurement_time).isoformat(),
                self._measurements[measurement_time]
            )
            for measurement_time in self._measurements.keys()
        ]
        self._attr_extra_state_attributes = attr
        _LOGGER.debug(
            "period_rain update_data_from_sensor _extra_state_attributes %s",
            self._attr_extra_state_attributes
        )

    def update_data_from_last_state(self) -> None:
        """Update data from stored last state."""
        super().update_data_from_last_state()
        _LOGGER.debug("period_rain update_data_from_last_state")
        if self._last_extra_data is not None:
            extra_state_attributes = self._last_extra_data.as_dict()
            if extra_state_attributes is not None:
                measurements_iso = extra_state_attributes.get(
                    STATE_ATTR_MEASUREMTS, None)
                if measurements_iso is not None:
                    _LOGGER.debug(
                        "period_rain update_data_from_last_state %s",
                        measurements_iso,
                    )
                    measurements = {
                        datetime.fromisoformat(measurement[0]).timestamp():
                        float(measurement[1])
                        for measurement in measurements_iso
                    }
                    self._measurements = measurements
                last_update_iso = extra_state_attributes.get(
                    STATE_ATTR_LAST_UPDATED, None)
                if last_update_iso is not None:
                    _LOGGER.debug(
                        "rain update_data_from_last_state last_update_iso %s", 
                        last_update_iso
                    )
                    self._last_update = datetime.fromisoformat(
                        last_update_iso).timestamp()


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
    entities = [
        MobileAlertesSensor(coordinator, sensor, measurement)
        for measurement in sensor.measurements
        if measurement.type not in BINARY_MEASUREMENT_TYPES
    ]
    for measurement in sensor.measurements:
        if measurement.type == MeasurementType.RAIN:
            entities.append(MobileAlertesPeriodRainSensor(
                coordinator,
                sensor,
                last_rain_description,
                LAST_RAIN_PERIOD,
            ))
            entities.append(MobileAlertesPeriodRainSensor(
                coordinator,
                sensor,
                last_hour_rain_description,
                60 * 60.0,
            ))
            entities.append(MobileAlertesPeriodRainSensor(
                coordinator,
                sensor,
                last_day_rain_description,
                24 * 60 * 60.0,
            ))
            break
    return entities


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
        entities = create_sensor_entities(coordinator, sensor)
        async_add_entities(entities)
        coordinator.add_entities(entities)
