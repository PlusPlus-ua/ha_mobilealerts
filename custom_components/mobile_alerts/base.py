"""Base classes for the MobileAlerts integration."""
from __future__ import annotations

from typing import Any

import dataclasses
from datetime import datetime
from xmlrpc.client import Boolean

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant, State
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)


from .const import (
    DOMAIN,
    MANUFACTURER,
    STATE_ATTR_BY_EVENT,
    STATE_ATTR_ERROR,
    STATE_ATTR_EXTRA,
    STATE_ATTR_LAST_UPDATE,
    STATE_ATTR_PRIOR_VALUE,
    STATE_ATTR_RESTORED,
)

from .mobilealerts import Gateway, MeasurementError, Measurement, Proxy, Sensor

import logging

_LOGGER = logging.getLogger(__name__)


class MobileAlertesBaseCoordinator(DataUpdateCoordinator):

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        proxy: Proxy,
        gateway: Gateway
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name=DOMAIN,
        )
        self._entry: ConfigEntry = entry
        self._proxy: Proxy = proxy
        self._gateway: Gateway = gateway
        self._proxy.set_handler(self)

    @property
    def gateway(self) -> Gateway:
        return self._gateway


@dataclasses.dataclass
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

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self,
                 coordinator: Any,
                 sensor: Sensor,
                 measurement: Measurement | None
                 ) -> None:
        _LOGGER.debug("MobileAlertesEntity(%r, %r, %r)", coordinator, sensor, measurement)
        super().__init__(coordinator)
        self._sensor = sensor
        self._measurement = measurement
        self._added_to_hass = False
        self._extra_state_attributes: dict[str, Any] | None = None
        self._last_state: State | None = None
        self._last_extra_data: ExtraStoredData | None = None

    @property
    def sensor(self) -> Sensor:
        return self._sensor

    @property
    def measurement(self) -> Measurement | None:
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

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        _LOGGER.debug("async_added_to_hass")
        await super().async_added_to_hass()
        self._added_to_hass = True
        self._last_state = await self.async_get_last_state()
        self._last_extra_data = await self.async_get_last_extra_data()
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug("_handle_coordinator_update")
        updated: bool = False
        if self._sensor.last_update is not None:
            _LOGGER.debug("self._sensor.last_update is not None")
            self.update_data_from_sensor()
            updated = True
        elif self._last_state is not None:
            _LOGGER.debug("_handle_coordinator_update self._last_state.state %s", self._last_state.state)
            self.update_data_from_last_state()
            updated = True

        if updated and self._added_to_hass:
            attr: dict[str, Any] = {}
            if self._sensor.last_update is not None:
                attr[STATE_ATTR_LAST_UPDATE] = datetime.fromtimestamp(self._sensor.timestamp).isoformat()
                if self._measurement:
                    attr[STATE_ATTR_BY_EVENT] = self._sensor.by_event
                    if self._measurement.has_prior_value:
                        attr[STATE_ATTR_PRIOR_VALUE] = self._measurement.prior_value
                    if type(self._measurement.value) is MeasurementError:
                        attr[STATE_ATTR_ERROR] = self._measurement.value_str
                self._extra_state_attributes = attr
            elif self._last_extra_data is not None:
                self._extra_state_attributes = self._last_extra_data.as_dict()
                attr[STATE_ATTR_RESTORED] = True
                attr |= self._extra_state_attributes

            _LOGGER.debug("extra_state_attributes %s", attr)

            self._attr_extra_state_attributes = attr

            self.async_write_ha_state()

    def update_data_from_sensor(self) -> None:
        """Update data from the sensor."""
        pass

    def update_data_from_last_state(self) -> None:
        """Update data from stored last state."""
        pass

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        result: bool = self._sensor.last_update is not None or self._last_state is not None
        _LOGGER.debug("available %s", result)
        return result

    @property
    def extra_restore_state_data(self) -> MobileAlertesExtraStoredData:
        """Return sensor specific state data to be restored."""
        return MobileAlertesExtraStoredData(self._extra_state_attributes)
