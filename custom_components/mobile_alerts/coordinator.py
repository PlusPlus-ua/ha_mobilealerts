"""Data update coordinator for the MobileAlerts integration."""
from __future__ import annotations

import logging

import json
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.mqtt import async_publish
from homeassistant.const import Platform
from mobilealerts import Gateway, MeasurementType, Sensor, SensorHandler

from .base import MobileAlertesBaseCoordinator
from .binary_sensor import create_binary_sensor_entities
from .const import (
    CONF_MODE,
    CONF_MQTT_TOPIC_PREFIX,
    DEFAULT_MQTT_TOPIC_PREFIX,
    MODE_ENTITIES,
    MODE_MQTT,
)
from .sensor import create_sensor_entities

_LOGGER = logging.getLogger(__name__)


# Measurement types published as arrays (templates read index [0]).
_ARRAY_KEY = {
    MeasurementType.HUMIDITY: "humidity",
    MeasurementType.AIR_PRESSURE: "airPressure",
    MeasurementType.CO2: "co2",
    MeasurementType.RAIN: "rain",
}

# Measurement types published as scalars.
_SCALAR_KEY = {
    MeasurementType.WIND_SPEED: "windSpeed",
    MeasurementType.GUST: "gustSpeed",
    MeasurementType.WETNESS: "wetness",
    MeasurementType.DOOR_WINDOW: "contact",
}

_COMPASS = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]


def _compass(degrees: float) -> str:
    """Convert wind direction in degrees to a 16-point compass string."""
    return _COMPASS[int((degrees % 360) / 22.5 + 0.5) % 16]


# Rain sensor packet type (also the first byte of the sensor id).
_RAIN_SENSOR_TYPE = 0x08


def _event_time(value: int) -> int:
    """Decode a rain event time: top 2 bits select the scale, low 14 bits the count."""
    scale = (value >> 14) & 3
    value &= (1 << 14) - 1
    return value * (86400, 3600, 60, 1)[scale]


class MobileAlertesDataCoordinator(MobileAlertesBaseCoordinator, SensorHandler):
    """Class to manage MobileAlerts data."""

    @property
    def gateway(self) -> Gateway:
        return self._gateway

    @property
    def _mode(self) -> str:
        return self._entry.options.get(CONF_MODE, MODE_ENTITIES)

    async def _publish_mqtt(self, sensor: Sensor) -> None:
        """Publish sensor readings as sarnau-compatible MQTT JSON."""
        payload: dict[str, Any] = {}
        for measurement in sensor.measurements:
            value = measurement.value
            if not isinstance(value, (int, float)):
                continue
            if isinstance(value, float):
                # The library computes some values as `x * 0.1`, which introduces
                # binary floating-point noise (e.g. 18.400000000000002). Round to
                # the sensors' real resolution so published values stay clean.
                value = round(value, 4)
            m_type = measurement.type
            if m_type == MeasurementType.TEMPERATURE:
                key = "temperature" if not measurement.prefix else "temperatureExt"
                payload.setdefault(key, []).append(value)
            elif m_type in _ARRAY_KEY:
                payload.setdefault(_ARRAY_KEY[m_type], []).append(value)
            elif m_type == MeasurementType.WIND_DIRECTION:
                payload["directionDegree"] = value
                payload["direction"] = _compass(value)
            elif m_type in _SCALAR_KEY:
                payload[_SCALAR_KEY[m_type]] = value
        if not payload:
            return

        # Drop a packet already published: the gateway can deliver the same
        # sensor packet more than once, and a repeat would otherwise be counted
        # again by consumers that accumulate (rain event counters). maserver
        # skipped packets whose transmit counter was unchanged; do the same.
        if self._last_published_counter.get(sensor.sensor_id) == sensor.counter:
            _LOGGER.debug(
                "Skipping duplicate packet from %s (counter %s)",
                sensor.sensor_id,
                sensor.counter,
            )
            return
        self._last_published_counter[sensor.sensor_id] = sensor.counter

        # Per-sensor metadata (maserver-compatible keys)
        payload["id"] = sensor.sensor_id.lower()
        payload["battery"] = "low" if sensor.low_battery else "ok"
        payload["offline"] = False
        if sensor.timestamp:
            payload["t"] = datetime.fromtimestamp(
                sensor.timestamp, timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        if sensor.update_period:
            payload["lastTransmit"] = sensor.update_period
        if sensor.by_event is not None:
            payload["by_event"] = bool(sensor.by_event)
        payload["counter"] = sensor.counter
        payload["model"] = sensor.model
        payload["name"] = sensor.name

        # Rain sensors: expose the raw event counter and event times parsed
        # straight from the packet, which the library does not surface (needed
        # for rain-gauge templates). Layout follows MMMMobileAlerts ID08.
        raw = sensor.last_update
        if (
            isinstance(raw, (bytes, bytearray))
            and len(raw) >= 36
            and raw[6] == _RAIN_SENSOR_TYPE
        ):
            body = raw[14:]
            payload["eventCounter"] = int.from_bytes(body[2:4], "big")
            payload["eventTimes"] = [
                _event_time(int.from_bytes(body[4 + 2 * i : 6 + 2 * i], "big"))
                for i in range(9)
            ]

        prefix = self._entry.options.get(
            CONF_MQTT_TOPIC_PREFIX, DEFAULT_MQTT_TOPIC_PREFIX
        )
        topic = f"{prefix}{sensor.sensor_id.lower()}/json"
        _LOGGER.debug("Publishing MQTT %s -> %s", topic, payload)
        await async_publish(self.hass, topic, json.dumps(payload), retain=True)

    def _add_sensor_entities(self, sensor: Sensor) -> None:
        """Create entities for a newly discovered sensor on each loaded platform."""
        for platform, create_entities in (
            (Platform.BINARY_SENSOR, create_binary_sensor_entities),
            (Platform.SENSOR, create_sensor_entities),
        ):
            add_entities = self._add_entities_callbacks.get(platform)
            if add_entities is None:
                continue
            entities = create_entities(self, sensor)
            # Register with the coordinator first, exactly as platform setup
            # does, so calculated entities (e.g. rain per period) can find the
            # entities they depend on.
            self.add_entities(entities)
            add_entities(entities, True)

    async def sensor_added(self, sensor: Sensor) -> None:
        _LOGGER.debug("sensor_added %r", sensor)

        if self._mode == MODE_MQTT:
            await self._publish_mqtt(sensor)
            return

        self._add_sensor_entities(sensor)

        self.hass.config_entries.async_update_entry(self._entry)

    async def sensor_updated(self, sensor: Sensor) -> None:
        _LOGGER.debug("sensor_updated %r", sensor)
        if self._mode == MODE_MQTT:
            await self._publish_mqtt(sensor)
            return
        self.async_set_updated_data({})
