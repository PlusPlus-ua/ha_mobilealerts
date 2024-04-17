"""Base classes for the MobileAlerts integration."""
from __future__ import annotations

from typing import Any

import dataclasses
import logging
import time
import asyncio #Home Assistant's built-in scheduler
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from mobilealerts import Gateway, Measurement, MeasurementError, Proxy, Sensor

from .const import (
    DOMAIN,
    GATEWAY_DEF_NAME,
    MANUFACTURER,
    STATE_ATTR_BY_EVENT,
    STATE_ATTR_ERROR,
    STATE_ATTR_EXTRA,
    STATE_ATTR_LAST_UPDATED,
    STATE_ATTR_PRIOR_VALUE,
)
from .util import gateway_full_name

_LOGGER = logging.getLogger(__name__)


class MobileAlertesBaseCoordinator(DataUpdateCoordinator):
    """Base class to manage MobileAlerts data."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, proxy: Proxy, gateway: Gateway
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )
        self._entry: ConfigEntry = entry
        self._proxy: Proxy = proxy
        self._gateway: Gateway = gateway
        self._gateway_ip: str | None = gateway.ip_address
        self._proxy.set_handler(self)
        self._entities: dict[Measurement, MobileAlertesEntity] = {}

    async def async_get_or_create_gateway_device(self) -> None:         
        _id = self._gateway.gateway_id
        mac = ":".join(a + b for a, b in zip(_id[::2], _id[1::2]))
        device_registry = dr.async_get(self.hass)
        _LOGGER.debug("async_get_or_create_gateway_device id: %s, entry_id: %s, mac: %s", _id, self._entry.entry_id, mac)
        device_entry = device_registry.async_get_or_create(
            config_entry_id=self._entry.entry_id,
            configuration_url=self._gateway.url,
            identifiers={(DOMAIN, _id)},
            connections={(dr.CONNECTION_NETWORK_MAC, mac)},
            name=gateway_full_name(self._gateway),
            model=GATEWAY_DEF_NAME,
            manufacturer=MANUFACTURER,
            hw_version=self._gateway.version,
        )
        _LOGGER.debug("async_get_or_create_gateway_device device: %s", device_entry)

    async def _async_update_data(self):
        """Update state of the gateway."""
        _LOGGER.debug("_async_update_data")
        await self._gateway.ping(True)
        if self._gateway_ip != self._gateway.ip_address:
            await self.async_get_or_create_gateway_device()
            self._gateway_ip = self._gateway.ip_address

    def add_entities(self, entities: list[MobileAlertesEntity]) -> None:
        for entity in entities:
            if entity.measurement is not None:
                self._entities[entity.measurement] = entity

    def get_entity(self, measurement: Measurement) -> MobileAlertesEntity | None:
        return self._entities.get(measurement)

    @property
    def gateway(self) -> Gateway:
        """MobileAlerts gateway."""
        return self._gateway

    @property
    def proxy(self) -> Proxy:
        """MobileAlerts proxy."""
        return self._proxy


@dataclasses.dataclass(frozen=True)
class MobileAlertesExtraStoredData(ExtraStoredData):
    """Object to hold extra stored data."""

    attributes: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the number data."""
        return self.attributes

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> MobileAlertesExtraStoredData | None:
        """Initialize a stored number state from a dict."""
        return cls(
            {
                attr_name: restored[attr_name]
                for attr_name in restored.keys()
                if attr_name in STATE_ATTR_EXTRA
            }
        )


class MobileAlertesEntity(CoordinatorEntity, RestoreEntity):
    """MobileAlertes base entity."""

    def __init__(
        self, 
        coordinator: MobileAlertesBaseCoordinator, 
        sensor: Sensor, 
        measurement: Measurement | None
    ) -> None:
        """Initialize entity."""
        _LOGGER.debug(
            "MobileAlertesEntity(%r, %r, %r)", coordinator, sensor, measurement
        )
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_should_poll = False
        self._coordinator = coordinator
        self._sensor = sensor
        self._measurement: Measurement | None = measurement
        self._added_to_hass = False
        self._extra_state_attributes: dict[str, Any] | None = None
        self._attr_extra_state_attributes: dict[str, Any] | None = None
        self._last_state: State | None = None
        self._last_extra_data: ExtraStoredData | None = None
        self._value_is_calculated = False
        self._dependent_entities: list[MobileAlertesEntity] = []

    @property
    def sensor(self) -> Sensor:
        """MobileAlerts sensor."""
        return self._sensor

    @property
    def measurement(self) -> Measurement | None:
        """One measurement of MobileAlerts sensor."""
        return self._measurement

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        _LOGGER.debug("device_info")
        device_info = DeviceInfo(
            identifiers={(DOMAIN, self._sensor.sensor_id)},
            manufacturer=MANUFACTURER,
            model=self._sensor.model,
            name=self._sensor.name,
            via_device=(DOMAIN, self._sensor.parent.gateway_id),
        )

        area_registry = ar.async_get(self.hass)
        if area_registry.async_get_area_by_name(self._sensor.name):
            device_info["suggested_area"] = self._sensor.name

        return device_info
    
    def add_dependent(self, entity: MobileAlertesEntity) -> None:
        if not entity in self._dependent_entities:
            self._dependent_entities.append(entity)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        _LOGGER.debug("async_added_to_hass")
        await super().async_added_to_hass()
        self._added_to_hass = True
        self._last_state = await self.async_get_last_state()
        _LOGGER.debug("restored last state: %r", self._last_state)
        self._last_extra_data = await self.async_get_last_extra_data()
        _LOGGER.debug("restored last extra data: %r", self._last_extra_data)
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug("_handle_coordinator_update")
        updated: bool = False
        if self._value_is_calculated:
            _LOGGER.debug("self._value_is_calculated")
            if self._last_state is not None:
                self.update_data_from_last_state()
            self.update_data_from_sensor()
            updated = True
        elif self._sensor.last_update is not None:
            _LOGGER.debug("self._sensor.last_update is not None")
            self.update_data_from_sensor()
            updated = True
        elif self._last_state is not None:
            _LOGGER.debug(
                "_handle_coordinator_update self._last_state.state %s",
                self._last_state.state,
            )
            self.update_data_from_last_state()
            updated = True

        if updated:
            for entity in self._dependent_entities:
                entity.update_data_from_sensor()

        if updated and self._added_to_hass:
            attr: dict[str, Any] = {}
            if self._sensor.last_update is not None:
                attr[STATE_ATTR_LAST_UPDATED] = datetime.fromtimestamp(
                    self._sensor.timestamp
                ).isoformat()
                if self._measurement:
                    attr[STATE_ATTR_BY_EVENT] = self._sensor.by_event
                    if self._measurement.has_prior_value:
                        attr[STATE_ATTR_PRIOR_VALUE] = self._measurement.prior_value
                    if isinstance(self._measurement.value, MeasurementError):
                        attr[STATE_ATTR_ERROR] = self._measurement.value_str
                self._extra_state_attributes = attr
            elif self._last_extra_data is not None:
                self._extra_state_attributes = self._last_extra_data.as_dict()
                if self._extra_state_attributes is not None:
                    attr.update(self._extra_state_attributes)

            _LOGGER.debug("extra_state_attributes %s", attr)

            if self._attr_extra_state_attributes:
                self._attr_extra_state_attributes.update(attr)
            else:
                self._attr_extra_state_attributes = attr

            _LOGGER.debug("self._attr_extra_state_attributes %s", attr)

            #if self._sensor.last_update is not None or self._value_is_calculated:
            self.async_write_ha_state()

    def update_data_from_sensor(self) -> None:
        """Update data from the sensor."""

    def update_data_from_last_state(self) -> None:
        """Update data from stored last state."""

    @property
    def prior_value(self) -> float:
        result: float = -1
        if self._sensor is not None and self._sensor.last_update is not None:
            if self._measurement is not None and self._measurement.has_prior_value:
                if self._measurement.prior_value is not None:
                    result = float(self._measurement.prior_value)
        elif self._last_extra_data is not None:
            extra_state_attributes = self._last_extra_data.as_dict()
            if extra_state_attributes is not None:
                result_str = extra_state_attributes.get(STATE_ATTR_PRIOR_VALUE, None)
                if result_str is not None:
                    result = float(result_str)
        return result

    @property
    def last_update(self) -> float:
        result: float = 0
        if self._sensor is not None and self._sensor.last_update is not None:
            result = self._sensor.timestamp
            _LOGGER.debug(
                "self._sensor.last_update is not None %s", 
                datetime.fromtimestamp(result).isoformat(),
            )
        elif self._last_extra_data is not None:
            extra_state_attributes = self._last_extra_data.as_dict()
            if extra_state_attributes is not None:
                last_update_iso = extra_state_attributes.get(
                    STATE_ATTR_LAST_UPDATED, 
                    None,
                )
                if last_update_iso is not None:
                    result = datetime.fromisoformat(
                        last_update_iso).timestamp()
                    _LOGGER.debug(
                        "self._last_extra_data is not None %s", 
                        datetime.fromtimestamp(result).isoformat(),
                    )
        return result

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        result: bool = False
        if (
            self._sensor.update_period == 0 or
            self._value_is_calculated
        ):
            result = self._sensor.parent.is_online
        else:
            result = (self.last_update + 
                      self._sensor.update_period * 12.1) >= time.time()
        _LOGGER.debug("available %s", result)
        return result

    @property
    def extra_restore_state_data(self) -> ExtraStoredData | None:
        """Return sensor specific state data to be restored."""
        _LOGGER.debug(
            "extra_restore_state_data %s", 
            self._attr_extra_state_attributes,
        )
        return MobileAlertesExtraStoredData(
            self._attr_extra_state_attributes
        )
