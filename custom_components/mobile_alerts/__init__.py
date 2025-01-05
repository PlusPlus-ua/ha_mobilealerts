"""The MobileAlerts integration."""

from __future__ import annotations

from typing import Any

import logging

from homeassistant.components.network import async_get_source_ip
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from mobilealerts import Gateway, Proxy, Sensor

from .const import CONF_SEND_DATA_TO_CLOUD, DOMAIN
from .coordinator import MobileAlertesDataCoordinator
from .util import gateway_full_name

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Mobile-Alerts from a config entry."""
    _LOGGER.debug("async_setup_entry %r", entry.as_dict())

    local_ip = await async_get_source_ip(hass)
    gateway = Gateway(entry.unique_id, local_ip)
    gateway.send_data_to_cloud = entry.options.get(CONF_SEND_DATA_TO_CLOUD, True)
    if not await gateway.init():
        raise ConfigEntryNotReady("Error initialization of MobileAlerts Gateway (%s)", gateway.gateway_id)

    gateway_ip = gateway.ip_address
    proxy_ip = await async_get_source_ip(hass, gateway_ip)
    _LOGGER.debug("async_setup_entry gateway_ip %s, proxy_ip %s", gateway_ip, proxy_ip)
    proxy = Proxy(None, proxy_ip)

    coordinator = MobileAlertesDataCoordinator(hass, entry, proxy, gateway)

    await proxy.start()
    proxy.attach_gateway(gateway)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await coordinator.async_get_or_create_gateway_device()

    device_registry = dr.async_get(hass)

    for device in device_registry.devices.values():
        if (
            entry.entry_id in device.config_entries
            and (DOMAIN, gateway.gateway_id) not in device.identifiers
        ):
            for identifier in device.identifiers:
                if identifier[0] == DOMAIN:
                    gateway.add_sensor(Sensor(gateway, identifier[1], device.name))
                    _LOGGER.debug("entry device %s %s", device.name, identifier[1])
                    break

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # await gateway.handle_sensor_update(bytes.fromhex("E06322C5E6241829EFCB988DC0D3E200E735273800E6352738010405090C100202020202020000000000000000000000000000000000000000000000000000"), 0x79)
    # await gateway.handle_sensor_update(bytes.fromhex("D66322C4331A065526A17A613AF3008C00B50A5F008B00B50A601A000000000000000000000000000000000000000000000000000000000000000000000000"), 0x04)
    # await gateway.handle_sensor_update(bytes.fromhex("ce5d8a6e0e1215ffffffffff4019114a0902040000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"), 0x16)
    # await gateway.handle_sensor_update(bytes.fromhex("ce5d8bc69e1215ffffffffff401a210a4a02040000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"), 0x11)
    # await gateway.handle_sensor_update(bytes.fromhex("ce5d8bc9301215ffffffffff401d13cb0a03050000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"), 0x1e)
    # await gateway.handle_sensor_update(bytes.fromhex("ce5d8bcb801215ffffffffff4023128e0b04060000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"), 0x3b)
    # await gateway.handle_sensor_update(bytes.fromhex("ce5d8bcb801216ffffffffff4023128e0b04060000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"), 0x3c)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("async_unload_entry %r", entry.as_dict())
    coordinator: MobileAlertesDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    unload_ok: bool = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.proxy.stop()

    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    _LOGGER.debug(
        "async_remove_config_entry_device config_entry %r, device_entry %r",
        config_entry.as_dict(),
        device_entry,
    )
    return (DOMAIN, config_entry.unique_id) not in device_entry.identifiers
