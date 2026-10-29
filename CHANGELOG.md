# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog],
and this project adheres to [Semantic Versioning].

## [0.3.14] - 2026-09-30

### Fixed

- Native-entities mode: the CO2 sensor no longer uses the deprecated `CONCENTRATION_PARTS_PER_MILLION` constant, which Home Assistant removes in Core 2027.8 (logged as "The deprecated constant CONCENTRATION_PARTS_PER_MILLION was used from mobile_alerts"). It now uses `UnitOfRatio.PARTS_PER_MILLION`. Both are the string `ppm`, so existing statistics are unaffected. Home Assistant versions that predate `UnitOfRatio` keep using the old constant, detected at import time. A scan of every name the integration imports from Home Assistant found no other deprecated constants.

## [0.3.13] - 2026-09-30

### Added

- Repository: a GitHub Action (`.github/workflows/changelog.yml`) that fails a push or pull request when the newest `CHANGELOG.md` heading does not match the version in `manifest.json`, when that section is empty or has no date, when versions are duplicated or out of order, or when `custom_components/` changes without a `CHANGELOG.md` change in the same push. The logic is in `.github/scripts/check_changelog.py`, which can also be run locally. No change to the integration itself.

## [0.3.12] - 2026-09-30

### Fixed

- Native-entities mode: binary sensors (low battery, and contact/wetness sensors) for a newly discovered sensor were not created until the integration was reloaded. Since 0.3.6, new entities are added through each platform's registered `async_add_entities` callback, but the registration in `binary_sensor.py` was never committed, so only the `sensor` platform had one. The binary sensor platform now registers and unregisters its callback like the sensor platform. MQTT gateway mode was not affected.

## [0.3.11] - 2026-09-30

### Fixed

- Native-entities mode: temperature, humidity, CO2, air pressure, wind speed and gust sensors now declare `state_class: measurement`. Without a state class Home Assistant records no long-term statistics for a sensor, so these entities never had any. Users coming from a fork that did set it (for example Iminet72/ha_mobilealerts) saw a repair notice, "we have generated statistics in the past, but it no longer has a state class", and their statistics stopped. With the state class restored, statistics resume under the same entity ids and the existing history is kept. Sensors with an `enum` device class (key press) deliberately have none, because Home Assistant does not allow a state class there.

### Changed

- Documentation: README explains the state classes and long-term statistics in native-entities mode, and what to do about the "no longer has a state class" repair notice after switching from another fork.
- `manifest.json`: added `@m-l` to `codeowners`, so the maintainer of this fork is listed as an author in HACS. Credits in the README updated to match.

## [0.3.10] - 2026-09-30

### Fixed

- Sensor devices are now linked to their gateway with `via_device_id` (the gateway device's registry id) instead of the deprecated `via_device` identifier tuple, which Home Assistant will stop accepting in 2027.8.0. The gateway's id is captured when the gateway device is registered, which happens before any sensor device is created. On Home Assistant versions that predate `via_device_id` the integration detects this and keeps using `via_device`.

## [0.3.9] - 2026-09-30

### Changed

- Documentation: README now has a rain sensor example (total in mm, calibrated total from the tip counter, time of the last tip, a "rain tip" binary sensor, and daily/hourly totals via a utility meter), with notes on calibration and on why rain entities should not use a short `expire_after`.
- Documentation: added a note that some models omit keys such as `lastTransmit`, and that templates should read them with `value_json.get('key')`.
- Documentation: corrected the battery example's introduction, which promised a staleness check it did not show.

## [0.3.8] - 2026-09-30

### Fixed

- Native-entities mode: the rain-by-period sensors (last rain, last hour rain, last day rain) raised `RuntimeError: dictionary changed size during iteration` when an old reading aged out of its window, because expired entries were removed while iterating over the dictionary. The loop now iterates over a copy. Same fix as Silver-Volt4/ha_mobilealerts@28c70ed.

## [0.3.7] - 2026-09-07

### Fixed

- MQTT gateway mode no longer republishes a sensor packet it has already published. The gateway can deliver the same packet more than once and the library reports every delivery as an update, so a repeat was published again and counted a second time by accumulating consumers such as rain event-counter templates. Packets are now dropped when their transmit counter is unchanged, matching maserver.

## [0.3.6] - 2026-09-07

### Fixed

- Native-entities mode no longer reaches into Home Assistant's private `hass.data[Platform.*]._platforms` to add entities for newly discovered sensors. Each platform now registers its public `async_add_entities` callback with the coordinator during setup (and unregisters on unload), which is stable across Home Assistant versions.
- Entities created at runtime for newly discovered sensors are now also registered with the coordinator, as platform setup already did, so calculated entities (rain per period, is raining) can locate the entities they depend on without needing a reload first.

## [0.3.5] - 2026-09-07

### Fixed

- Removed use of the deprecated `device_registry.devices` mapping; the integration now uses `async_entries_for_config_entry` to find its devices.
- Replaced deprecated `hass.async_add_job` with `hass.async_create_task` when adding entities for newly discovered sensors.

## [0.3.4] - 2026-09-06

### Fixed

- The "proxy is used" gateway diagnostic now reflects the live proxy state (`use_proxy`) instead of the preserved original (`orig_use_proxy`).
- Options-flow fields now have proper labels and descriptions: `Mode` and `MQTT topic prefix` no longer render as raw keys.

## [0.3.3] - 2026-09-06

### Fixed

- Cloud forwarding ("Send data to cloud") now relays directly to the Mobile-Alerts cloud instead of routing through the gateway's previously configured upstream proxy. Previously, if that proxy was a local server that had since been stopped (e.g. maserver), every forward failed with `ConnectionRefusedError`. Local MQTT/entity data was unaffected; only the cloud copy erred.

## [0.3.2] - 2026-09-06

### Fixed

- Published measurement values are rounded to 4 decimals, removing binary floating-point noise (e.g. `18.400000000000002` now published as `18.4`) that the library introduces for values computed as `x * 0.1`.

## [0.3.1] - 2026-09-06

### Added

- Rain sensors now publish `eventCounter` (cumulative bucket-tip counter) and `eventTimes` (seconds since each of the last 9 events), parsed directly from the packet following the MMMMobileAlerts ID08 layout. This resolves the rain limitation noted in 0.3.0 and restores compatibility with rain-gauge counter templates.

## [0.3.0] - 2026-09-06

### Added

- MQTT gateway payload now includes per-sensor metadata with maserver-compatible keys: `id`, `t` (reading time, ISO 8601 UTC), `lastTransmit` (transmit interval), `offline`, `by_event`, `counter`, `model` and `name`.
- Wind direction is published as both `directionDegree` (degrees) and `direction` (16-point compass string).

### Fixed

- Wind values (`windSpeed`, `gustSpeed`) are now published as scalars, not single-element arrays, matching the maserver format expected by existing `mqtt:` sensor templates.

### Known limitations

- `offline` is always `false` (the integration publishes on transmit only; there is no post-silence watchdog — use the age of `t` for staleness).
- maserver rain event fields (`eventCounter`, `eventTimes`) are not produced; the library exposes rain only as a cumulative measurement.

## [0.2.3] - 2026-09-06

### Added

- MQTT gateway mode now publishes battery status as `battery` (`"ok"` / `"low"`), matching the maserver JSON format.

## [0.2.2] - 2026-09-06

### Changed

- Documentation: README now covers the native-entities and MQTT gateway modes, the `<prefix><sensor_id>/json` topic layout, the JSON payload format and an example `mqtt:` sensor configuration, plus a credits section. HACS repository badge points at this fork.

## [0.2.1] - 2026-09-06

### Fixed

- Proxy diagnostic now reports the live proxy target (`gateway.proxy`) instead of the preserved original setting (`orig_proxy`), which previously showed the address of a prior/external proxy server (e.g. a former maserver).

## [0.2.0] - 2026-09-06

### Added

- **MQTT gateway mode**: publish sensor readings as sarnau/MMMMobileAlerts-compatible JSON to `<prefix><sensor_id>/json` (default prefix `/MobileAlerts/`, lower-case id) instead of creating native entities, selectable from the options flow. Enables drop-in replacement of a standalone maserver while reusing existing `mqtt:` sensors.
- Configurable MQTT topic prefix in the options flow.
- Automatic reload of the config entry when options change, so mode and cloud-forwarding changes apply without a manual reload.

### Fixed

- Options flow crashed on import on Home Assistant 2024.11+ (and later cores) due to an invalid `config_entry` setter in the options handler. Removed the self-managed `config_entry` and rely on the framework-provided property.

### Changed

- `manifest.json`: added `mqtt` to `after_dependencies`.

## [0.1.4] - 2025-07-10

### Changed

Fix compatibility with frozen dataclasses for Home Assistant 2024.x

- Refactor entity descriptions to use dataclasses.replace instead of direct attribute assignment
- Prevent FrozenInstanceError on Sensor and BinarySensor entities
- Clean up legacy code and ensure compatibility with latest Home Assistant core

## [0.1.3] - 2023-04-20

### Changed

- Improved handling of rain sensor.

[Keep a Changelog]: https://keepachangelog.com/en/1.1.0/
[Semantic Versioning]: https://semver.org/spec/v2.0.0.html
